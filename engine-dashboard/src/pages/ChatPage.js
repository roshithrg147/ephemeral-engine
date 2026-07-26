import React, {
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Check,
  Code2,
  Copy,
  FileCode2,
  Flame,
  GitBranch,
  Layers3,
  LoaderCircle,
  MessageSquare,
  PanelRight,
  Plus,
  Send,
  ServerCog,
  Sparkles,
  Square,
  Zap,
} from 'lucide-react';
import { TelemetryContext } from '../App';
import { parseSseFrame, splitSseFrames } from '../sse';

const MAX_TELEMETRY_POINTS = 200;
const appendBounded = (items, item) => [...items, item].slice(-MAX_TELEMETRY_POINTS);

function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="workspace-empty-state">
      <div className="empty-icon-wrap">
        <Icon size={28} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

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
            {busy ? <span className="spinner" /> : isCreate ? <Plus size={16} /> : <Flame size={16} />}
            {busy ? 'Working…' : isCreate ? 'Create session' : 'Burn session'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default function ChatPage() {
  const {
    apiUrl,
    burnSession,
    getAuthHeaders,
    refreshSessions,
    sessionState,
    setNotice,
    setSessionState,
  } = useContext(TelemetryContext) || {};

  const [inputQuery, setInputQuery] = useState('');
  const [activeStream, setActiveStream] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [inspectorTab, setInspectorTab] = useState('context');
  const [sessionDialog, setSessionDialog] = useState(null);
  const [dialogError, setDialogError] = useState('');
  const [dialogBusy, setDialogBusy] = useState(false);

  // Dynamic Context & Events Inspector state
  const [groundedQuery, setGroundedQuery] = useState('');
  const [groundedPromptText, setGroundedPromptText] = useState('');
  const [contextCards, setContextCards] = useState([]);
  const [eventFilter, setEventFilter] = useState('All');
  const [expandedLogId, setExpandedLogId] = useState(null);

  const abortControllerRef = useRef(null);
  const streamEndRef = useRef(null);
  const promptRef = useRef(null);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeStream, sessionState.chatHistory]);

  useEffect(() => {
    if (!sessionState.activeSessionId) return;
    const controller = new AbortController();

    const fetchSessionHistory = async () => {
      try {
        const response = await fetch(
          `${apiUrl}/api/session/history/${encodeURIComponent(sessionState.activeSessionId)}`,
          { headers: getAuthHeaders?.() || {}, signal: controller.signal },
        );
        if (!response.ok) throw new Error(`History request failed (${response.status})`);
        const payload = await response.json();
        if (payload.status === 'success') {
          setSessionState((previous) => ({
            ...previous,
            chatHistory: Array.isArray(payload.data) ? payload.data : [],
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
  }, [apiUrl, getAuthHeaders, sessionState.activeSessionId, setNotice, setSessionState]);

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  const updateFromEvent = (event, data, accumulatedRef) => {
    if (data === '[DONE]') return;

    const timeStr = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

    let parsedData = data;
    try {
      parsedData = JSON.parse(data);
    } catch {
      // Plain text payload
    }

    // Append to system logs for real-time Events Tab
    const logItem = {
      id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      type: event,
      time: timeStr,
      data: parsedData,
      raw: data,
    };

    setSessionState((previous) => ({
      ...previous,
      systemLogs: appendBounded(previous.systemLogs || [], logItem),
    }));

    if (event === 'token' || event === 'response_content') {
      let content = data;
      try {
        content = JSON.parse(data);
      } catch {
        // Plain text SSE payloads are valid.
      }
      if (typeof content === 'string') {
        accumulatedRef.current =
          event === 'response_content' ? content : accumulatedRef.current + content;
        setActiveStream(accumulatedRef.current);
      }
      return;
    }

    if (event === 'query_reformulation') {
      if (typeof parsedData === 'object' && parsedData !== null) {
        if (parsedData.search_vector_query) setGroundedQuery(parsedData.search_vector_query);
        if (parsedData.grounded_llm_prompt) setGroundedPromptText(parsedData.grounded_llm_prompt);
      } else if (typeof parsedData === 'string') {
        setGroundedQuery(parsedData);
      }
      return;
    }

    if (event === 'retrieved_context') {
      const cards = [];
      let rawText = '';
      if (Array.isArray(parsedData)) rawText = parsedData.join('\n');
      else if (typeof parsedData === 'string') rawText = parsedData;
      else if (typeof parsedData === 'object') rawText = JSON.stringify(parsedData, null, 2);

      const depMatch = rawText.match(/<graphify_context>([\s\S]*?)<\/graphify_context>/);
      if (depMatch) {
        cards.push({
          id: 'graphify-ast',
          type: 'Graphify AST Grounding',
          content: depMatch[1].trim(),
          tone: 'accent',
        });
      }

      const memoryMatches = rawText.matchAll(
        /<retrieved_memory>([\s\S]*?)<\/retrieved_memory>/g,
      );
      for (const [index, match] of [...memoryMatches].entries()) {
        cards.push({
          id: `memory-${index}`,
          type: `Retrieved Memory Anchor ${index + 1}`,
          content: match[1].trim(),
          tone: 'primary',
        });
      }

      if (cards.length === 0 && rawText.trim()) {
        cards.push({
          id: 'retrieved-general',
          type: 'Grounding Evidence Context',
          content: rawText,
          tone: 'secondary',
        });
      }

      setContextCards(cards);
      return;
    }

    if (event === 'metadata') {
      if (typeof parsedData === 'object' && parsedData !== null) {
        setSessionState((previous) => {
          const tokensSaved = parsedData.tokensSaved ?? previous.tokensSaved;
          return {
            ...previous,
            memoryAnchors: parsedData.memoryAnchors || previous.memoryAnchors || [],
            tokenHistory: appendBounded(previous.tokenHistory, { time: timeStr, tokens: tokensSaved }),
            tokensSaved,
          };
        });
      }
      return;
    }

    if (event === 'token_usage') {
      if (typeof parsedData === 'object' && parsedData !== null) {
        setSessionState((previous) => ({
          ...previous,
          tokensUsed: {
            m1: previous.tokensUsed.m1 + Number(parsedData.m1 || 0),
            m2: previous.tokensUsed.m2 + Number(parsedData.m2 || 0),
          },
        }));
      }
      return;
    }

    if (event === 'intent') {
      const intentName = typeof parsedData === 'string' ? parsedData : parsedData?.intent || 'chat';
      setSessionState((previous) => ({
        ...previous,
        intentDistribution: {
          ...previous.intentDistribution,
          [intentName]: (previous.intentDistribution[intentName] || 0) + 1,
        },
      }));
    }
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
    setGroundedQuery('');
    setGroundedPromptText('');
    setContextCards([]);

    setSessionState((previous) => ({
      ...previous,
      phase: 'STREAMING_RESPONSE',
      chatHistory: appendBounded(previous.chatHistory, { role: 'user', content: currentQuery }),
    }));

    try {
      const response = await fetch(`${apiUrl}/api/agent/query`, {
        method: 'POST',
        headers: getAuthHeaders?.({
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        }) || {
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
        parsed.frames.forEach((frame) => updateFromEvent(frame.event, frame.data, accumulatedRef));
      }

      sseBuffer += decoder.decode();
      if (sseBuffer.trim()) {
        const finalFrame = parseSseFrame(sseBuffer);
        if (finalFrame) updateFromEvent(finalFrame.event, finalFrame.data, accumulatedRef);
      }

      if (accumulatedRef.current) {
        setSessionState((previous) => ({
          ...previous,
          chatHistory: appendBounded(previous.chatHistory, {
            role: 'assistant',
            content: accumulatedRef.current,
          }),
        }));
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        setNotice('Response generation stopped.');
      } else {
        setSessionState((previous) => ({
          ...previous,
          systemLogs: appendBounded(previous.systemLogs, {
            type: 'error',
            time: new Date().toLocaleTimeString(),
            data: error.message,
          }),
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
        headers: getAuthHeaders?.({ 'Content-Type': 'application/json' }) || {
          'Content-Type': 'application/json',
        },
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
        return (
          <p className="message-text" key={key}>
            {part}
          </p>
        );
      }

      const match = part.match(/```(\w*)\n([\s\S]*?)```/);
      const language = match?.[1] || 'code';
      const code = match?.[2] || part.slice(3, -3);
      return (
        <div className="code-block" key={key}>
          <div className="code-header">
            <span>
              <FileCode2 size={14} aria-hidden="true" /> {language}
            </span>
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
          <pre>
            <code>{code}</code>
          </pre>
        </div>
      );
    });
  };

  const filteredLogs = useMemo(() => {
    const logs = sessionState.systemLogs || [];
    if (eventFilter === 'All') return logs;
    if (eventFilter === 'Stream')
      return logs.filter((l) => l.type === 'token' || l.type === 'response_content');
    if (eventFilter === 'Context')
      return logs.filter(
        (l) => l.type === 'query_reformulation' || l.type === 'retrieved_context',
      );
    if (eventFilter === 'System')
      return logs.filter((l) => l.type === 'metadata' || l.type === 'token_usage');
    if (eventFilter === 'Error') return logs.filter((l) => l.type === 'error');
    return logs;
  }, [sessionState.systemLogs, eventFilter]);

  return (
    <div className="workspace-page expanded-chat-workspace">
      <section className="workspace-panel conversation-panel" aria-labelledby="conversation-heading">
        <div className="workspace-panel-header conversation-header">
          <div>
            <span className="eyebrow">
              Isolated Context: {sessionState.activeSessionId || 'default'}
            </span>
            <h2 id="conversation-heading">
              <MessageSquare size={17} /> Bounded Reasoning Workspace
            </h2>
          </div>
          <div className="header-status-group">
            <span className={`status-chip status-${isProcessing ? 'working' : 'ready'}`}>
              {isProcessing && <LoaderCircle className="spinner-icon" size={14} />}
              {isProcessing ? 'Generating' : 'Ready'}
            </span>
          </div>
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
              <article
                className={`message message-${message.role}`}
                key={`${message.role}-${index}`}
              >
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
              <div className="message-avatar" aria-hidden="true">
                <Code2 size={16} />
              </div>
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
          <label className="sr-only" htmlFor="workspace-prompt">
            Message SC-EVM
          </label>
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
            placeholder={
              sessionState.activeSessionId
                ? 'Describe the task, constraint, or decision…'
                : 'Waiting for an active session…'
            }
            ref={promptRef}
            rows={3}
            value={inputQuery}
          />
          <div className="composer-footer">
            <span>Enter to send · Shift + Enter for a new line</span>
            {isProcessing ? (
              <button
                className="button button-secondary button-compact"
                onClick={stopGeneration}
                type="button"
              >
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
            {(sessionState.systemLogs || []).length > 0 && (
              <span className="tab-count">{(sessionState.systemLogs || []).length}</span>
            )}
          </button>
        </div>

        {inspectorTab === 'context' ? (
          <div className="inspector-content" id="context-panel" role="tabpanel">
            <div className="inspector-intro">
              <PanelRight size={17} aria-hidden="true" />
              <div>
                <strong>Context Grounding & Framing</strong>
                <p>Inspect search vectors, grounded prompt framing, and AST evidence.</p>
              </div>
            </div>

            {/* Query Reformulation & Vector Query */}
            {(groundedQuery || groundedPromptText) && (
              <div className="context-card context-card-query">
                <div className="context-card-header">
                  <Sparkles size={15} className="icon-accent" />
                  <strong>Grounded Query Framing</strong>
                </div>
                {groundedQuery && (
                  <div className="query-field">
                    <small>Search Vector Query:</small>
                    <code>{groundedQuery}</code>
                  </div>
                )}
                {groundedPromptText && (
                  <div className="query-field">
                    <small>Grounded LLM Prompt:</small>
                    <p>{groundedPromptText}</p>
                  </div>
                )}
              </div>
            )}

            {/* Retrieved Context Cards */}
            {contextCards.length > 0 ? (
              <div className="retrieved-cards-list">
                {contextCards.map((card) => (
                  <div key={card.id} className={`context-card context-card-${card.tone}`}>
                    <div className="context-card-header">
                      {card.tone === 'accent' ? <GitBranch size={15} /> : <Zap size={15} />}
                      <strong>{card.type}</strong>
                    </div>
                    <pre className="context-card-body">{card.content}</pre>
                  </div>
                ))}
              </div>
            ) : (
              !groundedQuery && (
                <EmptyState
                  description="When a query is executed, retrieved AST nodes, vector chunks, and prompt grounding will appear here."
                  icon={Layers3}
                  title="No context retrieved yet"
                />
              )
            )}

            {/* Memory Anchors */}
            {(sessionState.memoryAnchors || []).length > 0 && (
              <div className="memory-anchors-panel">
                <h4>Learned Session Memory Anchors</h4>
                <ul>
                  {sessionState.memoryAnchors.map((anchor, idx) => (
                    <li key={idx}>
                      <Zap size={13} /> {anchor}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="inspector-content" id="events-panel" role="tabpanel">
            <div className="inspector-intro">
              <ServerCog size={17} aria-hidden="true" />
              <div>
                <strong>Live Event Stream</strong>
                <p>Monitor real-time SSE frame events and internal SC-EVM calls.</p>
              </div>
            </div>

            <div className="events-filter-bar">
              {['All', 'Stream', 'Context', 'System', 'Error'].map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`filter-btn ${eventFilter === f ? 'is-active' : ''}`}
                  onClick={() => setEventFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>

            <div className="events-log-list">
              {filteredLogs.length === 0 ? (
                <EmptyState
                  description="System events and streaming frames will appear here in real time."
                  icon={ServerCog}
                  title="No event frames captured"
                />
              ) : (
                filteredLogs
                  .slice()
                  .reverse()
                  .map((log) => {
                    const isExpanded = expandedLogId === log.id;
                    const isError = log.type === 'error';
                    return (
                      <div
                        key={log.id}
                        className={`event-log-item ${isError ? 'event-error' : ''}`}
                        onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="event-log-header">
                          <span className="event-time">{log.time || 'now'}</span>
                          <span className={`event-tag tag-${log.type}`}>{log.type}</span>
                          <span className="event-summary">
                            {typeof log.data === 'string'
                              ? log.data.slice(0, 50)
                              : JSON.stringify(log.data).slice(0, 50)}
                          </span>
                        </div>
                        {isExpanded && (
                          <pre className="event-json">
                            {JSON.stringify(log.data || log.raw, null, 2)}
                          </pre>
                        )}
                      </div>
                    );
                  })
              )}
            </div>
          </div>
        )}
      </aside>

      <SessionDialog
        busy={dialogBusy}
        error={dialogError}
        mode={sessionDialog?.mode}
        onClose={() => setSessionDialog(null)}
        onConfirm={handleDialogConfirm}
        open={Boolean(sessionDialog)}
        sessionId={sessionDialog?.sessionId}
      />
    </div>
  );
}
