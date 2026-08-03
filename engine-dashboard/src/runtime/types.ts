// Session lifecycle tiers
export type SessionTier = 'healthy' | 'expiring_soon' | 'critical' | 'expired' | 'burning' | 'burned';

// Connection states
export type ConnectionState = 'connected' | 'connecting' | 'reconnecting' | 'offline' | 'auth_expired' | 'forbidden';

// Auth/backend status
export type BackendStatus = 'operational' | 'degraded' | 'down';
export type AuthStatus = 'authenticated' | 'expired' | 'forbidden';
export type ModelStatus = 'available' | 'rate_limited' | 'retrying' | 'unavailable';

export type EventType = 
  | 'session.created' | 'session.selected' | 'session.expiring' | 'session.expired'
  | 'session.burning' | 'session.burned' | 'session.burn_failed'
  | 'request.started' | 'request.completed' | 'request.failed' | 'request.retrying' | 'request.cancelled'
  | 'stream.started' | 'stream.delta' | 'stream.completed' | 'stream.interrupted' | 'stream.truncated'
  | 'tool.called' | 'tool.result' | 'tool.failed'
  | 'connection.connected' | 'connection.reconnecting' | 'connection.lost' | 'connection.restored'
  | 'auth.expired' | 'auth.forbidden'
  | 'model.rate_limited' | 'model.retrying' | 'model.available'
  | 'telemetry.snapshot'
  | 'degradation.started' | 'degradation.resolved'
  | 'error.occurred';

export interface EventEnvelope {
  id: string;
  seq: number;
  type: EventType;
  timestamp: number;
  sessionId: string;
  payload: any;
  read: boolean;
}

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool' | 'warning' | 'error' | 'cancelled';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  streaming?: boolean;
  streamBuffer?: string;
  tokenCount?: number;
  latencyMs?: number;
  toolName?: string;
  toolArgs?: string;
  toolResult?: string;
  cancelled?: boolean;
  error?: string;
  timestamp: number;
}

export interface Session {
  id: string;
  name: string;
  createdAt: number;
  expiresAt: number;
  tier: SessionTier;
  burnedAt?: number;
  messages: Message[];
  tokenUsage: { prompt: number; completion: number; total: number };
  lastActivity: number;
}

export interface TelemetrySnapshot {
  timestamp: number;
  tokensPerMinute: number;
  latencyP50: number;
  latencyP99: number;
  contextUtilization: number;
  requestCount: number;
  errorRate: number;
}

export interface RuntimeState {
  connectionState: ConnectionState;
  reconnectAttempts: number;
  lastConnectedAt: number | null;
  
  backendStatus: BackendStatus;
  authStatus: AuthStatus;
  modelStatus: ModelStatus;
  modelRetryCountdown: number | null;

  sessions: Record<string, Session>;
  activeSessionId: string | null;
  pendingBurnSessionId: string | null;

  events: EventEnvelope[];
  maxEvents: 200;
  lastSeq: number;
  seenEventIds: Set<string>;

  telemetry: TelemetrySnapshot[];
  maxTelemetry: 60;

  composerDraft: string;
  composerSessionId: string | null;
  isSubmitting: boolean;
  lastSubmitError: string | null;
  
  inspectorOpen: boolean;
  inspectorTab: 'context' | 'events';
  eventFilter: EventType | 'all';
  themeMode: 'dark' | 'light';
}

export type RuntimeAction =
  | { type: 'CONNECTION_STATE_CHANGED'; state: ConnectionState }
  | { type: 'BACKEND_STATUS_CHANGED'; status: BackendStatus }
  | { type: 'AUTH_STATUS_CHANGED'; status: AuthStatus }
  | { type: 'MODEL_STATUS_CHANGED'; status: ModelStatus; retryIn?: number }
  | { type: 'EVENT_RECEIVED'; event: EventEnvelope }
  | { type: 'EVENTS_BATCH'; events: EventEnvelope[] }
  | { type: 'SESSION_CREATED'; session: Session }
  | { type: 'SESSION_SELECTED'; sessionId: string }
  | { type: 'SESSION_TIER_UPDATED'; sessionId: string; tier: SessionTier }
  | { type: 'SESSION_BURN_INITIATED'; sessionId: string }
  | { type: 'SESSION_BURNED'; sessionId: string; burnedAt: number }
  | { type: 'SESSION_BURN_FAILED'; sessionId: string; error: string }
  | { type: 'MESSAGE_APPENDED'; sessionId: string; message: Message }
  | { type: 'STREAM_DELTA'; sessionId: string; messageId: string; delta: string }
  | { type: 'STREAM_COMPLETED'; sessionId: string; messageId: string; finalContent: string; tokenCount: number; latencyMs: number }
  | { type: 'STREAM_INTERRUPTED'; sessionId: string; messageId: string }
  | { type: 'STREAM_CANCELLED'; sessionId: string; messageId: string }
  | { type: 'TELEMETRY_SNAPSHOT'; snapshot: TelemetrySnapshot }
  | { type: 'COMPOSER_DRAFT_CHANGED'; draft: string }
  | { type: 'COMPOSER_SUBMIT_STARTED' }
  | { type: 'COMPOSER_SUBMIT_FAILED'; error: string }
  | { type: 'COMPOSER_SUBMIT_SUCCEEDED' }
  | { type: 'INSPECTOR_TOGGLE' }
  | { type: 'INSPECTOR_TAB_CHANGED'; tab: 'context' | 'events' }
  | { type: 'EVENT_FILTER_CHANGED'; filter: EventType | 'all' }
  | { type: 'PENDING_BURN_SET'; sessionId: string | null }
  | { type: 'THEME_TOGGLED' }
  | { type: 'MODEL_RETRY_TICK' };
