'use client';

import { useState } from 'react';
import { Modal } from '../ui/Modal';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';
import { apiCall } from '../../lib/api';

interface AddUserModalProps {
    open: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

const ROLES = [
    { value: 'candidate', label: 'Candidate' },
    { value: 'interviewer', label: 'Interviewer' },
    { value: 'hr', label: 'HR Manager' },
    { value: 'admin', label: 'Admin' },
];

export function AddUserModal({ open, onClose, onSuccess }: AddUserModalProps) {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState('candidate');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleCreate = async () => {
        if (!name || !email || !password) { setError('All fields are required'); return; }
        setLoading(true);
        setError('');
        try {
            await apiCall('POST', '/users', { full_name: name, email, password, role });
            setName(''); setEmail(''); setPassword(''); setRole('candidate');
            onClose();
            onSuccess();
        } catch (e: unknown) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Modal open={open} onClose={onClose} title="Add New User">
            {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}
            <div className="form-group">
                <label className="form-label">Full Name</label>
                <input value={name} onChange={e => setName(e.target.value)} placeholder="John Smith" />
            </div>
            <div className="form-group">
                <label className="form-label">Email Address</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="john@company.com" />
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
            <hr className="divider" />
            <div className="flex justify-between">
                <Button variant="ghost" onClick={onClose}>Cancel</Button>
                <Button variant="primary" loading={loading} icon="fa-plus" onClick={handleCreate}>
                    Create User
                </Button>
            </div>
        </Modal>
    );
}
