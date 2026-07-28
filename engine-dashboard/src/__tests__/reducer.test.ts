import { describe, it, expect } from 'vitest';
import { runtimeReducer, initialState } from '../runtime/reducer';
import { RuntimeState, EventEnvelope, Session } from '../runtime/types';

describe('Runtime Reducer', () => {
  it('handles EVENT_RECEIVED with deduplication', () => {
    const event: EventEnvelope = { id: '1', seq: 1, type: 'error.occurred', timestamp: 0, sessionId: 's1', payload: {}, read: false };
    
    let state = runtimeReducer(initialState, { type: 'EVENT_RECEIVED', event });
    expect(state.events).toHaveLength(1);
    expect(state.seenEventIds.has('1')).toBe(true);
    
    // Duplicate
    state = runtimeReducer(state, { type: 'EVENT_RECEIVED', event });
    expect(state.events).toHaveLength(1); // Still 1
  });

  it('rejects stale events by seq', () => {
    const event1: EventEnvelope = { id: '1', seq: 2, type: 'error.occurred', timestamp: 0, sessionId: 's1', payload: {}, read: false };
    const event2: EventEnvelope = { id: '2', seq: 1, type: 'error.occurred', timestamp: 0, sessionId: 's1', payload: {}, read: false };
    
    let state = runtimeReducer(initialState, { type: 'EVENT_RECEIVED', event: event1 });
    state = runtimeReducer(state, { type: 'EVENT_RECEIVED', event: event2 });
    
    expect(state.events).toHaveLength(1);
    expect(state.events[0].id).toBe('1');
  });

  it('evicts oldest events when max > 200', () => {
    let state = { ...initialState };
    for (let i = 1; i <= 205; i++) {
      const event: EventEnvelope = { id: i.toString(), seq: i, type: 'error.occurred', timestamp: 0, sessionId: 's1', payload: {}, read: false };
      state = runtimeReducer(state, { type: 'EVENT_RECEIVED', event });
    }
    
    expect(state.events).toHaveLength(200);
    // oldest evicted, starts from 6
    expect(state.events[0].id).toBe('6');
  });

  it('handles STREAM_DELTA and STREAM_COMPLETED', () => {
    const s1: Session = { id: 's1', name: 'S1', createdAt: 0, expiresAt: 0, tier: 'healthy', messages: [
      { id: 'm1', role: 'assistant', content: '', streaming: true, streamBuffer: 'A', timestamp: 0 }
    ], tokenUsage: { prompt: 0, completion: 0, total: 0 }, lastActivity: 0 };
    
    let state: RuntimeState = { ...initialState, sessions: { s1 } };
    
    state = runtimeReducer(state, { type: 'STREAM_DELTA', sessionId: 's1', messageId: 'm1', delta: 'B' });
    expect(state.sessions.s1.messages[0].streamBuffer).toBe('AB');
    
    state = runtimeReducer(state, { type: 'STREAM_COMPLETED', sessionId: 's1', messageId: 'm1', finalContent: 'AB!', tokenCount: 5, latencyMs: 100 });
    expect(state.sessions.s1.messages[0].streamBuffer).toBeUndefined();
    expect(state.sessions.s1.messages[0].content).toBe('AB!');
    expect(state.sessions.s1.messages[0].streaming).toBe(false);
  });

  it('handles session burn cycle', () => {
    const s1: Session = { id: 's1', name: 'S1', createdAt: 0, expiresAt: 0, tier: 'healthy', messages: [], tokenUsage: { prompt: 0, completion: 0, total: 0 }, lastActivity: 0 };
    let state: RuntimeState = { ...initialState, sessions: { s1 } };

    state = runtimeReducer(state, { type: 'SESSION_BURN_INITIATED', sessionId: 's1' });
    expect(state.pendingBurnSessionId).toBe('s1');

    state = runtimeReducer(state, { type: 'SESSION_BURNED', sessionId: 's1', burnedAt: 123 });
    expect(state.pendingBurnSessionId).toBeNull();
    expect(state.sessions.s1.tier).toBe('burned');
    expect(state.sessions.s1.burnedAt).toBe(123);
  });

  it('handles session burn failed', () => {
    const s1: Session = { id: 's1', name: 'S1', createdAt: 0, expiresAt: 0, tier: 'healthy', messages: [], tokenUsage: { prompt: 0, completion: 0, total: 0 }, lastActivity: 0 };
    let state: RuntimeState = { ...initialState, sessions: { s1 } };

    state = runtimeReducer(state, { type: 'SESSION_BURN_INITIATED', sessionId: 's1' });
    state = runtimeReducer(state, { type: 'SESSION_BURN_FAILED', sessionId: 's1', error: 'err' });
    
    expect(state.pendingBurnSessionId).toBeNull();
    expect(state.sessions.s1.tier).toBe('healthy'); // unchanged
  });
});
