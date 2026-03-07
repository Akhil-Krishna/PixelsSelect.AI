'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import './watch.css';
import { Message, Metrics, FlagItem, InterviewSession } from '../../../lib/types';
import { apiCall, API_BASE, formatTime } from '../../../lib/api';
import { useWebRTC } from '../../../hooks/useWebRTC';

// Components
import { MetricsPanel } from '../../../components/watch/MetricsPanel';
import { FlagsList } from '../../../components/watch/FlagsList';
import { VideoGrid } from '../../../components/watch/VideoGrid';
import { ChatView } from '../../../components/watch/ChatView';

export default function WatchPage() {
    const params = useParams();
    const token = params.token as string;

    // ── Session state ─────────────────────────────────────────────────────────
    const [session, setSession] = useState<InterviewSession | null>(null);
    const [status, setStatus] = useState('');
    const [isLive, setIsLive] = useState(false);
    const [elapsed, setElapsed] = useState(0);
    const [aiPaused, setAiPaused] = useState(false);

    // ── Chat ──────────────────────────────────────────────────────────────────
    const [messages, setMessages] = useState<Message[]>([]);
    const [totalMsgs, setTotalMsgs] = useState(0);
    const [aiQ, setAiQ] = useState(0);
    const [candR, setCandR] = useState(0);
    const [askInput, setAskInput] = useState('');

    // ── Metrics & Flags ───────────────────────────────────────────────────────
    const [metrics, setMetrics] = useState<Metrics>({});
    const [prevMetrics, setPrevMetrics] = useState<Metrics>({});
    const [flags, setFlags] = useState<FlagItem[]>([]);
    const flagIdRef = useRef(0);

    // ── Recording ─────────────────────────────────────────────────────────────
    const [recStatus, setRecStatus] = useState('Not started');
    const [recLink, setRecLink] = useState('');

    // ── Media ─────────────────────────────────────────────────────────────────
    const [roomMuted, setRoomMuted] = useState(false);
    const [roomCamOff, setRoomCamOff] = useState(false);
    const [jwtToken, setJwtToken] = useState('');
    const [roomStreamState, setRoomStreamState] = useState<MediaStream | null>(null);
    const [remoteStreams, setRemoteStreams] = useState<import('../../../hooks/useWebRTC').RemoteParticipant[]>([]);
    const localVideoRef = useRef<HTMLVideoElement>(null);
    const roomStream = useRef<MediaStream | null>(null);

    // ── Intervals ─────────────────────────────────────────────────────────────
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const metricsRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const lastMsgId = useRef<string | null>(null);
    const startedAt = useRef<Date | null>(null);

    // ── Helpers ───────────────────────────────────────────────────────────────
    const addFlag = useCallback((text: string, type: FlagItem['type'], icon: string) => {
        setFlags(prev => [{
            id: ++flagIdRef.current, text, type, icon, time: new Date().toLocaleTimeString(),
        }, ...prev.slice(0, 49)]);
    }, []);

    const updateCounts = (msgs: Message[]) => {
        setTotalMsgs(msgs.length);
        setAiQ(msgs.filter(m => m.role === 'ai').length);
        setCandR(msgs.filter(m => m.role === 'candidate').length);
    };

    const appendMsg = useCallback((m: Message) => {
        setMessages(prev => {
            if (prev.find(x => x.id === m.id)) return prev;
            const next = [...prev, m];
            updateCounts(next);
            return next;
        });
        if (m.role === 'candidate' && m.code_snippet) {
            addFlag('Candidate submitted code solution', 'info', 'fa-code');
        }
    }, [addFlag]);

    const startTimer = useCallback(() => {
        if (timerRef.current) return;
        timerRef.current = setInterval(() => {
            const base = startedAt.current ?? new Date();
            setElapsed(Math.floor((Date.now() - base.getTime()) / 1000));
        }, 1000);
    }, []);

    const detectFlags = useCallback((m: Metrics) => {
        const prevTab = prevMetrics.tab_switches || 0;
        const newTab = m.tab_switches || 0;
        if (newTab > prevTab) {
            for (let i = prevTab; i < newTab; i++)
                addFlag(`Tab switch #${i + 1} detected`, 'danger', 'fa-arrow-right-arrow-left');
        }
        if ((m.face_count ?? 1) === 0) addFlag('No face detected', 'danger', 'fa-face-frown');
        if ((m.face_count ?? 1) > 1) addFlag(`${m.face_count} faces in frame`, 'danger', 'fa-users');
        const risk = m.cheating_score ?? 0;
        if (risk > 50 && (prevMetrics.cheating_score ?? 0) <= 50)
            addFlag(`High integrity risk: ${risk.toFixed(1)}%`, 'danger', 'fa-triangle-exclamation');
        else if (risk > 25 && (prevMetrics.cheating_score ?? 0) <= 25)
            addFlag(`Moderate integrity risk: ${risk.toFixed(1)}%`, 'warn', 'fa-exclamation-circle');
    }, [prevMetrics, addFlag]);

    // ── Polling ───────────────────────────────────────────────────────────────
    const doPoll = useCallback(async () => {
        try {
            const path = `/interview-session/messages/${token}${lastMsgId.current ? '?since_id=' + lastMsgId.current : ''}`;
            const msgs = await apiCall<Message[]>('GET', path);
            if (msgs?.length) {
                msgs.forEach(appendMsg);
                lastMsgId.current = msgs[msgs.length - 1].id;
            }
            const st = await apiCall<{ status: string; ai_paused: boolean }>('GET', `/interview-session/status/${token}`);
            if (st) {
                setStatus(st.status);
                setIsLive(st.status === 'in_progress');
                if (st.status === 'in_progress' && !timerRef.current) {
                    if (!startedAt.current) startedAt.current = new Date();
                    startTimer();
                }
                setAiPaused(st.ai_paused);
                if (st.status === 'completed') {
                    if (pollRef.current) clearInterval(pollRef.current);
                    if (metricsRef.current) clearInterval(metricsRef.current);
                    addFlag('Interview completed', 'success', 'fa-flag-checkered');
                    // Load recording
                    const d = await apiCall<InterviewSession>('GET', `/interview-session/join/${token}`);
                    if (d?.has_recording) {
                        setRecStatus('Available');
                        setRecLink(`${API_BASE}/recordings/download/${token}`);
                    } else {
                        setRecStatus('Not available');
                    }
                }
            }
        } catch { }
    }, [token, appendMsg, startTimer, addFlag]);

    const doMetrics = useCallback(async () => {
        try {
            const m = await apiCall<Metrics>('GET', `/interview-session/metrics/${token}`);
            if (!m) return;
            detectFlags(m);
            setMetrics(m);
            setPrevMetrics(m);
        } catch { }
    }, [token, detectFlags]);

    // ── Boot ──────────────────────────────────────────────────────────────────
    useEffect(() => {
        const tok = localStorage.getItem('token');
        if (!tok) { window.location.href = '/'; return; }

        (async () => {
            try {
                const me = await apiCall<{ role: string }>('GET', '/users/me');
                if (!me || !['admin', 'hr', 'interviewer'].includes(me.role)) {
                    alert('Access denied'); window.location.href = '/'; return;
                }
                const data = await apiCall<InterviewSession>('GET', `/interview-session/join/${token}`);
                if (!data) { alert('Interview not found'); return; }
                setSession(data);
                setStatus(data.status);
                setIsLive(data.status === 'in_progress');
                setAiPaused(!!data.ai_paused);

                if (data.status === 'in_progress' && data.started_at) {
                    const iso = data.started_at.includes('Z') || data.started_at.includes('+')
                        ? data.started_at : data.started_at + 'Z';
                    startedAt.current = new Date(iso);
                    startTimer();
                }

                // Camera
                try {
                    const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                    roomStream.current = s;
                    setRoomStreamState(s);                     // triggers WebRTC
                    if (localVideoRef.current) localVideoRef.current.srcObject = s;
                } catch { addFlag('Camera/mic unavailable', 'warn', 'fa-video-slash'); }

                // Read JWT for WebRTC WS auth
                setJwtToken(localStorage.getItem('token') || '');

                // Load messages
                const msgs = await apiCall<Message[]>('GET', `/interview-session/messages/${token}`);
                if (msgs?.length) {
                    setMessages(msgs); updateCounts(msgs);
                    lastMsgId.current = msgs[msgs.length - 1].id;
                }

                pollRef.current = setInterval(doPoll, 2000);
                setTimeout(() => { metricsRef.current = setInterval(doMetrics, 3000); doMetrics(); }, 1000);
            } catch (e) { console.error(e); }
        })();

        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
            if (metricsRef.current) clearInterval(metricsRef.current);
            if (timerRef.current) clearInterval(timerRef.current);
            roomStream.current?.getTracks().forEach(t => t.stop());
        };
    }, [token]);

    // ── WebRTC ───────────────────────────────────────────────────────────
    useWebRTC({
        token,
        jwtToken,
        localStream: roomStreamState,
        onRemoteStream: (p) => {
            setRemoteStreams(prev => {
                const others = prev.filter(s => s.participantId !== p.participantId);
                return [...others, p];
            });
        },
        onRemoteLeft: (pid) => setRemoteStreams(prev => prev.filter(s => s.participantId !== pid)),
    });

    // ── Actions ───────────────────────────────────────────────────────────────
    const startRoomCamera = async () => {
        const videoOnly = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        const track = videoOnly.getVideoTracks()[0];
        if (!track) return;
        if (!roomStream.current) {
            roomStream.current = new MediaStream();
        }
        roomStream.current.addTrack(track);
        setRoomStreamState(new MediaStream(roomStream.current.getTracks()));
        if (localVideoRef.current) {
            localVideoRef.current.srcObject = roomStream.current;
            localVideoRef.current.play().catch(() => { });
        }
    };

    const stopRoomCamera = () => {
        const stream = roomStream.current;
        if (!stream) return;
        stream.getVideoTracks().forEach(track => {
            track.stop();
            stream.removeTrack(track);
        });
    };

    const toggleMute = () => {
        setRoomMuted(m => { roomStream.current?.getAudioTracks().forEach(t => t.enabled = m); return !m; });
    };
    const toggleCam = async () => {
        if (roomCamOff) {
            try {
                await startRoomCamera();
                setRoomCamOff(false);
            } catch {
                addFlag('Could not re-enable camera', 'warn', 'fa-video');
            }
            return;
        }
        stopRoomCamera();
        setRoomCamOff(true);
        setRoomStreamState(roomStream.current ? new MediaStream(roomStream.current.getTracks()) : null);
    };
    const leaveRoom = () => { roomStream.current?.getTracks().forEach(t => t.stop()); window.location.href = '/'; };

    const pauseAI = async () => {
        try { await apiCall('POST', `/interview-session/pause-ai/${token}`); setAiPaused(true); addFlag('AI paused', 'info', 'fa-pause-circle'); }
        catch (e: unknown) { alert((e as Error).message); }
    };
    const resumeAI = async () => {
        try { await apiCall('POST', `/interview-session/resume-ai/${token}`); setAiPaused(false); addFlag('AI resumed', 'success', 'fa-play-circle'); }
        catch (e: unknown) { alert((e as Error).message); }
    };
    const sendQuestion = async () => {
        if (!askInput.trim()) return;
        try {
            const r = await apiCall<Message>('POST', `/interview-session/ask/${token}`, { question: askInput.trim() });
            if (r) { appendMsg(r); setAskInput(''); }
        } catch (e: unknown) { alert((e as Error).message); }
    };

    const timerStr = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;

    // ── Loading screen ────────────────────────────────────────────────────────
    if (!session) {
        return (
            <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: '#0F172A', flexDirection: 'column', gap: 16 }}>
                <div style={{ fontSize: 48 }}>📡</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#F1F5F9' }}>PixelsSelect.AI — Live Monitor</div>
                <div style={{ color: '#94A3B8', fontSize: 13 }}>Loading interview session...</div>
            </div>
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            {/* ── Topbar ── */}
            <div className="topbar">
                <span className="logo">PixelsSelect.AI</span>
                <span className="sep">|</span>
                <span className="iv-name">{session.title}</span>
                <div className={`pill ${isLive ? 'pill-live' : 'pill-wait'}`}>
                    <div className={`dot ${isLive ? 'dot-live' : 'dot-wait'}`} />
                    <span>{isLive ? 'LIVE' : status.replace('_', ' ').toUpperCase()}</span>
                </div>
                <div className="tb-right">
                    <span className="timer">{timerStr}</span>
                    <a href="/" className="btn btn-o" style={{ fontSize: 11, padding: '5px 12px' }}>
                        ← Dashboard
                    </a>
                </div>
            </div>

            {/* ── 3-column layout ── */}
            <div className="layout" style={{ flex: 1, overflow: 'hidden' }}>
                {/* LEFT: Metrics + Flags */}
                <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                    <div style={{ flex: 1, overflowY: 'auto' }}>
                        <MetricsPanel
                            sessionInfo={{
                                candidateName: session.candidate?.full_name ?? '-',
                                jobRole: session.job_role,
                                status,
                                aiPaused,
                                durationMin: session.duration_minutes,
                            }}
                            metrics={metrics}
                            counters={{ totalMsgs, aiQ, candR }}
                            recStatus={recStatus}
                            recLink={recLink}
                        />
                        <FlagsList flags={flags} />
                    </div>
                </div>

                {/* CENTER: Video tiles */}
                <VideoGrid
                    localVideoRef={localVideoRef}
                    remoteStreams={remoteStreams}
                    roomMuted={roomMuted}
                    roomCamOff={roomCamOff}
                    onToggleMute={toggleMute}
                    onToggleCam={toggleCam}
                    onLeave={leaveRoom}
                />

                {/* RIGHT: Chat + AI controls */}
                <ChatView
                    messages={messages}
                    totalMsgs={totalMsgs}
                    isLive={isLive}
                    aiPaused={aiPaused}
                    askInput={askInput}
                    onAskChange={setAskInput}
                    onAskSend={sendQuestion}
                    onPauseAI={pauseAI}
                    onResumeAI={resumeAI}
                />
            </div>
        </div>
    );
}
