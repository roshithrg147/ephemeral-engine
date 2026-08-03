import { RuntimeState, Session, SessionTier, EventEnvelope } from './types';

export function selectActiveSession(state: RuntimeState): Session | null {
  if (!state.activeSessionId) return null;
  return state.sessions[state.activeSessionId] || null;
}

export function selectSessionTier(session: Session, now: number): SessionTier {
  if (session.tier === 'burned' || session.tier === 'burning') {
    return session.tier;
  }
  const timeRemaining = Math.max(0, session.expiresAt - now);
  if (timeRemaining <= 0) return 'expired';
  if (timeRemaining <= 5 * 60 * 1000) return 'critical';
  if (timeRemaining <= 30 * 60 * 1000) return 'expiring_soon';
  return 'healthy';
}

export function selectTimeRemaining(session: Session, now: number): number {
  return Math.max(0, session.expiresAt - now);
}

export function selectFilteredEvents(state: RuntimeState, filter: string): EventEnvelope[] {
  if (filter === 'all') return state.events;
  return state.events.filter(e => {
    if (filter === 'request') return e.type.startsWith('request.');
    if (filter === 'stream') return e.type.startsWith('stream.');
    if (filter === 'session') return e.type.startsWith('session.');
    if (filter === 'error') return e.type.startsWith('error.');
    if (filter === 'system') return e.type.startsWith('connection.') || e.type.startsWith('auth.') || e.type.startsWith('model.');
    return e.type === filter;
  });
}

export function selectRecentEvents(state: RuntimeState, limit: number): EventEnvelope[] {
  return state.events.slice(-limit);
}

export function selectUnreadCount(state: RuntimeState): number {
  return state.events.filter(e => !e.read).length;
}

export function selectTelemetryChart(state: RuntimeState) {
  const timestamps: number[] = [];
  const tpm: number[] = [];
  const p50: number[] = [];
  const p99: number[] = [];
  const ctx: number[] = [];
  
  for (const snap of state.telemetry) {
    timestamps.push(snap.timestamp);
    tpm.push(snap.tokensPerMinute);
    p50.push(snap.latencyP50);
    p99.push(snap.latencyP99);
    ctx.push(snap.contextUtilization);
  }
  
  return { timestamps, tpm, p50, p99, ctx };
}

export function selectUsageSummary(state: RuntimeState) {
  if (state.telemetry.length === 0) {
    return { totalTokens: 0, totalRequests: 0, avgLatency: 0, errorRate: 0 };
  }
  
  let totalRequests = 0;
  let totalErrors = 0;
  let latencySum = 0;
  
  for (const snap of state.telemetry) {
    totalRequests += snap.requestCount;
    totalErrors += (snap.requestCount * snap.errorRate);
    latencySum += snap.latencyP50;
  }
  
  const lastSnap = state.telemetry[state.telemetry.length - 1];
  
  return {
    totalTokens: Object.values(state.sessions).reduce((acc, s) => acc + s.tokenUsage.total, 0),
    totalRequests,
    avgLatency: latencySum / state.telemetry.length,
    errorRate: totalRequests > 0 ? (totalErrors / totalRequests) : 0
  };
}

export function selectSessionList(state: RuntimeState): Session[] {
  return Object.values(state.sessions).sort((a, b) => {
    // Active first
    if (a.id === state.activeSessionId) return -1;
    if (b.id === state.activeSessionId) return 1;
    
    // Then by tier severity (expired > critical > expiring > healthy > burning > burned)
    const tierOrder = { expired: 0, critical: 1, expiring_soon: 2, healthy: 3, burning: 4, burned: 5 };
    if (tierOrder[a.tier] !== tierOrder[b.tier]) {
      return tierOrder[a.tier] - tierOrder[b.tier];
    }
    
    // Then by recency
    return b.lastActivity - a.lastActivity;
  });
}
