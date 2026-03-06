interface ScoreBox {
    label: string;
    val: number;
    color: string;
}

interface CompleteOverlayProps {
    visible: boolean;
    title?: string;
    subtitle?: string;
    scores?: ScoreBox[];
}

export function CompleteOverlay({ visible, title, subtitle, scores }: CompleteOverlayProps) {
    if (!visible) return null;

    return (
        <div className="complete-ov show">
            <div className="complete-card">
                <div style={{ fontSize: 60, marginBottom: 16 }}>🏆</div>
                <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 8 }}>
                    {title || 'Interview Complete!'}
                </div>
                <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 24, lineHeight: 1.6 }}>
                    {subtitle || 'Uploading recording and calculating scores...'}
                </div>

                {scores && scores.length > 0 && (
                    <div className="score-grid" style={{ marginBottom: 24 }}>
                        {scores.map(s => (
                            <div key={s.label} className="score-box" style={{ borderTopColor: s.color }}>
                                <div className="score-val" style={{ color: s.color }}>{s.val.toFixed(1)}%</div>
                                <div className="score-lbl">{s.label}</div>
                            </div>
                        ))}
                    </div>
                )}

                <div className="flex gap-2 justify-center">
                    <button className="btn btn-outline btn-sm" onClick={() => window.close()}>
                        Close Tab
                    </button>
                    <button className="btn btn-p btn-sm" onClick={() => window.location.href = '/'}>
                        <i className="fas fa-gauge" /> Dashboard
                    </button>
                </div>
            </div>
        </div>
    );
}
