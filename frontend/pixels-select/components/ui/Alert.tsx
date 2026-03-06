interface AlertProps {
    type?: 'error' | 'success' | 'info' | 'warning';
    children: React.ReactNode;
    onClose?: () => void;
}

const ICONS: Record<string, string> = {
    error: 'fa-circle-xmark',
    success: 'fa-check-circle',
    info: 'fa-info-circle',
    warning: 'fa-triangle-exclamation',
};

export function Alert({ type = 'info', children, onClose }: AlertProps) {
    if (!children) return null;
    return (
        <div className={`alert alert-${type}`}>
            <i className={`fas ${ICONS[type]}`} />
            <span style={{ flex: 1 }}>{children}</span>
            {onClose && (
                <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', opacity: 0.6, fontSize: 16 }}>×</button>
            )}
        </div>
    );
}
