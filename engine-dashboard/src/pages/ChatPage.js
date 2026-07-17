import React, { useState, useEffect, useRef, useContext } from 'react';
import { TelemetryContext } from '../App';
import { Terminal, Cpu, Play, Layers, Copy, Check, FileCode, AlertCircle, Plus, Trash2, FolderKanban, MessageSquare } from 'lucide-react';
import { parseSseFrame, splitSseFrames } from '../sse';

const MAX_TELEMETRY_POINTS = 200;
const appendBounded = (items, item) => [...items, item].slice(-MAX_TELEMETRY_POINTS);

export default function ChatPage() {
  const { sessionState, setSessionState } = useContext(TelemetryContext);
  const [activeStream, setActiveStream] = useState('');
  const [inputQuery, setInputQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);

  const streamEndRef = useRef(null);
  const logsEndRef = useRef(null);
  const contextEndRef = useRef(null);

  const API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeStream, sessionState.chatHistory]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessionState.systemLogs]);

  useEffect(() => {
    contextEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessionState.systemLogs]);

  // Fetch session history when active session changes
  useEffect(() => {
    if (!sessionState.activeSessionId) return;

    const fetchSessionHistory = async () => {
      try {
        const res = await fetch(`${API_URL}/api/session/history/${sessionState.activeSessionId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'success') {
            setSessionState(prev => ({
              ...prev,
              chatHistory: data.data || [],
              systemLogs: [], // Reset logs for fresh session context
              memoryAnchors: [] // Reset anchors to fetch clean state
            }));
          }
        }
      } catch (e) {
        console.error("Failed to fetch session history:", e);
      }
    };

    fetchSessionHistory();
  }, [sessionState.activeSessionId, API_URL, setSessionState]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputQuery || !sessionState.activeSessionId) return;
    
    const currentQuery = inputQuery;
    const requestStarted = performance.now();
    setInputQuery('');
    setIsProcessing(true);
    setSessionState(prev => ({ 
      ...prev, 
      chatHistory: appendBounded(prev.chatHistory, { role: 'user', content: currentQuery })
    }));
    setActiveStream('');
    
    try {
      setSessionState(prev => ({ ...prev, phase: 'Streaming Response' }));
      
      const response = await fetch(`${API_URL}/api/agent/query`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json', 
          'Accept': 'text/event-stream' 
        },
        body: JSON.stringify({ prompt: currentQuery, session_id: sessionState.activeSessionId })
      });

      if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedStream = '';
      let sseBuffer = '';

      const handleFrame = ({ event, data }) => {
        if (data === '[DONE]') return;

        if (event === 'token' || event === 'response_content') {
          let content;
          try {
            content = JSON.parse(data);
          } catch {
            content = data;
          }
          if (typeof content === 'string') {
            accumulatedStream = event === 'response_content'
              ? content
              : accumulatedStream + content;
            setActiveStream(accumulatedStream);
          }
          return;
        }

        if (event === 'metadata') {
          try {
            const meta = JSON.parse(data);
            setSessionState(prev => {
              const tokensSaved = meta.tokensSaved ?? prev.tokensSaved;
              const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
              return {
                ...prev,
                tokensSaved,
                memoryAnchors: meta.memoryAnchors || [],
                tokenHistory: appendBounded(prev.tokenHistory, { time, tokens: tokensSaved })
              };
            });
          } catch {}
          return;
        }

        if (event === 'token_usage') {
          try {
            const usage = JSON.parse(data);
            setSessionState(prev => ({
              ...prev,
              tokensUsed: {
                m1: prev.tokensUsed.m1 + Number(usage.m1 || 0),
                m2: prev.tokensUsed.m2 + Number(usage.m2 || 0)
              }
            }));
          } catch {}
          return;
        }

        if (event === 'intent') {
          try {
            const intent = JSON.parse(data);
            setSessionState(prev => ({
              ...prev,
              intentDistribution: {
                ...prev.intentDistribution,
                [intent]: (prev.intentDistribution[intent] || 0) + 1
              }
            }));
          } catch {}
          return;
        }

        try {
          const parsed = JSON.parse(data);
          setSessionState(prev => ({
            ...prev,
            systemLogs: appendBounded(prev.systemLogs, { type: event, data: parsed })
          }));
        } catch (error) {
          console.error("Failed to parse event data", data, error);
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const parsed = splitSseFrames(sseBuffer, decoder.decode(value, { stream: true }));
        sseBuffer = parsed.remainder;
        parsed.frames.forEach(handleFrame);
      }

      sseBuffer += decoder.decode();
      if (sseBuffer.trim()) {
        const finalFrame = parseSseFrame(sseBuffer);
        if (finalFrame) handleFrame(finalFrame);
      }
      
      if (accumulatedStream) {
        setSessionState(prev => ({
          ...prev,
          chatHistory: appendBounded(prev.chatHistory, { role: 'assistant', content: accumulatedStream })
        }));
      }
      setActiveStream('');
      
    } catch (error) {
      console.error("Stream Error:", error);
      setSessionState(prev => ({
        ...prev,
        systemLogs: appendBounded(prev.systemLogs, { type: 'error', data: error.message })
      }));
    } finally {
      setIsProcessing(false);
      setSessionState(prev => ({
        ...prev,
        phase: 'IDLE',
        lastLatencyMs: Math.round(performance.now() - requestStarted)
      }));
    }
  };

  const handleCreateSession = async () => {
    const sessionName = prompt("Enter a unique name/ID for the new session:");
    if (!sessionName) return;
    const cleanName = sessionName.trim().replace(/\s+/g, '_').toLowerCase();
    if (!cleanName) return;
    
    if (sessionState.sessions.includes(cleanName)) {
      alert("A session with this ID already exists!");
      return;
    }
    
    try {
      const res = await fetch(`${API_URL}/api/session/initialize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: cleanName })
      });
      if (res.ok) {
        setSessionState(prev => ({
          ...prev,
          sessions: [...prev.sessions, cleanName],
          activeSessionId: cleanName
        }));
      }
    } catch (e) {
      console.error("Failed to initialize session:", e);
    }
  };

  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to /burn session "${sessionId}"?`)) return;
    
    try {
      const res = await fetch(`${API_URL}/api/session/burn/${sessionId}`, { method: 'DELETE' });
      if (res.ok) {
        const listRes = await fetch(`${API_URL}/api/session/list`);
        if (listRes.ok) {
          const listData = await listRes.json();
          const remainingSessions = listData.data || [];
          
          if (remainingSessions.length === 0) {
            const defaultSession = 'session_1';
            await fetch(`${API_URL}/api/session/initialize`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ session_id: defaultSession })
            });
            setSessionState(prev => ({
              ...prev,
              sessions: [defaultSession],
              activeSessionId: defaultSession,
              chatHistory: [],
              systemLogs: []
            }));
          } else {
            const nextActive = sessionId === sessionState.activeSessionId ? remainingSessions[0] : sessionState.activeSessionId;
            setSessionState(prev => ({
              ...prev,
              sessions: remainingSessions,
              activeSessionId: nextActive
            }));
          }
        }
      }
    } catch (e) {
      console.error("Failed to delete session:", e);
    }
  };

  const handleCopyCode = (code, index) => {
    navigator.clipboard.writeText(code);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const renderMessageContent = (content, messageIdx) => {
    if (!content) return null;
    const parts = content.split(/(```[\s\S]*?```)/g);
    
    return parts.map((part, partIdx) => {
      const globalIdx = `${messageIdx}-${partIdx}`;
      if (part.startsWith('```') && part.endsWith('```')) {
        const match = part.match(/```(\w*)\n([\s\S]*?)```/);
        const language = match ? match[1] : 'code';
        const code = match ? match[2] : part.slice(3, -3);
        
        return (
          <div key={globalIdx} className="my-3 rounded-lg overflow-hidden border border-gray-800/80 bg-gray-950/80 font-mono text-xs shadow-2xl transition-all duration-300 hover:border-emerald-500/30">
            <div className="flex justify-between items-center bg-gray-900/60 px-4 py-2 border-b border-gray-800/80 text-gray-400">
              <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 flex items-center gap-1.5">
                <FileCode size={12} /> {language || 'code'}
              </span>
              <button 
                onClick={() => handleCopyCode(code, globalIdx)}
                className="text-[10px] hover:text-emerald-400 transition-colors uppercase font-bold tracking-widest cursor-pointer flex items-center gap-1"
              >
                {copiedIndex === globalIdx ? (
                  <>
                    <Check size={12} className="text-emerald-400 animate-scale" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
            <pre className="p-4 overflow-x-auto text-gray-300 whitespace-pre leading-relaxed scrollbar-thin">
              <code>{code}</code>
            </pre>
          </div>
        );
      }
      
      return (
        <div key={globalIdx} className="whitespace-pre-wrap text-sm leading-relaxed text-gray-200">
          {part}
        </div>
      );
    });
  };

  const parseRetrievedContext = () => {
    const logs = [...sessionState.systemLogs].reverse();
    const contextLog = logs.find(log => log.type === 'retrieved_context');
    if (!contextLog || !contextLog.data || contextLog.data.length === 0) return [];

    const contextStr = contextLog.data[0];
    const cards = [];

    const graphifyMatch = contextStr.match(/<graphify_context>([\s\S]*?)<\/graphify_context>/);
    if (graphifyMatch) {
      cards.push({
        id: 'graphify',
        type: 'Graphify Dependency Link',
        content: graphifyMatch[1].trim(),
        style: 'border-purple-900/50 bg-purple-950/10 text-purple-200 glow-border-purple card-3d-purple'
      });
    }

    const memoryMatches = contextStr.matchAll(/<retrieved_memory>([\s\S]*?)<\/retrieved_memory>/g);
    let index = 1;
    for (const match of memoryMatches) {
      cards.push({
        id: `memory-${index}`,
        type: `Vector Cluster Memory #${index}`,
        content: match[1].trim(),
        style: 'border-emerald-900/50 bg-emerald-950/10 text-emerald-200 glow-border-emerald card-3d'
      });
      index++;
    }

    return cards;
  };

  const retrievedContextCards = parseRetrievedContext();

  const getLatestReformulation = () => {
    const logs = [...sessionState.systemLogs].reverse();
    const reformLog = logs.find(log => log.type === 'query_reformulation');
    return reformLog ? reformLog.data : null;
  };

  const latestReformulation = getLatestReformulation();

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-gray-950 p-6 overflow-hidden perspective-1000">
      
      {/* 3 Vertical Sections side-by-side Layout (Sidebar + Chat Terminal + Context & Logs stacked) */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">
        
        {/* Section 1: Sessions manager Sidebar (col-span-2) */}
        <div className="lg:col-span-2 flex flex-col gap-4 border border-gray-800 bg-gray-900/20 backdrop-blur-md rounded-xl p-4 shadow-xl overflow-hidden h-full card-3d preserve-3d">
          <div className="flex justify-between items-center border-b border-gray-800 pb-2 shrink-0">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1.5 font-mono">
              <FolderKanban size={14} className="text-emerald-400" />
              Sessions
            </h2>
            <button 
              onClick={handleCreateSession}
              title="Create New Session"
              className="p-1 bg-emerald-950/40 hover:bg-emerald-800/80 border border-emerald-900/50 rounded text-emerald-400 hover:text-white transition-all cursor-pointer hover:scale-105 active:scale-95"
            >
              <Plus size={14} />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto flex flex-col gap-2 min-h-0 pr-1 scrollbar-thin">
            {sessionState.sessions.length === 0 ? (
              <span className="text-xs text-gray-600 italic p-2 text-center">No active sessions</span>
            ) : (
              sessionState.sessions.map((sid) => {
                const isActive = sid === sessionState.activeSessionId;
                return (
                  <div
                    key={sid}
                    onClick={() => setSessionState(prev => ({ ...prev, activeSessionId: sid }))}
                    className={`group flex justify-between items-center px-3 py-2.5 rounded-lg border text-xs font-mono transition-all duration-300 cursor-pointer ${
                      isActive 
                        ? 'border-purple-800/80 bg-purple-950/20 text-purple-200 glow-border-purple shadow-md' 
                        : 'border-gray-800/60 bg-gray-950/20 text-gray-400 hover:text-gray-200 hover:border-gray-700/50 hover:bg-gray-900/30'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <MessageSquare size={12} className={isActive ? 'text-purple-400' : 'text-gray-500'} />
                      <span className="truncate" title={sid}>{sid}</span>
                    </div>
                    
                    <button
                      onClick={(e) => handleDeleteSession(sid, e)}
                      title="Burn Session"
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-950/40 border border-transparent hover:border-red-900/50 rounded text-red-500 hover:text-red-400 transition-all cursor-pointer shrink-0"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Section 2: Interactive Chat Terminal (col-span-6) */}
        <div className="lg:col-span-6 flex flex-col gap-4 border border-gray-800 bg-gray-900/20 backdrop-blur-md rounded-xl p-4 shadow-xl overflow-hidden h-full card-3d preserve-3d">
          <div className="flex justify-between items-center border-b border-gray-800 pb-2 shrink-0">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2 font-mono">
              <Terminal size={14} className="text-emerald-400" />
              Interactive Chat Terminal
            </h2>
            {isProcessing && (
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
            )}
          </div>
          
          <div className="flex-1 overflow-y-auto flex flex-col gap-4 min-h-0 pr-1 scrollbar-thin">
            {sessionState.chatHistory.length === 0 && !activeStream && (
               <div className="flex-1 flex flex-col items-center justify-center text-center p-6 select-none animate-float">
                  <div className="p-4 bg-emerald-950/20 border border-emerald-900/30 rounded-full mb-3 text-emerald-500 shadow-inner">
                    <Terminal size={32} />
                  </div>
                  <h3 className="text-sm font-bold text-gray-300">Awaiting Ingestion...</h3>
                  <p className="text-xs text-gray-500 mt-1 max-w-[240px]">Initialize the session registry and input architectural constraints.</p>
               </div>
            )}
            
            {sessionState.chatHistory.map((msg, idx) => (
              <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-start' : 'items-end'} transition-all duration-300 animate-slide`}>
                <div className={`max-w-[90%] rounded-xl p-4 border shadow-md transition-all ${
                  msg.role === 'user' 
                    ? 'bg-blue-950/20 border-blue-900/50 text-blue-100 focus-within:border-blue-700 hover:border-blue-800/80 shadow-blue-950/10' 
                    : 'bg-gray-900/60 border-gray-800/80 text-gray-200 hover:border-gray-700/80 shadow-black/20'
                }`}>
                  <span className={`text-[10px] font-bold uppercase tracking-widest mb-1.5 block ${msg.role === 'user' ? 'text-blue-400' : 'text-emerald-400'}`}>
                    {msg.role === 'user' ? 'react_dashboard_01' : 'Assistant'}
                  </span>
                  <div>{renderMessageContent(msg.content, idx)}</div>
                </div>
              </div>
            ))}

            {activeStream && (
              <div className="flex flex-col items-end animate-slide">
                <div className="max-w-[90%] rounded-xl p-4 bg-gray-900/60 border border-emerald-900/30 text-gray-200 shadow-lg glow-border-emerald">
                  <span className="text-[10px] font-bold uppercase tracking-widest mb-1.5 block text-emerald-400 animate-pulse">
                    Assistant (Streaming...)
                  </span>
                  <div>{renderMessageContent(activeStream, 'active')}</div>
                </div>
              </div>
            )}
            <div ref={streamEndRef} />
          </div>

          {/* Input Form */}
          <form onSubmit={handleSubmit} className="flex gap-3 mt-auto shrink-0 border-t border-gray-800/80 pt-4">
            <input 
              type="text" 
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Enter prompt or architectural requirement..."
              className="flex-1 bg-gray-950/80 border border-gray-800 focus:border-emerald-500/50 text-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-1 focus:ring-emerald-500/20 transition-all text-sm font-sans shadow-inner placeholder:text-gray-600"
              disabled={isProcessing}
            />
            <button 
              type="submit" 
              disabled={isProcessing || !inputQuery}
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 px-6 rounded-lg transition-all text-sm shadow-lg btn-3d disabled:bg-gray-800 disabled:text-gray-500 disabled:shadow-none disabled:transform-none shrink-0 flex items-center gap-1.5 cursor-pointer"
            >
              <Play size={14} fill="currentColor" /> Execute
            </button>
          </form>
        </div>

        {/* Section 3: System Context & Logs stacked vertically (col-span-4) */}
        <div className="lg:col-span-4 flex flex-col gap-6 h-full min-h-0">
          
          {/* Top Panel: Grounding Context (50% height) */}
          <div className="flex-1 flex flex-col gap-3 border border-gray-800 bg-gray-900/20 backdrop-blur-md rounded-xl p-4 shadow-xl overflow-hidden card-3d card-3d-purple preserve-3d min-h-0">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest border-b border-gray-800 pb-2 shrink-0 flex items-center gap-2 font-mono">
              <Layers size={14} className="text-purple-400" />
              Grounding & Context
            </h2>
            
            <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0 pr-1 scrollbar-thin">
              {latestReformulation ? (
                <div className="flex flex-col gap-3">
                  <div className="p-3 bg-gray-950/60 border border-gray-800 rounded-lg shadow-inner">
                    <span className="text-[9px] font-bold uppercase tracking-widest text-emerald-400 block mb-1">Vector DB Search Query</span>
                    <p className="text-xs text-gray-300 leading-relaxed font-mono">{latestReformulation.search_vector_query}</p>
                  </div>
                  
                  <div className="p-3 bg-gray-950/60 border border-gray-800 rounded-lg shadow-inner">
                    <span className="text-[9px] font-bold uppercase tracking-widest text-blue-400 block mb-1">Grounded LLM Prompt</span>
                    <p className="text-xs text-gray-300 leading-relaxed">{latestReformulation.grounded_llm_prompt}</p>
                  </div>
                </div>
              ) : (
                <div className="p-3 bg-gray-950/20 border border-gray-800/40 rounded-lg text-center select-none py-4">
                  <AlertCircle size={14} className="text-gray-600 mx-auto mb-1.5" />
                  <span className="text-xs text-gray-600 italic">No query reformulation context...</span>
                </div>
              )}

              <div className="border-t border-gray-800/60 my-1 pt-2 shrink-0">
                <span className="text-[9px] font-bold uppercase tracking-widest text-purple-400 block mb-2">Memory Anchors</span>
              </div>

              {retrievedContextCards.length === 0 ? (
                <div className="p-4 border border-dashed border-gray-800/60 rounded-lg text-gray-600 italic text-xs text-center select-none">
                  No active vector context.
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {retrievedContextCards.map(card => (
                    <div key={card.id} className={`border rounded-lg p-2.5 shadow-md transition-all duration-300 text-xs ${card.style}`}>
                      <span className="font-bold uppercase tracking-widest text-[8px] text-gray-400 border-b border-gray-800/60 pb-1 block mb-1.5">{card.type}</span>
                      <pre className="whitespace-pre-wrap font-sans leading-relaxed text-gray-300 text-[10px]">{card.content}</pre>
                    </div>
                  ))}
                </div>
              )}
              <div ref={contextEndRef} />
            </div>
          </div>

          {/* Bottom Panel: System Event Logs (50% height) */}
          <div className="flex-1 flex flex-col gap-3 border border-gray-800 bg-gray-900/20 backdrop-blur-md rounded-xl p-4 shadow-xl overflow-hidden card-3d card-3d-blue preserve-3d min-h-0">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest border-b border-gray-800 pb-2 shrink-0 flex items-center gap-2 font-mono">
              <Cpu size={14} className="text-blue-400" />
              System Event Logs
            </h2>
            
            <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0 pr-1 scrollbar-thin">
              {sessionState.systemLogs.length === 0 ? (
                <span className="text-gray-600 text-xs italic p-2 select-none text-center block">System logs empty...</span>
              ) : (
                sessionState.systemLogs.map((log, idx) => {
                  let badgeColor = 'text-blue-400 border-blue-900/40 bg-blue-950/10';
                  if (log.type === 'error') badgeColor = 'text-red-400 border-red-950 bg-red-950/10';
                  if (log.type === 'action') badgeColor = 'text-amber-400 border-amber-900/40 bg-amber-950/10';
                  if (log.type === 'query_reformulation') badgeColor = 'text-purple-400 border-purple-900/40 bg-purple-950/10';
                  if (log.type === 'retrieved_context') badgeColor = 'text-emerald-400 border-emerald-900/40 bg-emerald-950/10';

                  return (
                    <div key={idx} className="p-3 rounded-lg text-xs bg-gray-950 border border-gray-900 shadow-md hover:border-gray-800 transition-all animate-slide">
                      <span className={`inline-block border px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest mb-2 ${badgeColor}`}>
                        {log.type}
                      </span>
                      
                      {log.type === 'query_reformulation' && (
                        <div className="text-gray-400 font-sans space-y-1 mt-1 leading-relaxed text-[11px]">
                          <div><strong className="text-gray-500 font-semibold text-[9px] uppercase block">Search Vector:</strong> {log.data.search_vector_query}</div>
                          <div><strong className="text-gray-500 font-semibold text-[9px] uppercase block">Grounded Prompt:</strong> {log.data.grounded_llm_prompt}</div>
                        </div>
                      )}
                      
                      {log.type === 'retrieved_context' && (
                        <div className="text-gray-400 mt-1 text-[11px]">
                          Context size loaded: <strong className="text-emerald-400 font-mono">{(log.data[0] || '').length.toLocaleString()}</strong> chars.
                        </div>
                      )}
                      
                      {log.type === 'action' && (
                        <div className="text-gray-400 font-sans space-y-1 mt-1 leading-relaxed text-[11px]">
                          <div><strong className="text-gray-500 font-semibold text-[9px] uppercase block">Action:</strong> {log.data.type}</div>
                          {log.data.payload && (
                            <div className="bg-gray-900 p-2 rounded border border-gray-800 font-mono text-[9px] text-amber-300/80 overflow-x-auto">
                              {JSON.stringify(log.data.payload)}
                            </div>
                          )}
                        </div>
                      )}

                      {log.type === 'error' && (
                        <div className="text-red-400 font-mono leading-relaxed mt-1 text-[11px]">{log.data}</div>
                      )}

                      {log.type !== 'query_reformulation' && log.type !== 'retrieved_context' && log.type !== 'action' && log.type !== 'error' && (
                        <pre className="text-gray-400 font-mono overflow-x-auto text-[9px] leading-relaxed mt-1">
                          {JSON.stringify(log.data, null, 2)}
                        </pre>
                      )}
                    </div>
                  );
                })
              )}
              <div ref={logsEndRef} />
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
