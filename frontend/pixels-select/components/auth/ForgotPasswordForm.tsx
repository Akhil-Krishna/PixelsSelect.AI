'use client';

import { useState } from 'react';
import { apiCall } from '../../lib/api';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';

interface ForgotPasswordFormProps {
    onBack: () => void;
}

export function ForgotPasswordForm({ onBack }: ForgotPasswordFormProps) {
    const [email, setEmail] = useState('');
    const [status, setStatus] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
    const [loading, setLoading] = useState(false);
    const [sent, setSent] = useState(false);

    const handleSubmit = async () => {
        if (!email) { setStatus({ msg: 'Please enter your email address', type: 'error' }); return; }
        setLoading(true);
        setStatus(null);
        try {
            await apiCall('POST', '/auth/forgot-password', { email });
            setSent(true);
        } catch (e: unknown) {
            setStatus({ msg: (e as Error).message || 'Something went wrong', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    if (sent) {
        return (
            <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>🔒</div>
                <h3 style={{ margin: '0 0 8px', color: 'var(--foreground)' }}>Check your inbox</h3>
                <p style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.5, margin: '0 0 20px' }}>
                    If <strong>{email}</strong> is registered, you'll receive a password reset link shortly.
                </p>
                <Button variant="ghost" size="sm" onClick={onBack}>
                    Back to Sign In
                </Button>
            </div>
        );
    }

    return (
        <>
            <p style={{ color: 'var(--muted)', fontSize: 14, marginTop: -4, marginBottom: 16 }}>
                Enter your email and we&apos;ll send you a reset link.
            </p>

            {status && (
                <Alert type={status.type} onClose={() => setStatus(null)}>{status.msg}</Alert>
            )}

            <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                />
            </div>

            <Button variant="primary" fullWidth loading={loading} icon="fa-paper-plane" onClick={handleSubmit}>
                Send Reset Link
            </Button>

            <p className="text-sm text-muted" style={{ textAlign: 'center', marginTop: 14 }}>
                <a href="#" onClick={e => { e.preventDefault(); onBack(); }} style={{ color: 'var(--primary)' }}>
                    ← Back to Sign In
                </a>
            </p>
        </>
    );
}
