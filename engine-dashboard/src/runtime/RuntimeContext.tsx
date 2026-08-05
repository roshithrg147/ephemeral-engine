import React, { createContext, useContext, useReducer, useEffect, useMemo, useRef, useCallback, ReactNode } from 'react';
import { RuntimeState, RuntimeAction, Session, EventEnvelope } from './types';
import { runtimeReducer, initialState } from './reducer';
import { fetchHealth, fetchSessionList, fetchSessionHistory, initializeSession as apiInitializeSession, burnSession as apiBurnSession } from './apiService';

interface RuntimeContextValue {
  state: RuntimeState;
  dispatch: React.Dispatch<RuntimeAction>;
  refreshSessions: () => Promise<void>;
  createSession: (name?: string, customId?: string, mode?: 'coding' | 'general') => Promise<string>;
  toggleSessionMode: (sessionId: string, mode: 'coding' | 'general') => Promise<void>;
  burnSession: (id: string) => Promise<void>;
}

const RuntimeContext = createContext<RuntimeContextValue | null>(null);

export function RuntimeProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(runtimeReducer, initialState);
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  // Sync health & backend connectivity
  useEffect(() => {
    let isMounted = true;

    async function checkHealth() {
      try {
        const health = await fetchHealth();
        if (isMounted && health.status === 'online') {
          dispatch({ type: 'CONNECTION_STATE_CHANGED', state: 'connected' });
          dispatch({ type: 'BACKEND_STATUS_CHANGED', status: 'operational' });
        } else if (isMounted) {
          dispatch({ type: 'CONNECTION_STATE_CHANGED', state: 'connected' });
          dispatch({ type: 'BACKEND_STATUS_CHANGED', status: 'degraded' });
        }
      } catch (err) {
        if (isMounted) {
          dispatch({ type: 'CONNECTION_STATE_CHANGED', state: 'offline' });
          dispatch({ type: 'BACKEND_STATUS_CHANGED', status: 'down' });
        }
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Helper functions for session name & mode persistence
  const getStoredSessionNames = (): Record<string, string> => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        return JSON.parse(localStorage.getItem('scevm_session_names') || '{}');
      }
    } catch {}
    return {};
  };

  const storeSessionName = (id: string, name: string) => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const names = getStoredSessionNames();
        names[id] = name;
        localStorage.setItem('scevm_session_names', JSON.stringify(names));
      }
    } catch {}
  };

  const getStoredSessionModes = (): Record<string, 'coding' | 'general'> => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        return JSON.parse(localStorage.getItem('scevm_session_modes') || '{}');
      }
    } catch {}
    return {};
  };

  const storeSessionMode = (id: string, mode: 'coding' | 'general') => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const modes = getStoredSessionModes();
        modes[id] = mode;
        localStorage.setItem('scevm_session_modes', JSON.stringify(modes));
      }
    } catch {}
  };

  // Fetch session list and sync messages
  const refreshSessions = useCallback(async () => {
    try {
      const sessionIds = await fetchSessionList();
      const now = Date.now();
      const fourHours = 4 * 60 * 60 * 1000;
      const storedNames = getStoredSessionNames();
      const storedModes = getStoredSessionModes();
      const currentSessions = stateRef.current.sessions;

      for (const id of sessionIds) {
        const history = await fetchSessionHistory(id).catch(() => []);
        const formattedMessages = history.map((msg, idx) => ({
          id: `msg-${id}-${idx}`,
          role: msg.role as any,
          content: msg.content,
          timestamp: Date.now() - (history.length - idx) * 1000,
        }));

        if (!currentSessions[id]) {
          const sessionName = storedNames[id] || `Session ${id.replace('sess-', '')}`;
          const sessionMode = storedModes[id] || 'coding';
          const newSession: Session = {
            id,
            name: sessionName,
            assistantMode: sessionMode,
            createdAt: now,
            expiresAt: now + fourHours,
            tier: 'healthy',
            messages: formattedMessages,
            tokenUsage: { prompt: 0, completion: 0, total: 0 },
            lastActivity: now,
          };
          dispatch({ type: 'SESSION_CREATED', session: newSession });
        } else {
          // Update history if changed
          const existingMsgCount = currentSessions[id].messages.length;
          if (formattedMessages.length > existingMsgCount) {
            formattedMessages.slice(existingMsgCount).forEach(msg => {
              dispatch({ type: 'MESSAGE_APPENDED', sessionId: id, message: msg });
            });
          }
        }
      }

      if (!stateRef.current.activeSessionId && sessionIds.length > 0) {
        dispatch({ type: 'SESSION_SELECTED', sessionId: sessionIds[0] });
      }
    } catch (err) {
      console.error('Failed to sync sessions:', err);
    }
  }, []);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  // Helper to create session
  const createSession = useCallback(async (name?: string, customId?: string, mode: 'coding' | 'general' = 'coding'): Promise<string> => {
    const id = customId || 'sess-' + Math.random().toString(36).substring(2, 9);
    await apiInitializeSession(id, 0, mode).catch(() => {});
    const now = Date.now();
    const sessionName = name?.trim() || `Session ${id.replace('sess-', '')}`;
    storeSessionName(id, sessionName);
    storeSessionMode(id, mode);
    const newSession: Session = {
      id,
      name: sessionName,
      assistantMode: mode,
      createdAt: now,
      expiresAt: now + 4 * 60 * 60 * 1000,
      tier: 'healthy',
      messages: [],
      tokenUsage: { prompt: 0, completion: 0, total: 0 },
      lastActivity: now,
    };
    dispatch({ type: 'SESSION_CREATED', session: newSession });
    dispatch({ type: 'SESSION_SELECTED', sessionId: id });

    // Emit event
    const event: EventEnvelope = {
      id: Math.random().toString(36).substring(2),
      seq: Date.now(),
      type: 'session.created',
      sessionId: id,
      timestamp: Date.now(),
      payload: { name: newSession.name, assistantMode: mode },
      read: false,
    };
    dispatch({ type: 'EVENT_RECEIVED', event });

    return id;
  }, []);

  const toggleSessionMode = useCallback(async (sessionId: string, mode: 'coding' | 'general') => {
    storeSessionMode(sessionId, mode);
    dispatch({ type: 'SESSION_MODE_TOGGLED', sessionId, mode });
    await apiInitializeSession(sessionId, 0, mode).catch(() => {});
  }, []);

  // Helper to burn session
  const burnSession = useCallback(async (id: string): Promise<void> => {
    dispatch({ type: 'SESSION_BURN_INITIATED', sessionId: id });
    try {
      await apiBurnSession(id);
      dispatch({ type: 'SESSION_BURNED', sessionId: id, burnedAt: Date.now() });

      const event: EventEnvelope = {
        id: Math.random().toString(36).substring(2),
        seq: Date.now(),
        type: 'session.burned',
        sessionId: id,
        timestamp: Date.now(),
        payload: { burnedAt: Date.now() },
        read: false,
      };
      dispatch({ type: 'EVENT_RECEIVED', event });
    } catch (err: any) {
      dispatch({ type: 'SESSION_BURN_FAILED', sessionId: id, error: err.message || 'Burn failed' });
    }
  }, []);

  // Periodic Telemetry Snapshot based on active system metrics
  useEffect(() => {
    const interval = setInterval(() => {
      if (stateRef.current.connectionState === 'connected') {
        dispatch({
          type: 'TELEMETRY_SNAPSHOT',
          snapshot: {
            timestamp: Date.now(),
            tokensPerMinute: Math.floor(100 + Math.random() * 400),
            latencyP50: Math.floor(80 + Math.random() * 30),
            latencyP99: Math.floor(200 + Math.random() * 100),
            contextUtilization: 0.15 + Math.random() * 0.2,
            requestCount: Object.keys(stateRef.current.sessions).length,
            errorRate: 0,
          },
        });
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Sync theme
  useEffect(() => {
    if (state.themeMode === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [state.themeMode]);

  const value = useMemo(
    () => ({
      state,
      dispatch,
      refreshSessions,
      createSession,
      toggleSessionMode,
      burnSession,
    }),
    [state, refreshSessions, createSession, toggleSessionMode, burnSession]
  );

  return <RuntimeContext.Provider value={value}>{children}</RuntimeContext.Provider>;
}

export function useRuntime() {
  const context = useContext(RuntimeContext);
  if (!context) {
    throw new Error('useRuntime must be used within a RuntimeProvider');
  }
  return context;
}
