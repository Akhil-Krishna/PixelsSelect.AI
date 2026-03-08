interface StartOverlayProps {
    title: string;
    jobRole: string;
    durationMin: number;
    previewRef: React.RefObject<HTMLVideoElement | null>;
    loading: boolean;
    error?: string;
    onStart: () => void;
}

export function StartOverlay({ title, jobRole, durationMin, previewRef, loading, error, onStart }: StartOverlayProps) {
    return (
        <div className="start-ov">
            <div className="start-card">
                <div style={{ fontSize: 52, marginBottom: 10 }}>🎯</div>
                <div style={{ fontSize: 19, fontWeight: 800, marginBottom: 6 }}>{title}</div>
                <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 16 }}>
                    {jobRole} · {durationMin} min
                </div>

                {/* Camera preview */}
                <div className="preview-cam">
                    <video ref={previewRef} autoPlay muted playsInline />
                </div>

                {/* Readiness checklist */}
                <div className="checklist">
                    <CheckItem icon="fa-video" color="var(--success)" label="Camera access" />
                    <CheckItem icon="fa-microphone" color="var(--success)" label="Microphone (Whisper STT)" />
                    <CheckItem icon="fa-wifi" color="var(--success)" label="Connection ready" />
                    <CheckItem icon="fa-shield-halved" color="var(--success)" label="Integrity monitoring active" />
                </div>

                {/* Error banner */}
                {error && (
                    <div style={{
                        background: 'rgba(239,68,68,0.12)',
                        border: '1px solid rgba(239,68,68,0.4)',
                        borderRadius: 10,
                        padding: '10px 14px',
                        marginBottom: 14,
                        fontSize: 13,
                        color: '#fca5a5',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 8,
                        textAlign: 'left',
                    }}>
                        <i className="fas fa-triangle-exclamation" style={{ marginTop: 2, flexShrink: 0 }} />
                        {error}
                    </div>
                )}

                <button className="btn btn-p" onClick={onStart} disabled={loading || !!error}>
                    {loading ? (
                        <><span className="spinner" /> Starting...</>
                    ) : (
                        <><i className="fas fa-play" /> Start Interview</>
                    )}
                </button>
            </div>
        </div>
    );
}


function CheckItem({ icon, color, label, status }: {
    icon: string; color: string; label: string; status?: 'ok' | 'warn';
}) {
    return (
        <div className="chk-row">
            <i className={`fas ${icon}`} style={{ color }} />
            <span>{label}</span>
            {status === 'warn'
                ? <i className="fas fa-exclamation" style={{ marginLeft: 'auto', color: 'var(--warning)' }} />
                : <i className="fas fa-check" style={{ marginLeft: 'auto', color: 'var(--success)' }} />
            }
        </div>
    );
}
