'use client';

import { useState, useEffect, useRef } from 'react';
import { apiCall } from '../../lib/api';
import { Department, QuestionBank } from '../../lib/types';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';

const API_BASE = '/api/v1';

export function DepartmentPanel() {
    const [departments, setDepartments] = useState<Department[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Create form
    const [newName, setNewName] = useState('');
    const [creating, setCreating] = useState(false);

    // QB upload
    const [activeDeptId, setActiveDeptId] = useState<string | null>(null);
    const [qbs, setQbs] = useState<QuestionBank[]>([]);
    const [qbLabel, setQbLabel] = useState('');
    const [qbFile, setQbFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const fileRef = useRef<HTMLInputElement>(null);

    const load = async () => {
        setLoading(true);
        try {
            const list = await apiCall<Department[]>('GET', '/departments');
            setDepartments(list);
        } catch {
            setError('Failed to load departments');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const loadQBs = async (deptId: string) => {
        try {
            const list = await apiCall<QuestionBank[]>('GET', `/departments/${deptId}/question-banks`);
            setQbs(list);
        } catch {
            setQbs([]);
        }
    };

    const handleCreate = async () => {
        if (!newName.trim()) return;
        setCreating(true);
        setError('');
        try {
            await apiCall('POST', '/departments', { name: newName.trim() });
            setNewName('');
            await load();
        } catch (e: unknown) {
            setError((e as Error).message);
        } finally {
            setCreating(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this department? All its question banks will also be deleted.')) return;
        try {
            await apiCall('DELETE', `/departments/${id}`);
            if (activeDeptId === id) { setActiveDeptId(null); setQbs([]); }
            await load();
        } catch (e: unknown) {
            setError((e as Error).message);
        }
    };

    const handleUploadQB = async () => {
        if (!activeDeptId || !qbFile || !qbLabel.trim()) return;
        setUploading(true);
        setError('');
        try {
            const formData = new FormData();
            formData.append('file', qbFile);
            const res = await fetch(
                `${API_BASE}/departments/${activeDeptId}/question-banks?label=${encodeURIComponent(qbLabel.trim())}`,
                { method: 'POST', body: formData, credentials: 'include' }
            );
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail || 'Upload failed');
            }
            setQbLabel('');
            setQbFile(null);
            if (fileRef.current) fileRef.current.value = '';
            await loadQBs(activeDeptId);
        } catch (e: unknown) {
            setError((e as Error).message);
        } finally {
            setUploading(false);
        }
    };

    const handleDeleteQB = async (qbId: string) => {
        try {
            await apiCall('DELETE', `/departments/question-banks/${qbId}`);
            if (activeDeptId) await loadQBs(activeDeptId);
        } catch (e: unknown) {
            setError((e as Error).message);
        }
    };

    const selectDept = (deptId: string) => {
        if (activeDeptId === deptId) {
            setActiveDeptId(null);
            setQbs([]);
        } else {
            setActiveDeptId(deptId);
            loadQBs(deptId);
        }
    };

    if (loading) return <p className="text-muted" style={{ padding: 16 }}>Loading departments…</p>;

    return (
        <div>
            {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}

            {/* Create Department */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <input
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    placeholder="Department name (e.g. Backend, Frontend, QA)"
                    style={{ flex: 1 }}
                    onKeyDown={e => { if (e.key === 'Enter') handleCreate(); }}
                />
                <Button variant="primary" size="sm" icon="fa-plus" loading={creating} onClick={handleCreate}>
                    Create
                </Button>
            </div>

            {/* Department List */}
            {departments.length === 0 ? (
                <p className="text-muted text-sm" style={{ padding: 16, textAlign: 'center' }}>
                    No departments yet. Create one above.
                </p>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {departments.map(dept => (
                        <div key={dept.id}>
                            <div style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                padding: '12px 16px', borderRadius: 8,
                                background: activeDeptId === dept.id ? 'var(--primary-alpha, rgba(79,70,229,0.08))' : 'var(--bg-secondary, #f8f9fa)',
                                border: activeDeptId === dept.id ? '1px solid var(--primary)' : '1px solid transparent',
                                cursor: 'pointer', transition: 'all 0.2s',
                            }} onClick={() => selectDept(dept.id)}>
                                <div>
                                    <strong style={{ fontSize: 14 }}><i className="fas fa-building" style={{ marginRight: 8, color: 'var(--primary)' }} />{dept.name}</strong>
                                    {dept.lead_name && <span className="text-xs text-muted" style={{ marginLeft: 12 }}>Lead: {dept.lead_name}</span>}
                                </div>
                                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                                    <span className="text-xs text-muted">
                                        {activeDeptId === dept.id ? 'Click to collapse' : 'Click to manage QBs'}
                                    </span>
                                    <button onClick={e => { e.stopPropagation(); handleDelete(dept.id); }}
                                        style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 14 }}
                                        title="Delete department">
                                        <i className="fas fa-trash" />
                                    </button>
                                </div>
                            </div>

                            {/* Question Banks Panel */}
                            {activeDeptId === dept.id && (
                                <div style={{
                                    margin: '8px 0 8px 24px', padding: 16,
                                    background: 'var(--bg-secondary, #f8f9fa)', borderRadius: 8,
                                    borderLeft: '3px solid var(--primary)',
                                }}>
                                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12 }}>
                                        <i className="fas fa-file-lines" style={{ marginRight: 6 }} />
                                        Question Banks
                                    </div>

                                    {/* Upload form */}
                                    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                                        <input
                                            value={qbLabel}
                                            onChange={e => setQbLabel(e.target.value)}
                                            placeholder="Label (e.g. Database Senior)"
                                            style={{ flex: '1 1 160px', minWidth: 120 }}
                                        />
                                        <input
                                            ref={fileRef}
                                            type="file"
                                            accept=".txt,.csv"
                                            onChange={e => setQbFile(e.target.files?.[0] || null)}
                                            style={{ flex: '1 1 160px', minWidth: 120 }}
                                        />
                                        <Button variant="primary" size="sm" icon="fa-upload" loading={uploading}
                                            onClick={handleUploadQB}>
                                            Upload
                                        </Button>
                                    </div>

                                    {/* QB list */}
                                    {qbs.length === 0 ? (
                                        <p className="text-muted text-sm">No question banks uploaded yet.</p>
                                    ) : (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                            {qbs.map(qb => (
                                                <div key={qb.id} style={{
                                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                                    padding: '8px 12px', background: '#fff', borderRadius: 6,
                                                    border: '1px solid #e5e7eb',
                                                }}>
                                                    <div>
                                                        <strong style={{ fontSize: 13 }}>{qb.label}</strong>
                                                        <span className="text-xs text-muted" style={{ marginLeft: 8 }}>{qb.file_name}</span>
                                                    </div>
                                                    <button onClick={() => handleDeleteQB(qb.id)}
                                                        style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 12 }}
                                                        title="Delete question bank">
                                                        <i className="fas fa-times" />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
