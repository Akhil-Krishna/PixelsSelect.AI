'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiCall } from '../lib/api';
import { User, Interview, StatCard } from '../lib/types';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';

// Layout
import { Sidebar } from '../components/layout/Sidebar';
import { Topbar } from '../components/layout/Topbar';

// Landing
import { LandingPage } from '../components/landing/LandingPage';

// Auth
import { LoginForm } from '../components/auth/LoginForm';
import { OrgRegisterForm } from '../components/auth/RegisterForm';
import { ForgotPasswordForm } from '../components/auth/ForgotPasswordForm';

// Dashboard
import { StatsRow } from '../components/dashboard/StatsRow';
import { InterviewTable } from '../components/dashboard/InterviewTable';
import { DepartmentPanel } from '../components/dashboard/DepartmentPanel';
import { ProfilePage } from '../components/dashboard/ProfilePage';

// Modals
import { ScheduleModal } from '../components/modals/ScheduleModal';
import { AddUserModal } from '../components/modals/AddUserModal';
import { DetailModal } from '../components/modals/DetailModal';

// UI
import { ToastContainer } from '../components/ui/Toast';
import { RoleBadge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

type AppPage = 'Dashboard' | 'Interviews' | 'Upcoming' | 'Departments' | 'Users' | 'Profile';

// ── Auth Page ──────────────────────────────────────────────────────────────────
function AuthPage({ onSuccess, initialMode = 'login', onBackToLanding }: { onSuccess: (user: User) => void; initialMode?: 'login' | 'register'; onBackToLanding: () => void }) {
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>(initialMode);

  const headings: Record<typeof mode, string> = {
    login: 'Welcome back',
    register: 'Register Organisation',
    forgot: 'Forgot Password',
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-icon">🤖</div>
          <div className="auth-title">PixelsSelect.AI</div>
          <div className="auth-sub">{headings[mode]}</div>
        </div>

        {mode === 'login' && (
          <LoginForm
            onSuccess={onSuccess}
            onSwitchToRegister={() => setMode('register')}
            onForgotPassword={() => setMode('forgot')}
          />
        )}
        {mode === 'register' && (
          <OrgRegisterForm
            onSwitchToLogin={() => setMode('login')}
          />
        )}
        {mode === 'forgot' && (
          <ForgotPasswordForm
            onBack={() => setMode('login')}
          />
        )}

        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <button
            onClick={onBackToLanding}
            style={{
              background: 'none', border: 'none', color: 'var(--muted)',
              cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
            }}
          >
            ← Back to home
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Users Page ─────────────────────────────────────────────────────────────────
function UsersPage({ onAddUser }: { onAddUser: () => void }) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await apiCall<User[]>('GET', '/users');
      setUsers(data);
    } catch { }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleStatus = async (u: User) => {
    try {
      await apiCall('PATCH', `/users/${u.id}`, { is_active: !u.is_active });
      load();
    } catch (e) { console.error(e); }
  };

  if (loading) {
    return <div className="empty"><i className="fas fa-spinner fa-spin" /><h3>Loading users...</h3></div>;
  }

  if (!users.length) {
    return (
      <div className="empty">
        <i className="fas fa-users" />
        <h3>No users yet</h3>
        <p>Add your first user to get started</p>
        <Button variant="primary" size="sm" icon="fa-plus" onClick={onAddUser} style={{ marginTop: 16 }}>
          Add User
        </Button>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Organisation</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map(u => (
            <tr key={u.id}>
              <td><strong>{u.full_name}</strong></td>
              <td className="text-muted">{u.email}</td>
              <td><RoleBadge role={u.role} /></td>
              <td className="text-sm text-muted">{u.organisation?.name || '–'}</td>
              <td>
                <StatusBadge status={u.is_active ? 'completed' : 'cancelled'} />
              </td>
              <td>
                <Button variant="ghost" size="xs" onClick={() => toggleStatus(u)}>
                  {u.is_active ? 'Disable' : 'Enable'}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Loading Screen ─────────────────────────────────────────────────────────────
function LoadingScreen() {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#F1F5F9', flexDirection: 'column', gap: 16,
    }}>
      <div style={{ fontSize: 52 }}>🤖</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: '#0F172A' }}>PixelsSelect.AI</div>
      <div style={{ color: '#64748B', fontSize: 13 }}>Loading platform...</div>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────────
export default function HomePage() {
  const { currentUser, setCurrentUser, loading, logout } = useAuth();
  const { toasts, toast, dismiss } = useToast();

  const [page, setPage] = useState<AppPage>('Dashboard');
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [detailIv, setDetailIv] = useState<Interview | null>(null);
  const [showSchedule, setShowSchedule] = useState(false);
  const [showAddUser, setShowAddUser] = useState(false);
  const [showAddUserForUsers, setShowAddUserForUsers] = useState(false);
  const [showLanding, setShowLanding] = useState(true);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');

  const loadInterviews = useCallback(async () => {
    try {
      const data = await apiCall<Interview[]>('GET', '/interviews');
      setInterviews(data);
    } catch { }
  }, []);

  useEffect(() => {
    if (currentUser) loadInterviews();
  }, [currentUser, loadInterviews]);

  const handleAuthSuccess = (user: User) => {
    // Token is stored in httpOnly cookie by the server.
    // No localStorage needed.
    setCurrentUser(user);
  };

  const handleScheduleSuccess = () => {
    loadInterviews();
    toast('Interview scheduled and invite sent!');
  };

  const handleCancel = async (id: string) => {
    if (!confirm('Cancel this interview?')) return;
    try {
      await apiCall('DELETE', `/interviews/${id}`);
      toast('Interview cancelled');
      loadInterviews();
    } catch (e: unknown) {
      toast((e as Error).message, 'error');
    }
  };

  const handleViewDetail = (id: string) => {
    const iv = interviews.find(i => i.id === id);
    if (iv) setDetailIv(iv);
  };

  // Build stats from interviews
  const stats: StatCard[] = currentUser ? [
    {
      icon: 'fa-calendar-alt', bg: '#EEF2FF', ic: '#4F46E5',
      val: interviews.length,
      lbl: currentUser.role === 'candidate' ? 'My Interviews' : 'Total',
    },
    {
      icon: 'fa-clock', bg: '#FEF3C7', ic: '#D97706',
      val: interviews.filter(i => i.status === 'scheduled').length,
      lbl: 'Scheduled',
    },
    {
      icon: 'fa-check-circle', bg: '#DCFCE7', ic: '#16A34A',
      val: interviews.filter(i => i.status === 'completed').length,
      lbl: 'Completed',
    },
    {
      icon: 'fa-trophy', bg: '#FEF9C3', ic: '#CA8A04',
      val: interviews.filter(i => i.passed === true).length,
      lbl: 'Passed',
    },
  ] : [];

  if (loading) return <LoadingScreen />;

  // ── Landing / Authentication View ──
  if (!currentUser) {
    if (showLanding) {
      return (
        <LandingPage
          onLogin={() => { setAuthMode('login'); setShowLanding(false); }}
          onRegister={() => { setAuthMode('register'); setShowLanding(false); }}
        />
      );
    }
    return <AuthPage onSuccess={handleAuthSuccess} initialMode={authMode} onBackToLanding={() => setShowLanding(true)} />;
  }

  const isAdminOrHR = ['hr', 'admin'].includes(currentUser.role);

  // ── App View ──
  return (
    <>
      <Sidebar
        currentUser={currentUser}
        activePage={page}
        onNavigate={p => setPage(p as AppPage)}
        onLogout={logout}
      />

      <main className="main">
        <Topbar
          title={page}
          currentUser={currentUser}
          activePage={page}
          onSchedule={() => setShowSchedule(true)}
          onAddUser={() => setShowAddUserForUsers(true)}
        />

        <div className="content">
          {/* ── Dashboard ── */}
          {page === 'Dashboard' && (
            <>
              <StatsRow stats={stats} />
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Recent Interviews</div>
                    <div className="card-subtitle">Your latest interview activity</div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setPage('Interviews')}>
                    View all →
                  </Button>
                </div>
                <InterviewTable
                  interviews={interviews.slice(0, 6)}
                  currentUser={currentUser}
                  onViewDetail={handleViewDetail}
                  onCancel={handleCancel}
                />
              </div>
            </>
          )}

          {/* ── Interviews ── */}
          {page === 'Interviews' && (
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title">All Interviews</div>
                  <div className="card-subtitle">{interviews.length} total</div>
                </div>
                {isAdminOrHR && (
                  <Button variant="primary" size="sm" icon="fa-plus" onClick={() => setShowSchedule(true)}>
                    Schedule Interview
                  </Button>
                )}
              </div>
              <InterviewTable
                interviews={interviews}
                currentUser={currentUser}
                onViewDetail={handleViewDetail}
                onCancel={handleCancel}
                emptyMessage={isAdminOrHR ? 'Schedule an interview to get started.' : 'No interviews assigned to you yet.'}
              />
            </div>
          )}

          {/* ── Upcoming ── */}
          {page === 'Upcoming' && (() => {
            const upcoming = interviews
              .filter(i => i.status === 'scheduled' || i.status === 'in_progress')
              .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime());
            return (
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Upcoming Interviews</div>
                    <div className="card-subtitle">{upcoming.length} scheduled</div>
                  </div>
                  {isAdminOrHR && (
                    <Button variant="primary" size="sm" icon="fa-plus" onClick={() => setShowSchedule(true)}>
                      Schedule Interview
                    </Button>
                  )}
                </div>
                <InterviewTable
                  interviews={upcoming}
                  currentUser={currentUser}
                  onViewDetail={handleViewDetail}
                  onCancel={handleCancel}
                  emptyMessage="No upcoming interviews. All caught up!"
                />
              </div>
            );
          })()}

          {/* ── Users ── */}
          {page === 'Users' && (
            <div className="card">
              <div className="card-header">
                <div className="card-title">User Management</div>
                <Button variant="primary" size="sm" icon="fa-plus" onClick={() => setShowAddUserForUsers(true)}>
                  Add User
                </Button>
              </div>
              <UsersPage onAddUser={() => setShowAddUserForUsers(true)} />
            </div>
          )}

          {/* ── Departments ── */}
          {page === 'Departments' && (
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title">Department Management</div>
                  <div className="card-subtitle">Create departments and manage question banks</div>
                </div>
              </div>
              <DepartmentPanel />
            </div>
          )}

          {/* ── Profile ── */}
          {page === 'Profile' && (
            <ProfilePage
              currentUser={currentUser}
              onUserUpdated={(u) => setCurrentUser(u)}
            />
          )}
        </div>
      </main>

      {/* ── Modals ── */}
      <ScheduleModal
        open={showSchedule}
        onClose={() => setShowSchedule(false)}
        onSuccess={handleScheduleSuccess}
      />

      <AddUserModal
        open={showAddUser || showAddUserForUsers}
        onClose={() => { setShowAddUser(false); setShowAddUserForUsers(false); }}
        onSuccess={() => { toast('User created successfully'); }}
      />

      <DetailModal
        interview={detailIv}
        currentUserRole={currentUser.role}
        onClose={() => setDetailIv(null)}
      />


      {/* ── Toasts ── */}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </>
  );
}
