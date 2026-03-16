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
    { key: 'answer_score', label: 'Q&A', icon: 'fa-comments', color: '#4F46E5', bg: '#EEF2FF' },
    { key: 'code_score', label: 'Code', icon: 'fa-code', color: '#10B981', bg: '#ECFDF5' },
    { key: 'emotion_score', label: 'Confidence', icon: 'fa-face-smile', color: '#F59E0B', bg: '#FFFBEB' },
    { key: 'integrity_score', label: 'Integrity', icon: 'fa-shield-halved', color: '#EF4444', bg: '#FEF2F2' },
    { key: 'human_evaluator_score', label: 'Human Review', icon: 'fa-user-check', color: '#7C3AED', bg: '#F5F3FF', outOf10: true },
] as const;

const REC_COLORS: Record<string, { bg: string; color: string; border: string }> = {
    'Strong Hire': { bg: '#ECFDF5', color: '#059669', border: '#A7F3D0' },
    'Hire': { bg: '#EEF2FF', color: '#4F46E5', border: '#C7D2FE' },
    'Borderline': { bg: '#FFFBEB', color: '#D97706', border: '#FDE68A' },
    'No Hire': { bg: '#FEF2F2', color: '#DC2626', border: '#FECACA' },
};

export function DetailModal({ interview: iv, currentUserRole, onClose }: DetailModalProps) {
    if (!iv) return null;

    const pass = (iv.overall_score ?? 0) >= 60;
    const isCompleted = iv.status === 'completed';
    const isStaff = ['admin', 'hr', 'interviewer'].includes(currentUserRole);
    const rec = iv.final_hiring_recommendation || '';
    const recStyle = REC_COLORS[rec] || { bg: '#F8FAFC', color: '#64748B', border: '#E2E8F0' };

    return (
        <Modal open={!!iv} onClose={onClose} title={iv.title} size="lg">
            <div style={{ maxHeight: '75vh', overflowY: 'auto', paddingRight: 4 }}>

                {/* ── Interview Info ─────────────────────────────── */}
                <div style={{
                    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
                    fontSize: 13, marginBottom: 18,
                    background: '#F8FAFC', borderRadius: 10, padding: 14, border: '1px solid var(--border)',
                }}>
                    <InfoRow label="Candidate" value={iv.candidate?.full_name || '–'} />
                    <InfoRow label="Email" value={iv.candidate?.email || '–'} />
                    <InfoRow label="Role" value={iv.job_role} />
                    <InfoRow label="Duration" value={`${iv.duration_minutes} minutes`} />
                    <InfoRow label="Scheduled" value={formatDate(iv.scheduled_at)} />
                    <InfoRow label="Status" value={<StatusBadge status={iv.status} />} />
                    {iv.started_at && <InfoRow label="Started" value={formatDate(iv.started_at)} />}
                    {iv.ended_at && <InfoRow label="Ended" value={formatDate(iv.ended_at)} />}
                    {iv.resume_path && <InfoRow label="Resume" value={<span style={{ color: 'var(--success)' }}>✓ Uploaded</span>} />}
                </div>

                {/* ── Evaluation Results (completed only) ────────── */}
                {isCompleted && iv.overall_score != null && (
                    <>
                        {/* Overall Score Hero */}
                        <div style={{
                            textAlign: 'center', padding: '20px 16px', marginBottom: 16,
                            background: pass
                                ? 'linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%)'
                                : 'linear-gradient(135deg, #FEF2F2 0%, #FECACA 100%)',
                            borderRadius: 12, border: `1.5px solid ${pass ? '#A7F3D0' : '#FECACA'}`,
                        }}>
                            <div style={{
                                fontSize: 48, fontWeight: 900, lineHeight: 1,
                                color: pass ? '#059669' : '#DC2626',
                            }}>
                                {iv.overall_score.toFixed(1)}%
                            </div>
                            <div style={{
                                fontSize: 15, fontWeight: 700, marginTop: 8,
                                color: pass ? '#059669' : '#DC2626',
                            }}>
                                {pass ? '✅ PASSED' : '❌ DID NOT PASS'}
                            </div>

                            {/* Hiring Recommendation Badge */}
                            {rec && (
                                <div style={{
                                    display: 'inline-block', marginTop: 10,
                                    padding: '5px 16px', borderRadius: 20, fontSize: 12, fontWeight: 700,
                                    background: recStyle.bg, color: recStyle.color,
                                    border: `1.5px solid ${recStyle.border}`,
                                    textTransform: 'uppercase', letterSpacing: 0.5,
                                }}>
                                    {rec}
                                </div>
                            )}
                        </div>

                        {/* Sub-Score Cards */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 10, marginBottom: 16 }}>
                            {SCORE_SECTIONS.map(({ key, label, icon, color, bg, ...rest }) => {
                                const val = iv[key] as number | undefined;
                                if (val == null) return null;
                                const isOutOf10 = 'outOf10' in rest && rest.outOf10;
                                return (
                                    <div key={key} style={{
                                        background: bg, borderRadius: 10, padding: '14px 10px',
                                        textAlign: 'center', borderTop: `3px solid ${color}`,
                                    }}>
                                        <i className={`fas ${icon}`} style={{ color, fontSize: 16, marginBottom: 6, display: 'block' }} />
                                        <div style={{ fontSize: 24, fontWeight: 800, color }}>
                                            {isOutOf10 ? `${val.toFixed(1)}/10` : `${val.toFixed(1)}%`}
                                        </div>
                                        <div style={{ fontSize: 10, color: '#64748B', marginTop: 3, textTransform: 'uppercase', fontWeight: 600 }}>{label}</div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Strengths & Weaknesses */}
                        {((iv.strengths && iv.strengths.length > 0) || (iv.weaknesses && iv.weaknesses.length > 0)) && (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
                                {iv.strengths && iv.strengths.length > 0 && (
                                    <div style={{
                                        background: '#ECFDF5', border: '1px solid #A7F3D0',
                                        borderRadius: 10, padding: 14,
                                    }}>
                                        <div style={{ fontSize: 12, fontWeight: 700, color: '#059669', marginBottom: 8, textTransform: 'uppercase' }}>
                                            <i className="fas fa-check-circle" style={{ marginRight: 5 }} /> Strengths
                                        </div>
                                        <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5, color: '#065F46', lineHeight: 1.8 }}>
                                            {iv.strengths.map((s, i) => <li key={i}>{s}</li>)}
                                        </ul>
                                    </div>
                                )}
                                {iv.weaknesses && iv.weaknesses.length > 0 && (
                                    <div style={{
                                        background: '#FEF2F2', border: '1px solid #FECACA',
                                        borderRadius: 10, padding: 14,
                                    }}>
                                        <div style={{ fontSize: 12, fontWeight: 700, color: '#DC2626', marginBottom: 8, textTransform: 'uppercase' }}>
                                            <i className="fas fa-exclamation-circle" style={{ marginRight: 5 }} /> Areas to Improve
                                        </div>
                                        <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5, color: '#991B1B', lineHeight: 1.8 }}>
                                            {iv.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* AI Feedback */}
                        {iv.ai_feedback && (
                            <div style={{
                                background: '#F8FAFC', border: '1px solid var(--border)',
                                borderRadius: 10, padding: 14, fontSize: 13, lineHeight: 1.7, marginBottom: 12,
                            }}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: '#4F46E5', marginBottom: 6, textTransform: 'uppercase' }}>
                                    <i className="fas fa-robot" style={{ marginRight: 5 }} /> AI Assessment
                                </div>
                                {iv.ai_feedback}
                            </div>
                        )}

                        {/* Recommendation Justification */}
                        {iv.recommendation_justification && (
                            <div style={{
                                background: recStyle.bg, border: `1px solid ${recStyle.border}`,
                                borderRadius: 10, padding: 14, fontSize: 13, lineHeight: 1.7, marginBottom: 12,
                            }}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: recStyle.color, marginBottom: 6, textTransform: 'uppercase' }}>
                                    <i className="fas fa-gavel" style={{ marginRight: 5 }} /> Recommendation
                                </div>
                                {iv.recommendation_justification}
                            </div>
                        )}

                        {/* Integrity Metrics (staff only) */}
                        {isStaff && (
                            <div style={{
                                display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16,
                            }}>
                                <MetricCard
                                    label="Tab Switches"
                                    value={iv.tab_switch_count ?? 0}
                                    icon="fa-arrow-right-arrow-left"
                                    color={(iv.tab_switch_count ?? 0) > 3 ? '#DC2626' : '#64748B'}
                                />
                                <MetricCard
                                    label="Cheating Risk"
                                    value={iv.cheating_score != null ? `${iv.cheating_score.toFixed(1)}%` : '–'}
                                    icon="fa-user-secret"
                                    color={(iv.cheating_score ?? 0) > 30 ? '#DC2626' : '#64748B'}
                                />
                                <MetricCard
                                    label="Integrity"
                                    value={iv.integrity_score != null ? `${iv.integrity_score.toFixed(1)}%` : '–'}
                                    icon="fa-shield-halved"
                                    color={(iv.integrity_score ?? 0) >= 70 ? '#059669' : '#DC2626'}
                                />
                            </div>
                        )}

                        {/* Recording */}
                        {iv.has_recording && isStaff && (
                            <Button as="a" href={`/api/v1/recordings/download/${iv.access_token}`} target="_blank" variant="outline" size="sm" icon="fa-video">
                                View Recording
                            </Button>
                        )}
                    </>
                )}

                {/* ── Not Completed State ───────────────────────── */}
                {!isCompleted && (
                    <div style={{
                        textAlign: 'center', padding: 24, color: 'var(--muted)', fontSize: 13,
                        background: '#F8FAFC', borderRadius: 10,
                    }}>
                        <i className="fas fa-clock" style={{ fontSize: 24, marginBottom: 8, display: 'block' }} />
                        {iv.status === 'in_progress'
                            ? 'Interview is currently in progress. Results will appear after completion.'
                            : iv.status === 'cancelled'
                                ? 'This interview was cancelled.'
                                : 'Interview has not started yet. Results will appear after completion.'}
                    </div>
                )}
            </div>

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

/* ── Helper components ─────────────────────────────────────────────── */

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
    return (
        <div>
            <span style={{ color: 'var(--muted)', fontSize: 11, textTransform: 'uppercase', fontWeight: 600, display: 'block', marginBottom: 2 }}>{label}</span>
            <span style={{ fontWeight: 500, fontSize: 13 }}>{value}</span>
        </div>
    );
}

function MetricCard({ label, value, icon, color }: { label: string; value: string | number; icon: string; color: string }) {
    return (
        <div style={{
            background: '#F8FAFC', border: '1px solid var(--border)', borderRadius: 10,
            padding: 12, textAlign: 'center',
        }}>
            <i className={`fas ${icon}`} style={{ color, fontSize: 16, marginBottom: 4, display: 'block' }} />
            <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
            <div style={{ fontSize: 10, color: '#64748B', marginTop: 2, textTransform: 'uppercase', fontWeight: 600 }}>{label}</div>
        </div>
    );
}
