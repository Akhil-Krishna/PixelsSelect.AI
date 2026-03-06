'use client';

import { useEffect, useRef } from 'react';
import type { RemoteParticipant } from '../../hooks/useWebRTC';

interface VideoStageProps {
    localVideoRef: React.RefObject<HTMLVideoElement | null>;
    camOff: boolean;
    remoteStreams?: RemoteParticipant[];
}

export function VideoStage({ localVideoRef, camOff, remoteStreams = [] }: VideoStageProps) {
    return (
        <div className="stage-panel">
            <div style={{
                flex: 1, display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 10, padding: 10, overflow: 'hidden', alignContent: 'start',
                height: '100%',
            }}>
                {/* Candidate's own camera — always in DOM to keep ref valid */}
                <VideoTile label="You — Live">
                    <video
                        ref={localVideoRef}
                        autoPlay
                        muted
                        playsInline
                        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                    />
                    {camOff && (
                        <div style={{
                            position: 'absolute', inset: 0,
                            background: '#020617',
                            display: 'flex', flexDirection: 'column',
                            alignItems: 'center', justifyContent: 'center',
                            color: '#94a3b8',
                        }}>
                            <div style={{ fontSize: 36 }}>🎥</div>
                            <div style={{ fontSize: 11, marginTop: 4 }}>Camera off</div>
                        </div>
                    )}
                </VideoTile>

                {/* AI tile */}
                <VideoTile label="AI Interviewer" id="tile-ai" gradient>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 48 }}>🤖</div>
                        <div style={{ fontSize: 12, color: '#cbd5e1', marginTop: 6 }}>AI Interviewer</div>
                    </div>
                </VideoTile>

                {/* Remote HR/Interviewer streams */}
                {remoteStreams.map(p => (
                    <RemoteVideoTile key={p.participantId} participant={p} />
                ))}
            </div>
        </div>
    );
}

// ── Remote video tile ───────────────────────────────────────────────────────

function RemoteVideoTile({ participant }: { participant: RemoteParticipant }) {
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        const video = videoRef.current;
        if (!video || !participant.stream) return;
        // Re-assign srcObject every time participant updates (new tracks may have been added)
        // Checking reference avoids unnecessary flicker
        if (video.srcObject !== participant.stream) {
            video.srcObject = participant.stream;
        }
        video.play().catch(() => { });
        // participant object reference changes each time onRemoteStream fires, even if stream ref is same
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [participant]);

    const label = participant.role === 'hr' ? '👤 HR Observer'
        : participant.role === 'interviewer' ? '🎙 Interviewer'
            : participant.displayName || 'Participant';

    return (
        <VideoTile label={label} live>
            <video
                ref={videoRef}
                autoPlay
                playsInline
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            />
        </VideoTile>
    );
}

// ── Shared tile shell ────────────────────────────────────────────────────────

interface VideoTileProps {
    label: string;
    id?: string;
    gradient?: boolean;
    live?: boolean;
    children: React.ReactNode;
}

function VideoTile({ label, id, gradient, live, children }: VideoTileProps) {
    return (
        <div
            id={id}
            style={{
                position: 'relative',
                border: `2px solid ${live ? '#22c55e' : '#334155'}`,
                borderRadius: 12,
                overflow: 'hidden',
                background: gradient
                    ? 'linear-gradient(135deg,#1e1b4b,#111827)'
                    : '#020617',
                minHeight: 180,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'border-color .3s',
            }}
        >
            {children}
            <div style={{
                position: 'absolute', left: 8, bottom: 8,
                background: 'rgba(2,6,23,.85)', padding: '2px 8px',
                borderRadius: 10, fontSize: 11, color: '#fff',
                display: 'flex', alignItems: 'center', gap: 5,
            }}>
                {live && (
                    <span style={{
                        width: 6, height: 6, borderRadius: '50%',
                        background: '#22c55e', display: 'inline-block',
                        animation: 'pulse-dot 1.5s infinite',
                    }} />
                )}
                {label}
            </div>
        </div>
    );
}
