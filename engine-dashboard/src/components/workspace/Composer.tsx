import React, { useRef, useEffect } from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { Send, StopCircle } from 'lucide-react';
import { streamQuery } from '../../runtime/apiService';
import { Message, EventEnvelope } from '../../runtime/types';

export function Composer() {
  const { state, dispatch } = useRuntime();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeSessionId = state.activeSessionId;

  const activeSession = activeSessionId ? state.sessions[activeSessionId] : null;
  const isStreaming = activeSession?.messages[activeSession.messages.length - 1]?.streaming;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [state.composerDraft]);

  const handleSubmit = async () => {
    if (!activeSessionId || !state.composerDraft.trim() || state.isSubmitting || isStreaming) return;

    const prompt = state.composerDraft.trim();
    dispatch({ type: 'COMPOSER_SUBMIT_STARTED' });
    dispatch({ type: 'COMPOSER_SUBMIT_SUCCEEDED' });

    const userMsgId = 'msg-' + Math.random().toString(36).substring(2, 9);
    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: prompt,
      timestamp: Date.now(),
    };
    dispatch({ type: 'MESSAGE_APPENDED', sessionId: activeSessionId, message: userMsg });

    // Emit event
    const reqStartedEvent: EventEnvelope = {
      id: Math.random().toString(36).substring(2),
      seq: Date.now(),
      type: 'request.started',
      sessionId: activeSessionId,
      timestamp: Date.now(),
      payload: { prompt },
      read: false,
    };
    dispatch({ type: 'EVENT_RECEIVED', event: reqStartedEvent });

    const asstMsgId = 'msg-' + Math.random().toString(36).substring(2, 9);
    const asstMsg: Message = {
      id: asstMsgId,
      role: 'assistant',
      content: '',
      streaming: true,
      streamBuffer: '',
      timestamp: Date.now(),
    };
    dispatch({ type: 'MESSAGE_APPENDED', sessionId: activeSessionId, message: asstMsg });

    const streamStartedEvent: EventEnvelope = {
      id: Math.random().toString(36).substring(2),
      seq: Date.now() + 1,
      type: 'stream.started',
      sessionId: activeSessionId,
      timestamp: Date.now(),
      payload: { messageId: asstMsgId },
      read: false,
    };
    dispatch({ type: 'EVENT_RECEIVED', event: streamStartedEvent });

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let fullText = '';
    let totalTokens = 0;
    const startTime = Date.now();

    try {
      await streamQuery(
        activeSessionId,
        prompt,
        {
          onMetadata: (metadata) => {
            const metaEvent: EventEnvelope = {
              id: Math.random().toString(36).substring(2),
              seq: Date.now(),
              type: 'telemetry.snapshot',
              sessionId: activeSessionId,
              timestamp: Date.now(),
              payload: metadata,
              read: false,
            };
            dispatch({ type: 'EVENT_RECEIVED', event: metaEvent });
          },
          onQueryReformulation: (reformulation) => {
            const refEvent: EventEnvelope = {
              id: Math.random().toString(36).substring(2),
              seq: Date.now(),
              type: 'request.retrying',
              sessionId: activeSessionId,
              timestamp: Date.now(),
              payload: reformulation,
              read: false,
            };
            dispatch({ type: 'EVENT_RECEIVED', event: refEvent });
          },
          onResponseContent: (text) => {
            fullText = text;
            dispatch({
              type: 'STREAM_DELTA',
              sessionId: activeSessionId,
              messageId: asstMsgId,
              delta: text,
            });
          },
          onAction: (action) => {
            if (action && action.type !== 'none') {
              const toolEvent: EventEnvelope = {
                id: Math.random().toString(36).substring(2),
                seq: Date.now(),
                type: 'tool.called',
                sessionId: activeSessionId,
                timestamp: Date.now(),
                payload: action,
                read: false,
              };
              dispatch({ type: 'EVENT_RECEIVED', event: toolEvent });
            }
          },
          onTokenUsage: (tokens) => {
            totalTokens = (tokens.m1 || 0) + (tokens.m2 || 0);
          },
          onError: (err) => {
            dispatch({
              type: 'STREAM_INTERRUPTED',
              sessionId: activeSessionId,
              messageId: asstMsgId,
            });
            dispatch({ type: 'COMPOSER_SUBMIT_FAILED', error: err });
          },
          onDone: () => {
            const latencyMs = Date.now() - startTime;
            dispatch({
              type: 'STREAM_COMPLETED',
              sessionId: activeSessionId,
              messageId: asstMsgId,
              finalContent: fullText,
              tokenCount: totalTokens || Math.max(10, Math.floor(fullText.length / 4)),
              latencyMs,
            });

            const streamDoneEvent: EventEnvelope = {
              id: Math.random().toString(36).substring(2),
              seq: Date.now(),
              type: 'stream.completed',
              sessionId: activeSessionId,
              timestamp: Date.now(),
              payload: { messageId: asstMsgId, latencyMs },
              read: false,
            };
            dispatch({ type: 'EVENT_RECEIVED', event: streamDoneEvent });
          },
        },
        controller.signal
      );
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        dispatch({
          type: 'STREAM_INTERRUPTED',
          sessionId: activeSessionId,
          messageId: asstMsgId,
        });
      }
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (!activeSessionId) return;
    const lastMsg = activeSession?.messages[activeSession.messages.length - 1];
    if (lastMsg && lastMsg.streaming) {
      dispatch({ type: 'STREAM_CANCELLED', sessionId: activeSessionId, messageId: lastMsg.id });
    }
  };

  return (
    <div className="p-4 bg-surface-1 border-t border-border-subtle">
      <div className="max-w-3xl mx-auto">
        {state.lastSubmitError && (
          <div className="mb-2 text-xs text-status-error bg-[rgba(221,68,68,0.1)] px-3 py-1.5 rounded-md border border-[rgba(221,68,68,0.2)]">
            {state.lastSubmitError}
          </div>
        )}

        <div className="relative flex items-end gap-2 bg-canvas border border-border-strong rounded-xl p-2 focus-within:border-focus-ring focus-within:ring-1 focus-within:ring-focus-ring transition-shadow">
          <textarea
            ref={textareaRef}
            value={state.composerDraft}
            onChange={(e) => dispatch({ type: 'COMPOSER_DRAFT_CHANGED', draft: e.target.value })}
            onKeyDown={handleKeyDown}
            disabled={!activeSessionId || state.isSubmitting}
            placeholder={activeSessionId ? "Message session..." : "Select a session to message..."}
            className="flex-1 max-h-[120px] min-h-[24px] bg-transparent resize-none outline-none py-1.5 px-2 text-sm text-text-primary placeholder:text-text-tertiary disabled:opacity-50"
            rows={1}
            data-testid="composer-input"
            aria-label="Message composer"
          />

          {isStreaming ? (
            <button
              onClick={handleCancel}
              className="p-2 text-text-tertiary hover:text-status-error bg-surface-2 hover:bg-[rgba(221,68,68,0.1)] rounded-lg transition-colors flex-none"
              aria-label="Stop generation"
              data-testid="composer-cancel"
            >
              <StopCircle className="w-5 h-5" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!activeSessionId || !state.composerDraft.trim() || state.isSubmitting}
              className="p-2 text-white bg-accent hover:bg-accent-hover disabled:bg-surface-2 disabled:text-text-tertiary rounded-lg transition-colors flex-none"
              aria-label="Send message"
              data-testid="composer-submit"
            >
              <Send className="w-5 h-5" />
            </button>
          )}
        </div>

        <div className="mt-2 text-right">
          {state.composerDraft.length > 500 && (
            <span className="text-[10px] font-mono text-text-tertiary">
              {state.composerDraft.length} chars
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
