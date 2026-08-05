import { customFetch } from '../lib/customFetch';
import { getGlobalIdToken, notifyGlobalForbidden, triggerGlobalSignOut } from '../context/AuthContext';

export interface StandardResponse<T = any> {
  status: string;
  message: string;
  data: T;
}

export interface BackendHealth {
  status: string;
  message: string;
}

export interface MemoryData {
  pending_commit_buffer: string[];
  base_threshold: number;
  token_budget: number;
  indexed_documents: any[];
}

export interface ChatMessageData {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export async function fetchHealth(): Promise<BackendHealth> {
  return await customFetch<BackendHealth>('/api/health', {
    responseType: 'json',
    skipAuth: true,
  }).catch(() =>
    customFetch<BackendHealth>('/', { responseType: 'json', skipAuth: true })
  );
}

export async function fetchSessionList(): Promise<string[]> {
  const res = await customFetch<StandardResponse<string[]>>('/api/session/list', {
    responseType: 'json',
  });
  return res.data || [];
}

export async function initializeSession(sessionId: string, developmentPhase = 0, assistantMode: 'coding' | 'general' = 'coding'): Promise<any> {
  return await customFetch<StandardResponse<any>>('/api/session/initialize', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      development_phase: developmentPhase,
      assistant_mode: assistantMode,
    }),
  });
}

export async function fetchSessionHistory(sessionId: string): Promise<ChatMessageData[]> {
  const res = await customFetch<StandardResponse<ChatMessageData[]>>(`/api/session/history/${sessionId}`, {
    responseType: 'json',
  });
  return res.data || [];
}

export async function fetchSessionMemory(sessionId: string): Promise<MemoryData | null> {
  const res = await customFetch<StandardResponse<MemoryData>>(`/api/session/memory/${sessionId}`, {
    responseType: 'json',
  });
  return res.data || null;
}

export async function burnSession(sessionId: string): Promise<void> {
  await customFetch(`/api/session/burn/${sessionId}`, {
    method: 'DELETE',
  });
}

export interface SSEQueryHandlers {
  onMetadata?: (data: { tokensSaved: number; memoryAnchors: string[] }) => void;
  onQueryReformulation?: (data: { search_vector_query: string; grounded_llm_prompt: string }) => void;
  onRetrievedContext?: (data: string[]) => void;
  onResponseContent?: (data: string) => void;
  onAction?: (data: { type: string; payload: any }) => void;
  onRoutingDecision?: (data: { mode: string; intent: string; confidence: number; reason: string; memory_config: any }) => void;
  onUsageReport?: (data: any[]) => void;
  onTokenUsage?: (data: { m1: number; m2: number }) => void;
  onIntent?: (data: string) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
}

export async function streamQuery(
  sessionId: string,
  prompt: string,
  handlers: SSEQueryHandlers,
  signal?: AbortSignal
): Promise<void> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  };

  let token = await getGlobalIdToken(false);
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch('/api/agent/query', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        session_id: sessionId,
        prompt,
        graphify_enabled: true,
        diagnostic_mode: false,
      }),
      signal,
    });
  } catch (err: any) {
    if (signal?.aborted) return;
    handlers.onError?.(`Stream connection error: ${err?.message || err}`);
    return;
  }

  // Controlled 401 retry on SSE stream initialization
  if (response.status === 401) {
    token = await getGlobalIdToken(true);
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
      try {
        response = await fetch('/api/agent/query', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            session_id: sessionId,
            prompt,
            graphify_enabled: true,
            diagnostic_mode: false,
          }),
          signal,
        });
      } catch (err: any) {
        if (signal?.aborted) return;
        handlers.onError?.(`Stream retry failed: ${err?.message || err}`);
        return;
      }
    }
  }

  if (response.status === 401) {
    await triggerGlobalSignOut();
    handlers.onError?.('Authentication expired. Please sign in again.');
    return;
  }

  if (response.status === 403) {
    const errorText = await response.text().catch(() => response.statusText);
    notifyGlobalForbidden(errorText || 'Access denied - Account not admitted');
    handlers.onError?.(`HTTP 403 Forbidden: ${errorText}`);
    return;
  }

  if (!response.ok || !response.body) {
    const errorText = await response.text().catch(() => response.statusText);
    handlers.onError?.(`HTTP ${response.status}: ${errorText}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        if (!rawEvent.trim()) continue;

        let eventType = '';
        let dataStr = '';

        const lines = rawEvent.split('\n');
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            dataStr += (dataStr ? '\n' : '') + line.substring(5).trim();
          }
        }

        if (!eventType || !dataStr) continue;

        try {
          let parsedData: any = dataStr;
          try {
            parsedData = JSON.parse(dataStr);
          } catch {
            // Leave as raw string if not valid JSON
          }

          switch (eventType) {
            case 'metadata':
              handlers.onMetadata?.(parsedData);
              break;
            case 'query_reformulation':
              handlers.onQueryReformulation?.(parsedData);
              break;
            case 'retrieved_context':
              handlers.onRetrievedContext?.(parsedData);
              break;
            case 'response_content':
              handlers.onResponseContent?.(parsedData);
              break;
            case 'action':
              handlers.onAction?.(parsedData);
              break;
            case 'routing_decision':
              handlers.onRoutingDecision?.(parsedData);
              break;
            case 'usage_report':
              handlers.onUsageReport?.(parsedData);
              break;
            case 'token_usage':
              handlers.onTokenUsage?.(parsedData);
              break;
            case 'intent':
              handlers.onIntent?.(parsedData);
              break;
            case 'system':
              if (parsedData?.event === 'SESSION_RECOVERED') {
                console.info('Session context self-healed successfully:', parsedData.correlation_id);
              }
              break;
            case 'error':
              handlers.onError?.(typeof parsedData === 'string' ? parsedData : JSON.stringify(parsedData));
              break;
            case 'done':
              handlers.onDone?.();
              break;
          }
        } catch (err: any) {
          console.error('Error handling SSE event:', err);
        }
      }
    }
  } catch (readErr: any) {
    if (signal?.aborted) return;
    handlers.onError?.(`Stream read interrupted: ${readErr?.message || readErr}`);
  }
}
