'use client';

import { useState } from 'react';
import { apiCall } from '../../lib/api';
import { User } from '../../lib/types';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';

interface LoginFormProps {
    onSuccess: (user: User, token: string) => void;
    onSwitchToRegister: () => void;
}

export function LoginForm({ onSuccess, onSwitchToRegister }: LoginFormProps) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleLogin = async () => {
        if (!email) { setError('Please enter your email'); return; }
        if (!password) { setError('Please enter your password'); return; }
        setLoading(true);
        setError('');
        try {
            const d = await apiCall<{ access_token: string; user: User }>('POST', '/auth/login', { email, password });
            onSuccess(d.user, d.access_token);
        } catch (e: unknown) {
            setError((e as Error).message || 'Login failed. Check your credentials.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}

            <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    onKeyDown={e => e.key === 'Enter' && handleLogin()}
                />
            </div>

            <div className="form-group">
                <label className="form-label">Password</label>
                <input
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                    onKeyDown={e => e.key === 'Enter' && handleLogin()}
                />
            </div>

            <Button variant="primary" fullWidth loading={loading} icon="fa-sign-in-alt" onClick={handleLogin}>
                Sign In
            </Button>

            <p className="text-sm text-muted" style={{ textAlign: 'center', marginTop: 14 }}>
                No account?{' '}
                <a href="#" onClick={e => { e.preventDefault(); onSwitchToRegister(); }} style={{ color: 'var(--primary)' }}>
                    Register here
                </a>
            </p>
        </>
    );
}
