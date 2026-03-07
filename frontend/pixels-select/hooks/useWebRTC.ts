'use client';

import { useEffect, useRef } from 'react';

const WS_BASE =
    typeof window !== 'undefined'
        ? (process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000')
        : 'ws://localhost:8000';

export interface RemoteParticipant {
    participantId: string;
    stream: MediaStream;
    role: string;
    displayName: string;
}

interface UseWebRTCOptions {
    token: string;
    jwtToken: string;          // pass '' to keep hook dormant
    localStream: MediaStream | null;
    onRemoteStream: (p: RemoteParticipant) => void;
    onRemoteLeft: (participantId: string) => void;
}

export function useWebRTC({
    token,
    jwtToken,
    localStream,
    onRemoteStream,
    onRemoteLeft,
}: UseWebRTCOptions) {

    // ── Stable refs so callbacks never invalidate the WS effect ──────────────
    const onRemoteStreamRef = useRef(onRemoteStream);
    onRemoteStreamRef.current = onRemoteStream;
    const onRemoteLeftRef = useRef(onRemoteLeft);
    onRemoteLeftRef.current = onRemoteLeft;
    const localStreamRef = useRef<MediaStream | null>(null);
    localStreamRef.current = localStream;

    // ── Peer state (lives for the lifetime of the WS connection) ─────────────
    const wsRef = useRef<WebSocket | null>(null);
    const selfPidRef = useRef('');
    const peersRef = useRef<Map<string, RTCPeerConnection>>(new Map());
    const participantsRef = useRef<Map<string, { role: string; displayName: string }>>(new Map());

    // ── When localStream arrives / changes — patch existing peers ─────────────
    useEffect(() => {
        if (!localStream) return;
        peersRef.current.forEach((pc) => {
            localStream.getTracks().forEach(track => {
                const transceivers = pc.getTransceivers();
                const existing = transceivers.find(t =>
                    t.sender.track?.kind === track.kind ||
                    t.receiver.track?.kind === track.kind
                );

                if (existing) {
                    // Update direction to allow sending, and attach the track
                    if (existing.direction === 'recvonly') existing.direction = 'sendrecv';
                    if (existing.direction === 'inactive') existing.direction = 'sendonly';
                    existing.sender.replaceTrack(track).catch(() => { });
                } else {
                    try { pc.addTrack(track, localStream); } catch { }
                }
            });
        });
    }, [localStream]);

    // ── Main WS effect — depends only on stable primitives ───────────────────
    useEffect(() => {
        if (!jwtToken || !token) return;

        const wsUrl = `${WS_BASE}/api/v1/ws/rtc/${token}?token=${encodeURIComponent(jwtToken)}`;
        console.log('[WebRTC] connecting');
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        // ── helpers scoped to this effect ────────────────────────────────────
        function send(payload: object) {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(payload));
            }
        }

        function createPeer(targetPid: string, initiator: boolean): RTCPeerConnection {
            const existing = peersRef.current.get(targetPid);
            if (existing) return existing;

            const pc = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' },
                ],
            });

            // ── 1. Set up all handlers FIRST, before adding tracks ────────────
            const remoteStream = new MediaStream();

            pc.ontrack = (ev) => {
                // Use ev.track directly — ev.streams[0] can be undefined in some browsers
                const track = ev.track;
                if (!remoteStream.getTracks().find(t => t.id === track.id)) {
                    remoteStream.addTrack(track);
                }

                const info = participantsRef.current.get(targetPid);
                const participant = {
                    participantId: targetPid,
                    stream: remoteStream,
                    role: info?.role ?? 'unknown',
                    displayName: info?.displayName ?? '',
                };

                // Always fire so the tile appears — video element will fill in when ready
                onRemoteStreamRef.current(participant);
            };

            pc.onicecandidate = (ev) => {
                if (ev.candidate) {
                    send({ type: 'ice', to: targetPid, candidate: ev.candidate.toJSON() });
                }
            };

            pc.oniceconnectionstatechange = () => {
                console.log('[WebRTC] ICE state', targetPid, pc.iceConnectionState);
                if (pc.iceConnectionState === 'failed') {
                    pc.restartIce();
                }
                if (pc.iceConnectionState === 'closed') {
                    peersRef.current.delete(targetPid);
                    onRemoteLeftRef.current(targetPid);
                }
            };

            if (initiator) {
                pc.onnegotiationneeded = async () => {
                    try {
                        console.log('[WebRTC] negotiation needed →', targetPid);
                        const offer = await pc.createOffer();
                        await pc.setLocalDescription(offer);
                        send({ type: 'offer', to: targetPid, sdp: pc.localDescription });
                    } catch (e) {
                        console.error('[WebRTC] negotiation error', e);
                    }
                };
            }

            // ── 2. Now add tracks — onnegotiationneeded will fire after this ─
            const stream = localStreamRef.current;
            if (stream) {
                stream.getTracks().forEach(t => pc.addTrack(t, stream));
            }

            // If we don't have tracks yet (e.g. camera loading or off), we MUST
            // still add transceivers so that onnegotiationneeded fires and we can
            // at least receive the other person's video.
            const hasVideo = stream && stream.getVideoTracks().length > 0;
            const hasAudio = stream && stream.getAudioTracks().length > 0;

            if (!hasVideo) {
                pc.addTransceiver('video', { direction: 'recvonly' });
            }
            if (!hasAudio) {
                pc.addTransceiver('audio', { direction: 'recvonly' });
            }

            peersRef.current.set(targetPid, pc);
            return pc;
        }

        // ── WS message handler ────────────────────────────────────────────────
        ws.onopen = () => console.log('[WebRTC] WS open');
        ws.onclose = (e) => console.log('[WebRTC] WS closed', e.code, e.reason);
        ws.onerror = (e) => console.error('[WebRTC] WS error', e);

        ws.onmessage = async (ev) => {
            let msg: Record<string, unknown>;
            try { msg = JSON.parse(ev.data as string); } catch { return; }

            const type = msg.type as string;

            if (type === 'joined') {
                const p = msg.participant as { participant_id: string; role: string };
                selfPidRef.current = p.participant_id;
                console.log('[WebRTC] joined as', p.role, p.participant_id);
            }

            if (type === 'participants_snapshot') {
                const list = (msg.participants as Array<{
                    participant_id: string; role: string; display_name: string;
                }>) ?? [];
                list.forEach(p => {
                    if (p.participant_id !== selfPidRef.current) {
                        participantsRef.current.set(p.participant_id, {
                            role: p.role,
                            displayName: p.display_name,
                        });
                    }
                });
            }

            if (type === 'participant_joined') {
                const p = msg.participant as { participant_id: string; role: string; display_name: string };
                if (p.participant_id !== selfPidRef.current) {
                    participantsRef.current.set(p.participant_id, {
                        role: p.role,
                        displayName: p.display_name,
                    });
                }
            }

            // Backend tells the NEW joiner's existing peers to initiate with them
            if (type === 'negotiate_with') {
                const targetPid = msg.participant_id as string;
                console.log('[WebRTC] negotiate_with', targetPid);
                createPeer(targetPid, true /* I am the initiator */);
            }

            if (type === 'offer') {
                const fromPid = msg.from as string;
                console.log('[WebRTC] offer from', fromPid);
                const pc = createPeer(fromPid, false);

                // Perfect negotiation: handle glare
                const offerCollision =
                    pc.signalingState !== 'stable' ||
                    pc.localDescription !== null;

                if (offerCollision) {
                    await Promise.all([
                        pc.setLocalDescription({ type: 'rollback' }).catch(() => { }),
                        pc.setRemoteDescription(msg.sdp as RTCSessionDescriptionInit),
                    ]);
                } else {
                    await pc.setRemoteDescription(msg.sdp as RTCSessionDescriptionInit);
                }

                const answer = await pc.createAnswer();
                await pc.setLocalDescription(answer);
                send({ type: 'answer', to: fromPid, sdp: pc.localDescription });
            }

            if (type === 'answer') {
                const fromPid = msg.from as string;
                const pc = peersRef.current.get(fromPid);
                if (pc?.signalingState === 'have-local-offer') {
                    await pc.setRemoteDescription(msg.sdp as RTCSessionDescriptionInit);
                }
            }

            if (type === 'ice') {
                const fromPid = msg.from as string;
                const pc = peersRef.current.get(fromPid);
                if (pc && pc.remoteDescription && msg.candidate) {
                    try {
                        await pc.addIceCandidate(new RTCIceCandidate(msg.candidate as RTCIceCandidateInit));
                    } catch { }
                }
            }

            if (type === 'participant_left') {
                const pid = msg.participant_id as string;
                const pc = peersRef.current.get(pid);
                if (pc) { pc.close(); peersRef.current.delete(pid); }
                participantsRef.current.delete(pid);
                onRemoteLeftRef.current(pid);
            }

            if (type === 'ping') send({ type: 'pong' });
        };

        return () => {
            console.log('[WebRTC] cleanup');
            ws.close();
            wsRef.current = null;
            peersRef.current.forEach(pc => pc.close());
            peersRef.current.clear();
            participantsRef.current.clear();
        };
        // Only re-run when the actual connection parameters change, NOT callbacks
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token, jwtToken]);
}
