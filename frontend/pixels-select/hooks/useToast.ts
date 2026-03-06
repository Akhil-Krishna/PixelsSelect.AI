import { useState, useCallback } from 'react';
import { ToastItem } from '../lib/types';

export function useToast() {
    const [toasts, setToasts] = useState<ToastItem[]>([]);

    const toast = useCallback((msg: string, type: ToastItem['type'] = 'success') => {
        const id = Date.now();
        setToasts(prev => [...prev, { id, msg, type }]);
        setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500);
    }, []);

    const dismiss = useCallback((id: number) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    return { toasts, toast, dismiss };
}
