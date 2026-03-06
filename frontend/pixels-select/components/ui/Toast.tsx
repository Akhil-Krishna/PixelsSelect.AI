import { ToastItem } from '../../lib/types';

interface ToastContainerProps {
    toasts: ToastItem[];
    onDismiss?: (id: number) => void;
}

const BG: Record<string, string> = {
    success: '#10B981',
    error: '#EF4444',
    info: '#3B82F6',
    warning: '#F59E0B',
};

const ICON: Record<string, string> = {
    success: '✓',
    error: '✕',
    info: 'ℹ',
    warning: '⚠',
};

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
    if (!toasts.length) return null;
    return (
        <div className="toast-wrap">
            {toasts.map(t => (
                <div
                    key={t.id}
                    onClick={() => onDismiss?.(t.id)}
                    style={{
                        background: BG[t.type] || BG.info,
                        color: '#fff',
                        padding: '12px 18px',
                        borderRadius: 10,
                        fontSize: 13.5,
                        fontWeight: 500,
                        boxShadow: '0 4px 20px rgba(0,0,0,.2)',
                        maxWidth: 340,
                        animation: 'slideUp .2s ease',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                    }}
                >
                    <span style={{ fontWeight: 700, fontSize: 15 }}>{ICON[t.type]}</span>
                    <span style={{ flex: 1 }}>{t.msg}</span>
                </div>
            ))}
        </div>
    );
}
