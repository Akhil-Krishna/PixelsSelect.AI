'use client';

import { useState } from 'react';
import { API_BASE } from '../../lib/api';

interface ScoreBox {
    label: string;
    val: number;
    color: string;
}

interface CompleteOverlayProps {
    visible: boolean;
    title?: string;
    subtitle?: string;
    scores?: ScoreBox[];
    /** If true, show optional "Create Account" prompt (magic-link candidates) */
    showRegister?: boolean;
}

export function CompleteOverlay({ visible, title, subtitle, scores, showRegister }: CompleteOverlayProps) {
    const [password, setPassword] = useState('');
    const [confirm, setConfirm] = useState('');
    const [regError, setRegError] = useState('');
    const [regDone, setRegDone] = useState(false);
    const [regLoading, setRegLoading] = useState(false);

    if (!visible) return null;

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setRegError('');
        if (password.length < 6) { setRegError('Password must be at least 6 characters.'); return; }
        if (password !== confirm) { setRegError('Passwords do not match.'); return; }
        setRegLoading(true);
        try {
            const res = await fetch(`${API_BASE}/auth/candidate-register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ password }),
            });
            const data = await res.json();
            if (!res.ok) { setRegError(data.detail || 'Registration failed.'); return; }
            setRegDone(true);
        } catch {
            setRegError('Network error. Please try again.');
        } finally {
            setRegLoading(false);
        }
    };

    return (
        <div className="complete-ov show">
            <div className="complete-card">
                <div style={{ fontSize: 60, marginBottom: 16 }}>🏆</div>
                <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 8 }}>
                    {title || 'Interview Complete!'}
                </div>
                <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 24, lineHeight: 1.6 }}>
                    {subtitle || 'Uploading recording and calculating scores...'}
                </div>

                {scores && scores.length > 0 && (
                    <div className="score-grid" style={{ marginBottom: 24 }}>
                        {scores.map(s => (
                            <div key={s.label} className="score-box" style={{ borderTopColor: s.color }}>
                                <div className="score-val" style={{ color: s.color }}>{s.val.toFixed(1)}%</div>
                                <div className="score-lbl">{s.label}</div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Optional account creation for magic-link candidates */}
                {showRegister && !regDone && (
                    <div style={{
                        background: '#f9fafb', border: '1px solid #d1d5db',
                        borderRadius: 10, padding: 18, marginBottom: 20, textAlign: 'left',
                    }}>
                        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4, color: '#1f2937' }}>
                            📋 Create Your Account <span style={{ fontSize: 11, fontWeight: 400, color: '#6b7280' }}>(optional)</span>
                        </div>
                        <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12, lineHeight: 1.5 }}>
                            Set a password to log in later and track your interview history.
                        </div>
                        <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            <input
                                type="password"
                                placeholder="Choose a password"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                required
                                minLength={6}
                                style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, background: '#fff', color: '#1f2937' }}
                            />
                            <input
                                type="password"
                                placeholder="Confirm password"
                                value={confirm}
                                onChange={e => setConfirm(e.target.value)}
                                required
                                minLength={6}
                                style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, background: '#fff', color: '#1f2937' }}
                            />
                            {regError && <div style={{ color: '#EF4444', fontSize: 12 }}>{regError}</div>}
                            <button
                                type="submit"
                                disabled={regLoading}
                                style={{
                                    padding: '8px 16px', borderRadius: 6, background: '#4F46E5',
                                    color: '#fff', fontWeight: 600, border: 'none', fontSize: 13, cursor: 'pointer',
                                    opacity: regLoading ? 0.7 : 1,
                                }}
                            >
                                {regLoading ? 'Creating...' : 'Create Account'}
                            </button>
                        </form>
                    </div>
                )}

                {regDone && (
                    <div style={{
                        background: '#DCFCE7', border: '1px solid #16A34A', borderRadius: 10,
                        padding: 14, marginBottom: 20, color: '#15803D', fontSize: 13, fontWeight: 600,
                    }}>
                        ✅ Account created! You can now log in with your email and password.
                    </div>
                )}

                <div className="flex gap-2 justify-center">
                    <button className="btn btn-outline btn-sm" onClick={() => window.close()}>
                        Close Tab
                    </button>
                    <button className="btn btn-p btn-sm" onClick={() => window.location.href = '/'}>
                        <i className="fas fa-gauge" /> Dashboard
                    </button>
                </div>
            </div>
        </div>
    );
}
