import { RuntimeAction, RuntimeState, EventEnvelope } from './types';

export const initialState: RuntimeState = {
  connectionState: 'connecting',
  reconnectAttempts: 0,
  lastConnectedAt: null,
  
  backendStatus: 'operational',
  authStatus: 'authenticated',
  modelStatus: 'available',
  modelRetryCountdown: null,

  sessions: {},
  activeSessionId: null,
  pendingBurnSessionId: null,

  events: [],
  maxEvents: 200,
  lastSeq: 0,
  seenEventIds: new Set<string>(),

  telemetry: [],
  maxTelemetry: 60,

  composerDraft: '',
  composerSessionId: null,
  isSubmitting: false,
  lastSubmitError: null,
  
  inspectorOpen: false,
  sessionRailOpen: true,
  inspectorTab: 'context',
  eventFilter: 'all',
  themeMode: 'dark',
};

function processEvent(state: RuntimeState, event: EventEnvelope): RuntimeState {
  if (state.seenEventIds.has(event.id)) return state;
  if (event.seq <= state.lastSeq) return state;

  const newSeen = new Set(state.seenEventIds);
  newSeen.add(event.id);
  
  const newEvents = [...state.events, event];
  if (newEvents.length > state.maxEvents) {
    newEvents.shift();
  }

  return {
    ...state,
    events: newEvents,
    seenEventIds: newSeen,
    lastSeq: Math.max(state.lastSeq, event.seq),
  };
}

export function runtimeReducer(state: RuntimeState, action: RuntimeAction): RuntimeState {
  switch (action.type) {
    case 'CONNECTION_STATE_CHANGED':
      return { ...state, connectionState: action.state };
    
    case 'BACKEND_STATUS_CHANGED':
      return { ...state, backendStatus: action.status };
      
    case 'AUTH_STATUS_CHANGED':
      return { ...state, authStatus: action.status };
      
    case 'MODEL_STATUS_CHANGED':
      return { 
        ...state, 
        modelStatus: action.status, 
        modelRetryCountdown: action.retryIn ?? null 
      };

    case 'MODEL_RETRY_TICK':
      if (state.modelRetryCountdown && state.modelRetryCountdown > 0) {
        return { ...state, modelRetryCountdown: state.modelRetryCountdown - 1 };
      }
      return state;

    case 'EVENT_RECEIVED':
      return processEvent(state, action.event);

    case 'EVENTS_BATCH': {
      let nextState = state;
      for (const event of action.events) {
        nextState = processEvent(nextState, event);
      }
      return nextState;
    }

    case 'SESSION_CREATED':
      return {
        ...state,
        sessions: { ...state.sessions, [action.session.id]: action.session },
      };

    case 'SESSION_SELECTED':
      return { ...state, activeSessionId: action.sessionId };

    case 'SESSION_MODE_TOGGLED':
      if (!state.sessions[action.sessionId]) return state;
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.sessionId]: {
            ...state.sessions[action.sessionId],
            assistantMode: action.mode,
          },
        },
      };

    case 'SESSION_TIER_UPDATED':
      if (!state.sessions[action.sessionId]) return state;
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.sessionId]: {
            ...state.sessions[action.sessionId],
            tier: action.tier,
          }
        }
      };

    case 'SESSION_BURN_INITIATED':
      return { ...state, pendingBurnSessionId: action.sessionId };

    case 'SESSION_BURNED':
      if (!state.sessions[action.sessionId]) return state;
      return {
        ...state,
        pendingBurnSessionId: state.pendingBurnSessionId === action.sessionId ? null : state.pendingBurnSessionId,
        sessions: {
          ...state.sessions,
          [action.sessionId]: {
            ...state.sessions[action.sessionId],
            tier: 'burned',
            burnedAt: action.burnedAt,
          }
        }
      };

    case 'SESSION_BURN_FAILED':
      return {
        ...state,
        pendingBurnSessionId: state.pendingBurnSessionId === action.sessionId ? null : state.pendingBurnSessionId,
      };

    case 'MESSAGE_APPENDED': {
      const session = state.sessions[action.sessionId];
      if (!session) return state;
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.sessionId]: {
            ...session,
            messages: [...session.messages, action.message],
            lastActivity: Date.now(),
          }
        }
      };
    }

    case 'STREAM_DELTA': {
      const session = state.sessions[action.sessionId];
      if (!session) return state;
      
      const messages = session.messages.map(msg => 
        msg.id === action.messageId 
          ? { ...msg, streamBuffer: (msg.streamBuffer || '') + action.delta }
          : msg
      );
      
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.sessionId]: { ...session, messages, lastActivity: Date.now() }
        }
      };
    }

    case 'STREAM_COMPLETED': {
      const session = state.sessions[action.sessionId];
      if (!session) return state;
      
      const messages = session.messages.map(msg => 
        msg.id === action.messageId 
          ? { 
              ...msg, 
              content: action.finalContent, 
              streamBuffer: undefined, 
              streaming: false,
              tokenCount: action.tokenCount,
              latencyMs: action.latencyMs
            }
          : msg
      );
      
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.sessionId]: { 
            ...session, 
            messages, 
            lastActivity: Date.now(),
            tokenUsage: {
              ...session.tokenUsage,
              completion: session.tokenUsage.completion + action.tokenCount,
              total: session.tokenUsage.total + action.tokenCount
            }
          }
        }
      };
    }
    
    case 'STREAM_CANCELLED': {
      const session = state.sessions[action.sessionId];
      if (!session) return state;
      
      const messages = session.messages.map(msg => 
        msg.id === action.messageId 
          ? { 
              ...msg, 
              streaming: false,
              cancelled: true,
              content: msg.streamBuffer || msg.content || '',
              streamBuffer: undefined
            }
          : msg
      );
      
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.sessionId]: { ...session, messages, lastActivity: Date.now() }
        }
      };
    }

    case 'STREAM_INTERRUPTED': {
      const session = state.sessions[action.sessionId];
      if (!session) return state;
      
      const messages = session.messages.map(msg => 
        msg.id === action.messageId 
          ? { 
              ...msg, 
              streaming: false,
              error: 'Stream interrupted',
              content: msg.streamBuffer || msg.content || '',
              streamBuffer: undefined
            }
          : msg
      );
      
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.sessionId]: { ...session, messages, lastActivity: Date.now() }
        }
      };
    }

    case 'TELEMETRY_SNAPSHOT': {
      const newTelemetry = [...state.telemetry, action.snapshot];
      if (newTelemetry.length > state.maxTelemetry) {
        newTelemetry.shift();
      }
      return { ...state, telemetry: newTelemetry };
    }

    case 'COMPOSER_DRAFT_CHANGED':
      return { ...state, composerDraft: action.draft };

    case 'COMPOSER_SUBMIT_STARTED':
      return { ...state, isSubmitting: true, lastSubmitError: null };

    case 'COMPOSER_SUBMIT_FAILED':
      return { ...state, isSubmitting: false, lastSubmitError: action.error };

    case 'COMPOSER_SUBMIT_SUCCEEDED':
      return { ...state, isSubmitting: false, composerDraft: '' };

    case 'INSPECTOR_TOGGLE':
      return { ...state, inspectorOpen: !state.inspectorOpen };

    case 'SESSION_RAIL_TOGGLE':
      return { ...state, sessionRailOpen: state.sessionRailOpen === undefined ? false : !state.sessionRailOpen };

    case 'INSPECTOR_TAB_CHANGED':
      return { ...state, inspectorTab: action.tab };

    case 'EVENT_FILTER_CHANGED':
      return { ...state, eventFilter: action.filter };
      
    case 'PENDING_BURN_SET':
      return { ...state, pendingBurnSessionId: action.sessionId };
      
    case 'THEME_TOGGLED':
      return { ...state, themeMode: state.themeMode === 'dark' ? 'light' : 'dark' };

    default:
      return state;
  }
}
