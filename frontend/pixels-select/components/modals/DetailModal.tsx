'use client';

import { Modal } from '../ui/Modal';
import { StatusBadge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Interview } from '../../lib/types';
import { formatDate } from '../../lib/api';

interface DetailModalProps {
    interview: Interview | null;
    currentUserRole: 'admin' | 'hr' | 'interviewer' | 'candidate';
    onClose: () => void;
}

const SCORE_SECTIONS = [
    { key: 'answer_score', label: 'Q&A', color: '#4F46E5' },
    { key: 'code_score', label: 'Code', color: '#10B981' },
    { key: 'emotion_score', label: 'Confidence', color: '#F59E0B' },
    { key: 'integrity_score', label: 'Integrity', color: '#EF4444' },
] as const;

export function DetailModal({ interview: iv, currentUserRole, onClose }: DetailModalProps) {
    if (!iv) return null;

    const pass = (iv.overall_score ?? 0) >= 60;
    const isCompleted = iv.status === 'completed';

    return (
        <Modal open={!!iv} onClose={onClose} title={iv.title} size="lg">
            {/* Info grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 16px', fontSize: 13.5, marginBottom: 16 }}>
                <span className="text-muted">Candidate</span>
                <strong>{iv.candidate?.full_name || '–'} <span className="text-muted">({iv.candidate?.email || ''})</span></strong>
                <span className="text-muted">Scheduled</span>
                <span>{formatDate(iv.scheduled_at)}</span>
                <span className="text-muted">Duration</span>
                <span>{iv.duration_minutes} minutes</span>
                <span className="text-muted">Status</span>
                <span><StatusBadge status={iv.status} /></span>
                <span className="text-muted">Interview Link</span>
                <span>
                    <a href={`/interview/${iv.access_token}`} target="_blank" rel="noopener" style={{ color: 'var(--primary)' }}>
                        /interview/{iv.access_token.slice(0, 12)}…
                    </a>
                </span>
                {iv.resume_path && (
                    <>
                        <span className="text-muted">Resume</span>
                        <span style={{ color: 'var(--success)' }}>✓ Uploaded</span>
                    </>
                )}
            </div>

            {/* Scores (completed only) */}
            {isCompleted && iv.overall_score != null && (
                <>
                    <hr className="divider" />
                    <div style={{ textAlign: 'center', margin: '16px 0' }}>
                        <div style={{
                            fontSize: 44, fontWeight: 900,
                            color: pass ? 'var(--success)' : 'var(--danger)'
                        }}>
                            {iv.overall_score.toFixed(1)}%
                        </div>
                        <div style={{ fontSize: 14, fontWeight: 700, marginTop: 6 }}>
                            {pass ? '✅ PASSED' : '❌ DID NOT PASS'}
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 8, marginBottom: 16 }}>
                        {SCORE_SECTIONS.map(({ key, label, color }) => {
                            const val = iv[key];
                            if (val == null) return null;
                            return (
                                <div key={key} style={{ background: '#F8FAFC', borderRadius: 9, padding: 12, textAlign: 'center', borderTop: `3px solid ${color}` }}>
                                    <div style={{ fontSize: 22, fontWeight: 800, color }}>{val.toFixed(1)}%</div>
                                    <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 3, textTransform: 'uppercase' }}>{label}</div>
                                </div>
                            );
                        })}
                    </div>

                    {iv.ai_feedback && (
                        <div style={{ background: '#F8FAFC', border: '1px solid var(--border)', borderRadius: 9, padding: 14, fontSize: 13, lineHeight: 1.7, marginBottom: 12 }}>
                            <strong>AI Feedback:</strong><br />{iv.ai_feedback}
                        </div>
                    )}

                    {iv.has_recording && currentUserRole !== 'candidate' && (
                        <Button as="a" href={`/api/v1/recordings/download/${iv.access_token}`} target="_blank" variant="outline" size="sm" icon="fa-video">
                            View Recording
                        </Button>
                    )}
                </>
            )}

            <hr className="divider" />
            <div className="flex justify-between">
                <Button variant="ghost" onClick={onClose}>Close</Button>
                {iv.status === 'in_progress' && (currentUserRole !== 'interviewer' || iv.is_assigned !== false) && (
                    <Button as="a" href={`/watch/${iv.access_token}`} target="_blank" variant="primary" size="sm" icon="fa-eye">
                        Watch Live
                    </Button>
                )}
            </div>
        </Modal>
    );
}
