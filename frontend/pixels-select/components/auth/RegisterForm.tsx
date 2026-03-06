'use client';

import { useState } from 'react';
import { apiCall } from '../../lib/api';
import { User } from '../../lib/types';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';

interface RegisterFormProps {
    onSuccess: (user: User, token: string) => void;
    onSwitchToLogin: () => void;
}

const ROLES = [
    { value: 'candidate', label: 'Candidate' },
    { value: 'interviewer', label: 'Interviewer' },
    { value: 'hr', label: 'HR Manager' },
    { value: 'admin', label: 'Admin' },
];

export function RegisterForm({ onSuccess, onSwitchToLogin }: RegisterFormProps) {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState('candidate');
    const [status, setStatus] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
    const [loading, setLoading] = useState(false);

    const handleRegister = async () => {
        if (!name) { setStatus({ msg: 'Please enter your full name', type: 'error' }); return; }
        if (!email) { setStatus({ msg: 'Please enter your email', type: 'error' }); return; }
        if (!password || password.length < 6) { setStatus({ msg: 'Password must be at least 6 characters', type: 'error' }); return; }
        setLoading(true);
        setStatus(null);
        try {
            await apiCall('POST', '/auth/register', { full_name: name, email, password, role });
            setStatus({ msg: '✓ Account created! Signing you in...', type: 'success' });
            setTimeout(async () => {
                try {
                    const d = await apiCall<{ access_token: string; user: User }>('POST', '/auth/login', { email, password });
                    onSuccess(d.user, d.access_token);
                } catch {
                    onSwitchToLogin();
                }
            }, 700);
        } catch (e: unknown) {
            setStatus({ msg: (e as Error).message || 'Registration failed', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            {status && (
                <Alert type={status.type} onClose={() => setStatus(null)}>{status.msg}</Alert>
            )}

            <div className="form-group">
                <label className="form-label">Full Name</label>
                <input value={name} onChange={e => setName(e.target.value)} placeholder="John Smith" />
            </div>

            <div className="form-group">
                <label className="form-label">Email</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" />
            </div>

            <div className="form-group">
                <label className="form-label">Password</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Min 6 characters" />
            </div>

            <div className="form-group">
                <label className="form-label">Role</label>
                <select value={role} onChange={e => setRole(e.target.value)}>
                    {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
            </div>

            <Button variant="primary" fullWidth loading={loading} icon="fa-user-plus" onClick={handleRegister}>
                Create Account
            </Button>

            <p className="text-sm text-muted" style={{ textAlign: 'center', marginTop: 14 }}>
                Have an account?{' '}
                <a href="#" onClick={e => { e.preventDefault(); onSwitchToLogin(); }} style={{ color: 'var(--primary)' }}>
                    Sign In
                </a>
            </p>
        </>
    );
}
