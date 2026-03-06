import { FlagItem } from '../../lib/types';

interface MonitorPanelProps {
    title: string;
    qCount: number;
    rCount: number;
    tabSwitches: number;
    lookAway: number;
    multiFace: number;
    faceCount: number;
    gaze: string;
    emotion: string;
    flags: FlagItem[];
}

export function MonitorPanel({
    title, qCount, rCount, tabSwitches,
    lookAway, multiFace, faceCount, gaze, emotion, flags,
}: MonitorPanelProps) {
    return (
        <div className="left-panel">
            <div className="monitor-hdr">
                <i className="fas fa-shield-halved" style={{ color: 'var(--warning)' }} />
                Interview Info
            </div>

            <InfoSection title="Room">
                <InfoRow label="Title" value={title.slice(0, 20)} />
                <InfoRow label="Your role" value="Candidate" />
            </InfoSection>

            <InfoSection title="Session">
                <InfoRow label="AI Questions" value={qCount} />
                <InfoRow label="Your Replies" value={rCount} />
                <InfoRow label="Tab Switches" value={tabSwitches} valueColor="var(--warning)" />
            </InfoSection>

            <InfoSection title="Integrity">
                <InfoRow label="Away from cam" value={lookAway} valueColor="var(--danger)" />
                <InfoRow label="Multiple faces" value={multiFace} valueColor="var(--danger)" />
            </InfoSection>

            <InfoSection title="Vision">
                <InfoRow label="Faces" value={faceCount} />
                <InfoRow label="Gaze" value={gaze} valueColor={gaze === 'OK' ? 'var(--success)' : 'var(--danger)'} />
                <InfoRow label="Emotion" value={emotion} />
            </InfoSection>

            <InfoSection title="Tips" noBorder>
                <TipsList tips={[
                    'Keep face visible & centred',
                    'Speak clearly',
                    'Use code editor for coding Qs',
                    "Don't switch browser tabs",
                    'Think aloud for better scoring',
                ]} />
            </InfoSection>

            {/* Integrity Alerts */}
            <div className="flags-section">
                <div className="flags-title">
                    <span><i className="fas fa-triangle-exclamation" /> Alerts</span>
                    <span style={{ background: '#334155', padding: '1px 7px', borderRadius: 10, fontSize: 9 }}>
                        {flags.length}
                    </span>
                </div>
                {flags.length === 0 ? (
                    <div className="flags-empty">
                        <i className="fas fa-check-circle" style={{ fontSize: 22, display: 'block', marginBottom: 7, color: 'var(--success)' }} />
                        No alerts — stay focused!
                    </div>
                ) : (
                    flags.map(f => (
                        <div key={f.id} className={`flag-item flag-${f.type}`}>
                            <i className={`fas ${f.icon} flag-icon`} />
                            <div className="flag-text">
                                {f.text}
                                <span className="flag-time">{f.time}</span>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

function InfoSection({ title, children, noBorder }: { title: string; children: React.ReactNode; noBorder?: boolean }) {
    return (
        <div className="rp-sec" style={noBorder ? { borderBottom: 'none' } : {}}>
            <div className="rp-title">{title}</div>
            {children}
        </div>
    );
}

function InfoRow({ label, value, valueColor }: { label: string; value: string | number; valueColor?: string }) {
    return (
        <div className="rp-row">
            <span>{label}</span>
            <span className="rp-val" style={valueColor ? { color: valueColor } : {}}>
                {value}
            </span>
        </div>
    );
}

function TipsList({ tips }: { tips: string[] }) {
    return (
        <div style={{ fontSize: 11.5, color: 'var(--muted)', lineHeight: 2.1 }}>
            {tips.map((tip, i) => <div key={i}>{tip}</div>)}
        </div>
    );
}
