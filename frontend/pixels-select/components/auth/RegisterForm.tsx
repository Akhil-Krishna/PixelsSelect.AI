'use client';

import { useState } from 'react';
import { apiCall } from '../../lib/api';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';

interface OrgRegisterFormProps {
    onSwitchToLogin: () => void;
}

/**
 * Organisation Registration Form.
 * Creates the organisation + first admin account.
 * Staff (HR, Interviewers) are added via invitation after registration.
 */
export function OrgRegisterForm({ onSwitchToLogin }: OrgRegisterFormProps) {
    const [orgName, setOrgName] = useState('');
    const [adminEmail, setAdminEmail] = useState('');
    const [adminName, setAdminName] = useState('');
    const [password, setPassword] = useState('');
    const [status, setStatus] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
    const [loading, setLoading] = useState(false);
    const [done, setDone] = useState(false);

    const handleRegister = async () => {
        if (!orgName) { setStatus({ msg: 'Please enter your organisation name', type: 'error' }); return; }
        if (!adminName) { setStatus({ msg: 'Please enter your full name', type: 'error' }); return; }
        if (!adminEmail) { setStatus({ msg: 'Please enter your work email', type: 'error' }); return; }
        if (!password || password.length < 8) { setStatus({ msg: 'Password must be at least 8 characters', type: 'error' }); return; }

        setLoading(true);
        setStatus(null);
        try {
            await apiCall('POST', '/auth/org/register', {
                name: orgName,
                admin_email: adminEmail,
                admin_name: adminName,
                password,
            });
            setDone(true);
        } catch (e: unknown) {
            setStatus({ msg: (e as Error).message || 'Registration failed', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    if (done) {
        return (
            <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>📬</div>
                <h3 style={{ margin: '0 0 8px', color: 'var(--foreground)' }}>Check your inbox</h3>
                <p style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.5, margin: '0 0 20px' }}>
                    We sent a verification email to <strong>{adminEmail}</strong>.
                    Click the link in the email to activate your account.
                </p>
                <Button variant="ghost" size="sm" onClick={onSwitchToLogin}>
                    Back to Sign In
                </Button>
            </div>
        );
    }

    return (
        <>
            {status && (
                <Alert type={status.type} onClose={() => setStatus(null)}>{status.msg}</Alert>
            )}

            <div className="form-group">
                <label className="form-label">Organisation Name</label>
                <input value={orgName} onChange={e => setOrgName(e.target.value)} placeholder="Acme Corp" />
            </div>

            <div className="form-group">
                <label className="form-label">Your Full Name</label>
                <input value={adminName} onChange={e => setAdminName(e.target.value)} placeholder="Jane Smith" />
            </div>

            <div className="form-group">
                <label className="form-label">Work Email</label>
                <input type="email" value={adminEmail} onChange={e => setAdminEmail(e.target.value)} placeholder="jane@company.com" />
            </div>

            <div className="form-group">
                <label className="form-label">Password</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Min 8 characters" onKeyDown={e => e.key === 'Enter' && handleRegister()} />
            </div>

            <Button variant="primary" fullWidth loading={loading} icon="fa-building" onClick={handleRegister}>
                Register Organisation
            </Button>

            <p className="text-sm text-muted" style={{ textAlign: 'center', marginTop: 14 }}>
                Already have an account?{' '}
                <a href="#" onClick={e => { e.preventDefault(); onSwitchToLogin(); }} style={{ color: 'var(--primary)' }}>
                    Sign In
                </a>
            </p>
        </>
    );
}
