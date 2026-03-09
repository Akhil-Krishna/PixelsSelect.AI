export const API_BASE = '/api/v1';

export async function apiCall<T = unknown>(
    method: string,
    path: string,
    body: object | null = null
): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };

    const res = await fetch(API_BASE + path, {
        method,
        headers,
        credentials: 'include',   // Always send httpOnly cookie — no localStorage token
        body: body ? JSON.stringify(body) : null,
    });

    const data = await res.json().catch(() => ({}));

    // Backend wraps errors in {error: {message, code, detail}}
    // Fall back to bare {detail} (FastAPI default) then generic status
    const errorMessage = data?.error?.message || data?.detail || `Error ${res.status}`;

    if (res.status === 401) {
        // Just throw — the caller (useAuth / page.tsx) handles 401 by showing
        // the login form. DO NOT redirect to '/' here; that causes an infinite
        // reload loop since '/' itself calls /users/me on every mount.
        throw new Error(errorMessage);
    }

    if (!res.ok) throw new Error(errorMessage);
    return data as T;
}

export async function uploadFile(path: string, file: File, fieldName = 'file'): Promise<void> {
    const fd = new FormData();
    fd.append(fieldName, file);
    const res = await fetch(API_BASE + path, {
        method: 'POST',
        credentials: 'include',
        body: fd,
    });
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const errorMessage = data?.error?.message || data?.detail || `Error ${res.status}`;
        throw new Error(errorMessage);
    }
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
