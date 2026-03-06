interface BadgeProps {
    variant: string;
    children: React.ReactNode;
    dot?: boolean;
}

export function Badge({ variant, children, dot }: BadgeProps) {
    return (
        <span className={`badge badge-${variant}`}>
            {dot && <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />}
            {children}
        </span>
    );
}

export function StatusBadge({ status }: { status: string }) {
    const label = status.replace(/_/g, ' ');
    return <Badge variant={status}>{label}</Badge>;
}

export function RoleBadge({ role }: { role: string }) {
    return <Badge variant={role}>{role}</Badge>;
}
