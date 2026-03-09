'use client';

import { useEffect, useState } from 'react';
import { apiCall } from '../../lib/api';

export default function VerifyEmailPage() {
    const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
    const [message, setMessage] = useState('');

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const token = params.get('token');

        if (!token) {
            setStatus('error');
            setMessage('No verification token found in the link. Please check your email again.');
            return;
        }

        apiCall<{ message: string }>('POST', '/auth/org/verify-email', { token })
            .then((d: { message: string }) => {
                setMessage(d.message || 'Email verified successfully!');
                setStatus('success');
            })
            .catch((e: unknown) => {
                // Token already used = already verified, treat as success
                const msg = (e as Error).message || '';
                if (msg.toLowerCase().includes('already verified') || msg.includes('400')) {
                    setMessage('Your email is already verified. You can sign in now.');
                    setStatus('success');
                } else {
                    setMessage(msg || 'Verification failed. The link may have expired.');
                    setStatus('error');
                }
            });
    }, []);

    function goToSignIn() {
        // Replace the current history entry so the back button doesn't loop
        // back to the verify-email page with a used token.
        window.location.replace('/');
    }

    return (
        <div style={{
            minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--bg)', padding: 24,
        }}>
            <div style={{
                background: 'var(--surface)', borderRadius: 16, padding: '40px 36px',
                maxWidth: 440, width: '100%', textAlign: 'center',
                boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
            }}>
                {status === 'loading' && (
                    <>
                        <div style={{ fontSize: 48, marginBottom: 16 }}>
                            <i className="fas fa-spinner fa-spin" style={{ color: 'var(--primary)' }} />
                        </div>
                        <h2 style={{ margin: '0 0 8px', color: 'var(--foreground)' }}>Verifying…</h2>
                        <p style={{ color: 'var(--muted)', fontSize: 14 }}>Please wait while we verify your email.</p>
                    </>
                )}

                {status === 'success' && (
                    <>
                        <div style={{ fontSize: 52, marginBottom: 16 }}>✅</div>
                        <h2 style={{ margin: '0 0 8px', color: 'var(--foreground)' }}>Email Verified!</h2>
                        <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 24 }}>{message}</p>
                        <button
                            onClick={goToSignIn}
                            style={{
                                display: 'inline-block', background: 'var(--primary)', color: '#fff',
                                padding: '12px 28px', borderRadius: 8, border: 'none', cursor: 'pointer',
                                fontWeight: 700, fontSize: 14,
                            }}
                        >
                            Go to Sign In →
                        </button>
                    </>
                )}

                {status === 'error' && (
                    <>
                        <div style={{ fontSize: 52, marginBottom: 16 }}>❌</div>
                        <h2 style={{ margin: '0 0 8px', color: 'var(--foreground)' }}>Verification Failed</h2>
                        <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 24 }}>{message}</p>
                        <button
                            onClick={goToSignIn}
                            style={{
                                display: 'inline-block', background: 'var(--surface-2, #f1f5f9)', color: 'var(--foreground)',
                                padding: '12px 28px', borderRadius: 8, border: '1px solid var(--border)',
                                cursor: 'pointer', fontWeight: 600, fontSize: 14,
                            }}
                        >
                            ← Back to Home
                        </button>
                    </>
                )}
            </div>
        </div>
    );
}
