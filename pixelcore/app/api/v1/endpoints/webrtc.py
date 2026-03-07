"""
WebRTC signalling endpoint — WebSocket-based SDP/ICE relay.

Handles:
  - JWT auth from URL query param (browsers can't set WS headers)
  - Role resolution (candidate | hr | interviewer | admin)
  - Join rate-limiting and room capacity enforcement
  - offer / answer / ice forwarding (point-to-point or via Redis pub/sub)
  - media_state / speaking_state broadcast
  - Heartbeat ping/pong with miss detection
  - Clean leave + participant_left broadcast on disconnect
"""
import asyncio
import json
import logging
import uuid
from typing import Optional, Tuple

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.interview import Interview, InterviewInterviewer, InterviewStatus
from app.models.user import User, UserRole
from app.services.access_policy import AccessPolicy
from app.services.room_manager import RoomManager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webrtc"])

# Unique per worker process — used to filter pub/sub echo
WORKER_ID = uuid.uuid4().hex

room_manager = RoomManager(
    capacity=settings.RTC_ROOM_CAPACITY,
    join_rate_limit=settings.RTC_JOIN_RATE_LIMIT,
    join_window_seconds=settings.RTC_JOIN_WINDOW_SECONDS,
)


# ── Access helpers ─────────────────────────────────────────────────────────────

async def _load_access_context(
    interview_token: str, user_id: str
) -> Tuple[Optional[Interview], Optional[User]]:
    async with AsyncSessionLocal() as db:
        iv_res = await db.execute(
            select(Interview)
            .options(
                selectinload(Interview.hr).selectinload(User.organisation),
                selectinload(Interview.interviewers).selectinload(InterviewInterviewer.interviewer),
                selectinload(Interview.candidate),
            )
            .where(Interview.access_token == interview_token)
        )
        interview = iv_res.scalar_one_or_none()
        if not interview:
            return None, None

        user_res = await db.execute(
            select(User).options(selectinload(User.organisation)).where(User.id == user_id)
        )
        user = user_res.scalar_one_or_none()
        return interview, user


def _resolve_server_role(interview: Interview, user: User) -> Optional[str]:
    """Return the server-authoritative role string, or None if not authorised."""
    if not user or not user.is_active:
        return None
    if user.role == UserRole.ADMIN:
        return "admin"
    if interview.candidate_id == user.id:
        return "candidate"
    if user.role == UserRole.HR:
        hr_org = interview.hr.organisation_id if interview.hr else None
        return "hr" if (hr_org and user.organisation_id == hr_org) else None
    if user.role == UserRole.INTERVIEWER:
        assigned = {ii.interviewer_id for ii in interview.interviewers}
        return "interviewer" if user.id in assigned else None
    return None


# ── WS helpers ────────────────────────────────────────────────────────────────

async def _send(ws: WebSocket, payload: dict) -> bool:
    try:
        await ws.send_text(json.dumps(payload))
        return True
    except Exception:
        return False


async def _broadcast(
    room_token: str, payload: dict, exclude_pid: Optional[str] = None
) -> None:
    for ws in await room_manager.others_ws(room_token, exclude_participant_id=exclude_pid):
        await _send(ws, payload)
    await room_manager.publish_event(
        room_token, {**payload, "__exclude_pid": exclude_pid, "__worker_id": WORKER_ID}
    )


async def _relay_external_events(
    room_token: str, websocket: WebSocket, self_pid: str
) -> None:
    """Forward pub/sub messages from other workers to this websocket."""
    if room_manager.backend_name() != "redis":
        return
    async for msg in room_manager.subscribe_events(room_token):
        if msg.get("__worker_id") == WORKER_ID:
            continue
        exclude_pid = msg.pop("__exclude_pid", None)
        msg.pop("__worker_id", None)
        if exclude_pid and exclude_pid == self_pid:
            continue
        target = msg.get("to")
        if target and target != self_pid:
            continue
        await _send(websocket, msg)


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/rtc/{interview_token}")
async def rtc_signaling(
    websocket: WebSocket,
    interview_token: str,
    token: str = Query(default=None, description="JWT bearer token (required)"),
    role: str = Query(default="participant", description="Client-side role hint"),
):
    """
    WebRTC signalling room.
    Auth token is passed as a URL query param because browsers cannot set
    custom headers on WebSocket connections.
    """
    participant = None
    joined = False
    relay_task: Optional[asyncio.Task] = None
    missed_heartbeats = 0

    # ── Auth ──────────────────────────────────────────────────────────────────
    if not token:
        await websocket.close(code=4001, reason="Missing auth token")
        return

    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4003, reason="Invalid or expired JWT")
        return

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        await websocket.close(code=4003, reason="Invalid token payload")
        return

    # ── Rate limit ────────────────────────────────────────────────────────────
    if not await room_manager.allow_join(interview_token, user_id):
        await websocket.close(code=4008, reason="Join rate limit exceeded")
        return

    # ── Load interview + user ─────────────────────────────────────────────────
    interview, user = await _load_access_context(interview_token, user_id)
    if not interview:
        await websocket.close(code=4004, reason="Interview not found")
        return
    if not user:
        await websocket.close(code=4003, reason="User not found")
        return

    server_role = _resolve_server_role(interview, user)
    if not server_role:
        await websocket.close(code=4003, reason="Not authorised for this room")
        return
    if interview.status == InterviewStatus.SCHEDULED and server_role == "candidate":
        if not AccessPolicy.candidate_join_window_ok(interview):
            await websocket.close(code=4003, reason="Outside allowed interview join window")
            return

    await websocket.accept()

    # ── Join room ─────────────────────────────────────────────────────────────
    participant, join_err = await room_manager.join(
        room_token=interview_token,
        user_id=user.id,
        role=server_role,
        display_name=user.full_name or user.email,
        ws=websocket,
    )
    if join_err == "room_full":
        await _send(websocket, {"type": "error", "detail": "Room capacity reached"})
        await websocket.close(code=4010, reason="Room full")
        return
    if not participant:
        await websocket.close(code=1011, reason="Could not join room")
        return

    joined = True
    logger.info(
        "RTC join room=%.8s participant=%s user=%s server_role=%s",
        interview_token, participant.participant_id, user.id, server_role,
    )

    # Send join confirmation + participant snapshot
    await _send(websocket, {
        "type": "joined",
        "participant": participant.as_public(),
        "room_capacity": settings.RTC_ROOM_CAPACITY,
    })
    participants_now = await room_manager.snapshot(interview_token)
    await _send(websocket, {
        "type": "participants_snapshot",
        "participants": participants_now,
        "participant_count": len(participants_now),
    })

    # Notify existing peers
    await _broadcast(
        interview_token,
        {
            "type": "participant_joined",
            "participant": participant.as_public(),
            "participant_count": len(participants_now),
        },
        exclude_pid=participant.participant_id,
    )

    # Trigger negotiation with existing peers
    for peer in participants_now:
        peer_pid = peer.get("participant_id")
        if not peer_pid or peer_pid == participant.participant_id:
            continue
        peer_ws = await room_manager.get_ws(interview_token, peer_pid)
        if peer_ws:
            await _send(peer_ws, {"type": "negotiate_with", "participant_id": participant.participant_id})

    relay_task = asyncio.create_task(
        _relay_external_events(interview_token, websocket, participant.participant_id)
    )

    # ── Message loop ──────────────────────────────────────────────────────────
    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=float(max(settings.RTC_HEARTBEAT_SECONDS, 1)),
                )
            except asyncio.TimeoutError:
                await _send(websocket, {"type": "ping"})
                missed_heartbeats += 1
                if missed_heartbeats >= 3:
                    await websocket.close(code=1011, reason="Heartbeat timeout")
                    break
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send(websocket, {"type": "error", "detail": "Invalid JSON"})
                continue

            await room_manager.touch(interview_token, participant.participant_id)
            missed_heartbeats = 0
            msg_type = msg.get("type")

            if msg_type == "ping":
                await _send(websocket, {"type": "pong"})
                continue

            if msg_type == "pong":
                continue

            if msg_type in ("offer", "answer", "ice"):
                target_pid = msg.get("to")
                if not target_pid:
                    await _send(websocket, {"type": "error", "detail": "Missing 'to' participant id"})
                    continue
                relay: dict = {"type": msg_type, "from": participant.participant_id, "to": target_pid}
                if msg_type in ("offer", "answer"):
                    relay["sdp"] = msg.get("sdp")
                else:
                    relay["candidate"] = msg.get("candidate")

                target_ws = await room_manager.get_ws(interview_token, target_pid)
                if target_ws:
                    await _send(target_ws, relay)
                elif room_manager.backend_name() == "redis":
                    await room_manager.publish_event(
                        interview_token, {**relay, "__worker_id": WORKER_ID}
                    )
                else:
                    await _send(websocket, {"type": "error", "detail": "Target participant not found"})
                continue

            if msg_type == "media_state":
                mic_on = bool(msg.get("mic_on", True))
                cam_on = bool(msg.get("cam_on", True))
                await room_manager.update_media(interview_token, participant.participant_id, mic_on, cam_on)
                parts = await room_manager.snapshot(interview_token)
                await _broadcast(
                    interview_token,
                    {
                        "type": "participant_media",
                        "participant_id": participant.participant_id,
                        "mic_on": mic_on,
                        "cam_on": cam_on,
                        "participant_count": len(parts),
                    },
                    exclude_pid=participant.participant_id,
                )
                continue

            if msg_type == "speaking_state":
                speaking = bool(msg.get("speaking", False))
                await room_manager.update_speaking(interview_token, participant.participant_id, speaking)
                await _broadcast(
                    interview_token,
                    {
                        "type": "speaking_state",
                        "participant_id": participant.participant_id,
                        "speaking": speaking,
                    },
                    exclude_pid=participant.participant_id,
                )
                continue

            await _send(websocket, {"type": "error", "detail": f"Unsupported message type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info(
            "RTC disconnect room=%.8s participant=%s",
            interview_token, participant.participant_id if participant else "-",
        )
    except Exception as exc:
        logger.exception(
            "RTC error room=%.8s participant=%s err=%s",
            interview_token, participant.participant_id if participant else "-", exc,
        )
        await _send(websocket, {"type": "error", "detail": "Server signaling error"})

    finally:
        if relay_task:
            relay_task.cancel()
        if joined and participant:
            await room_manager.leave(interview_token, participant.participant_id)
            remaining = await room_manager.snapshot(interview_token)
            await _broadcast(
                interview_token,
                {
                    "type": "participant_left",
                    "participant_id": participant.participant_id,
                    "participant_count": len(remaining),
                },
            )
            # Send updated snapshot
            for ws in await room_manager.others_ws(interview_token):
                await _send(ws, {
                    "type": "participants_snapshot",
                    "participants": remaining,
                    "participant_count": len(remaining),
                })
