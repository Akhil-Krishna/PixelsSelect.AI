'use client';

import { useRef, useEffect } from 'react';
import { Message } from '../../lib/types';

interface ChatPanelProps {
    messages: Message[];
    aiPaused: boolean;
    voiceOn: boolean;
    isRecording: boolean;
    sttStatus: string;
    sending: boolean;
    codeOpen: boolean;
    codeInput: string;
    codeLang: string;
    textInput: string;
    onToggleVoice: () => void;
    onToggleCode: () => void;
    onToggleListen: () => void;
    onCodeChange: (v: string) => void;
    onCodeLangChange: (v: string) => void;
    onCodeClear: () => void;
    onTextChange: (v: string) => void;
    onSend: () => void;
}

const CODE_LANGS = ['python', 'javascript', 'typescript', 'java', 'cpp', 'go', 'sql', 'rust'];

const ROLE_LABELS: Record<string, string> = {
    ai: 'AI',
    candidate: 'You',
    interviewer: 'Interviewer',
};

const isCodingPromptText = (text: string) =>
    (text || '').trimStart().startsWith('[CODING_QUESTION]');

export function ChatPanel({
    messages, aiPaused, voiceOn, isRecording, sttStatus, sending,
    codeOpen, codeInput, codeLang, textInput,
    onToggleVoice, onToggleCode, onToggleListen,
    onCodeChange, onCodeLangChange, onCodeClear,
    onTextChange, onSend,
}: ChatPanelProps) {
    const chatRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
    };

    // Auto-scroll whenever new messages arrive
    useEffect(() => { scrollToBottom(); }, [messages]);

    return (
        <div className="chat-panel">
            {/* Header */}
            <div className="chat-header">
                <i className="fas fa-robot" style={{ color: 'var(--primary)' }} />
                <div className="chat-title">AI Interviewer</div>
            </div>

            {/* Messages */}
            <div className="chat-messages" ref={chatRef}>
                {messages.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--muted)', fontSize: 13 }}>
                        <i className="fas fa-robot" style={{ fontSize: 32, display: 'block', marginBottom: 12, opacity: 0.3 }} />
                        Your interview will begin shortly...
                    </div>
                )}

                {messages.map((m, index) => {
                    const isCQ = m.role === 'ai' && isCodingPromptText(m.content);
                    const content = isCQ ? m.content.replace('[CODING_QUESTION]', '').trim() : m.content;

                    return (
                        <div key={m.id ?? String(index)} className={`msg ${m.role}`}>
                            <span className="msg-label">{ROLE_LABELS[m.role] || m.role}</span>
                            <div className="msg-bubble">{content}</div>
                            {m.code_snippet && <pre className="msg-code">{m.code_snippet}</pre>}
                            {isCQ && (
                                <div className="coding-hint">
                                    <i className="fas fa-code" /> Coding question — use the code editor below
                                </div>
                            )}
                        </div>
                    );
                })}

                {aiPaused && (
                    <div className="paused-banner">
                        <i className="fas fa-pause-circle" /> Interviewer has taken over
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="input-area">
                {/* Toolbar */}
                <div className="input-tools">
                    <button className={`tool-btn${codeOpen ? ' act' : ''}`} onClick={onToggleCode}>
                        <i className="fas fa-code" /> Code Editor
                    </button>
                    <button className={`tool-btn${voiceOn ? ' act' : ''}`} onClick={onToggleVoice}>
                        <i className="fas fa-microphone-lines" /> Voice
                    </button>
                    {sttStatus && (
                        <span style={{ fontSize: 10.5, color: 'var(--muted)', marginLeft: 4 }}>{sttStatus}</span>
                    )}
                </div>

                {/* Code Editor */}
                {codeOpen && (
                    <div className="code-editor-wrap show">
                        <div className="code-editor-top">
                            <span><i className="fas fa-code" /> Code</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <select className="code-lang" value={codeLang} onChange={e => onCodeLangChange(e.target.value)}>
                                    {CODE_LANGS.map(l => <option key={l}>{l}</option>)}
                                </select>
                                <button className="tool-btn" onClick={onCodeClear} style={{ fontSize: 10, padding: '2px 6px' }}>
                                    <i className="fas fa-trash" />
                                </button>
                            </div>
                        </div>
                        <textarea
                            className="code-input"
                            value={codeInput}
                            onChange={e => onCodeChange(e.target.value)}
                            placeholder="// Write your solution here..."
                            onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) onSend(); }}
                        />
                    </div>
                )}

                {/* Text input row */}
                <div className="text-row">
                    <textarea
                        className="text-input"
                        value={textInput}
                        onChange={e => onTextChange(e.target.value)}
                        placeholder="Type your answer or speak..."
                        rows={1}
                        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}
                    />
                    <button
                        className={`mic-btn${isRecording ? ' on' : ''}`}
                        onClick={onToggleListen}
                        title="Voice input"
                    >
                        <i className="fas fa-microphone" />
                    </button>
                    <button
                        className="send-btn"
                        onClick={onSend}
                        disabled={sending || !textInput.trim()}
                    >
                        <i className="fas fa-paper-plane" />
                    </button>
                </div>
            </div>
        </div>
    );
}
