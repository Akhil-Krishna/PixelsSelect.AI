'use client';

import { useState } from 'react';
import { apiCall } from '../../lib/api';
import { Button } from '../../components/ui/Button';
import { Alert } from '../../components/ui/Alert';

export default function ResetPasswordPage() {
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [status, setStatus] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
    const [loading, setLoading] = useState(false);
    const [done, setDone] = useState(false);

    const getToken = () => {
        if (typeof window === 'undefined') return '';
        return new URLSearchParams(window.location.search).get('token') || '';
    };

    const handleReset = async () => {
        const token = getToken();
        if (!token) { setStatus({ msg: 'Invalid reset link. Please request a new one.', type: 'error' }); return; }
        if (!password || password.length < 8) { setStatus({ msg: 'Password must be at least 8 characters', type: 'error' }); return; }
        if (password !== confirmPassword) { setStatus({ msg: 'Passwords do not match', type: 'error' }); return; }

        setLoading(true);
        setStatus(null);
        try {
            await apiCall('POST', '/auth/reset-password', { token, new_password: password });
            setDone(true);
        } catch (e: unknown) {
            setStatus({ msg: (e as Error).message || 'Failed to reset password', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const cardStyle: React.CSSProperties = {
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg)', padding: 24,
    };
    const innerStyle: React.CSSProperties = {
        background: 'var(--surface)', borderRadius: 16, padding: '40px 36px',
        maxWidth: 440, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
    };

    if (done) {
        return (
            <div style={cardStyle}>
                <div style={{ ...innerStyle, textAlign: 'center' }}>
                    <div style={{ fontSize: 52, marginBottom: 12 }}>✅</div>
                    <h2 style={{ margin: '0 0 8px', color: 'var(--foreground)' }}>Password Reset!</h2>
                    <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 24 }}>
                        Your password has been updated. You can now sign in with your new password.
                    </p>
                    <a
                        href="/"
                        style={{
                            display: 'inline-block', background: 'var(--primary)', color: '#fff',
                            padding: '12px 28px', borderRadius: 8, textDecoration: 'none', fontWeight: 700,
                        }}
                    >
                        Go to Sign In →
                    </a>
                </div>
            </div>
        );
    }

    return (
        <div style={cardStyle}>
            <div style={innerStyle}>
                <div style={{ textAlign: 'center', marginBottom: 28 }}>
                    <div style={{ fontSize: 40, marginBottom: 8 }}>🔒</div>
                    <h2 style={{ margin: '0 0 4px', color: 'var(--foreground)' }}>Reset Password</h2>
                    <p style={{ color: 'var(--muted)', fontSize: 13, margin: 0 }}>Enter your new password below.</p>
                </div>

                {status && <Alert type={status.type} onClose={() => setStatus(null)}>{status.msg}</Alert>}

                <div className="form-group">
                    <label className="form-label">New Password</label>
                    <input
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="Min 8 characters"
                    />
                </div>

                <div className="form-group">
                    <label className="form-label">Confirm New Password</label>
                    <input
                        type="password"
                        value={confirmPassword}
                        onChange={e => setConfirmPassword(e.target.value)}
                        placeholder="Confirm your password"
                        onKeyDown={e => e.key === 'Enter' && handleReset()}
                    />
                </div>

                <Button variant="primary" fullWidth loading={loading} icon="fa-key" onClick={handleReset}>
                    Reset Password
                </Button>

                <p className="text-sm text-muted" style={{ textAlign: 'center', marginTop: 14 }}>
                    <a href="/" style={{ color: 'var(--primary)' }}>← Back to Sign In</a>
                </p>
            </div>
        </div>
    );
}
