'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiCall } from '../../lib/api';
import { User } from '../../lib/types';
import { Button } from '../ui/Button';
import { RoleBadge } from '../ui/Badge';
import { Alert } from '../ui/Alert';

interface Stats {
    total: number;
    completed: number;
    passed: number;
    failed: number;
    pass_rate: number;
    role: string;
    // Admin-only org-wide fields
    scheduled?: number;
    in_progress?: number;
    cancelled?: number;
    avg_score?: number;
    total_interviewers?: number;
    total_candidates?: number;
    [key: string]: unknown;
}

interface ProfilePageProps {
    currentUser: User;
    onUserUpdated: (user: User) => void;
}

interface StatCardDef {
    icon: string;
    bg: string;
    color: string;
    key: string;
    label: string;
}

const STAT_CARDS: Record<string, StatCardDef[]> = {
    admin: [
        { icon: 'fa-briefcase', bg: '#EEF2FF', color: '#4F46E5', key: 'total', label: 'Total Interviews' },
        { icon: 'fa-check-circle', bg: '#DCFCE7', color: '#16A34A', key: 'completed', label: 'Completed' },
        { icon: 'fa-trophy', bg: '#FEF9C3', color: '#CA8A04', key: 'passed', label: 'Passed' },
        { icon: 'fa-times-circle', bg: '#FEE2E2', color: '#DC2626', key: 'failed', label: 'Failed' },
    ],
    hr: [
        { icon: 'fa-calendar-alt', bg: '#EEF2FF', color: '#4F46E5', key: 'total', label: 'Scheduled' },
        { icon: 'fa-check-circle', bg: '#DCFCE7', color: '#16A34A', key: 'completed', label: 'Completed' },
        { icon: 'fa-trophy', bg: '#FEF9C3', color: '#CA8A04', key: 'passed', label: 'Passed' },
        { icon: 'fa-times-circle', bg: '#FEE2E2', color: '#DC2626', key: 'failed', label: 'Failed' },
    ],
    interviewer: [
        { icon: 'fa-clipboard-list', bg: '#EEF2FF', color: '#4F46E5', key: 'total', label: 'Assigned' },
        { icon: 'fa-check-circle', bg: '#DCFCE7', color: '#16A34A', key: 'completed', label: 'Completed' },
        { icon: 'fa-trophy', bg: '#FEF9C3', color: '#CA8A04', key: 'passed', label: 'Passed' },
        { icon: 'fa-times-circle', bg: '#FEE2E2', color: '#DC2626', key: 'failed', label: 'Failed' },
    ],
    candidate: [
        { icon: 'fa-briefcase', bg: '#EEF2FF', color: '#4F46E5', key: 'total', label: 'Interviews' },
        { icon: 'fa-check-circle', bg: '#DCFCE7', color: '#16A34A', key: 'completed', label: 'Completed' },
        { icon: 'fa-trophy', bg: '#FEF9C3', color: '#CA8A04', key: 'passed', label: 'Passed' },
        { icon: 'fa-times-circle', bg: '#FEE2E2', color: '#DC2626', key: 'failed', label: 'Failed' },
    ],
};

export function ProfilePage({ currentUser, onUserUpdated }: ProfilePageProps) {
    const [stats, setStats] = useState<Stats | null>(null);
    const [editing, setEditing] = useState(false);
    const [editName, setEditName] = useState(currentUser.full_name);
    const [saving, setSaving] = useState(false);
    const [alert, setAlert] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

    const loadStats = useCallback(async () => {
        try {
            const data = await apiCall<Stats>('GET', '/users/me/stats');
            setStats(data);
        } catch { }
    }, []);

    useEffect(() => { loadStats(); }, [loadStats]);

    const handleSave = async () => {
        if (!editName.trim()) return;
        setSaving(true);
        try {
            const updated = await apiCall<User>('PATCH', '/users/me', { full_name: editName.trim() });
            onUserUpdated(updated);
            setEditing(false);
            setAlert({ msg: 'Profile updated successfully!', type: 'success' });
            setTimeout(() => setAlert(null), 3000);
        } catch (e: unknown) {
            setAlert({ msg: (e as Error).message || 'Failed to update', type: 'error' });
        }
        setSaving(false);
    };

    const cards = STAT_CARDS[currentUser.role] || STAT_CARDS.candidate;
    const passRate = stats?.pass_rate ?? 0;
    const isAdmin = currentUser.role === 'admin';

    return (
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
            {alert && <Alert type={alert.type} onClose={() => setAlert(null)}>{alert.msg}</Alert>}

            {/* ── User Card ── */}
            <div className="card" style={{ marginBottom: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '28px 24px' }}>
                    <div style={{
                        width: 72, height: 72, borderRadius: '50%',
                        background: 'linear-gradient(135deg, #4F46E5, #7C3AED)',
                        color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 28, fontWeight: 800, flexShrink: 0,
                    }}>
                        {currentUser.full_name[0]?.toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        {editing ? (
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                                <input
                                    value={editName}
                                    onChange={e => setEditName(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && handleSave()}
                                    style={{
                                        fontSize: 18, fontWeight: 700, padding: '6px 12px',
                                        border: '2px solid var(--primary)', borderRadius: 8,
                                        outline: 'none', flex: 1, fontFamily: 'inherit',
                                    }}
                                    autoFocus
                                />
                                <Button variant="primary" size="xs" loading={saving} onClick={handleSave}>Save</Button>
                                <Button variant="ghost" size="xs" onClick={() => { setEditing(false); setEditName(currentUser.full_name); }}>Cancel</Button>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{currentUser.full_name}</h2>
                                <button
                                    onClick={() => setEditing(true)}
                                    style={{
                                        background: 'none', border: 'none', cursor: 'pointer',
                                        color: 'var(--muted)', fontSize: 13, padding: 4,
                                    }}
                                    title="Edit name"
                                >
                                    <i className="fas fa-pen" />
                                </button>
                            </div>
                        )}
                        <div style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 8 }}>
                            <i className="fas fa-envelope" style={{ marginRight: 6, width: 14 }} />
                            {currentUser.email}
                        </div>
                        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                            <RoleBadge role={currentUser.role} />
                            {currentUser.organisation && (
                                <span style={{
                                    fontSize: 11, background: '#F1F5F9', color: 'var(--muted)',
                                    padding: '3px 10px', borderRadius: 20, fontWeight: 600,
                                }}>
                                    <i className="fas fa-building" style={{ marginRight: 4 }} />
                                    {currentUser.organisation.name}
                                </span>
                            )}
                            {currentUser.department_name && (
                                <span style={{
                                    fontSize: 11, background: '#EEF2FF', color: '#4F46E5',
                                    padding: '3px 10px', borderRadius: 20, fontWeight: 600,
                                }}>
                                    <i className="fas fa-sitemap" style={{ marginRight: 4 }} />
                                    {currentUser.department_name}
                                </span>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Admin: Org Overview Row ── */}
            {isAdmin && stats && (
                <div className="card" style={{ marginBottom: 20, padding: '20px 24px' }}>
                    <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                        <i className="fas fa-building" style={{ marginRight: 6 }} />
                        Organisation Overview
                    </div>
                    <div style={{
                        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                        gap: 12,
                    }}>
                        {[
                            { icon: 'fa-users', label: 'Interviewers', val: stats.total_interviewers ?? 0, color: '#7C3AED' },
                            { icon: 'fa-user-graduate', label: 'Candidates', val: stats.total_candidates ?? 0, color: '#3B82F6' },
                            { icon: 'fa-clock', label: 'Scheduled', val: stats.scheduled ?? 0, color: '#D97706' },
                            { icon: 'fa-spinner', label: 'In Progress', val: stats.in_progress ?? 0, color: '#0891B2' },
                            { icon: 'fa-ban', label: 'Cancelled', val: stats.cancelled ?? 0, color: '#EF4444' },
                            { icon: 'fa-star', label: 'Avg Score', val: stats.avg_score ?? 0, color: '#CA8A04' },
                        ].map(item => (
                            <div key={item.label} style={{ textAlign: 'center', padding: '12px 8px', background: '#F8FAFC', borderRadius: 10 }}>
                                <i className={`fas ${item.icon}`} style={{ color: item.color, fontSize: 18, marginBottom: 6, display: 'block' }} />
                                <div style={{ fontSize: 22, fontWeight: 900, color: item.color }}>{item.val}</div>
                                <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: 0.3, marginTop: 2 }}>
                                    {item.label}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* ── Stats Grid ── */}
            <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: 14, marginBottom: 20,
            }}>
                {cards.map(c => (
                    <div key={c.key} className="card" style={{
                        padding: '20px 18px', textAlign: 'center',
                        borderTop: `3px solid ${c.color}`,
                    }}>
                        <div style={{
                            width: 40, height: 40, borderRadius: 10,
                            background: c.bg, display: 'flex', alignItems: 'center',
                            justifyContent: 'center', margin: '0 auto 10px',
                        }}>
                            <i className={`fas ${c.icon}`} style={{ color: c.color, fontSize: 16 }} />
                        </div>
                        <div style={{ fontSize: 28, fontWeight: 900, color: c.color }}>
                            {stats ? (stats as Record<string, unknown>)[c.key] as number ?? '–' : '–'}
                        </div>
                        <div style={{
                            fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase',
                            fontWeight: 700, letterSpacing: 0.5, marginTop: 4,
                        }}>
                            {c.label}
                        </div>
                    </div>
                ))}
            </div>

            {/* ── Pass Rate ── */}
            {stats && stats.completed > 0 && (
                <div className="card" style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div>
                            <div style={{ fontWeight: 700, fontSize: 15 }}>
                                {isAdmin ? 'Organisation Pass Rate' : 'Pass Rate'}
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                                {stats.passed} passed out of {stats.completed} completed
                            </div>
                        </div>
                        <div style={{
                            fontSize: 28, fontWeight: 900,
                            color: passRate >= 60 ? 'var(--success)' : passRate >= 40 ? 'var(--warning)' : 'var(--danger)',
                        }}>
                            {passRate}%
                        </div>
                    </div>
                    <div style={{
                        height: 10, background: '#F1F5F9', borderRadius: 99,
                        overflow: 'hidden',
                    }}>
                        <div style={{
                            height: '100%', borderRadius: 99,
                            width: `${Math.min(passRate, 100)}%`,
                            background: passRate >= 60 ? 'var(--success)' : passRate >= 40 ? 'var(--warning)' : 'var(--danger)',
                            transition: 'width 0.6s ease',
                        }} />
                    </div>
                </div>
            )}

            {/* ── Empty state ── */}
            {stats && stats.total === 0 && (
                <div className="card" style={{ padding: '40px 24px', textAlign: 'center' }}>
                    <i className="fas fa-chart-bar" style={{ fontSize: 40, color: 'var(--border)', marginBottom: 12 }} />
                    <div style={{ fontWeight: 600, color: 'var(--muted)' }}>No interview data yet</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                        {currentUser.role === 'candidate'
                            ? 'Complete your first interview to see analytics here.'
                            : 'Schedule or participate in interviews to see your stats.'}
                    </div>
                </div>
            )}
        </div>
    );
}
