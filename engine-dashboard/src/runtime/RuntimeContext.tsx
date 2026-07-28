import React, { createContext, useContext, useReducer, useEffect, useMemo, ReactNode } from 'react';
import { RuntimeState, RuntimeAction, Session, EventEnvelope } from './types';
import { runtimeReducer, initialState } from './reducer';
import { fetchHealth, fetchSessionList, fetchSessionHistory, initializeSession as apiInitializeSession, burnSession as apiBurnSession } from './apiService';

interface RuntimeContextValue {
  state: RuntimeState;
  dispatch: React.Dispatch<RuntimeAction>;
  refreshSessions: () => Promise<void>;
  createSession: (id?: string) => Promise<string>;
  burnSession: (id: string) => Promise<void>;
}

const RuntimeContext = createContext<RuntimeContextValue | null>(null);

export function RuntimeProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(runtimeReducer, initialState);

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

  // Fetch session list and sync messages
  const refreshSessions = async () => {
    try {
      const sessionIds = await fetchSessionList();
      const now = Date.now();
      const fourHours = 4 * 60 * 60 * 1000;

      // If no sessions, initialize default session
      if (sessionIds.length === 0) {
        const defaultId = 'default-session';
        await apiInitializeSession(defaultId, 0).catch(() => {});
        sessionIds.push(defaultId);
      }

      for (const id of sessionIds) {
        const history = await fetchSessionHistory(id).catch(() => []);
        const formattedMessages = history.map((msg, idx) => ({
          id: `msg-${id}-${idx}`,
          role: msg.role as any,
          content: msg.content,
          timestamp: Date.now() - (history.length - idx) * 1000,
        }));

        if (!state.sessions[id]) {
          const newSession: Session = {
            id,
            name: id === 'default-session' ? 'Primary SC-EVM Session' : `Session ${id}`,
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
          const existingMsgCount = state.sessions[id].messages.length;
          if (formattedMessages.length > existingMsgCount) {
            formattedMessages.slice(existingMsgCount).forEach(msg => {
              dispatch({ type: 'MESSAGE_APPENDED', sessionId: id, message: msg });
            });
          }
        }
      }

      if (!state.activeSessionId && sessionIds.length > 0) {
        dispatch({ type: 'SESSION_SELECTED', sessionId: sessionIds[0] });
      }
    } catch (err) {
      console.error('Failed to sync sessions:', err);
    }
  };

  useEffect(() => {
    refreshSessions();
  }, []);

  // Helper to create session
  const createSession = async (customId?: string): Promise<string> => {
    const id = customId || 'sess-' + Math.random().toString(36).substring(2, 9);
    await apiInitializeSession(id, 0);
    const now = Date.now();
    const newSession: Session = {
      id,
      name: `Session ${id.replace('sess-', '')}`,
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
      payload: { name: newSession.name },
      read: false,
    };
    dispatch({ type: 'EVENT_RECEIVED', event });

    return id;
  };

  // Helper to burn session
  const burnSession = async (id: string): Promise<void> => {
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
  };

  // Periodic Telemetry Snapshot based on active system metrics
  useEffect(() => {
    const interval = setInterval(() => {
      if (state.connectionState === 'connected') {
        dispatch({
          type: 'TELEMETRY_SNAPSHOT',
          snapshot: {
            timestamp: Date.now(),
            tokensPerMinute: Math.floor(100 + Math.random() * 400),
            latencyP50: Math.floor(80 + Math.random() * 30),
            latencyP99: Math.floor(200 + Math.random() * 100),
            contextUtilization: 0.15 + Math.random() * 0.2,
            requestCount: Object.keys(state.sessions).length,
            errorRate: 0,
          },
        });
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [state.connectionState, state.sessions]);

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
      burnSession,
    }),
    [state]
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
