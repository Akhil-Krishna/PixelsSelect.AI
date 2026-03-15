'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import './interview.css';
import { Message, InterviewSession } from '../../../lib/types';
import { apiCall, API_BASE } from '../../../lib/api';
import { useWebRTC } from '../../../hooks/useWebRTC';

// Components
import { VideoStage } from '../../../components/interview/VideoStage';
import { ChatPanel } from '../../../components/interview/ChatPanel';
import { StartOverlay } from '../../../components/interview/StartOverlay';
import { CompleteOverlay } from '../../../components/interview/CompleteOverlay';

const VISION_INTERVAL_MS = 3000;

interface ScoreBox { label: string; val: number; color: string; }
interface CompletedState { title: string; sub: string; scores: ScoreBox[]; }

const hasMeaningfulTranscript = (text: string) => /[A-Za-z0-9]/.test(text);
const isCodingPromptText = (text: string) =>
    (text || '').includes('[CODING_QUESTION]');

export default function InterviewPage() {
    const params = useParams();
    const token = params.token as string;

    // ── Core state ────────────────────────────────────────────────────────────
    const [session, setSession] = useState<InterviewSession | null>(null);
    const [loadError, setLoadError] = useState('');
    const [started, setStarted] = useState(false);
    const [completed, setCompleted] = useState(false);
    const [completedData, setCompletedData] = useState<CompletedState | null>(null);
    const [startLoading, setStartLoading] = useState(false);
    const [startError, setStartError] = useState('');

    // ── Candidate verification (magic-link flow) ──────────────────────────────
    const [needsVerify, setNeedsVerify] = useState(false);
    const [verifyEmail, setVerifyEmail] = useState('');
    const [verifyName, setVerifyName] = useState('');
    const [verifyError, setVerifyError] = useState('');
    const [verifyStatus, setVerifyStatus] = useState<'idle' | 'early' | 'expired' | 'ok'>('idle');
    const [verifyScheduledAt, setVerifyScheduledAt] = useState('');
    const [verifyLoading, setVerifyLoading] = useState(false);
    const [verifiedViaMagicLink, setVerifiedViaMagicLink] = useState(false);

    // ── Messages ───────────────────────────────────────────────────────────────
    const [messages, setMessages] = useState<Message[]>([]);

    // ── Input state ───────────────────────────────────────────────────────────
    const [textInput, setTextInput] = useState('');
    const [codeInput, setCodeInput] = useState('');
    const [codeLang, setCodeLang] = useState('python');
    const [codeOpen, setCodeOpen] = useState(false);
    const [sending, setSending] = useState(false);
    // Refs for coding timer (avoids stale closures when timer fires minutes later)
    const codeInputRef = useRef('');
    const codeOpenRef = useRef(false);

    // ── Voice / STT ───────────────────────────────────────────────────────────
    const [voiceOn, setVoiceOn] = useState(true);
    const [isListening, setIsListening] = useState(false);
    const [sttStatus, setSttStatus] = useState('');
    const voiceOnRef = useRef(true);
    const isListeningRef = useRef(false);
    const isTtsSpeaking = useRef(false);
    const pendingAutoListen = useRef(false);
    const ttsSeq = useRef(0);
    const whisperRecorder = useRef<MediaRecorder | null>(null);
    const whisperChunks = useRef<Blob[]>([]);
    const audioCtxRef = useRef<AudioContext | null>(null);
    const vadRafRef = useRef<number | null>(null);
    const maxListenTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    // Stable refs so empty-dep useCallbacks always call the latest version
    const sendMessageRef = useRef<((text: string) => Promise<void>) | null>(null);
    const speakRef = useRef<((text: string) => void) | null>(null);
    const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
    const ttsAudioUrlRef = useRef<string | null>(null);

    // ── Media / Timer ─────────────────────────────────────────────────────────
    const [muted, setMuted] = useState(false);
    const [camOff, setCamOff] = useState(false);
    const [elapsed, setElapsed] = useState(0);
    const [isCritical, setIsCritical] = useState(false);
    const [isLive, setIsLive] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const [jwtToken, setJwtToken] = useState('');
    const [localStream, setLocalStream] = useState<MediaStream | null>(null);
    const [remoteStreams, setRemoteStreams] = useState<import('../../../hooks/useWebRTC').RemoteParticipant[]>([]);

    // ── Vision metrics ────────────────────────────────────────────────────────
    const [qCount, setQCount] = useState(0);
    const [rCount, setRCount] = useState(0);
    const [tabSwitches, setTabSwitches] = useState(0);
    const [lookAway, setLookAway] = useState(0);
    const [multiFace, setMultiFace] = useState(0);
    const [faceCount, setFaceCount] = useState(1);
    const [gaze, setGaze] = useState('OK');
    const [emotion, setEmotion] = useState('–');
    const [aiPaused, setAiPaused] = useState(false);

    // ── Refs ──────────────────────────────────────────────────────────────────
    const localVideoRef = useRef<HTMLVideoElement>(null);
    const previewVideoRef = useRef<HTMLVideoElement>(null);
    const camStream = useRef<MediaStream | null>(null);
    const screenStream = useRef<MediaStream | null>(null);
    const recorder = useRef<MediaRecorder | null>(null);
    const recordingStreamRef = useRef<MediaStream | null>(null);
    const recordingMime = useRef<string>('video/webm');
    const recordingAudioCtxRef = useRef<AudioContext | null>(null);
    const recordingAudioDestRef = useRef<MediaStreamAudioDestinationNode | null>(null);
    const recordingAudioSourcesRef = useRef<Map<string, MediaStreamAudioSourceNode>>(new Map());
    const recordingTtsSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
    const recChunks = useRef<Blob[]>([]);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const visionRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const tabSwRef = useRef(0);
    const frameSeqRef = useRef(0);
    const lastTabSwitchMsRef = useRef(0);
    const doneRef = useRef(false);
    const manualSendRequiredRef = useRef(false);
    const awaitingAiReplyRef = useRef(false);
    
    // ── TTS Completion Tracking ─────────────────────────────────────────────
    const ttsCompletedRef = useRef(true); // Track if TTS has finished speaking
    const interviewCompleteSentRef = useRef(false); // Track if INTERVIEW_COMPLETE was processed
    
    // ── Coding Question Timer ───────────────────────────────────────────────
    const codingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const codingWarningRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const codingStartTimeRef = useRef<number | null>(null);
    const codingTimeLimitRef = useRef<number>(0); // Time limit in seconds for coding
    const isCodingQuestionRef = useRef(false); // Track if currently in coding question

    const incrementTabSwitch = useCallback(() => {
        const now = Date.now();
        // Avoid duplicate increments when blur + visibilitychange fire together.
        if (now - lastTabSwitchMsRef.current < 700) return;
        lastTabSwitchMsRef.current = now;
        tabSwRef.current += 1;
        setTabSwitches(tabSwRef.current);
        // F6: Persist tab-switch count to backend immediately (fire-and-forget)
        apiCall('POST', `/interview-session/tab-switch/${token}`, { count: tabSwRef.current }).catch(() => {});
    }, [token]);

    const stopBackendTtsAudio = useCallback(() => {
        if (recordingTtsSourceRef.current) {
            try { recordingTtsSourceRef.current.disconnect(); } catch { }
            recordingTtsSourceRef.current = null;
        }
        const a = ttsAudioRef.current;
        if (a) {
            a.pause();
            a.src = '';
            ttsAudioRef.current = null;
        }
        if (ttsAudioUrlRef.current) {
            URL.revokeObjectURL(ttsAudioUrlRef.current);
            ttsAudioUrlRef.current = null;
        }
    }, []);

    const resetRecordingAudioGraph = useCallback(() => {
        recordingAudioSourcesRef.current.forEach((node) => {
            try { node.disconnect(); } catch { }
        });
        recordingAudioSourcesRef.current.clear();

        if (recordingTtsSourceRef.current) {
            try { recordingTtsSourceRef.current.disconnect(); } catch { }
            recordingTtsSourceRef.current = null;
        }

        const ctx = recordingAudioCtxRef.current;
        if (ctx && ctx.state !== 'closed') {
            void ctx.close().catch(() => { });
        }
        recordingAudioCtxRef.current = null;
        recordingAudioDestRef.current = null;
        recordingStreamRef.current = null;
    }, []);

    const ensureRecordingAudioGraph = useCallback(() => {
        if (!recordingAudioCtxRef.current || recordingAudioCtxRef.current.state === 'closed') {
            const win = window as Window & { webkitAudioContext?: typeof AudioContext; AudioContext?: typeof AudioContext };
            const AudioContextClass = win.AudioContext || win.webkitAudioContext;
            if (!AudioContextClass) return { ctx: null, dest: null };
            recordingAudioCtxRef.current = new AudioContextClass();
            recordingAudioDestRef.current = recordingAudioCtxRef.current!.createMediaStreamDestination();
        }
        const ctx = recordingAudioCtxRef.current;
        if (ctx?.state === 'suspended') {
            void ctx.resume().catch(() => { });
        }
        return {
            ctx: recordingAudioCtxRef.current,
            dest: recordingAudioDestRef.current,
        };
    }, []);

    const attachStreamToRecordingMix = useCallback((key: string, stream: MediaStream | null) => {
        if (!stream || recordingAudioSourcesRef.current.has(key)) return;
        const audioTracks = stream.getAudioTracks();
        if (!audioTracks.length) return;

        const { ctx, dest } = ensureRecordingAudioGraph();
        if (!ctx || !dest) return;

        const sourceStream = new MediaStream(audioTracks);
        const sourceNode = ctx.createMediaStreamSource(sourceStream);
        sourceNode.connect(dest);
        recordingAudioSourcesRef.current.set(key, sourceNode);
    }, [ensureRecordingAudioGraph]);

    const syncRemoteStreamsToRecordingMix = useCallback((streams: import('../../../hooks/useWebRTC').RemoteParticipant[]) => {
        const active = new Set(streams.map((p) => `remote:${p.participantId}`));
        streams.forEach((p) => {
            attachStreamToRecordingMix(`remote:${p.participantId}`, p.stream ?? null);
        });
        recordingAudioSourcesRef.current.forEach((node, key) => {
            if (!key.startsWith("remote:")) return;
            if (active.has(key)) return;
            try { node.disconnect(); } catch { }
            recordingAudioSourcesRef.current.delete(key);
        });
    }, [attachStreamToRecordingMix]);

    const attachTtsAudioToRecordingMix = useCallback((audioEl: HTMLAudioElement) => {
        const ctx = recordingAudioCtxRef.current;
        const dest = recordingAudioDestRef.current;
        if (!ctx || !dest) return;

        if (recordingTtsSourceRef.current) {
            try { recordingTtsSourceRef.current.disconnect(); } catch { }
            recordingTtsSourceRef.current = null;
        }
        try {
            const source = ctx.createMediaElementSource(audioEl);
            source.connect(dest);
            source.connect(ctx.destination);
            recordingTtsSourceRef.current = source;
        } catch (err) {
            console.warn("Could not connect AI audio to recorder mix", err);
        }
    }, []);

    const stopScreenShare = useCallback(() => {
        screenStream.current?.getTracks().forEach(track => track.stop());
        screenStream.current = null;
    }, []);


    // ── Coding Question Timer Functions ─────────────────────────────────────
    const startCodingTimer = useCallback((timeLimitSeconds: number) => {
        // Clear any existing timers
        if (codingTimerRef.current) clearTimeout(codingTimerRef.current);
        if (codingWarningRef.current) clearTimeout(codingWarningRef.current);
        
        codingStartTimeRef.current = Date.now();
        codingTimeLimitRef.current = timeLimitSeconds;
        isCodingQuestionRef.current = true;
        
        console.log(`[Coding Timer] Started with ${timeLimitSeconds}s limit`);
        
        // Warning at 75% of time
        const warningDelay = Math.floor(timeLimitSeconds * 0.75 * 1000);
        codingWarningRef.current = setTimeout(() => {
            if (!doneRef.current && isCodingQuestionRef.current) {
                setSttStatus('⚠️ Time almost up! Please submit your solution.');
                console.log('[Coding Timer] Warning sent at 75%');
            }
        }, warningDelay);
        
        // Auto-submit at 100% of time
        const autoSubmitDelay = timeLimitSeconds * 1000;
        codingTimerRef.current = setTimeout(() => {
            if (!doneRef.current && isCodingQuestionRef.current) {
                console.log('[Coding Timer] Auto-submitting code due to timeout');
                // Use refs (not state) — timer fires minutes after creation,
                // state values would be stale by then.
                if (codeInputRef.current.trim() || codeOpenRef.current) {
                    setSttStatus('⏰ Time up! Submitting your solution...');
                    sendMessageRef.current?.('[AUTO_SUBMIT] Code submission due to time limit');
                } else {
                    // No code written - submit empty
                    setSttStatus('⏰ Time up! Submitting empty solution...');
                    sendMessageRef.current?.('[AUTO_SUBMIT] No code submitted - time limit reached');
                }
                isCodingQuestionRef.current = false;
            }
        }, autoSubmitDelay);
    }, []);  // No state deps — uses only refs

    const stopCodingTimer = useCallback(() => {
        if (codingTimerRef.current) {
            clearTimeout(codingTimerRef.current);
            codingTimerRef.current = null;
        }
        if (codingWarningRef.current) {
            clearTimeout(codingWarningRef.current);
            codingWarningRef.current = null;
        }
        codingStartTimeRef.current = null;
        codingTimeLimitRef.current = 0;
        isCodingQuestionRef.current = false;
    }, []);

    // Extract time limit from AI message (format: [CODING_QUESTION] [TIME:5min] ...)
    const extractCodingTimeLimit = (content: string): number | null => {
        const timeMatch = content.match(/\[TIME:(\d+)(m|min|minutes|seconds|s)\]/i);
        if (timeMatch) {
            const value = parseInt(timeMatch[1], 10);
            const unit = timeMatch[2].toLowerCase();
            if (unit.startsWith('m')) return value * 60; // Convert to seconds
            return value;
        }
        return null;
    };

    const addMsg = useCallback((m: Message) => {
        setMessages(prev => {
            if (prev.find(x => x.id === m.id)) return prev;
            return [...prev, m];
        });
        if (m.role === 'ai') {
            awaitingAiReplyRef.current = false;
            setQCount(q => q + 1);
            
            // Reset TTS completion tracking for new AI message
            ttsCompletedRef.current = false;
            interviewCompleteSentRef.current = false;
            
            const text = m.content.replace(/\[CODING_QUESTION\]/gi, '').replace(/INTERVIEW_COMPLETE/gi, '').trim();
            if (text) {
                pendingAutoListen.current = true;
                // Use ref so we always call the latest speak (avoids stale closure)
                speakRef.current?.(text);
            }
            
            const isCodingPrompt = isCodingPromptText(m.content);
            if (isCodingPrompt) {
                setCodeOpen(true);
                setTextInput(prev => prev.trim() ? prev : '[CODE SUBMITTED]');
                manualSendRequiredRef.current = true;
                pendingAutoListen.current = false;
                // Keep mic ON (listening) but disable auto-send
                setSttStatus('🎤 Coding mode: type to send');
                
                // Extract time limit from message or calculate based on interview duration
                const extractedTime = extractCodingTimeLimit(m.content);
                const duration = session?.duration_minutes || 30;
                
                // Calculate default time based on interview duration:
                // - Short (5-15 min): 1-2 minutes
                // - Medium (20-30 min): 2-4 minutes  
                // - Long (45-60 min): 3-5 minutes
                let defaultTime: number;
                if (duration <= 15) {
                    defaultTime = Math.max(60, Math.floor(duration * 60 * 0.15)); // 15% for short
                } else if (duration <= 30) {
                    defaultTime = Math.floor(duration * 60 * 0.12); // 12% for medium
                } else {
                    defaultTime = Math.floor(duration * 60 * 0.08); // 8% for long (max ~5 min for 60 min interview)
                }
                
                const timeLimit = extractedTime || defaultTime;
                console.log(`[Coding Timer] Interview duration: ${duration}min, calculated time limit: ${timeLimit}s`);
                startCodingTimer(timeLimit);
            } else if (m.content.includes('INTERVIEW_COMPLETE')) {
                manualSendRequiredRef.current = false;
                stopCodingTimer(); // Stop any coding timer if running
                interviewCompleteSentRef.current = true;
                // Don't call endInterview immediately - wait for TTS to complete
                // The TTS completion will trigger endInterview via onSpeakingDone
            }
        }
        if (m.role === 'candidate') {
            setRCount(r => r + 1);
            // If candidate submits code, stop the coding timer
            if (isCodingQuestionRef.current && m.code_snippet) {
                stopCodingTimer();
            }
        }
    }, [session, startCodingTimer, stopCodingTimer]);


    // ── STT (Whisper) ─────────────────────────────────────────────────────────
    const startListening = useCallback(() => {


        if (manualSendRequiredRef.current) {
            setSttStatus('Coding mode: voice paused');
            return;
        }

        // Recover from Chrome TTS bug where onend never fires
        const backendAudio = ttsAudioRef.current;
        const backendSpeaking = Boolean(backendAudio && !backendAudio.paused && !backendAudio.ended);
        if (isTtsSpeaking.current && !window.speechSynthesis?.speaking && !backendSpeaking) {
            console.warn("Recovering stuck TTS lock");
            isTtsSpeaking.current = false;
        }

        if (isListeningRef.current || !camStream.current || isTtsSpeaking.current) {

            if (isTtsSpeaking.current) setSttStatus('AI speaking...');
            return;
        }

        // Guard: don't record if the mic is muted (disabled tracks produce silent audio)
        const audioTracks = camStream.current.getAudioTracks();
        if (!audioTracks.length || !audioTracks.some(t => t.enabled)) {
            console.warn("startListening aborted: microphone is muted or has no audio tracks.");
            setSttStatus('🔇 Mic muted');
            return;
        }

        try {

            const audio = new MediaStream(audioTracks);
            const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg', 'audio/mp4']
                .find(m => MediaRecorder.isTypeSupported(m)) || '';
            whisperRecorder.current = new MediaRecorder(audio, mime ? { mimeType: mime } : {});
            whisperChunks.current = [];
            whisperRecorder.current.ondataavailable = e => { if (e.data?.size) whisperChunks.current.push(e.data); };
            whisperRecorder.current.onstop = async () => {
                // Clear max-listen safety timer
                if (maxListenTimerRef.current) { clearTimeout(maxListenTimerRef.current); maxListenTimerRef.current = null; }

                const chunks = whisperChunks.current.splice(0);
                if (!chunks.length || doneRef.current) return;
                const blob = new Blob(chunks, { type: mime || 'audio/webm' });

                if (blob.size < 200) {
                    // Audio too short/silent — retry listening unless TTS is speaking
                    if (!isTtsSpeaking.current && voiceOnRef.current && !doneRef.current && !awaitingAiReplyRef.current) {
                        setTimeout(() => { if (!isTtsSpeaking.current) startListening(); }, 500);
                    }
                    return;
                }
                try {
                    const fd = new FormData(); fd.append('audio', blob, 'stt.webm');

                    const res = await fetch(`${API_BASE}/stt/transcribe`, {
                        method: 'POST', body: fd, credentials: 'include',
                    });
                    const d = await res.json().catch(() => ({}));

                    if (d.text?.trim()) {
                        const text = d.text.trim();
                        if (manualSendRequiredRef.current) {
                            setSttStatus('Coding mode: voice paused');
                            return;
                        }
                        if (!hasMeaningfulTranscript(text)) {
                            if (!isTtsSpeaking.current && voiceOnRef.current && !doneRef.current && !awaitingAiReplyRef.current) {
                                setTimeout(() => { if (!isTtsSpeaking.current) startListening(); }, 500);
                            }
                            return;
                        }
                        // Use ref to always call the latest sendMessage (avoids stale closure)
                        awaitingAiReplyRef.current = true;
                        sendMessageRef.current?.(text);
                    } else {

                        if (!isTtsSpeaking.current && voiceOnRef.current && !doneRef.current && !awaitingAiReplyRef.current) {
                            setTimeout(() => { if (!isTtsSpeaking.current) startListening(); }, 500);
                        } else {
                            pendingAutoListen.current = true;
                        }
                    }
                } catch (err) {
                    console.error("STT transcribing error:", err);
                    pendingAutoListen.current = true;
                }
            };
            whisperRecorder.current.start(250);
            isListeningRef.current = true;
            setIsListening(true);
            setSttStatus('🎤 Listening…');


            // Safety: stop listening after 30s max to avoid infinite silent recording
            maxListenTimerRef.current = setTimeout(() => {

                if (isListeningRef.current) stopListening();
            }, 30000);

            // ── VAD (Silence detection) ──────────────────────────────────────────
            try {
                const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
                if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
                    audioCtxRef.current = new AudioContextClass();
                }
                const ctx = audioCtxRef.current;
                if (ctx.state === 'suspended') {
                    ctx.resume().catch(() => { });
                }

                const src = ctx.createMediaStreamSource(audio);
                const an = ctx.createAnalyser();
                an.fftSize = 512;
                src.connect(an);

                const dataArray = new Uint8Array(an.frequencyBinCount);
                // Start lastSpeak from now so silence-after-no-speech also triggers cut-off
                let lastSpeak = Date.now();
                let speaking = false;
                // If no speech at all within 8s, stop and retry
                const silenceOnlyTimeout = setTimeout(() => {
                    if (!speaking && isListeningRef.current) {

                        stopListening();
                    }
                }, 8000);

                const checkSpeech = () => {
                    if (!isListeningRef.current) { clearTimeout(silenceOnlyTimeout); return; }
                    an.getByteFrequencyData(dataArray);
                    const avg = dataArray.reduce((acc, val) => acc + val, 0) / dataArray.length;

                    if (avg > 15) { // threshold for human speech
                        lastSpeak = Date.now();
                        if (!speaking) { speaking = true; clearTimeout(silenceOnlyTimeout); }
                    } else if (speaking && Date.now() - lastSpeak > 2000) {

                        speaking = false;
                        stopListening();
                        return;
                    }
                    vadRafRef.current = requestAnimationFrame(checkSpeech);
                };
                vadRafRef.current = requestAnimationFrame(checkSpeech);
            } catch (e) {
                console.error("VAD error", e);
            }
        } catch (e: unknown) { setSttStatus('Mic error'); console.error(e); }
    }, []);

    const stopListening = () => {
        if (maxListenTimerRef.current) { clearTimeout(maxListenTimerRef.current); maxListenTimerRef.current = null; }
        if (vadRafRef.current) cancelAnimationFrame(vadRafRef.current);
        vadRafRef.current = null;
        if (audioCtxRef.current) {
            audioCtxRef.current.close().catch(() => { });
            audioCtxRef.current = null;
        }

        if (whisperRecorder.current?.state !== 'inactive') {
            try { whisperRecorder.current?.stop(); } catch { }
        }
        isListeningRef.current = false;
        setIsListening(false);
        setSttStatus('');
    };

    // ── TTS ───────────────────────────────────────────────────────────────────
    // speak is defined AFTER startListening so the dep array is valid (no TDZ error)
    const speak = useCallback(async (text: string) => {

        const synth = window.speechSynthesis;
        ttsSeq.current += 1;
        const seq = ttsSeq.current;
        synth?.cancel();
        stopBackendTtsAudio();
        const clean = text.trim();
        if (!clean || clean.length < 2) {

            if (pendingAutoListen.current && voiceOnRef.current) {
                pendingAutoListen.current = false;
                startListening();
            }
            return;
        }

        const onSpeakingStart = () => {
            if (seq !== ttsSeq.current) return;
            isTtsSpeaking.current = true;
            setSttStatus('AI speaking...');
            const tile = document.getElementById('tile-ai');
            if (tile) tile.style.borderColor = '#22c55e';
        };

        const onSpeakingDone = () => {
            if (seq !== ttsSeq.current) return;
            isTtsSpeaking.current = false;
            ttsCompletedRef.current = true; // Mark TTS as completed
            setSttStatus('');
            const tile = document.getElementById('tile-ai');
            if (tile) tile.style.borderColor = '#334155';
            
            // Check if this was the INTERVIEW_COMPLETE message - end interview after TTS finishes
            if (interviewCompleteSentRef.current && !doneRef.current) {
                console.log('[TTS] INTERVIEW_COMPLETE message finished speaking, ending interview...');
                // Small delay to ensure smooth transition
                setTimeout(() => {
                    if (!doneRef.current) {
                        endInterview();
                    }
                }, 500);
                return;
            }
            
            if (pendingAutoListen.current && voiceOnRef.current) {
                pendingAutoListen.current = false;
                startListening();
            }
        };

        const speakWithWebSpeech = () => {
            if (!synth) {
                onSpeakingDone();
                return;
            }

            const doSpeak = (voice: SpeechSynthesisVoice | null) => {
                if (seq !== ttsSeq.current) return;
                const utt = new SpeechSynthesisUtterance(clean);
                utt.lang = 'en-IN'; utt.rate = 0.92; utt.pitch = 1.05;
                if (voice) utt.voice = voice;
                utt.onstart = () => {

                    onSpeakingStart();
                };
                const done = () => {

                    onSpeakingDone();
                };
                utt.onend = done; utt.onerror = done;
                (window as any)._currUtt = utt; // Anti-GC hack for Chrome

                synth.speak(utt);
            };

            const voices = synth.getVoices();
            if (!voices.length) {
                let fired = false;
                const handler = () => {
                    if (fired) return;
                    fired = true;

                    const v = synth.getVoices();
                    doSpeak(v.find(x => x.lang === 'en-IN') || v.find(x => x.lang.startsWith('en')) || null);
                };
                synth.addEventListener('voiceschanged', handler, { once: true });

                // Failsafe for Safari/Chrome bug where voiceschanged never fires
                setTimeout(() => {
                    if (!fired) {
                        console.warn("voiceschanged timeout! Forcing doSpeak...");
                        fired = true;
                        synth.removeEventListener('voiceschanged', handler);
                        doSpeak(null);
                    }
                }, 600);
            } else {

                doSpeak(voices.find(x => x.lang === 'en-IN') || voices.find(x => x.lang.startsWith('en')) || null);
            }
        };

        try {
            const res = await fetch(`${API_BASE}/tts/synthesize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ text: clean }),
            });
            if (seq !== ttsSeq.current) return;

            const contentType = (res.headers.get('content-type') || '').toLowerCase();
            if (res.ok && contentType.startsWith('audio/')) {
                const audioBlob = await res.blob();
                if (seq !== ttsSeq.current || !audioBlob.size) {
                    speakWithWebSpeech();
                    return;
                }

                const objectUrl = URL.createObjectURL(audioBlob);
                ttsAudioUrlRef.current = objectUrl;
                const audio = new Audio(objectUrl);
                ttsAudioRef.current = audio;
                attachTtsAudioToRecordingMix(audio);

                audio.onplay = () => onSpeakingStart();
                const done = () => {
                    stopBackendTtsAudio();
                    onSpeakingDone();
                };
                audio.onended = done;
                audio.onerror = done;
                try {
                    await audio.play();
                    return;
                } catch (err) {
                    console.warn("Backend TTS audio play failed. Falling back to webspeech.", err);
                    stopBackendTtsAudio();
                    speakWithWebSpeech();
                    return;
                }
            }
        } catch (err) {
            console.warn("Backend TTS request failed. Falling back to webspeech.", err);
        }

        speakWithWebSpeech();
    }, [startListening, stopBackendTtsAudio, attachTtsAudioToRecordingMix]);

    // Keep speakRef current so addMsg (empty-dep useCallback) always calls the latest speak
    useEffect(() => { speakRef.current = (text: string) => { void speak(text); }; }, [speak]);

    // ── Send message ──────────────────────────────────────────────────────────
    const sendMessage = useCallback(async (text: string) => {
        if (!text.trim() || doneRef.current || sending) return;
        if (isListeningRef.current) stopListening();
        pendingAutoListen.current = false;
        awaitingAiReplyRef.current = true;
        setSending(true);
        try {
            // Backend /chat now returns List[MessageOut] — always an array
            const msgs = await apiCall<Message[]>('POST', `/interview-session/chat/${token}`, {
                content: text.trim(),
                code_snippet: codeOpen && codeInput.trim() ? codeInput.trim() : undefined,
            });
            setTextInput(''); setCodeInput('');
            manualSendRequiredRef.current = false;
            const hasAiReply = msgs.some(m => m.role === 'ai');
            if (!hasAiReply) awaitingAiReplyRef.current = false;
            msgs.forEach(addMsg);
            pendingAutoListen.current = true;
        } catch (e) {
            awaitingAiReplyRef.current = false;
            console.error(e);
        }
        finally { setSending(false); }
    }, [token, codeOpen, codeInput, codeLang, addMsg, sending]);

    // Keep ref pointing to the latest sendMessage so startListening (empty-dep) never closes over a stale version
    useEffect(() => { sendMessageRef.current = sendMessage; }, [sendMessage]);
    // Keep coding-timer refs in sync with state
    useEffect(() => { codeInputRef.current = codeInput; }, [codeInput]);
    useEffect(() => { codeOpenRef.current = codeOpen; }, [codeOpen]);

    // ── End interview ─────────────────────────────────────────────────────────
    const endInterview = useCallback(async () => {
        if (doneRef.current) return;
        doneRef.current = true;
        stopListening();
        window.speechSynthesis?.cancel();
        stopBackendTtsAudio();
        if (timerRef.current) clearInterval(timerRef.current);
        if (visionRef.current) clearInterval(visionRef.current);

        try {
            if (recorder.current) {
                recorder.current.stop();
                await new Promise(r => { recorder.current!.onstop = r as () => void; setTimeout(r, 2500); });
                const blob = new Blob(recChunks.current, { type: recordingMime.current || 'video/webm' });
                const fd = new FormData(); fd.append('file', blob, 'recording.webm');
                await fetch(`${API_BASE}/recordings/upload/${token}`, {
                    method: 'POST', body: fd, credentials: 'include',
                });
            }
            const result = await apiCall<{
                answer_score?: number; code_score?: number;
                emotion_score?: number; integrity_score?: number; ai_feedback?: string;
            }>('POST', `/interview-session/end/${token}`);

            setCompletedData({
                title: 'Interview Complete!',
                sub: result?.ai_feedback ? 'Results have been calculated.' : 'Processing results...',
                scores: result ? [
                    { label: 'Q&A Score', val: result.answer_score ?? 0, color: '#4F46E5' },
                    { label: 'Code Score', val: result.code_score ?? 0, color: '#10B981' },
                    { label: 'Confidence', val: result.emotion_score ?? 0, color: '#F59E0B' },
                    { label: 'Integrity', val: result.integrity_score ?? 0, color: '#EF4444' },
                ] : [],
            });
        } catch {
            setCompletedData({ title: 'Interview Complete!', sub: 'Processing results...', scores: [] });
        } finally {
            recorder.current = null;
            recordingStreamRef.current = null;
            setIsRecording(false);
            stopScreenShare();
            resetRecordingAudioGraph();
        }
        setCompleted(true);
    }, [token, stopBackendTtsAudio, stopScreenShare, resetRecordingAudioGraph]);

    const stopLocalCamera = useCallback(() => {
        const stream = camStream.current;
        if (!stream) return;
        const videoTracks = stream.getVideoTracks();
        videoTracks.forEach(track => {
            track.stop();
            stream.removeTrack(track);
        });
    }, []);

    const startLocalCamera = useCallback(async () => {
        const videoOnly = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
        const videoTrack = videoOnly.getVideoTracks()[0];
        if (!videoTrack) return;

        if (!camStream.current) {
            camStream.current = new MediaStream();
        }
        camStream.current.addTrack(videoTrack);
        setLocalStream(new MediaStream(camStream.current.getTracks()));

        if (previewVideoRef.current) {
            previewVideoRef.current.srcObject = camStream.current;
            previewVideoRef.current.play().catch(() => { });
        }
        if (localVideoRef.current) {
            localVideoRef.current.srcObject = camStream.current;
            localVideoRef.current.play().catch(() => { });
        }
    }, []);

    // ── Begin interview ───────────────────────────────────────────────────────
    const beginInterview = async () => {
        setStartLoading(true);
        setStartError('');
        window.speechSynthesis?.getVoices();
        try {
            // Screen share must be requested from this user gesture handler.
            try {
                const shared = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
                screenStream.current = shared;

                const videoTrack = shared.getVideoTracks()[0];
                if (videoTrack) {
                    videoTrack.onended = () => {
                        stopScreenShare();
                    };
                }
            } catch (err) {
                console.warn("Screen share permission denied/cancelled", err);
                setStartError('Screen sharing is required to start the interview.');
                // F3: Release mic when screen share is denied
                camStream.current?.getAudioTracks().forEach(t => t.stop());
                return;
            }

            // Start recording from a mixed stream:
            // screen video + mic audio + shared-screen audio + remote participant audio.
            const shared = screenStream.current;
            if (!shared) {
                setStartError('Could not access shared screen stream.');
                return;
            }
            const screenVideoTrack = shared.getVideoTracks()[0];
            if (!screenVideoTrack) {
                setStartError('No screen video track found for recording.');
                stopScreenShare();
                return;
            }
            const captureStream = new MediaStream([screenVideoTrack]);
            attachStreamToRecordingMix('mic', camStream.current);
            attachStreamToRecordingMix('screen', shared);
            syncRemoteStreamsToRecordingMix(remoteStreams);
            recordingAudioDestRef.current?.stream.getAudioTracks().forEach(track => captureStream.addTrack(track));
            recordingStreamRef.current = captureStream;
            const mime = [
                'video/webm;codecs=vp9,opus',
                'video/webm;codecs=vp8,opus',
                'video/webm',
                'video/mp4',
            ].find(m => MediaRecorder.isTypeSupported(m)) || '';
            recordingMime.current = mime || 'video/webm';
            console.info("Interview recording mime type:", recordingMime.current);

            try {
                recorder.current = new MediaRecorder(captureStream, mime ? { mimeType: mime } : undefined);
                recChunks.current = [];
                recorder.current.ondataavailable = e => { if (e.data.size) recChunks.current.push(e.data); };
                recorder.current.start(3000);
                setIsRecording(true);
            } catch (err) {
                console.error("Failed to initialize interview recorder", err);
                setStartError('Recording could not be started on this browser.');
                stopScreenShare();
                return;
            }

            const res = await apiCall<{ messages?: Message[]; ai_paused?: boolean }>(
                'POST', `/interview-session/start/${token}`
            );
            setStarted(true);
            setIsLive(true);

            // Start timer
            const limit = (session?.duration_minutes ?? 60) * 60;
            timerRef.current = setInterval(() => {
                setElapsed(prev => {
                    const next = prev + 1;
                    setIsCritical(limit - next < 300);
                    if (next >= limit + 60) endInterview();
                    return next;
                });
            }, 1000);

            // Vision (F1: guard against overlapping requests)
            const visionPending = { current: false };
            visionRef.current = setInterval(async () => {
                if (visionPending.current) return;
                const vid = localVideoRef.current;
                if (!vid?.videoWidth) return;
                visionPending.current = true;
                const cv = document.createElement('canvas'); cv.width = 160; cv.height = 120;
                cv.getContext('2d')!.drawImage(vid, 0, 0, 160, 120);
                const b64 = cv.toDataURL('image/jpeg', 0.6).split(',')[1];
                try {
                    frameSeqRef.current += 1;
                    const r = await apiCall<{
                        face_count?: number; dominant_emotion?: string; gaze_ok?: boolean;
                    }>('POST', '/vision/analyze', {
                        frame: b64,
                        interview_id: session?.id,
                        interview_token: token,
                        tab_switch_count: tabSwRef.current,
                        frame_seq: frameSeqRef.current,
                    });
                    const fc = r.face_count ?? 0;
                    setFaceCount(fc || 1);
                    if (fc === 0) {
                        setLookAway(a => a + 1); setGaze('Away');
                    } else setGaze('OK');
                    if (fc > 1) setMultiFace(m => m + 1);
                    if (r.dominant_emotion) setEmotion(r.dominant_emotion);
                } catch { }
                finally { visionPending.current = false; }
            }, VISION_INTERVAL_MS);

            if (res?.messages) res.messages.forEach(addMsg);
            if (res?.ai_paused) setAiPaused(true);
            // Delay fallback-listen by 4s to ensure TTS has had time to start.
            // TTS itself (via pendingAutoListen + speak.done) will call startListening when it finishes.
            // This fallback only fires if TTS never started (e.g. voice synthesis unavailable).
            setTimeout(() => {
                if (voiceOnRef.current && !isTtsSpeaking.current && !isListeningRef.current) {
                    startListening();
                }
            }, 4000);
        } catch (e: unknown) {
            const msg = (e as Error).message || 'Could not start interview';
            // If already completed, show a friendly message
            if (msg.toLowerCase().includes('completed')) {
                setStartError('This interview has already been completed. You cannot re-enter.');
            } else {
                setStartError(msg);
            }
            stopScreenShare();
            resetRecordingAudioGraph();
        } finally { setStartLoading(false); }
    };

    // ── Boot ──────────────────────────────────────────────────────────────────
    const loadSession = useCallback(async () => {
        try {
            const data = await apiCall<InterviewSession>('GET', `/interview-session/join/${token}`);
            setSession(data);
            setNeedsVerify(false);

            // If already completed — jump straight to the results overlay
            if ((data.status as string).toLowerCase() === 'completed') {
                setCompleted(true);
                setStarted(true);
                setCompletedData({
                    title: 'Interview Complete!',
                    sub: data.ai_feedback ? 'Your results are below.' : 'Results have been processed.',
                    scores: [
                        { label: 'Q&A Score', val: data.answer_score ?? 0, color: '#4F46E5' },
                        { label: 'Code Score', val: data.code_score ?? 0, color: '#10B981' },
                        { label: 'Confidence', val: data.emotion_score ?? 0, color: '#F59E0B' },
                        { label: 'Integrity', val: data.integrity_score ?? 0, color: '#EF4444' },
                    ],
                });
                // Check if candidate still needs to register (magic_link user without a password)
                try {
                    const me = await apiCall<{ auth_provider?: string }>('GET', '/users/me');
                    if (me.auth_provider === 'magic_link') {
                        setVerifiedViaMagicLink(true);
                    }
                } catch { /* not authenticated or non-candidate — skip */ }
                return;
            }

            // Camera setup
            navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: true })
                .then(async (s) => {
                    camStream.current = s;
                    setLocalStream(s);
                    if (previewVideoRef.current) previewVideoRef.current.srcObject = s;
                    // Fetch JWT for WebSocket auth (cookies don't work cross-origin for WS)
                    try {
                        const wt = await apiCall<{ token: string }>('GET', '/auth/ws-token');
                        if (wt?.token) setJwtToken(wt.token);
                    } catch { /* WebRTC will be unavailable */ }
                })
                .catch(() => { });
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            // 401 = not authenticated → show verification form (magic-link flow)
            if (msg.includes('Not authenticated') || msg.includes('401')) {
                setNeedsVerify(true);
            } else {
                setLoadError(msg);
            }
        }
    }, [token]);

    useEffect(() => {
        loadSession();

        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
            if (visionRef.current) clearInterval(visionRef.current);
            // Cleanup coding timer
            if (codingTimerRef.current) clearTimeout(codingTimerRef.current);
            if (codingWarningRef.current) clearTimeout(codingWarningRef.current);
            window.speechSynthesis?.cancel();
            stopBackendTtsAudio();
            camStream.current?.getTracks().forEach(t => t.stop());
            stopScreenShare();
            resetRecordingAudioGraph();
        };
    }, [loadSession, stopBackendTtsAudio, stopScreenShare, resetRecordingAudioGraph]);

    // ── Candidate verification handler ────────────────────────────────────────
    const handleVerify = async (e: React.FormEvent) => {
        e.preventDefault();
        setVerifyError('');
        setVerifyLoading(true);
        try {
            const res = await fetch(`${API_BASE}/interview-session/verify-candidate/${token}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email: verifyEmail, name: verifyName }),
            });
            const data = await res.json();

            if (!res.ok) {
                setVerifyError(data.detail || 'Verification failed');
                return;
            }

            if (data.status === 'early') {
                setVerifyStatus('early');
                setVerifyScheduledAt(data.scheduled_at || '');
                setVerifyError(data.message);
                return;
            }
            if (data.status === 'expired') {
                setVerifyStatus('expired');
                setVerifyError(data.message);
                return;
            }

            // status === 'ok' — JWT cookie has been set, reload session
            setVerifyStatus('ok');
            setVerifiedViaMagicLink(true);
            await loadSession();
        } catch {
            setVerifyError('Network error. Please try again.');
        } finally {
            setVerifyLoading(false);
        }
    };

    // ── Focus/visibility tracking: tab switches + window/app switches ─────────
    useEffect(() => {
        if (!started || completed) return;

        const onVisibilityChange = () => {
            if (document.hidden) incrementTabSwitch();
        };
        const onWindowBlur = () => {
            incrementTabSwitch();
        };

        document.addEventListener('visibilitychange', onVisibilityChange);
        window.addEventListener('blur', onWindowBlur);

        return () => {
            document.removeEventListener('visibilitychange', onVisibilityChange);
            window.removeEventListener('blur', onWindowBlur);
        };
    }, [started, completed, incrementTabSwitch]);

    // ── Re-attach camera stream when the interview room mounts ────────────────
    // When started=true, VideoStage renders a new <video> element in the DOM.
    // The boot useEffect ran before this element existed, so the stream was
    // only attached to the preview. We re-attach it here after the room renders.
    useEffect(() => {
        if (!started) return;
        // Use a small rAF delay to ensure the video element has mounted
        const raf = requestAnimationFrame(() => {
            if (localVideoRef.current && camStream.current) {
                localVideoRef.current.srcObject = camStream.current;
                localVideoRef.current.play().catch(() => { });
            }
        });
        return () => cancelAnimationFrame(raf);
    }, [started]);

    useEffect(() => {
        if (!isRecording) return;
        syncRemoteStreamsToRecordingMix(remoteStreams);
    }, [remoteStreams, isRecording, syncRemoteStreamsToRecordingMix]);

    // ── WebRTC: broadcast candidate camera to HR watchers ─────────────────────
    // Activates after interview starts and camera permission is granted.
    useWebRTC({
        token,
        jwtToken: started ? jwtToken : '',
        localStream,
        onRemoteStream: (p) => {
            setRemoteStreams(prev => {
                const others = prev.filter(s => s.participantId !== p.participantId);
                return [...others, p];
            });
        },
        onRemoteLeft: (pid) => setRemoteStreams(prev => prev.filter(s => s.participantId !== pid)),
    });

    const toggleMute = () => {
        setMuted(m => { camStream.current?.getAudioTracks().forEach(t => t.enabled = m); return !m; });
    };

    const toggleCam = async () => {
        if (camOff) {
            try {
                await startLocalCamera();
                setCamOff(false);
            } catch {
                setStartError('Could not re-enable camera');
            }
            return;
        }
        stopLocalCamera();
        setCamOff(true);
        setLocalStream(camStream.current ? new MediaStream(camStream.current.getTracks()) : null);
    };

    const toggleVoice = () => {
        const next = !voiceOn; setVoiceOn(next); voiceOnRef.current = next;
        if (!next) {
            if (isListeningRef.current) stopListening();
            window.speechSynthesis?.cancel();
            stopBackendTtsAudio();
            isTtsSpeaking.current = false;
        }
    };

    const toggleListen = () => {
        if (isListening) {
            stopListening();
        } else {
            isTtsSpeaking.current = false;
            window.speechSynthesis?.cancel();
            stopBackendTtsAudio();
            startListening();
        }
    };

    // ── Verification form (magic-link candidates) ────────────────────────────
    if (needsVerify) {
        return (
            <div className="start-ov">
                <div className="start-card" style={{ textAlign: 'center', maxWidth: 420 }}>
                    <div style={{ fontSize: 48, marginBottom: 10 }}>🎤</div>
                    <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Verify Your Identity</div>
                    <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 20 }}>
                        Enter the email and name from your interview invitation.
                    </div>

                    {verifyStatus === 'early' && verifyScheduledAt && (
                        <div style={{ background: '#EFF6FF', border: '1px solid #3B82F6', borderRadius: 8, padding: 14, marginBottom: 16, color: '#1E40AF', fontSize: 13 }}>
                            ⏰ Your interview is scheduled for <strong>{new Date(verifyScheduledAt).toLocaleString()}</strong>.
                            Please come back closer to the scheduled time.
                        </div>
                    )}
                    {verifyStatus === 'expired' && (
                        <div style={{ background: '#FEF2F2', border: '1px solid #EF4444', borderRadius: 8, padding: 14, marginBottom: 16, color: '#991B1B', fontSize: 13 }}>
                            ❌ The interview window has closed. Please contact the recruiter.
                        </div>
                    )}

                    <form onSubmit={handleVerify} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        <input
                            type="email"
                            placeholder="Your email address"
                            value={verifyEmail}
                            onChange={e => setVerifyEmail(e.target.value)}
                            required
                            style={{ padding: '10px 14px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 14, background: 'var(--bg-card)' }}
                        />
                        <input
                            type="text"
                            placeholder="Your full name"
                            value={verifyName}
                            onChange={e => setVerifyName(e.target.value)}
                            required
                            style={{ padding: '10px 14px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 14, background: 'var(--bg-card)' }}
                        />
                        {verifyError && verifyStatus === 'idle' && (
                            <div style={{ color: 'var(--danger)', fontSize: 13 }}>{verifyError}</div>
                        )}
                        <button
                            type="submit"
                            disabled={verifyLoading || verifyStatus === 'expired'}
                            style={{ padding: '10px 20px', borderRadius: 8, background: 'var(--primary)', color: '#fff', fontWeight: 700, border: 'none', fontSize: 14, cursor: 'pointer', opacity: verifyLoading ? 0.7 : 1 }}
                        >
                            {verifyLoading ? 'Verifying...' : 'Join Interview'}
                        </button>
                    </form>
                </div>
            </div>
        );
    }

    // ── Loading / Error ───────────────────────────────────────────────────────
    if (!session && !loadError) {
        return (
            <div className="start-ov">
                <div className="start-card" style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 48, marginBottom: 10 }}>🎯</div>
                    <div style={{ fontSize: 17, fontWeight: 700 }}>Loading Interview...</div>
                </div>
            </div>
        );
    }

    if (loadError) {
        return (
            <div className="start-ov">
                <div className="start-card" style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 48, marginBottom: 10 }}>❌</div>
                    <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--danger)' }}>{loadError}</div>
                    <a href="/" style={{ color: 'var(--primary)', fontSize: 13, marginTop: 12, display: 'block' }}>Return to Dashboard</a>
                </div>
            </div>
        );
    }

    return (
        <>
            {/* Pre-start overlay */}
            {!started && (
                <StartOverlay
                    title={session!.title}
                    jobRole={session!.job_role}
                    durationMin={session!.duration_minutes}
                    previewRef={previewVideoRef}
                    loading={startLoading}
                    error={startError}
                    onStart={beginInterview}
                />
            )}

            {/* Post-completion overlay */}
            <CompleteOverlay
                visible={completed}
                title={completedData?.title}
                subtitle={completedData?.sub}
                scores={completedData?.scores}
                showRegister={verifiedViaMagicLink}
            />

            {/* Interview Room */}
            {started && (
                <div className="room" id="mainRoom">
                    {/* ── TOPBAR: spans all 3 columns (grid-column: 1/-1) ── */}
                    <header className="topbar">
                        <div className="tb-left">
                            <div className={`status-dot${isLive ? ' live' : ''}`} />
                            <div className="tb-title">{session!.title}</div>
                            <span className="tb-role">{session!.job_role}</span>
                        </div>
                        <div className={`timer${isCritical ? ' critical' : ''}`}>
                            {String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}
                        </div>
                        <div className="tb-right">
                            {isRecording && (
                                <span className="badge rec-badge">
                                    <i className="fas fa-circle" /> REC
                                </span>
                            )}
                            <button className="btn btn-outline btn-sm" onClick={toggleMute} title={muted ? 'Unmute' : 'Mute'}>
                                <i className={`fas fa-microphone${muted ? '-slash' : ''}`} />
                            </button>
                            <button className="btn btn-outline btn-sm" onClick={toggleCam} title={camOff ? 'Enable Camera' : 'Disable Camera'}>
                                <i className={`fas fa-video${camOff ? '-slash' : ''}`} />
                            </button>
                            <button className="btn btn-danger btn-sm" onClick={endInterview}>
                                <i className="fas fa-phone-slash" /> End
                            </button>
                        </div>
                    </header>

                    {/* ── ROW 2: video + chat ── */}

                    {/* LEFT: Video stage */}
                    <VideoStage
                        localVideoRef={localVideoRef}
                        camOff={camOff}
                        remoteStreams={remoteStreams}
                    />

                    {/* RIGHT: Chat panel */}
                    <ChatPanel
                        messages={messages}
                        aiPaused={aiPaused}
                        voiceOn={voiceOn}
                        isRecording={isListening}
                        sttStatus={sttStatus}
                        sending={sending}
                        codeOpen={codeOpen}
                        codeInput={codeInput}
                        codeLang={codeLang}
                        textInput={textInput}
                        onToggleVoice={toggleVoice}
                        onToggleCode={() => setCodeOpen(o => !o)}
                        onToggleListen={toggleListen}
                        onCodeChange={setCodeInput}
                        onCodeLangChange={setCodeLang}
                        onCodeClear={() => setCodeInput('')}
                        onTextChange={setTextInput}
                        onSend={() => sendMessage(textInput)}
                    />
                </div>
            )}
        </>
    );
}
