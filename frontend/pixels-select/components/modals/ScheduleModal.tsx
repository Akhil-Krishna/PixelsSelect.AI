'use client';

import { useState } from 'react';
import { Modal } from '../ui/Modal';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';
import { apiCall, uploadFile } from '../../lib/api';
import { User } from '../../lib/types';

interface ScheduleModalProps {
    open: boolean;
    onClose: () => void;
    onSuccess: (tempPassword?: string, email?: string) => void;
}

export function ScheduleModal({ open, onClose, onSuccess }: ScheduleModalProps) {
    const [tab, setTab] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Basic Info
    const [title, setTitle] = useState('');
    const [role, setRole] = useState('');
    const [email, setEmail] = useState('');
    const [date, setDate] = useState(() => {
        const dt = new Date(Date.now() + 3_600_000);
        return new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    });
    const [duration, setDuration] = useState(60);
    const [desc, setDesc] = useState('');

    // Question Bank
    const [questions, setQuestions] = useState('');
    const [qbLabel, setQbLabel] = useState('Click to upload PDF or TXT question bank');

    // Resume & Team
    const [resumeFile, setResumeFile] = useState<File | null>(null);
    const [resumeLabel, setResumeLabel] = useState('Drop resume here or click to browse');
    const [interviewers, setInterviewers] = useState<User[]>([]);
    const [selectedIvs, setSelectedIvs] = useState<string[]>([]);
    const [ivsLoaded, setIvsLoaded] = useState(false);

    const loadInterviewers = async () => {
        if (ivsLoaded) return;
        const list = await apiCall<User[]>('GET', '/users/interviewers').catch(() => [] as User[]);
        setInterviewers(list);
        setIvsLoaded(true);
    };

    const parseQuestions = (raw: string) => {
        if (!raw.trim()) return null;
        return raw.trim().split('\n').filter(l => l.trim()).map(l => {
            const isCoding = l.trim().toUpperCase().startsWith('CODING:');
            return {
                question: l.replace(/^CODING:\s*/i, '').trim(),
                difficulty: 'medium',
                type: isCoding ? 'coding' : 'technical',
            };
        });
    };

    const toggleInterviewer = (id: string) => {
        setSelectedIvs(prev =>
            prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
        );
    };

    const handleSubmit = async () => {
        if (!title || !role || !email || !date) {
            setError('Please fill in Title, Role, Email and Date');
            return;
        }
        setLoading(true);
        setError('');
        try {
            const iv = await apiCall<{ id: string; temp_password?: string; access_token: string }>('POST', '/interviews', {
                title,
                job_role: role,
                candidate_email: email,
                scheduled_at: date,
                duration_minutes: duration,
                description: desc || null,
                interviewer_ids: selectedIvs,
                question_bank: parseQuestions(questions),
                enable_emotion_analysis: true,
                enable_cheating_detection: true,
            });

            if (resumeFile && iv.id) {
                await uploadFile(`/interviews/${iv.id}/resume`, resumeFile);
            }

            onClose();
            onSuccess(iv.temp_password, email);
        } catch (e: unknown) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    };

    const handleClose = () => {
        setTab(1); setError('');
        onClose();
    };

    return (
        <Modal open={open} onClose={handleClose} title={<><span style={{ color: 'var(--primary)' }}>📅</span> Schedule Interview</>} size="lg">
            {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}

            {/* Tab Bar */}
            <div className="tab-bar">
                {['Basic Info', 'Question Bank', 'Resume & Team'].map((t, i) => (
                    <button key={t} className={`tab-btn${tab === i + 1 ? ' active' : ''}`}
                        onClick={() => { setTab(i + 1); if (i + 1 === 3) loadInterviewers(); }}>
                        {t}
                    </button>
                ))}
            </div>

            {/* Tab 1: Basic Info */}
            {tab === 1 && (
                <>
                    <div className="form-group">
                        <label className="form-label">Interview Title</label>
                        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Senior Backend Engineer Interview" />
                    </div>
                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">Job Role</label>
                            <input value={role} onChange={e => setRole(e.target.value)} placeholder="e.g. Backend Engineer" />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Candidate Email</label>
                            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="candidate@email.com" />
                        </div>
                    </div>
                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">Scheduled Date &amp; Time</label>
                            <input type="datetime-local" value={date} onChange={e => setDate(e.target.value)} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Duration (minutes)</label>
                            <input type="number" value={duration} onChange={e => setDuration(+e.target.value)} min={15} max={180} />
                        </div>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Description <span className="optional">(optional)</span></label>
                        <textarea rows={2} value={desc} onChange={e => setDesc(e.target.value)}
                            placeholder="Interview notes or instructions for the candidate" />
                    </div>
                </>
            )}

            {/* Tab 2: Question Bank */}
            {tab === 2 && (
                <>
                    <Alert type="info">
                        AI will use these questions in order. Leave empty to let AI generate based on the job role.
                    </Alert>
                    <div className="form-group" style={{ marginTop: 12 }}>
                        <label className="form-label">Upload Question Bank <span className="optional">(PDF or TXT — one question per line)</span></label>
                        <div className="file-drop" onClick={() => document.getElementById('qbFile')?.click()}>
                            <i className="fas fa-file-pdf" style={{ fontSize: 28, color: '#EF4444' }} />
                            <div style={{ fontSize: 13 }}>{qbLabel}</div>
                            <p className="form-hint" style={{ marginTop: 6 }}>Each line becomes a question. Prefix with CODING: for coding questions.</p>
                        </div>
                        <input type="file" id="qbFile" style={{ display: 'none' }} accept=".pdf,.txt"
                            onChange={e => { const f = e.target.files?.[0]; if (f) setQbLabel(`✓ ${f.name}`); }} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Or type questions manually <span className="optional">(one per line)</span></label>
                        <textarea rows={7} value={questions} onChange={e => setQuestions(e.target.value)}
                            placeholder={"What is the time complexity of merge sort?\nExplain SOLID principles.\nCODING: Write a binary search."} />
                        <p className="form-hint">Prefix with CODING: to trigger the code editor automatically</p>
                    </div>
                </>
            )}

            {/* Tab 3: Resume & Team */}
            {tab === 3 && (
                <>
                    <div className="form-group">
                        <label className="form-label">Candidate Resume <span className="optional">(PDF, DOC, TXT)</span></label>
                        <div className="file-drop" onClick={() => document.getElementById('resumeFile')?.click()}>
                            <i className="fas fa-file-upload" />
                            <div>{resumeLabel}</div>
                            <p className="form-hint" style={{ marginTop: 6 }}>AI will use resume content to ask relevant questions</p>
                        </div>
                        <input type="file" id="resumeFile" style={{ display: 'none' }} accept=".pdf,.doc,.docx,.txt"
                            onChange={e => {
                                const f = e.target.files?.[0];
                                if (f) { setResumeFile(f); setResumeLabel(`✓ ${f.name} (${(f.size / 1024).toFixed(0)} KB)`); }
                            }} />
                    </div>
                    <hr className="divider" />
                    <div className="form-group">
                        <label className="form-label">Assign Interviewers <span className="optional">(from your organisation)</span></label>
                        <div className="check-list">
                            {interviewers.length === 0
                                ? <p className="text-muted text-sm" style={{ padding: 8 }}>No interviewers found in your organisation</p>
                                : interviewers.map(u => (
                                    <div key={u.id} className="check-item">
                                        <input type="checkbox" id={`iv_${u.id}`}
                                            checked={selectedIvs.includes(u.id)}
                                            onChange={() => toggleInterviewer(u.id)} />
                                        <label htmlFor={`iv_${u.id}`}>
                                            <strong>{u.full_name}</strong>{' '}
                                            <span className="text-xs text-muted">{u.email}</span>
                                        </label>
                                    </div>
                                ))}
                        </div>
                    </div>
                </>
            )}

            <hr className="divider" />
            <div className="flex justify-between">
                <Button variant="ghost" onClick={handleClose}>Cancel</Button>
                <Button variant="primary" loading={loading} icon="fa-paper-plane" onClick={handleSubmit}>
                    Schedule &amp; Send Invite
                </Button>
            </div>
        </Modal>
    );
}
