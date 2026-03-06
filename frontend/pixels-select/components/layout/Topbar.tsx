'use client';

import { User } from '../../lib/types';
import { Button } from '../ui/Button';

interface TopbarProps {
    title: string;
    currentUser: User;
    activePage: string;
    onSchedule?: () => void;
    onAddUser?: () => void;
}

export function Topbar({ title, currentUser, activePage, onSchedule, onAddUser }: TopbarProps) {
    const canSchedule = ['hr', 'admin'].includes(currentUser.role);

    return (
        <div className="topbar">
            <div className="topbar-left">
                <div className="topbar-title">{title}</div>
            </div>
            <div className="topbar-right">
                {activePage === 'Interviews' && canSchedule && onSchedule && (
                    <Button variant="primary" size="sm" icon="fa-plus" onClick={onSchedule}>
                        Schedule Interview
                    </Button>
                )}
                {activePage === 'Users' && onAddUser && (
                    <Button variant="primary" size="sm" icon="fa-plus" onClick={onAddUser}>
                        Add User
                    </Button>
                )}
            </div>
        </div>
    );
}
