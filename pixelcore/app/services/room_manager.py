"""
RoomManager — in-process or Redis-backed WebRTC signalling room state.

Design
------
* Participant  — dataclass representing one connected websocket peer
* RoomManager  — async-safe room state with capacity, rate-limit, and
                 optional Redis pub/sub for multi-worker deployments

Two backends are supported:
  memory  — single-process / single-dyno, no Redis
  redis   — horizontally scalable; participants stored as Redis hashes,
             events relayed via pub/sub channels
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Deque, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from redis.asyncio import Redis as AsyncRedis
except Exception:          # pragma: no cover
    AsyncRedis = None      # type: ignore[assignment,misc]


# ── Participant dataclass ──────────────────────────────────────────────────────

@dataclass
class Participant:
    """A single peer connected to the interview signalling room."""

    participant_id: str
    user_id: str
    role: str
    display_name: str
    ws: Any                            # WebSocket — not serialised to Redis

    mic_on: bool = True
    cam_on: bool = True
    speaking: bool = False
    joined_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def as_public(self) -> dict:
        return {
            "participant_id": self.participant_id,
            "user_id": self.user_id,
            "role": self.role,
            "display_name": self.display_name,
            "mic_on": self.mic_on,
            "cam_on": self.cam_on,
            "speaking": self.speaking,
        }

    @classmethod
    def from_public(cls, data: dict) -> "Participant":
        return cls(
            participant_id=data["participant_id"],
            user_id=data["user_id"],
            role=data["role"],
            display_name=data.get("display_name", ""),
            ws=None,
            mic_on=bool(data.get("mic_on", True)),
            cam_on=bool(data.get("cam_on", True)),
            speaking=bool(data.get("speaking", False)),
        )


# ── RoomManager ────────────────────────────────────────────────────────────────

class RoomManager:
    """
    Async-safe room state manager.

    Thread/task-safe via a single asyncio.Lock.
    Scales to multiple workers when ROOM_BACKEND=redis.
    """

    def __init__(
        self,
        capacity: int,
        join_rate_limit: int,
        join_window_seconds: int,
    ) -> None:
        self.capacity = capacity
        self.join_rate_limit = join_rate_limit
        self.join_window_seconds = join_window_seconds

        self._lock = asyncio.Lock()
        self._join_attempts: Dict[str, Deque[float]] = defaultdict(deque)
        self._rooms: Dict[str, Dict[str, Participant]] = defaultdict(dict)
        self._room_to_user_pid: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._touch_interval_seconds = 2.0

        self._backend = self._resolve_backend()
        self._redis: Optional[AsyncRedis] = self._build_redis()   # type: ignore[type-arg]

        logger.info("RoomManager backend=%s capacity=%d", self._backend, self.capacity)

    # ── Backend helpers ────────────────────────────────────────────────────────

    def _resolve_backend(self) -> str:
        mode = getattr(settings, "ROOM_BACKEND", "memory").lower()
        if mode == "redis":
            return "redis" if (AsyncRedis is not None and settings.REDIS_URL) else "memory"
        if mode == "memory":
            return "memory"
        # auto: prefer Redis if available
        if AsyncRedis is not None and settings.REDIS_URL:
            return "redis"
        return "memory"

    def backend_name(self) -> str:
        return self._backend

    def _build_redis(self) -> Optional[Any]:
        if self._backend != "redis" or AsyncRedis is None or not settings.REDIS_URL:
            return None
        return AsyncRedis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            decode_responses=True,
        )

    # ── Redis key helpers ─────────────────────────────────────────────────────

    def _room_key(self, token: str) -> str:
        return f"rtc:room:{token}:participants"

    def _user_idx_key(self, token: str) -> str:
        return f"rtc:room:{token}:user_index"

    def _channel_key(self, token: str) -> str:
        return f"rtc:room:{token}:events"

    def _join_key(self, token: str, user_id: str) -> str:
        return f"{token}:{user_id}"

    # ── Rate limiter ──────────────────────────────────────────────────────────

    def _prune_attempts(self, attempts: Deque[float], now: float) -> None:
        cutoff = now - self.join_window_seconds
        while attempts and attempts[0] < cutoff:
            attempts.popleft()

    async def allow_join(self, room_token: str, user_id: str) -> bool:
        now = time.time()
        async with self._lock:
            key = self._join_key(room_token, user_id)
            attempts = self._join_attempts[key]
            self._prune_attempts(attempts, now)
            if len(attempts) >= self.join_rate_limit:
                return False
            attempts.append(now)
            return True

    # ── Stale cleanup ─────────────────────────────────────────────────────────

    async def _cleanup_stale_locked(self, room_token: str) -> None:
        ttl = float(settings.RTC_STALE_PARTICIPANT_TTL_SECONDS)
        now = time.time()
        stale = [
            pid
            for pid, p in self._rooms[room_token].items()
            if (now - float(p.last_seen)) > ttl
        ]
        for pid in stale:
            p = self._rooms[room_token].pop(pid, None)
            if p and self._room_to_user_pid[room_token].get(p.user_id) == pid:
                self._room_to_user_pid[room_token].pop(p.user_id, None)
        if self._backend == "redis" and self._redis and stale:
            for pid in stale:
                await self._redis.hdel(self._room_key(room_token), pid)

    # ── Join / Leave ──────────────────────────────────────────────────────────

    async def join(
        self,
        room_token: str,
        user_id: str,
        role: str,
        display_name: str,
        ws: Any,
    ) -> Tuple[Optional[Participant], Optional[str]]:
        async with self._lock:
            await self._cleanup_stale_locked(room_token)

            # Handle reconnection: evict old slot
            existing_pid = self._room_to_user_pid[room_token].get(user_id)
            if existing_pid:
                self._rooms[room_token].pop(existing_pid, None)
                self._room_to_user_pid[room_token].pop(user_id, None)
                if self._backend == "redis" and self._redis:
                    await self._redis.hdel(self._room_key(room_token), existing_pid)

            if len(self._rooms[room_token]) >= self.capacity:
                return None, "room_full"

            pid = f"{user_id}:{uuid.uuid4().hex[:8]}"
            participant = Participant(
                participant_id=pid,
                user_id=user_id,
                role=role,
                display_name=display_name,
                ws=ws,
            )
            self._rooms[room_token][pid] = participant
            self._room_to_user_pid[room_token][user_id] = pid

            if self._backend == "redis" and self._redis:
                expiry = int(settings.RTC_STALE_PARTICIPANT_TTL_SECONDS * 3)
                await self._redis.hset(
                    self._room_key(room_token), pid,
                    json.dumps(participant.as_public(), ensure_ascii=True),
                )
                await self._redis.hset(self._user_idx_key(room_token), user_id, pid)
                await self._redis.expire(self._room_key(room_token), expiry)
                await self._redis.expire(self._user_idx_key(room_token), expiry)

            return participant, None

    async def leave(self, room_token: str, participant_id: str) -> Optional[Participant]:
        async with self._lock:
            leaving = self._rooms[room_token].pop(participant_id, None)
            if leaving and self._room_to_user_pid[room_token].get(leaving.user_id) == participant_id:
                self._room_to_user_pid[room_token].pop(leaving.user_id, None)
            if self._backend == "redis" and self._redis:
                await self._redis.hdel(self._room_key(room_token), participant_id)
                if leaving:
                    await self._redis.hdel(self._user_idx_key(room_token), leaving.user_id)
            if not self._rooms[room_token]:
                self._rooms.pop(room_token, None)
                self._room_to_user_pid.pop(room_token, None)
            return leaving

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    async def touch(self, room_token: str, participant_id: str) -> None:
        async with self._lock:
            p = self._rooms.get(room_token, {}).get(participant_id)
            if p:
                now = time.time()
                if now - float(p.last_seen) >= self._touch_interval_seconds:
                    p.last_seen = now

    # ── Media / Speaking state ────────────────────────────────────────────────

    async def update_media(
        self, room_token: str, participant_id: str, mic_on: bool, cam_on: bool
    ) -> bool:
        async with self._lock:
            room = self._rooms.get(room_token)
            if not room or participant_id not in room:
                return False
            p = room[participant_id]
            p.mic_on = bool(mic_on)
            p.cam_on = bool(cam_on)
            p.last_seen = time.time()
            if self._backend == "redis" and self._redis:
                await self._redis.hset(
                    self._room_key(room_token), participant_id,
                    json.dumps(p.as_public(), ensure_ascii=True),
                )
            return True

    async def update_speaking(
        self, room_token: str, participant_id: str, speaking: bool
    ) -> bool:
        async with self._lock:
            room = self._rooms.get(room_token)
            if not room or participant_id not in room:
                return False
            p = room[participant_id]
            p.speaking = bool(speaking)
            p.last_seen = time.time()
            if self._backend == "redis" and self._redis:
                await self._redis.hset(
                    self._room_key(room_token), participant_id,
                    json.dumps(p.as_public(), ensure_ascii=True),
                )
            return True

    # ── Snapshot & Sockets ────────────────────────────────────────────────────

    async def snapshot(self, room_token: str) -> List[dict]:
        if self._backend == "redis" and self._redis:
            try:
                rows = await self._redis.hvals(self._room_key(room_token))
                return [json.loads(r) for r in rows]
            except Exception:
                pass
        async with self._lock:
            return [p.as_public() for p in self._rooms.get(room_token, {}).values()]

    async def count(self, room_token: str) -> int:
        if self._backend == "redis" and self._redis:
            try:
                return int(await self._redis.hlen(self._room_key(room_token)))
            except Exception:
                pass
        async with self._lock:
            return len(self._rooms.get(room_token, {}))

    async def get_ws(self, room_token: str, participant_id: str) -> Optional[Any]:
        async with self._lock:
            p = self._rooms.get(room_token, {}).get(participant_id)
            return p.ws if p else None

    async def others_ws(
        self, room_token: str, exclude_participant_id: Optional[str] = None
    ) -> List[Any]:
        async with self._lock:
            room = self._rooms.get(room_token)
            if not room:
                return []
            return [
                p.ws
                for pid, p in room.items()
                if not exclude_participant_id or pid != exclude_participant_id
            ]

    # ── Pub/Sub (Redis multi-worker relay) ────────────────────────────────────

    async def publish_event(self, room_token: str, payload: dict) -> None:
        if self._backend != "redis" or not self._redis:
            return
        try:
            await self._redis.publish(
                self._channel_key(room_token),
                json.dumps(payload, ensure_ascii=True),
            )
        except Exception as exc:
            logger.debug("Redis publish failed: %s", exc)

    async def subscribe_events(self, room_token: str) -> AsyncIterator[dict]:
        if self._backend != "redis" or not self._redis:
            return
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._channel_key(room_token))
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg and isinstance(msg.get("data"), str):
                    try:
                        yield json.loads(msg["data"])
                    except Exception:
                        continue
                await asyncio.sleep(0.01)
        finally:
            await pubsub.unsubscribe(self._channel_key(room_token))
            await pubsub.close()
