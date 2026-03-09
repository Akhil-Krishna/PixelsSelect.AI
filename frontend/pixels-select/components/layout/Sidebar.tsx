'use client';

import { User } from '../../lib/types';

interface SidebarProps {
    currentUser: User;
    activePage: string;
    onNavigate: (page: string) => void;
    onLogout: () => void;
}

interface NavItem {
    icon: string;
    label: string;
    roles: User['role'][] | null;
}

const NAV_ITEMS: NavItem[] = [
    { icon: 'fa-gauge', label: 'Dashboard', roles: null },
    { icon: 'fa-calendar-check', label: 'Interviews', roles: null },
    { icon: 'fa-clock', label: 'Upcoming', roles: null },
    { icon: 'fa-building', label: 'Departments', roles: ['admin'] },
    { icon: 'fa-users', label: 'Users', roles: ['admin'] },
];

export function Sidebar({ currentUser, activePage, onNavigate, onLogout }: SidebarProps) {
    const visibleItems = NAV_ITEMS.filter(
        item => !item.roles || item.roles.includes(currentUser.role)
    );

    return (
        <aside className="sidebar">
            {/* Logo */}
            <div className="sidebar-logo">
                <div className="logo-icon">🤖</div>
                <div>
                    <div className="logo-text">PixelsSelect</div>
                    <div className="logo-sub">AI Platform</div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="sidebar-nav">
                <span className="nav-section-label">Navigation</span>
                {visibleItems.map(item => (
                    <button
                        key={item.label}
                        className={`nav-item${activePage === item.label ? ' active' : ''}`}
                        onClick={() => onNavigate(item.label)}
                    >
                        <i className={`fas ${item.icon}`} />
                        {item.label}
                    </button>
                ))}
            </nav>

            {/* User Footer */}
            <div className="sidebar-footer">
                <div className="user-card">
                    <div className="avatar">{currentUser.full_name[0].toUpperCase()}</div>
                    <div className="user-info-text">
                        <div className="user-name">{currentUser.full_name}</div>
                        <div className="user-role-tag">{currentUser.role.toUpperCase()}</div>
                    </div>
                    <button className="logout-btn" onClick={onLogout} title="Logout">
                        <i className="fas fa-sign-out-alt" />
                    </button>
                </div>
            </div>
        </aside>
    );
}
