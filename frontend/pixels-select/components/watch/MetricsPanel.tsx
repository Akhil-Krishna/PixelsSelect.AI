import { Metrics } from '../../lib/types';

interface MetricsPanelProps {
    sessionInfo: {
        candidateName: string;
        jobRole: string;
        status: string;
        aiPaused: boolean;
        durationMin: number;
    };
    metrics: Metrics;
    counters: {
        totalMsgs: number;
        aiQ: number;
        candR: number;
    };
    recStatus: string;
    recLink: string;
}

function pct(v?: number) {
    return v != null ? v.toFixed(1) + '%' : '-';
}

export function MetricsPanel({ sessionInfo, metrics, counters, recStatus, recLink }: MetricsPanelProps) {
    const risk = metrics.cheating_score || 0;

    return (
        <div className="left-col">
            {/* Session Info */}
            <Section title="Session Info">
                <Row label="Candidate" value={sessionInfo.candidateName || '-'} />
                <Row label="Role" value={sessionInfo.jobRole || '-'} />
                <Row label="Status" value={sessionInfo.status.replace('_', ' ')} />
                <Row label="AI Mode" value={sessionInfo.aiPaused ? 'Paused' : 'Active'}
                    valueColor={sessionInfo.aiPaused ? 'var(--warning)' : 'var(--success)'} />
                <Row label="Duration" value={`${sessionInfo.durationMin} min`} />
            </Section>

            {/* Vision Metrics */}
            <div className="metrics-box">
                <div className="metrics-title">
                    <span><i className="fas fa-chart-line" style={{ color: 'var(--primary)' }} /> Vision Metrics</span>
                    <span style={{ fontSize: 9, color: 'var(--muted)' }}>{metrics.frames_analyzed || 0} frames</span>
                </div>
                <MeterRow label="Confidence" value={metrics.confidence} color="#4F46E5" textColor="#818CF8" />
                <MeterRow label="Engagement" value={metrics.engagement} color="#10B981" textColor="#34D399" />
                <MeterRow label="Stress" value={metrics.stress} color="#F59E0B" textColor="#FCD34D" />
                <MeterRow label="Integrity Risk" value={risk} color="#EF4444" textColor="#FCA5A5" />
                <div className="metric-row" style={{ marginTop: 4 }}>
                    <span className="metric-lbl">Dominant Emotion</span>
                    <span className="metric-val" style={{ color: '#A5B4FC' }}>{metrics.dominant_emotion || '-'}</span>
                </div>
                <div className="metric-row">
                    <span className="metric-lbl">Faces in frame</span>
                    <span className="metric-val">{metrics.face_count ?? '-'}</span>
                </div>
                <div className="metric-row">
                    <span className="metric-lbl">Gaze</span>
                    <span className="metric-val" style={{ color: metrics.gaze_ok ? 'var(--success)' : 'var(--danger)' }}>
                        {metrics.gaze_ok != null ? (metrics.gaze_ok ? 'OK' : 'Away') : '-'}
                    </span>
                </div>
            </div>

            {/* Live Scores */}
            <Section title="Live Scores">
                <div className="score-grid">
                    {[
                        { id: 'conf', val: metrics.confidence, color: '#818CF8', top: '#4F46E5', lbl: 'Confidence' },
                        { id: 'eng', val: metrics.engagement, color: '#34D399', top: '#10B981', lbl: 'Engagement' },
                        { id: 'str', val: metrics.stress, color: '#FCD34D', top: '#F59E0B', lbl: 'Stress' },
                        {
                            id: 'risk', val: risk,
                            color: risk > 30 ? 'var(--danger)' : risk > 15 ? 'var(--warning)' : 'var(--success)',
                            top: '#EF4444', lbl: 'Risk Score',
                        },
                    ].map(s => (
                        <div key={s.id} className="score-card" style={{ borderTopColor: s.top }}>
                            <div className="score-num" style={{ color: s.color }}>
                                {s.val != null ? Math.round(s.val) + '%' : '-'}
                            </div>
                            <div className="score-lbl">{s.lbl}</div>
                        </div>
                    ))}
                </div>
            </Section>

            {/* Integrity Counters */}
            <Section title="Integrity Counters">
                <Row label="Away from cam" icon="fa-eye-slash" iconColor="var(--warning)"
                    value={metrics.look_away_count || 0} valueColor="var(--warning)" />
                <Row label="Multiple faces" icon="fa-users" iconColor="var(--danger)"
                    value={metrics.multi_face_count || 0} valueColor="var(--danger)" />
                <Row label="Tab switches" icon="fa-arrow-right-arrow-left" iconColor="var(--warning)"
                    value={metrics.tab_switches || 0} valueColor="var(--warning)" />
                <Row label="Frames analyzed" icon="fa-film" iconColor="var(--muted)"
                    value={metrics.frames_analyzed || 0} valueColor="var(--muted)" />
            </Section>

            {/* Chat Activity */}
            <Section title="Chat Activity">
                <Row label="Total messages" value={counters.totalMsgs} />
                <Row label="AI questions" value={counters.aiQ} />
                <Row label="Candidate replies" value={counters.candR} />
            </Section>

            {/* Recording */}
            <Section title="Recording">
                <Row label="Status" value={recStatus} valueColor={recLink ? 'var(--success)' : 'var(--muted)'} />
                {recLink && (
                    <div style={{ marginTop: 8 }}>
                        <a href={recLink} target="_blank" rel="noopener" className="btn btn-p"
                            style={{ fontSize: 11, padding: '7px 14px' }}>
                            <i className="fas fa-play" /> Watch Recording
                        </a>
                    </div>
                )}
            </Section>
        </div>
    );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="r-sec">
            <div className="r-title">{title}</div>
            {children}
        </div>
    );
}

function Row({ label, value, valueColor, icon, iconColor }: {
    label: string;
    value: string | number;
    valueColor?: string;
    icon?: string;
    iconColor?: string;
}) {
    return (
        <div className="r-row">
            <span>
                {icon && <i className={`fas ${icon}`} style={{ color: iconColor, marginRight: 5 }} />}
                {label}
            </span>
            <span className="r-val" style={valueColor ? { color: valueColor } : {}}>{value}</span>
        </div>
    );
}

function MeterRow({ label, value, color, textColor }: {
    label: string; value?: number; color: string; textColor: string;
}) {
    return (
        <div className="metric-row">
            <div>
                <div className="metric-lbl">{label}</div>
                <div className="meter">
                    <div className="meter-fill" style={{ background: color, width: `${value || 0}%` }} />
                </div>
            </div>
            <span className="metric-val" style={{ color: textColor }}>{pct(value)}</span>
        </div>
    );
}
