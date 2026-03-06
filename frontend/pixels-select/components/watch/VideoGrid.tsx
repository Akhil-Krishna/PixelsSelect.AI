'use client';

import { useEffect, useRef } from 'react';
import type { RemoteParticipant } from '../../hooks/useWebRTC';

interface VideoGridProps {
    localVideoRef: React.RefObject<HTMLVideoElement | null>;
    remoteStreams: RemoteParticipant[];
    roomMuted: boolean;
    roomCamOff: boolean;
    onToggleMute: () => void;
    onToggleCam: () => void;
    onLeave: () => void;
}

export function VideoGrid({
    localVideoRef, remoteStreams, roomMuted, roomCamOff,
    onToggleMute, onToggleCam, onLeave,
}: VideoGridProps) {

    // Find the candidate stream — role 'candidate'
    const candidateParticipant = remoteStreams.find(s => s.role === 'candidate') ?? null;

    return (
        <div className="mid-col">
            <div className="video-stage">
                <div className="video-grid">
                    {/* HR's own camera */}
                    <VideoTile label="You (Interviewer)">
                        <video ref={localVideoRef} autoPlay muted playsInline
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </VideoTile>

                    {/* AI tile */}
                    <VideoTile label="AI Interviewer" gradient>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 30 }}>🤖</div>
                            <div style={{ fontSize: 11, color: '#cbd5e1', marginTop: 4 }}>AI Interviewer</div>
                        </div>
                    </VideoTile>

                    {/* Live candidate feed */}
                    <CandidateTile participant={candidateParticipant} />

                    {/* Any other remote participants (interviewers, etc.) */}
                    {remoteStreams
                        .filter(s => s.role !== 'candidate')
                        .map(s => (
                            <RemoteTile key={s.participantId} participant={s} />
                        ))}
                </div>
            </div>

            {/* Controls */}
            <div className="controls-bar">
                <button className="btn btn-o" onClick={onToggleMute}>
                    <i className={`fas fa-microphone${roomMuted ? '-slash' : ''}`} /> Mic
                </button>
                <button className="btn btn-o" onClick={onToggleCam}>
                    <i className={`fas fa-video${roomCamOff ? '-slash' : ''}`} /> Camera
                </button>
                <button className="btn" style={{ background: '#ef4444', color: '#fff' }} onClick={onLeave}>
                    <i className="fas fa-phone-slash" /> Leave
                </button>
            </div>
        </div>
    );
}

// ── Shared tile shell ─────────────────────────────────────────────────────────

function VideoTile({ label, gradient, children }: {
    label: string; gradient?: boolean; children: React.ReactNode;
}) {
    return (
        <div style={{
            position: 'relative', border: '2px solid #334155', borderRadius: 10,
            overflow: 'hidden', background: gradient ? 'linear-gradient(135deg,#1e1b4b,#111827)' : '#020617',
            minHeight: 130, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
            {children}
            <TileLabel>{label}</TileLabel>
        </div>
    );
}

// ── Candidate tile ────────────────────────────────────────────────────────────

function CandidateTile({ participant }: { participant: RemoteParticipant | null }) {
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        const video = videoRef.current;
        if (!video || !participant?.stream) return;
        if (video.srcObject !== participant.stream) {
            video.srcObject = participant.stream;
        }
        video.play().catch(() => { });
        // participant object reference changes on every state update even if stream is same ref
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [participant]);

    const connected = !!participant;

    return (
        <div style={{
            position: 'relative', border: `2px solid ${connected ? '#22c55e' : '#334155'}`,
            borderRadius: 10, overflow: 'hidden', background: '#020617',
            minHeight: 130, display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'border-color 0.3s',
        }}>
            {/* video is always in DOM once participant exists so srcObject assignment works */}
            <video
                ref={videoRef}
                autoPlay
                playsInline
                style={{
                    width: '100%', height: '100%', objectFit: 'cover',
                    display: connected ? 'block' : 'none',
                }}
            />
            {!connected && (
                <div style={{ textAlign: 'center', color: '#64748b', padding: 16 }}>
                    <i className="fas fa-user-circle" style={{ fontSize: 36, display: 'block', marginBottom: 8, opacity: 0.4 }} />
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8' }}>Awaiting candidate...</div>
                    <div style={{ fontSize: 10, marginTop: 4, color: '#475569' }}>Live feed via WebRTC</div>
                </div>
            )}
            <TileLabel live={connected}>Candidate — Live</TileLabel>
        </div>
    );
}

// ── Other remote participants ─────────────────────────────────────────────────

function RemoteTile({ participant }: { participant: RemoteParticipant }) {
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;
        if (video.srcObject !== participant.stream) {
            video.srcObject = participant.stream;
        }
        video.play().catch(() => { });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [participant]);

    return (
        <div style={{
            position: 'relative', border: '2px solid #334155', borderRadius: 10,
            overflow: 'hidden', background: '#020617',
            minHeight: 130, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
            <video ref={videoRef} autoPlay playsInline
                style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            <TileLabel live>{participant.displayName || 'Participant'}</TileLabel>
        </div>
    );
}

// ── Labels ────────────────────────────────────────────────────────────────────

function TileLabel({ children, live }: { children: React.ReactNode; live?: boolean }) {
    return (
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
                }} />
            )}
            {children}
        </div>
    );
}
