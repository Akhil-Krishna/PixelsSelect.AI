import { Interview, User } from '../../lib/types';
import { formatDate } from '../../lib/api';
import { StatusBadge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface InterviewTableProps {
    interviews: Interview[];
    currentUser: User;
    onViewDetail: (id: string) => void;
    onCancel: (id: string) => void;
    emptyMessage?: string;
}

export function InterviewTable({
    interviews,
    currentUser,
    onViewDetail,
    onCancel,
    emptyMessage = 'No interviews yet. Schedule one to get started.',
}: InterviewTableProps) {
    const isCandidate = currentUser.role === 'candidate';
    const isStaff = ['hr', 'admin', 'interviewer'].includes(currentUser.role);

    if (!interviews.length) {
        return (
            <div className="empty">
                <i className="fas fa-calendar" />
                <h3>No interviews yet</h3>
                <p>{emptyMessage}</p>
            </div>
        );
    }

    return (
        <div className="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Title &amp; Role</th>
                        <th>{isCandidate ? 'Scheduled' : 'Candidate'}</th>
                        <th>{isCandidate ? 'Duration' : 'Date'}</th>
                        <th>Status</th>
                        <th>Score</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {interviews.map(iv => (
                        <InterviewRow
                            key={iv.id}
                            iv={iv}
                            isCandidate={isCandidate}
                            isStaff={isStaff}
                            currentUser={currentUser}
                            onViewDetail={onViewDetail}
                            onCancel={onCancel}
                        />
                    ))}
                </tbody>
            </table>
        </div>
    );
}

interface InterviewRowProps {
    iv: Interview;
    isCandidate: boolean;
    isStaff: boolean;
    currentUser: User;
    onViewDetail: (id: string) => void;
    onCancel: (id: string) => void;
}

function InterviewRow({ iv, isCandidate, isStaff, currentUser, onViewDetail, onCancel }: InterviewRowProps) {
    const canModify = ['hr', 'admin'].includes(currentUser.role);
    const isActive = ['scheduled', 'in_progress'].includes(iv.status);
    const score = iv.overall_score;
    const passed = score != null && score >= 60;

    return (
        <tr>
            {/* Title */}
            <td>
                <div style={{ fontWeight: 600 }}>{iv.title}</div>
                <div className="text-xs text-muted">{iv.job_role}</div>
            </td>

            {/* Candidate / Scheduled */}
            <td>
                {isCandidate ? (
                    formatDate(iv.scheduled_at)
                ) : (
                    <>
                        <div style={{ fontWeight: 500 }}>{iv.candidate?.full_name || '–'}</div>
                        <div className="text-xs text-muted">{iv.candidate?.email || ''}</div>
                    </>
                )}
            </td>

            {/* Duration / Date */}
            <td>{isCandidate ? `${iv.duration_minutes}m` : formatDate(iv.scheduled_at)}</td>

            {/* Status */}
            <td><StatusBadge status={iv.status} /></td>

            {/* Score */}
            <td>
                {score != null ? (
                    <span className={passed ? 'score-pass' : 'score-fail'}>{score.toFixed(1)}%</span>
                ) : '–'}
            </td>

            {/* Actions */}
            <td>
                <div className="flex gap-2">
                    {isCandidate && isActive && (
                        <Button as="a" href={`/interview/${iv.access_token}`} target="_blank" variant="primary" size="xs" icon="fa-play">
                            Join
                        </Button>
                    )}
                    {isStaff && (
                        <Button variant="ghost" size="xs" icon="fa-eye" onClick={() => onViewDetail(iv.id)}>
                            View
                        </Button>
                    )}
                    {isStaff && isActive && (canModify || iv.is_assigned !== false) && (
                        <Button as="a" href={`/watch/${iv.access_token}`} target="_blank" variant="outline" size="xs" icon="fa-video">
                            Watch
                        </Button>
                    )}
                    {iv.status === 'completed' && isCandidate && (
                        <Button variant="ghost" size="xs" icon="fa-chart-bar" onClick={() => onViewDetail(iv.id)}>
                            Report
                        </Button>
                    )}
                    {canModify && isActive && (
                        <Button variant="danger" size="xs" icon="fa-ban" onClick={() => onCancel(iv.id)} />
                    )}
                </div>
            </td>
        </tr>
    );
}
