import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'outline' | 'ghost' | 'danger' | 'success' | 'warning';
    size?: 'xs' | 'sm' | 'md';
    loading?: boolean;
    icon?: string;
    children?: React.ReactNode;
    fullWidth?: boolean;
    as?: 'button' | 'a';
    href?: string;
    target?: string;
}

export function Button({
    variant = 'primary',
    size = 'md',
    loading = false,
    icon,
    children,
    fullWidth,
    className = '',
    disabled,
    as: Tag = 'button',
    href,
    target,
    ...props
}: ButtonProps) {
    const variantClass: Record<string, string> = {
        primary: 'btn btn-primary',
        outline: 'btn btn-outline',
        ghost: 'btn btn-ghost',
        danger: 'btn btn-danger',
        success: 'btn btn-success',
        warning: 'btn btn-warning',
    };

    const sizeClass: Record<string, string> = {
        xs: 'btn-xs',
        sm: 'btn-sm',
        md: '',
    };

    const cls = [variantClass[variant], sizeClass[size], fullWidth ? 'w-full' : '', className]
        .filter(Boolean)
        .join(' ');

    if (Tag === 'a') {
        return (
            <a href={href} target={target} className={cls}>
                {icon && <i className={`fas ${icon}`} />}
                {children}
            </a>
        );
    }

    return (
        <button className={cls} disabled={disabled || loading} {...props}>
            {loading && <span className="spinner" />}
            {!loading && icon && <i className={`fas ${icon}`} />}
            {children}
        </button>
    );
}
