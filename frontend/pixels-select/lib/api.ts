export const API_BASE = '/api/v1';

function getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('token');
}

export async function apiCall<T = unknown>(
    method: string,
    path: string,
    body: object | null = null
): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(API_BASE + path, {
        method,
        headers,
        credentials: 'include',
        body: body ? JSON.stringify(body) : null,
    });

    const data = await res.json().catch(() => ({}));

    // Backend wraps errors in {error: {message, code, detail}}
    // Fall back to bare {detail} (FastAPI default) then generic status
    const errorMessage = data?.error?.message || data?.detail || `Error ${res.status}`;

    if (res.status === 401) {
        if (!path.startsWith('/auth/')) {
            if (typeof window !== 'undefined') {
                localStorage.removeItem('token');
                window.location.href = '/';
            }
        }
        throw new Error(errorMessage);
    }

    if (!res.ok) throw new Error(errorMessage);
    return data as T;
}

export async function uploadFile(path: string, file: File, fieldName = 'file'): Promise<void> {
    const token = getToken();
    const fd = new FormData();
    fd.append(fieldName, file);
    await fetch(API_BASE + path, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
        body: fd,
    });
}

export function formatDate(d: string | null | undefined): string {
    if (!d) return '–';
    return new Date(d).toLocaleString([], {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

export function formatTime(d: string | null | undefined): string {
    if (!d) return '–';
    return new Date(d).toLocaleTimeString([], {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
}
