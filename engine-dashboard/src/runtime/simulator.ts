import { RuntimeAction, Session, EventEnvelope, EventType, Message } from './types';

// Utility for generating IDs
function uuid() {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

const phrases = [
  "I'm initializing the environment. ",
  "Processing the dataset now. ",
  "Let me check the requested parameters. ",
  "The function completed successfully. ",
  "Based on the input, here is the result: ",
  "System stability is nominal. ",
  "Awaiting further instructions. ",
  "Calculating the optimal path. ",
  "Data stream synchronized. ",
  "Ready for next prompt. "
];

export function createSimulator(dispatch: (action: RuntimeAction) => void) {
  let intervals: number[] = [];
  let seqCounter = 1;

  function emitEvent(type: EventType, sessionId: string, payload: any = {}) {
    const event: EventEnvelope = {
      id: uuid(),
      seq: seqCounter++,
      type,
      sessionId,
      timestamp: Date.now(),
      payload,
      read: false
    };
    dispatch({ type: 'EVENT_RECEIVED', event });
  }

  function start() {
    const now = Date.now();
    const fourHours = 4 * 60 * 60 * 1000;
    
    // Create initial sessions
    const s1: Session = {
      id: 'sess-' + uuid(), name: 'Alpha Worker', createdAt: now - (3 * 60 * 60 * 1000 + 50 * 60 * 1000), expiresAt: now + (10 * 60 * 1000), tier: 'critical', messages: [], tokenUsage: { prompt: 12400, completion: 4320, total: 16720 }, lastActivity: now - 60000
    };
    const s2: Session = {
      id: 'sess-' + uuid(), name: 'Beta Processing', createdAt: now - (2 * 60 * 60 * 1000 + 15 * 60 * 1000), expiresAt: now + (1 * 60 * 60 * 1000 + 45 * 60 * 1000), tier: 'healthy', messages: [], tokenUsage: { prompt: 500, completion: 150, total: 650 }, lastActivity: now - 300000
    };
    const s3: Session = {
      id: 'sess-' + uuid(), name: 'Gamma Interactive', createdAt: now - (30 * 60 * 1000), expiresAt: now + (3 * 60 * 60 * 1000 + 30 * 60 * 1000), tier: 'healthy', messages: [], tokenUsage: { prompt: 200, completion: 45, total: 245 }, lastActivity: now - 10000
    };
    
    [s1, s2, s3].forEach(s => {
      dispatch({ type: 'SESSION_CREATED', session: s });
      emitEvent('session.created', s.id);
    });
    
    dispatch({ type: 'SESSION_SELECTED', sessionId: s3.id });
    
    // Simulate connection
    setTimeout(() => {
      dispatch({ type: 'CONNECTION_STATE_CHANGED', state: 'connected' });
      emitEvent('connection.connected', 'system');
    }, 1000);

    // Telemetry loop (every 5 seconds)
    intervals.push(window.setInterval(() => {
      dispatch({
        type: 'TELEMETRY_SNAPSHOT',
        snapshot: {
          timestamp: Date.now(),
          tokensPerMinute: 200 + Math.random() * 800,
          latencyP50: 120 + Math.random() * 50,
          latencyP99: 300 + Math.random() * 200,
          contextUtilization: 0.1 + Math.random() * 0.4,
          requestCount: Math.floor(Math.random() * 5),
          errorRate: Math.random() > 0.95 ? 0.05 : 0
        }
      });
      emitEvent('telemetry.snapshot', 'system');
    }, 5000));

    // Session tier updates (every 30s)
    intervals.push(window.setInterval(() => {
      // In real life, selector derives it, but we can emit events to show in feed
    }, 30000));

    // Streaming simulation loop on active session (s3)
    let isStreaming = false;
    intervals.push(window.setInterval(() => {
      if (isStreaming) return;
      if (Math.random() > 0.3) return; // Only sometimes

      isStreaming = true;
      const msgId = 'msg-' + uuid();
      
      // User message
      const userMsg: Message = {
        id: 'msg-' + uuid(), role: 'user', content: 'Execute next step in pipeline.', timestamp: Date.now()
      };
      dispatch({ type: 'MESSAGE_APPENDED', sessionId: s3.id, message: userMsg });
      emitEvent('request.started', s3.id, { messageId: userMsg.id });
      
      setTimeout(() => {
        // Assistant streaming
        const asstMsg: Message = {
          id: msgId, role: 'assistant', content: '', streaming: true, streamBuffer: '', timestamp: Date.now()
        };
        dispatch({ type: 'MESSAGE_APPENDED', sessionId: s3.id, message: asstMsg });
        emitEvent('stream.started', s3.id, { messageId: msgId });
        
        let iters = 0;
        const maxIters = 10 + Math.floor(Math.random() * 10);
        
        const streamInterval = setInterval(() => {
          iters++;
          const delta = phrases[Math.floor(Math.random() * phrases.length)];
          dispatch({ type: 'STREAM_DELTA', sessionId: s3.id, messageId: msgId, delta });
          
          if (iters >= maxIters) {
            clearInterval(streamInterval);
            // Compile final
            let finalContent = '';
            for(let i=0; i<maxIters; i++) finalContent += phrases[Math.floor(Math.random() * phrases.length)];
            dispatch({ 
              type: 'STREAM_COMPLETED', 
              sessionId: s3.id, 
              messageId: msgId, 
              finalContent, 
              tokenCount: maxIters * 5, 
              latencyMs: maxIters * 100 
            });
            emitEvent('stream.completed', s3.id, { messageId: msgId });
            isStreaming = false;
          }
        }, 150);
      }, 500);
      
    }, 15000));

    // Model retry tick
    intervals.push(window.setInterval(() => {
      dispatch({ type: 'MODEL_RETRY_TICK' });
    }, 1000));
  }

  function stop() {
    intervals.forEach(clearInterval);
    intervals = [];
  }

  return { start, stop };
}
