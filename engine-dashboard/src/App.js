import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  BrowserRouter as Router,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom';
import {
  Activity,
  Database,
  Flame,
  Moon,
  ShieldCheck,
  Sun,
  X,
} from 'lucide-react';
import Navigation from './components/Navigation';
import DashboardPage from './pages/DashboardPage';
import ChatPage from './pages/ChatPage';
import LoginPage from './pages/LoginPage';
import { AuthContext, AuthProvider } from './context/AuthContext';

export const TelemetryContext = createContext(null);

const INITIAL_SESSION_STATE = {
  phase: 'AWAITING_INPUT',
  tokensSaved: 0,
  tokensUsed: { m1: 0, m2: 0 },
  memoryAnchors: [],
  tokenHistory: [],
  intentDistribution: {},
  chatHistory: [],
  systemLogs: [],
  lastLatencyMs: null,
  activeSessionId: '',
  sessions: [],
};

function ConfirmDialog({ open, title, description, confirmLabel, busy, onCancel, onConfirm }) {
  const cancelButtonRef = useRef(null);
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    cancelButtonRef.current?.focus();

    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !busy) onCancel();
      if (event.key !== 'Tab') return;
      const focusable = dialogRef.current?.querySelectorAll('button:not(:disabled)');
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [busy, onCancel, open]);

  if (!open) return null;

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={busy ? undefined : onCancel}>
      <section
        aria-describedby="confirm-dialog-description"
        aria-labelledby="confirm-dialog-title"
        aria-modal="true"
        className="dialog-card"
        onMouseDown={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
      >
        <div className="dialog-icon dialog-icon-danger" aria-hidden="true">
          <Flame size={22} />
        </div>
        <div>
          <h2 id="confirm-dialog-title" className="dialog-title">{title}</h2>
          <p id="confirm-dialog-description" className="dialog-description">{description}</p>
        </div>
        <div className="dialog-actions">
          <button
            className="button button-secondary"
            disabled={busy}
            onClick={onCancel}
            ref={cancelButtonRef}
            type="button"
          >
            Cancel
          </button>
          <button
            className="button button-danger"
            disabled={busy}
            onClick={onConfirm}
            type="button"
          >
            {busy ? <span className="spinner" aria-hidden="true" /> : <Flame size={16} />}
            {busy ? 'Burning session…' : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}

function AppShell() {
  const location = useLocation();
  const [sessionState, setSessionState] = useState(INITIAL_SESSION_STATE);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [notice, setNotice] = useState('');
  const [burnDialogOpen, setBurnDialogOpen] = useState(false);
  const [isBurning, setIsBurning] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('sc-evm-theme') || 'dark');
  const mainContentRef = useRef(null);

  const { getAuthHeaders } = useContext(AuthContext);
  const apiUrl = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('sc-evm-theme', theme);
  }, [theme]);

  useEffect(() => {
    mainContentRef.current?.focus();
  }, [location.pathname]);

  const initializeDefaultSession = useCallback(async () => {
    const defaultSession = 'session_1';
    const response = await fetch(`${apiUrl}/api/session/initialize`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ session_id: defaultSession }),
    });
    if (!response.ok) throw new Error(`Session initialization failed (${response.status})`);
    return defaultSession;
  }, [apiUrl, getAuthHeaders]);

  const refreshSessions = useCallback(async (preferredSessionId = '') => {
    setConnectionStatus('connecting');
    try {
      const response = await fetch(`${apiUrl}/api/session/list`, {
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);
      const payload = await response.json();
      let sessions = payload.status === 'success' && Array.isArray(payload.data)
        ? payload.data
        : [];

      if (sessions.length === 0) {
        sessions = [await initializeDefaultSession()];
      }

      setSessionState((previous) => {
        const nextActiveSession = sessions.includes(preferredSessionId)
          ? preferredSessionId
          : sessions.includes(previous.activeSessionId)
            ? previous.activeSessionId
            : sessions[0];
        return {
          ...previous,
          sessions,
          activeSessionId: nextActiveSession,
        };
      });
      setConnectionStatus('online');
      return sessions;
    } catch (error) {
      setConnectionStatus('offline');
      setNotice(`Control plane unavailable. ${error.message}.`);
      return [];
    }
  }, [apiUrl, getAuthHeaders, initializeDefaultSession]);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(''), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const burnSession = useCallback(async (sessionId) => {
    if (!sessionId) return false;
    setIsBurning(true);
    try {
      const response = await fetch(`${apiUrl}/api/session/burn/${encodeURIComponent(sessionId)}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error(`Burn failed (${response.status})`);
      await refreshSessions();
      setSessionState((previous) => ({
        ...previous,
        phase: 'MEMORY_PURGED',
        tokensSaved: 0,
        tokensUsed: { m1: 0, m2: 0 },
        memoryAnchors: [],
        tokenHistory: [],
        intentDistribution: {},
        chatHistory: [],
        systemLogs: [],
      }));
      setNotice(`Session ${sessionId} was securely burned.`);
      return true;
    } catch (error) {
      setNotice(`Could not burn session. ${error.message}.`);
      return false;
    } finally {
      setIsBurning(false);
    }
  }, [apiUrl, getAuthHeaders, refreshSessions]);

  const handleConfirmBurn = async () => {
    const burned = await burnSession(sessionState.activeSessionId);
    if (burned) setBurnDialogOpen(false);
  };

  const pageTitle = location.pathname === '/chat' ? 'Workspace' : 'Overview';
  const phaseIsBusy = ['STREAMING_CODE', 'STREAMING_RESPONSE', 'COMPUTING', 'Streaming Response']
    .includes(sessionState.phase);

  const contextValue = useMemo(() => ({
    apiUrl,
    burnSession,
    connectionStatus,
    getAuthHeaders,
    refreshSessions,
    sessionState,
    setNotice,
    setSessionState,
  }), [apiUrl, burnSession, connectionStatus, getAuthHeaders, refreshSessions, sessionState]);

  return (
    <TelemetryContext.Provider value={contextValue}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="app-shell">
        <Navigation connectionStatus={connectionStatus} />
        <div className="app-column">
          <header className="topbar">
            <div className="topbar-title">
              <span className="eyebrow">SC-EVM control plane</span>
              <h1>{pageTitle}</h1>
            </div>

            <div className="topbar-context" aria-label="Current session status">
              <div className="context-item">
                <Database size={15} aria-hidden="true" />
                <span className="context-label">Session</span>
                <strong title={sessionState.activeSessionId || 'No active session'}>
                  {sessionState.activeSessionId || 'None'}
                </strong>
              </div>
              <div className={`status-chip status-${phaseIsBusy ? 'working' : 'ready'}`}>
                <span className="status-dot" aria-hidden="true" />
                {phaseIsBusy ? 'Processing' : sessionState.phase.replaceAll('_', ' ')}
              </div>
            </div>

            <div className="topbar-actions">
              <div className="saved-indicator" title="Tokens kept out of model context">
                <Activity size={15} aria-hidden="true" />
                <span>{sessionState.tokensSaved.toLocaleString()}</span>
                <span className="saved-label">saved</span>
              </div>
              <button
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
                className="icon-button"
                onClick={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')}
                type="button"
              >
                {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              </button>
              <button
                className="button button-danger button-compact"
                disabled={!sessionState.activeSessionId || isBurning}
                onClick={() => setBurnDialogOpen(true)}
                type="button"
              >
                <Flame size={15} aria-hidden="true" />
                <span className="desktop-only">Burn session</span>
              </button>
            </div>
          </header>

          <main id="main-content" className="main-content" ref={mainContentRef} tabIndex="-1">
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>

      {notice && (
        <div className="toast" role="status" aria-live="polite">
          <ShieldCheck size={17} aria-hidden="true" />
          <span>{notice}</span>
          <button
            aria-label="Dismiss notification"
            className="toast-dismiss"
            onClick={() => setNotice('')}
            type="button"
          >
            <X size={16} />
          </button>
        </div>
      )}

      <ConfirmDialog
        busy={isBurning}
        confirmLabel="Burn session"
        description={`This permanently removes the temporary context for “${sessionState.activeSessionId}”. This action cannot be undone.`}
        onCancel={() => setBurnDialogOpen(false)}
        onConfirm={handleConfirmBurn}
        open={burnDialogOpen}
        title="Burn this session?"
      />
    </TelemetryContext.Provider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/*" element={<AppShell />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}
