import { useState, useEffect } from 'react';
import { apiCall } from '../lib/api';
import { User } from '../lib/types';

export function useAuth() {
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Auth is fully cookie-based — no localStorage token needed.
        // The httpOnly cookie is sent automatically with credentials: 'include'.
        apiCall<User>('GET', '/users/me')
            .then(u => { setCurrentUser(u); setLoading(false); })
            .catch(() => { setLoading(false); });
    }, []);

    const logout = async () => {
        await apiCall('POST', '/auth/logout').catch(() => { });
        setCurrentUser(null);
    };

    return { currentUser, setCurrentUser, loading, logout };
}
