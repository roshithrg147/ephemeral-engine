import React, { createContext, useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navigation from './components/Navigation';
import DashboardPage from './pages/DashboardPage';
import ChatPage from './pages/ChatPage';
import { Database, Activity, ShieldAlert } from 'lucide-react';

// Export the context so child components (ChatPage) can consume it
export const TelemetryContext = createContext();

export default function App() {
  const [sessionState, setSessionState] = useState({
    phase: 'AWAITING_INPUT',
    tokensSaved: 0,
    tokensUsed: { m1: 0, m2: 0 },
    memoryAnchors: [],
    tokenHistory: [],
    intentDistribution: {},
    chatHistory: [],
    systemLogs: [],
    lastLatencyMs: null,
    activeSessionId: '',
    sessions: []
  });

  const API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

  // Bootstrap sessions list
  const bootstrapSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/session/list`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success' && data.data && data.data.length > 0) {
          setSessionState(prev => ({
            ...prev,
            sessions: data.data,
            activeSessionId: data.data[0]
          }));
        } else {
          // Initialize a default session if list is empty
          const defaultSession = 'session_1';
          await fetch(`${API_URL}/api/session/initialize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: defaultSession })
          });
          setSessionState(prev => ({
            ...prev,
            sessions: [defaultSession],
            activeSessionId: defaultSession
          }));
        }
      }
    } catch (e) {
      console.error("Failed to bootstrap sessions:", e);
    }
  }, [API_URL]);

  useEffect(() => {
    bootstrapSessions();
  }, [bootstrapSessions]);

  const handleBurn = async () => {
    if (!sessionState.activeSessionId) return;
    try {
      await fetch(`${API_URL}/api/session/burn/${sessionState.activeSessionId}`, { method: 'DELETE' });
      
      // Re-bootstrap to fetch remaining sessions or recreate default
      await bootstrapSessions();
      
      setSessionState(prev => ({
        ...prev,
        phase: 'MEMORY_PURGED',
        tokensSaved: 0,
        tokensUsed: { m1: 0, m2: 0 },
        memoryAnchors: [],
        tokenHistory: [],
        intentDistribution: {},
        chatHistory: [],
        systemLogs: []
      }));
    } catch (e) {
      console.error("Failed to burn session", e);
    }
  };

  return (
    <TelemetryContext.Provider value={{ sessionState, setSessionState }}>
      <Router>
        <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden font-sans antialiased">
          <Navigation />
          <div className="flex-1 flex flex-col min-w-0">
            {/* Premium Glassmorphic Global Telemetry Header */}
            <header className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-800/80 bg-gray-900/30 backdrop-blur-md p-4 shrink-0 shadow-2xl z-10 gap-4">
              
              <div className="flex flex-col shrink-0">
                <h2 className="text-lg font-bold tracking-wide text-glow-gradient">System Control Plane</h2>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Active Tenant:</span>
                  <span className="text-[10px] font-mono font-bold text-blue-400 bg-blue-950/30 border border-blue-900/40 px-2 py-0.5 rounded">
                    {sessionState.activeSessionId || 'None'}
                  </span>
                  <span className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold ml-1">Status:</span>
                  <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border ${
                    sessionState.phase === 'STREAMING_CODE' || sessionState.phase === 'STREAMING_RESPONSE' || sessionState.phase === 'COMPUTING'
                      ? 'text-amber-400 border-amber-900/40 bg-amber-950/20 animate-pulse' 
                      : 'text-emerald-400 border-emerald-900/40 bg-emerald-950/20'
                  }`}>
                    {sessionState.phase}
                  </span>
                </div>
              </div>

              {/* Active Memory Anchors Flex-Wrap Container */}
              <div className="flex-1 flex flex-wrap items-center gap-2 px-4 border-l border-gray-800/80 min-h-[40px]">
                {sessionState.memoryAnchors.length === 0 ? (
                  <span className="text-xs text-gray-600 italic">No active memory anchors in play...</span>
                ) : (
                  sessionState.memoryAnchors.map((anchor, idx) => (
                    <div key={idx} className="bg-purple-950/40 border border-purple-800/40 text-purple-300 text-[10px] font-semibold px-2.5 py-1 rounded-md shadow-md whitespace-nowrap truncate max-w-[200px] hover:border-purple-600/50 hover:bg-purple-900/10 transition-colors animate-float" style={{ animationDelay: `${idx * 0.1}s` }} title={anchor}>
                      {anchor}
                    </div>
                  ))
                )}
              </div>

              {/* Metrics & Actions */}
              <div className="flex gap-4 text-xs shrink-0 items-center">
                <div className="bg-gray-900/60 border border-gray-800/80 px-3 py-1.5 rounded-lg shadow-inner flex flex-col hover:border-emerald-600/30 transition-colors">
                  <span className="text-[9px] text-gray-500 uppercase tracking-widest font-bold flex items-center gap-1"><Database size={10} /> Tokens Saved</span>
                  <span className="font-bold text-emerald-400 text-sm mt-0.5">{sessionState.tokensSaved.toLocaleString()}</span>
                </div>
                <div className="bg-gray-900/60 border border-gray-800/80 px-3 py-1.5 rounded-lg shadow-inner flex flex-col hover:border-blue-600/30 transition-colors">
                  <span className="text-[9px] text-gray-500 uppercase tracking-widest font-bold flex items-center gap-1"><Activity size={10} /> M1 / M2 Used</span>
                  <span className="font-bold text-blue-400 text-sm mt-0.5">{sessionState.tokensUsed.m1.toLocaleString()} / <span className="text-purple-400">{sessionState.tokensUsed.m2.toLocaleString()}</span></span>
                </div>
                
                <button 
                  onClick={handleBurn} 
                  disabled={!sessionState.activeSessionId}
                  className="bg-red-950/20 hover:bg-red-900/40 border border-red-900/50 text-red-400 hover:text-red-300 px-4 py-2.5 rounded-lg transition-all uppercase tracking-widest font-bold text-[10px] cursor-pointer btn-3d btn-3d-red flex items-center gap-1.5 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ShieldAlert size={12} /> /burn
                </button>
              </div>
            </header>

            {/* Main Content Area */}
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </div>
      </Router>
    </TelemetryContext.Provider>
  );
}
