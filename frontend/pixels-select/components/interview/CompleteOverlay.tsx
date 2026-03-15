'use client';

interface CompleteOverlayProps {
    visible: boolean;
}

export function CompleteOverlay({ visible }: CompleteOverlayProps) {
    if (!visible) return null;

    return (
        <div className="complete-ov show">
            <div className="complete-card">
                <div style={{ fontSize: 60, marginBottom: 16 }}>✅</div>
                <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 8, color: 'var(--foreground)' }}>
                    Interview Complete!
                </div>
                <div style={{
                    fontSize: 14, color: 'var(--muted)', marginBottom: 24,
                    lineHeight: 1.7, maxWidth: 400, margin: '0 auto 24px',
                }}>
                    Thank you for completing the interview. Your interview report has been
                    generated and will be reviewed by our HR team. They will contact you
                    regarding the next steps.
                </div>

                <div className="flex gap-2 justify-center">
                    <button className="btn btn-outline btn-sm" onClick={() => window.close()}>
                        Close Tab
                    </button>
                    <button className="btn btn-p btn-sm" onClick={() => window.location.href = '/'}>
                        <i className="fas fa-home" /> Home
                    </button>
                </div>
            </div>
        </div>
    );
}
