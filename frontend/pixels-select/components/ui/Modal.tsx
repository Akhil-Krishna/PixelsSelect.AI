interface ModalProps {
    open: boolean;
    onClose: () => void;
    title: React.ReactNode;
    children: React.ReactNode;
    size?: 'sm' | 'md' | 'lg';
}

export function Modal({ open, onClose, title, children, size = 'md' }: ModalProps) {
    if (!open) return null;

    const maxWidth = size === 'sm' ? 420 : size === 'lg' ? 720 : 580;

    return (
        <div className="overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
            <div className={`modal${size === 'lg' ? ' modal-lg' : ''}`} style={{ maxWidth }}>
                <div className="modal-header">
                    <div className="modal-title">{title}</div>
                    <button className="modal-close" onClick={onClose}>×</button>
                </div>
                {children}
            </div>
        </div>
    );
}
