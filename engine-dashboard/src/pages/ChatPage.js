import React, {
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  AlertCircle,
  Check,
  Clipboard,
  Code2,
  Copy,
  Database,
  FileCode2,
  Flame,
  FolderKanban,
  Layers3,
  LoaderCircle,
  MessageSquare,
  PanelRight,
  Plus,
  Send,
  ServerCog,
  Square,
  Trash2,
} from 'lucide-react';
import { TelemetryContext } from '../App';
import { parseSseFrame, splitSseFrames } from '../sse';

const MAX_TELEMETRY_POINTS = 200;
const appendBounded = (items, item) => [...items, item].slice(-MAX_TELEMETRY_POINTS);

function SessionDialog({ open, mode, sessionId, busy, error, onClose, onConfirm }) {
  const [name, setName] = useState('');
  const inputRef = useRef(null);
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setName('');
    window.setTimeout(() => inputRef.current?.focus(), 0);

    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !busy) onClose();
      if (event.key !== 'Tab') return;
      const focusable = dialogRef.current?.querySelectorAll(
        'button:not(:disabled), input:not(:disabled)',
      );
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
  }, [busy, onClose, open]);

  if (!open) return null;
  const isCreate = mode === 'create';

  const handleSubmit = (event) => {
    event.preventDefault();
    onConfirm(isCreate ? name : sessionId);
  };

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={busy ? undefined : onClose}>
      <form
        aria-describedby="session-dialog-description"
        aria-labelledby="session-dialog-title"
        aria-modal="true"
        className="dialog-card"
        onMouseDown={(event) => event.stopPropagation()}
        onSubmit={handleSubmit}
        ref={dialogRef}
        role="dialog"
      >
        <div className={`dialog-icon ${isCreate ? 'dialog-icon-primary' : 'dialog-icon-danger'}`}>
          {isCreate ? <Plus size={22} /> : <Flame size={22} />}
        </div>
        <div>
          <h2 className="dialog-title" id="session-dialog-title">
            {isCreate ? 'Create a session' : 'Burn this session?'}
          </h2>
          <p className="dialog-description" id="session-dialog-description">
            {isCreate
              ? 'Use a short identifier for this isolated working context.'
              : `All temporary context in “${sessionId}” will be permanently removed.`}
          </p>
        </div>
        {isCreate && (
          <div className="field-group">
            <label htmlFor="session-name">Session name</label>
            <input
              aria-describedby={error ? 'session-name-error' : 'session-name-help'}
              aria-invalid={Boolean(error)}
              autoComplete="off"
              className="text-input"
              id="session-name"
              maxLength={64}
              onChange={(event) => setName(event.target.value)}
              placeholder="architecture-review"
              ref={inputRef}
              required
              type="text"
              value={name}
            />
            <small id="session-name-help">Letters, numbers, hyphens, and underscores.</small>
            {error && <p className="field-error" id="session-name-error" role="alert">{error}</p>}
          </div>
        )}
        <div className="dialog-actions">
          <button className="button button-secondary" disabled={busy} onClick={onClose} type="button">
            Cancel
          </button>
          <button
            className={`button ${isCreate ? 'button-primary' : 'button-danger'}`}
            disabled={busy || (isCreate && !name.trim())}
            type="submit"
          >
            {busy && <span className="spinner" aria-hidden="true" />}
            {busy ? 'Working…' : isCreate ? 'Create session' : 'Burn session'}
          </button>
        </div>
      </form>
    </div>
  );
}

function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="workspace-empty">
      <span className="empty-icon" aria-hidden="true"><Icon size={22} /></span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function formatEventLabel(value) {
  return String(value || 'event').replaceAll('_', ' ');
}

export default function ChatPage() {
  const {
    apiUrl,
    burnSession,
    refreshSessions,
    sessionState,
    setNotice,
    setSessionState,
  } = useContext(TelemetryContext);
  const [activeStream, setActiveStream] = useState('');
  const [inputQuery, setInputQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [inspectorTab, setInspectorTab] = useState('context');
  const [sessionDialog, setSessionDialog] = useState(null);
  const [dialogError, setDialogError] = useState('');
  const [dialogBusy, setDialogBusy] = useState(false);

  const streamEndRef = useRef(null);
  const promptRef = useRef(null);
  const abortControllerRef = useRef(null);

  const scrollToStreamEnd = () => {
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    streamEndRef.current?.scrollIntoView?.({ behavior: reducedMotion ? 'auto' : 'smooth' });
  };

  useEffect(scrollToStreamEnd, [activeStream, sessionState.chatHistory]);

  useEffect(() => {
    if (!sessionState.activeSessionId) return undefined;
    const controller = new AbortController();

    const fetchSessionHistory = async () => {
      try {
        const response = await fetch(
          `${apiUrl}/api/session/history/${encodeURIComponent(sessionState.activeSessionId)}`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error(`History request failed (${response.status})`);
        const payload = await response.json();
        if (payload.status === 'success') {
          setSessionState((previous) => ({
            ...previous,
            chatHistory: Array.isArray(payload.data) ? payload.data : [],
            memoryAnchors: [],
            systemLogs: [],
          }));
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          setNotice(`Could not load session history. ${error.message}.`);
        }
      }
    };

    fetchSessionHistory();
    return () => controller.abort();
  }, [apiUrl, sessionState.activeSessionId, setNotice, setSessionState]);

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  const updateFromEvent = (event, data, accumulatedRef) => {
    if (data === '[DONE]') return;

    if (event === 'token' || event === 'response_content') {
      let content = data;
      try {
        content = JSON.parse(data);
      } catch {
        // Plain text SSE payloads are valid.
      }
      if (typeof content === 'string') {
        accumulatedRef.current = event === 'response_content'
          ? content
          : accumulatedRef.current + content;
        setActiveStream(accumulatedRef.current);
      }
      return;
    }

    if (event === 'metadata') {
      try {
        const metadata = JSON.parse(data);
        setSessionState((previous) => {
          const tokensSaved = metadata.tokensSaved ?? previous.tokensSaved;
          const time = new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          });
          return {
            ...previous,
            memoryAnchors: metadata.memoryAnchors || [],
            tokenHistory: appendBounded(previous.tokenHistory, { time, tokens: tokensSaved }),
            tokensSaved,
          };
        });
      } catch {
        // Ignore malformed optional telemetry without interrupting the response.
      }
      return;
    }

    if (event === 'token_usage') {
      try {
        const usage = JSON.parse(data);
        setSessionState((previous) => ({
          ...previous,
          tokensUsed: {
            m1: previous.tokensUsed.m1 + Number(usage.m1 || 0),
            m2: previous.tokensUsed.m2 + Number(usage.m2 || 0),
          },
        }));
      } catch {
        // Ignore malformed optional telemetry without interrupting the response.
      }
      return;
    }

    if (event === 'intent') {
      try {
        const intent = JSON.parse(data);
        setSessionState((previous) => ({
          ...previous,
          intentDistribution: {
            ...previous.intentDistribution,
            [intent]: (previous.intentDistribution[intent] || 0) + 1,
          },
        }));
      } catch {
        // Ignore malformed optional telemetry without interrupting the response.
      }
      return;
    }

    let parsed = data;
    try {
      parsed = JSON.parse(data);
    } catch {
      // Preserve unstructured events as text for operator inspection.
    }
    setSessionState((previous) => ({
      ...previous,
      systemLogs: appendBounded(previous.systemLogs, { type: event, data: parsed }),
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const currentQuery = inputQuery.trim();
    if (!currentQuery || !sessionState.activeSessionId || isProcessing) return;

    const requestStarted = performance.now();
    const controller = new AbortController();
    const accumulatedRef = { current: '' };
    abortControllerRef.current = controller;
    setInputQuery('');
    setIsProcessing(true);
    setActiveStream('');
    setSessionState((previous) => ({
      ...previous,
      phase: 'STREAMING_RESPONSE',
      chatHistory: appendBounded(
        previous.chatHistory,
        { role: 'user', content: currentQuery },
      ),
    }));

    try {
      const response = await fetch(`${apiUrl}/api/agent/query`, {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: currentQuery,
          session_id: sessionState.activeSessionId,
        }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(`Runtime returned ${response.status}`);
      if (!response.body) throw new Error('Streaming is unavailable in this browser');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let sseBuffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const parsed = splitSseFrames(sseBuffer, decoder.decode(value, { stream: true }));
        sseBuffer = parsed.remainder;
        parsed.frames.forEach((frame) => updateFromEvent(
          frame.event,
          frame.data,
          accumulatedRef,
        ));
      }

      sseBuffer += decoder.decode();
      if (sseBuffer.trim()) {
        const finalFrame = parseSseFrame(sseBuffer);
        if (finalFrame) updateFromEvent(finalFrame.event, finalFrame.data, accumulatedRef);
      }

      if (accumulatedRef.current) {
        setSessionState((previous) => ({
          ...previous,
          chatHistory: appendBounded(
            previous.chatHistory,
            { role: 'assistant', content: accumulatedRef.current },
          ),
        }));
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        setNotice('Response generation stopped.');
      } else {
        setSessionState((previous) => ({
          ...previous,
          systemLogs: appendBounded(
            previous.systemLogs,
            { type: 'error', data: error.message },
          ),
        }));
        setNotice(`Response failed. ${error.message}.`);
        setInspectorTab('events');
      }
    } finally {
      abortControllerRef.current = null;
      setActiveStream('');
      setIsProcessing(false);
      setSessionState((previous) => ({
        ...previous,
        lastLatencyMs: Math.round(performance.now() - requestStarted),
        phase: 'IDLE',
      }));
      window.setTimeout(() => promptRef.current?.focus(), 0);
    }
  };

  const stopGeneration = () => abortControllerRef.current?.abort();

  const openCreateDialog = () => {
    setDialogError('');
    setSessionDialog({ mode: 'create' });
  };

  const handleDialogConfirm = async (value) => {
    if (!sessionDialog) return;
    setDialogError('');
    setDialogBusy(true);

    if (sessionDialog.mode === 'delete') {
      const burned = await burnSession(sessionDialog.sessionId);
      if (burned) setSessionDialog(null);
      setDialogBusy(false);
      return;
    }

    const cleanName = value.trim().replace(/\s+/g, '-').toLowerCase();
    if (!/^[a-z0-9_-]+$/.test(cleanName)) {
      setDialogError('Use only letters, numbers, hyphens, and underscores.');
      setDialogBusy(false);
      return;
    }
    if (sessionState.sessions.includes(cleanName)) {
      setDialogError('A session with this name already exists.');
      setDialogBusy(false);
      return;
    }

    try {
      const response = await fetch(`${apiUrl}/api/session/initialize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: cleanName }),
      });
      if (!response.ok) throw new Error(`Runtime returned ${response.status}`);
      await refreshSessions(cleanName);
      setSessionDialog(null);
      setNotice(`Session ${cleanName} is ready.`);
    } catch (error) {
      setDialogError(`Could not create the session. ${error.message}.`);
    } finally {
      setDialogBusy(false);
    }
  };

  const handleCopyCode = async (code, index) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedIndex(index);
      window.setTimeout(() => setCopiedIndex(null), 2000);
    } catch {
      setNotice('Clipboard access was unavailable.');
    }
  };

  const renderMessageContent = (content, messageIndex) => {
    if (!content) return null;
    const parts = content.split(/(```[\s\S]*?```)/g);

    return parts.map((part, partIndex) => {
      const key = `${messageIndex}-${partIndex}`;
      if (!(part.startsWith('```') && part.endsWith('```'))) {
        return <p className="message-text" key={key}>{part}</p>;
      }

      const match = part.match(/```(\w*)\n([\s\S]*?)```/);
      const language = match?.[1] || 'code';
      const code = match?.[2] || part.slice(3, -3);
      return (
        <div className="code-block" key={key}>
          <div className="code-header">
            <span><FileCode2 size={14} aria-hidden="true" /> {language}</span>
            <button
              aria-label={`Copy ${language} code`}
              className="code-copy"
              onClick={() => handleCopyCode(code, key)}
              type="button"
            >
              {copiedIndex === key ? <Check size={14} /> : <Copy size={14} />}
              {copiedIndex === key ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre><code>{code}</code></pre>
        </div>
      );
    });
  };

  const retrievedContextCards = useMemo(() => {
    const contextLog = [...sessionState.systemLogs]
      .reverse()
      .find((log) => log.type === 'retrieved_context');
    if (!contextLog?.data) return [];
    const rawContext = Array.isArray(contextLog.data) ? contextLog.data[0] : contextLog.data;
    if (typeof rawContext !== 'string') return [];

    const cards = [];
    const dependencyMatch = rawContext.match(/<graphify_context>([\s\S]*?)<\/graphify_context>/);
    if (dependencyMatch) {
      cards.push({
        id: 'dependency',
        type: 'Dependency context',
        content: dependencyMatch[1].trim(),
        tone: 'secondary',
      });
    }
    const memoryMatches = rawContext.matchAll(
      /<retrieved_memory>([\s\S]*?)<\/retrieved_memory>/g,
    );
    for (const [index, match] of [...memoryMatches].entries()) {
      cards.push({
        id: `memory-${index}`,
        type: `Retrieved memory ${index + 1}`,
        content: match[1].trim(),
        tone: 'primary',
      });
    }
    return cards;
  }, [sessionState.systemLogs]);

  const latestReformulation = useMemo(
    () => [...sessionState.systemLogs]
      .reverse()
      .find((log) => log.type === 'query_reformulation')?.data,
    [sessionState.systemLogs],
  );

  return (
    <div className="workspace-page">
      <aside className="workspace-panel session-panel" aria-labelledby="sessions-heading">
        <div className="workspace-panel-header">
          <div>
            <span className="eyebrow">Isolated contexts</span>
            <h2 id="sessions-heading"><FolderKanban size={17} /> Sessions</h2>
          </div>
          <button
            aria-label="Create session"
            className="icon-button icon-button-primary"
            onClick={openCreateDialog}
            title="Create session"
            type="button"
          >
            <Plus size={17} />
          </button>
        </div>
        <div className="session-list">
          {sessionState.sessions.length === 0 ? (
            <EmptyState
              description="A session will appear when the runtime connects."
              icon={Database}
              title="No sessions"
            />
          ) : sessionState.sessions.map((sessionId) => {
            const isActive = sessionId === sessionState.activeSessionId;
            return (
              <div className={`session-row ${isActive ? 'is-active' : ''}`} key={sessionId}>
                <button
                  aria-current={isActive ? 'true' : undefined}
                  className="session-select"
                  onClick={() => setSessionState((previous) => ({
                    ...previous,
                    activeSessionId: sessionId,
                  }))}
                  title={sessionId}
                  type="button"
                >
                  <MessageSquare size={15} aria-hidden="true" />
                  <span>{sessionId}</span>
                </button>
                <button
                  aria-label={`Burn session ${sessionId}`}
                  className="session-delete"
                  onClick={() => {
                    setDialogError('');
                    setSessionDialog({ mode: 'delete', sessionId });
                  }}
                  title="Burn session"
                  type="button"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            );
          })}
        </div>
        <div className="session-panel-footer">
          <span className="status-dot" aria-hidden="true" />
          {sessionState.sessions.length} active {sessionState.sessions.length === 1 ? 'session' : 'sessions'}
        </div>
      </aside>

      <section className="workspace-panel conversation-panel" aria-labelledby="conversation-heading">
        <div className="workspace-panel-header conversation-header">
          <div>
            <span className="eyebrow">Bounded reasoning</span>
            <h2 id="conversation-heading"><MessageSquare size={17} /> Conversation</h2>
          </div>
          <span className={`status-chip status-${isProcessing ? 'working' : 'ready'}`}>
            {isProcessing && <LoaderCircle className="spinner-icon" size={14} />}
            {isProcessing ? 'Generating' : 'Ready'}
          </span>
        </div>

        <div className="message-list" aria-live="polite">
          {sessionState.chatHistory.length === 0 && !activeStream ? (
            <EmptyState
              description="Ask a question or provide a task. SC-EVM will assemble only the context needed for this session."
              icon={MessageSquare}
              title="Start a focused session"
            />
          ) : (
            sessionState.chatHistory.map((message, index) => (
              <article className={`message message-${message.role}`} key={`${message.role}-${index}`}>
                <div className="message-avatar" aria-hidden="true">
                  {message.role === 'user' ? <span>RG</span> : <Code2 size={16} />}
                </div>
                <div className="message-body">
                  <div className="message-meta">
                    <strong>{message.role === 'user' ? 'You' : 'SC-EVM'}</strong>
                    {message.role !== 'user' && <span>AI-generated</span>}
                  </div>
                  <div>{renderMessageContent(message.content, index)}</div>
                </div>
              </article>
            ))
          )}

          {activeStream && (
            <article className="message message-assistant message-streaming">
              <div className="message-avatar" aria-hidden="true"><Code2 size={16} /></div>
              <div className="message-body">
                <div className="message-meta">
                  <strong>SC-EVM</strong>
                  <span>Generating</span>
                </div>
                <div>{renderMessageContent(activeStream, 'active')}</div>
              </div>
            </article>
          )}
          <div ref={streamEndRef} />
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="workspace-prompt">Message SC-EVM</label>
          <textarea
            className="composer-input"
            disabled={isProcessing || !sessionState.activeSessionId}
            id="workspace-prompt"
            maxLength={12000}
            onChange={(event) => setInputQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder={sessionState.activeSessionId
              ? 'Describe the task, constraint, or decision…'
              : 'Waiting for an active session…'}
            ref={promptRef}
            rows={3}
            value={inputQuery}
          />
          <div className="composer-footer">
            <span>Enter to send · Shift + Enter for a new line</span>
            {isProcessing ? (
              <button className="button button-secondary button-compact" onClick={stopGeneration} type="button">
                <Square size={14} fill="currentColor" /> Stop
              </button>
            ) : (
              <button
                className="button button-primary button-compact"
                disabled={!inputQuery.trim() || !sessionState.activeSessionId}
                type="submit"
              >
                <Send size={15} aria-hidden="true" /> Send
              </button>
            )}
          </div>
        </form>
      </section>

      <aside className="workspace-panel inspector-panel" aria-label="Context inspector">
        <div className="inspector-tabs" role="tablist" aria-label="Inspector views">
          <button
            aria-controls="context-panel"
            aria-selected={inspectorTab === 'context'}
            className={inspectorTab === 'context' ? 'is-active' : ''}
            onClick={() => setInspectorTab('context')}
            role="tab"
            type="button"
          >
            <Layers3 size={15} /> Context
          </button>
          <button
            aria-controls="events-panel"
            aria-selected={inspectorTab === 'events'}
            className={inspectorTab === 'events' ? 'is-active' : ''}
            onClick={() => setInspectorTab('events')}
            role="tab"
            type="button"
          >
            <ServerCog size={15} /> Events
            {sessionState.systemLogs.length > 0 && (
              <span className="tab-count">{sessionState.systemLogs.length}</span>
            )}
          </button>
        </div>

        {inspectorTab === 'context' ? (
          <div className="inspector-content" id="context-panel" role="tabpanel">
            <div className="inspector-intro">
              <PanelRight size={17} aria-hidden="true" />
              <div>
                <strong>Context used for this turn</strong>
                <p>Inspect what was selected before the model responded.</p>
              </div>
            </div>

            {latestReformulation && (
              <section className="inspector-section">
                <span className="eyebrow">Request framing</span>
                <div className="context-card">
                  <span>Retrieval query</span>
                  <p className="mono">{latestReformulation.search_vector_query}</p>
                </div>
                <div className="context-card">
                  <span>Grounded request</span>
                  <p>{latestReformulation.grounded_llm_prompt}</p>
                </div>
              </section>
            )}

            <section className="inspector-section">
              <div className="section-label-row">
                <span className="eyebrow">Retrieved evidence</span>
                <span>{retrievedContextCards.length}</span>
              </div>
              {retrievedContextCards.length === 0 ? (
                <EmptyState
                  description="Evidence selected for a request appears here."
                  icon={Clipboard}
                  title="No context selected"
                />
              ) : retrievedContextCards.map((card) => (
                <article className={`evidence-card evidence-${card.tone}`} key={card.id}>
                  <span>{card.type}</span>
                  <p>{card.content}</p>
                </article>
              ))}
            </section>
          </div>
        ) : (
          <div className="inspector-content" id="events-panel" role="tabpanel">
            <div className="inspector-intro">
              <ServerCog size={17} aria-hidden="true" />
              <div>
                <strong>Runtime event stream</strong>
                <p>Operational events from the current request.</p>
              </div>
            </div>
            {sessionState.systemLogs.length === 0 ? (
              <EmptyState
                description="Events appear as the runtime processes a request."
                icon={ServerCog}
                title="No events yet"
              />
            ) : (
              <ol className="event-list">
                {sessionState.systemLogs.map((log, index) => (
                  <li className={`event-row event-${log.type}`} key={`${log.type}-${index}`}>
                    <span className="event-marker" aria-hidden="true" />
                    <div>
                      <span className="event-label">{formatEventLabel(log.type)}</span>
                      {log.type === 'error' ? (
                        <p className="event-error"><AlertCircle size={14} /> {String(log.data)}</p>
                      ) : (
                        <pre>{typeof log.data === 'string'
                          ? log.data
                          : JSON.stringify(log.data, null, 2)}</pre>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </aside>

      <SessionDialog
        busy={dialogBusy}
        error={dialogError}
        mode={sessionDialog?.mode}
        onClose={() => !dialogBusy && setSessionDialog(null)}
        onConfirm={handleDialogConfirm}
        open={Boolean(sessionDialog)}
        sessionId={sessionDialog?.sessionId}
      />
    </div>
  );
}
