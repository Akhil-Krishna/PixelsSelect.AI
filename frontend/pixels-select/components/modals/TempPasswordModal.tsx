'use client';

import { useState } from 'react';
import { Button } from '../ui/Button';

interface TempPasswordModalProps {
    email: string;
    password: string;
    onClose: () => void;
}

export function TempPasswordModal({ email, password, onClose }: TempPasswordModalProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(`Email: ${email}\nPassword: ${password}`);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div style={{
            position: 'fixed', inset: 0, background: 'rgba(15,23,42,.88)',
            zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
            <div style={{
                background: '#1E293B', border: '1px solid #334155', borderRadius: 20,
                padding: 36, maxWidth: 480, width: '95%', textAlign: 'center',
            }}>
                <div style={{ fontSize: 52, marginBottom: 12 }}>🎉</div>
                <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 6 }}>Interview Scheduled!</div>
                <div style={{ fontSize: 13, color: '#94A3B8', marginBottom: 22 }}>
                    A new candidate account was created. Share these credentials with them.
                </div>

                <div style={{
                    background: '#0F172A', border: '1px solid #F59E0B', borderRadius: 12,
                    padding: 20, textAlign: 'left', marginBottom: 22,
                }}>
                    <div style={{ fontSize: 11, color: '#F59E0B', textTransform: 'uppercase', letterSpacing: '.8px', marginBottom: 14, fontWeight: 700 }}>
                        ⚠️ Share these login credentials with the candidate
                    </div>
                    <div style={{ marginBottom: 10 }}>
                        <span style={{ color: '#94A3B8', fontSize: 12, display: 'block', marginBottom: 3 }}>Email Address</span>
                        <strong style={{ color: '#F1F5F9', fontSize: 14 }}>{email}</strong>
                    </div>
                    <div>
                        <span style={{ color: '#94A3B8', fontSize: 12, display: 'block', marginBottom: 3 }}>Temporary Password</span>
                        <strong style={{ color: '#10B981', fontSize: 22, letterSpacing: 3, fontFamily: 'monospace' }}>{password}</strong>
                    </div>
                    <div style={{ marginTop: 14, fontSize: 11, color: '#64748B', lineHeight: 1.6 }}>
                        The candidate must log in at this platform and join from their dashboard using these credentials.
                    </div>
                </div>

                <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
                    <Button variant="primary" icon={copied ? 'fa-check' : 'fa-clipboard'} onClick={handleCopy}>
                        {copied ? 'Copied!' : 'Copy Credentials'}
                    </Button>
                    <Button variant="outline" onClick={onClose}>Done</Button>
                </div>
            </div>
        </div>
    );
}
