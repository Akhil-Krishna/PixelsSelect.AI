'use client';

import { useRef } from 'react';
import { Message } from '../../lib/types';

interface ChatViewProps {
    messages: Message[];
    totalMsgs: number;
    isLive: boolean;
    aiPaused: boolean;
    askInput: string;
    onAskChange: (v: string) => void;
    onAskSend: () => void;
    onPauseAI: () => void;
    onResumeAI: () => void;
}

const ROLE_LABELS: Record<string, string> = {
    ai: 'AI',
    candidate: 'Candidate',
    interviewer: 'Interviewer (You)',
};

export function ChatView({
    messages, totalMsgs, isLive, aiPaused,
    askInput, onAskChange, onAskSend, onPauseAI, onResumeAI,
}: ChatViewProps) {
    const chatRef = useRef<HTMLDivElement>(null);

    return (
        <div className="right-col">
            {/* Header */}
            <div className="chat-hdr">
                <i className="fas fa-comments" style={{ color: 'var(--primary)' }} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>Live Conversation</span>
                <span className="badge" style={{ background: '#1E293B', marginLeft: 'auto' }}>
                    {totalMsgs} msgs
                </span>
                {isLive && (
                    <div className="dot dot-live" style={{ marginLeft: 8 }} />
                )}
            </div>

            {/* Messages */}
            <div className="chat-msgs" ref={chatRef}>
                {messages.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>
                        <i className="fas fa-clock" style={{ fontSize: 32, display: 'block', marginBottom: 12, opacity: 0.3 }} />
                        Waiting for interview to start...
                    </div>
                ) : (
                    messages.map(m => {
                        const isCQ = m.role === 'ai' && m.content.startsWith('CODING_QUESTION:');
                        const content = isCQ ? m.content.replace('CODING_QUESTION:', '').trim() : m.content;
                        const ts = m.timestamp
                            ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                            : '';

                        return (
                            <div key={m.id} className={`msg ${m.role} msg-new`}>
                                <span className="msg-lbl">
                                    {ROLE_LABELS[m.role] || m.role}{' '}
                                    <span style={{ fontWeight: 400, opacity: 0.6 }}>{ts}</span>
                                </span>
                                <div className="msg-bbl">{content}</div>
                                {m.code_snippet && <pre className="msg-code">{m.code_snippet}</pre>}
                                {isCQ && (
                                    <div style={{ fontSize: 10, color: 'var(--warning)', marginTop: 3 }}>
                                        <i className="fas fa-code" /> Coding question
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>

            {/* Controls */}
            <div className="ask-bar">
                <div className="ctrl-row">
                    {!aiPaused ? (
                        <button className="ctrl-btn ctrl-pause" onClick={onPauseAI}>
                            <i className="fas fa-pause" /> Pause AI
                        </button>
                    ) : (
                        <button className="ctrl-btn ctrl-resume" onClick={onResumeAI}>
                            <i className="fas fa-play" /> Resume AI
                        </button>
                    )}
                </div>
                <div className="ask-row">
                    <input
                        type="text"
                        className="ask-input"
                        value={askInput}
                        onChange={e => onAskChange(e.target.value)}
                        placeholder="Ask a question to the candidate..."
                        onKeyDown={e => e.key === 'Enter' && onAskSend()}
                    />
                    <button className="ask-btn" onClick={onAskSend}>
                        <i className="fas fa-paper-plane" /> Ask
                    </button>
                </div>
            </div>
        </div>
    );
}
