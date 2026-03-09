'use client';

import { useEffect, useState } from 'react';
import { apiCall } from '../../lib/api';
import { Button } from '../../components/ui/Button';
import { Alert } from '../../components/ui/Alert';

interface InviteDetails {
    id: string;
    email: string;
    role: string;
    org_name: string;
    expires_at: string;
}

export default function AcceptInvitePage() {
    const [token, setToken] = useState('');
    const [invite, setInvite] = useState<InviteDetails | null>(null);
    const [fetchError, setFetchError] = useState('');

    const [fullName, setFullName] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [status, setStatus] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
    const [loading, setLoading] = useState(false);
    const [done, setDone] = useState(false);

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const t = params.get('token') || '';
        setToken(t);

        if (!t) {
            setFetchError('No invitation token found in the link.');
            return;
        }

        apiCall<InviteDetails>('GET', `/invitations/validate/${t}`)
            .then((d: InviteDetails) => setInvite(d))
            .catch((e: unknown) => setFetchError((e as Error).message || 'Invitation not found or expired.'));
    }, []);

    const handleAccept = async () => {
        if (!fullName) { setStatus({ msg: 'Please enter your full name', type: 'error' }); return; }
        if (!password || password.length < 8) { setStatus({ msg: 'Password must be at least 8 characters', type: 'error' }); return; }
        if (password !== confirmPassword) { setStatus({ msg: 'Passwords do not match', type: 'error' }); return; }

        setLoading(true);
        setStatus(null);
        try {
            await apiCall('POST', '/invitations/accept', { token, full_name: fullName, password });
            setDone(true);
        } catch (e: unknown) {
            setStatus({ msg: (e as Error).message || 'Failed to accept invitation', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const roleLabel = (r: string) => r.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());

    const cardStyle: React.CSSProperties = {
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg)', padding: 24,
    };
    const innerStyle: React.CSSProperties = {
        background: 'var(--surface)', borderRadius: 16, padding: '40px 36px',
        maxWidth: 460, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
    };

    if (fetchError) {
        return (
            <div style={cardStyle}>
                <div style={{ ...innerStyle, textAlign: 'center' }}>
                    <div style={{ fontSize: 48, marginBottom: 12 }}>⚠️</div>
                    <h2 style={{ margin: '0 0 8px' }}>Invalid Invitation</h2>
                    <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 24 }}>{fetchError}</p>
                    <a href="/" style={{ color: 'var(--primary)', fontWeight: 600 }}>← Back to Sign In</a>
                </div>
            </div>
        );
    }

    if (done) {
        return (
            <div style={cardStyle}>
                <div style={{ ...innerStyle, textAlign: 'center' }}>
                    <div style={{ fontSize: 52, marginBottom: 12 }}>🎉</div>
                    <h2 style={{ margin: '0 0 8px' }}>Account Created!</h2>
                    <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 24 }}>
                        Your account for <strong>{invite?.org_name}</strong> is ready. You can now sign in.
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

    if (!invite) {
        return (
            <div style={cardStyle}>
                <div style={{ ...innerStyle, textAlign: 'center' }}>
                    <i className="fas fa-spinner fa-spin" style={{ fontSize: 32, color: 'var(--primary)' }} />
                    <p style={{ color: 'var(--muted)', marginTop: 16 }}>Loading invitation…</p>
                </div>
            </div>
        );
    }

    return (
        <div style={cardStyle}>
            <div style={innerStyle}>
                <div style={{ textAlign: 'center', marginBottom: 28 }}>
                    <div style={{ fontSize: 40, marginBottom: 8 }}>📧</div>
                    <h2 style={{ margin: '0 0 4px', color: 'var(--foreground)' }}>You&apos;re Invited</h2>
                    <p style={{ color: 'var(--muted)', fontSize: 13, margin: 0 }}>
                        Join <strong>{invite.org_name}</strong> as <strong>{roleLabel(invite.role)}</strong>
                    </p>
                    <p style={{ color: 'var(--muted)', fontSize: 12, marginTop: 4 }}>
                        Account: {invite.email}
                    </p>
                </div>

                {status && <Alert type={status.type} onClose={() => setStatus(null)}>{status.msg}</Alert>}

                <div className="form-group">
                    <label className="form-label">Your Full Name</label>
                    <input value={fullName} onChange={e => setFullName(e.target.value)} placeholder="Jane Smith" />
                </div>

                <div className="form-group">
                    <label className="form-label">Choose a Password</label>
                    <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Min 8 characters" />
                </div>

                <div className="form-group">
                    <label className="form-label">Confirm Password</label>
                    <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} placeholder="Confirm your password" onKeyDown={e => e.key === 'Enter' && handleAccept()} />
                </div>

                <Button variant="primary" fullWidth loading={loading} icon="fa-check" onClick={handleAccept}>
                    Set Up My Account
                </Button>

                <p className="text-sm text-muted" style={{ textAlign: 'center', marginTop: 14 }}>
                    <a href="/" style={{ color: 'var(--primary)' }}>← Back to Sign In</a>
                </p>
            </div>
        </div>
    );
}
