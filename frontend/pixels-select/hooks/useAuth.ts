import { useState, useEffect } from 'react';
import { apiCall } from '../lib/api';
import { User } from '../lib/types';

export function useAuth() {
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = localStorage.getItem('token');
        if (token) {
            apiCall<User>('GET', '/users/me')
                .then(u => { setCurrentUser(u); setLoading(false); })
                .catch(() => { localStorage.removeItem('token'); setLoading(false); });
        } else {
            setLoading(false);
        }
    }, []);

    const logout = async () => {
        await apiCall('POST', '/auth/logout').catch(() => { });
        localStorage.removeItem('token');
        setCurrentUser(null);
    };

    return { currentUser, setCurrentUser, loading, logout };
}
