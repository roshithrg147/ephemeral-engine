import React, { useState } from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectSessionList } from '../../runtime/selectors';
import { Plus, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';
import { StatusBadge } from '../shared/LifecycleCountdown';

export function SessionRail() {
  const { state, dispatch, createSession, toggleSessionMode } = useRuntime();
  const sessions = Object.values(state.sessions).sort((a, b) => b.lastActivity - a.lastActivity);
  const isOpen = state.sessionRailOpen !== false;

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sessionName, setSessionName] = useState('');
  const [sessionMode, setSessionMode] = useState<'coding' | 'general'>('coding');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleOpenModal = () => {
    setSessionName('');
    setSessionMode('coding');
    setIsModalOpen(true);
  };

  const handleCreateSession = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const finalName = sessionName.trim() || `Session ${Math.random().toString(36).substring(2, 6)}`;
      await createSession(finalName, undefined, sessionMode);
      setIsModalOpen(false);
      setSessionName('');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => dispatch({ type: 'SESSION_RAIL_TOGGLE' })}
        data-testid="session-rail-toggle-open"
        className="absolute top-3 left-3 z-20 p-2 bg-surface-1 border border-border-default rounded-md text-text-secondary hover:text-text-primary hover:bg-surface-2 shadow-sm transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-ring"
        aria-label="Expand Sidebar"
        title="Expand Sidebar"
      >
        <PanelLeftOpen className="w-4 h-4" />
      </button>
    );
  }

  return (
    <>
      <aside className="w-64 border-r border-border-default bg-canvas flex flex-col h-full shrink-0">
        <div className="p-3 border-b border-border-default flex items-center justify-between gap-2">
          <button
            onClick={handleOpenModal}
            data-testid="session-rail-new-session-button"
            className="flex-1 py-1.5 px-3 bg-accent hover:bg-accent-hover text-white rounded-md text-xs font-medium flex items-center justify-center gap-1.5 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-ring"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Session</span>
          </button>
          <button
            onClick={() => dispatch({ type: 'SESSION_RAIL_TOGGLE' })}
            data-testid="session-rail-toggle-close"
            className="p-1.5 text-text-tertiary hover:text-text-primary rounded-md hover:bg-surface-2 transition-colors"
            aria-label="Collapse Sidebar"
            title="Collapse Sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto py-2">
          {sessions.length === 0 ? (
            <div className="p-4 text-center text-xs text-text-tertiary">
              No sessions yet. Click <strong>+ New Session</strong> to create one.
            </div>
          ) : (
            sessions.map(session => {
              const isActive = session.id === state.activeSessionId;
              const isBurned = session.tier === 'burned';
              const isGeneralMode = session.assistantMode === 'general';
              
              return (
                <div
                  key={session.id}
                  data-testid={`session-rail-item-${session.id}`}
                  onClick={() => dispatch({ type: 'SESSION_SELECTED', sessionId: session.id })}
                  className={`
                    w-full cursor-pointer text-left px-3.5 py-2.5 border-l-2 transition-colors flex items-center gap-3 group
                    ${isActive 
                      ? 'border-accent bg-surface-2 text-text-primary' 
                      : 'border-transparent text-text-secondary hover:bg-[rgba(255,255,255,0.02)] hover:text-text-primary'
                    }
                    ${isBurned ? 'opacity-50' : ''}
                  `}
                >
                  <StatusBadge tier={session.tier} dotOnly />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1 mb-0.5">
                      <span className="text-sm font-medium truncate">{session.name}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSessionMode(session.id, isGeneralMode ? 'coding' : 'general');
                        }}
                        className={`text-[9px] px-1.5 py-0.5 rounded font-mono border transition-colors ${
                          isGeneralMode
                            ? 'bg-purple-950/40 text-purple-300 border-purple-800/60 hover:bg-purple-900/60'
                            : 'bg-blue-950/40 text-blue-300 border-blue-800/60 hover:bg-blue-900/60'
                        }`}
                        title="Click to toggle Assistant Mode"
                      >
                        {isGeneralMode ? '🔬 Research' : '🛠️ Coding'}
                      </button>
                    </div>
                    <div className="text-[10px] font-mono text-text-tertiary truncate">{session.id}</div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* New Session Custom Name & Mode Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-surface-1 border border-border-default rounded-xl p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-text-primary">Create New Session</h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-text-tertiary hover:text-text-primary p-1 rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSession} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">
                  Session Name / Label
                </label>
                <input
                  type="text"
                  autoFocus
                  data-testid="session-name-input"
                  value={sessionName}
                  onChange={(e) => setSessionName(e.target.value)}
                  placeholder="e.g. Audit Phase 1, System Architecture Research"
                  className="w-full bg-canvas border border-border-strong rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-focus-ring focus:ring-1 focus:ring-focus-ring"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">
                  Assistant Mode
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setSessionMode('coding')}
                    className={`px-3 py-2 rounded-lg border text-left text-xs flex flex-col gap-0.5 transition-colors ${
                      sessionMode === 'coding'
                        ? 'bg-blue-950/60 border-blue-500 text-blue-200'
                        : 'bg-surface-2 border-border-default text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    <span className="font-semibold">🛠️ Coding (Architect)</span>
                    <span className="text-[10px] text-text-tertiary">Strict Database Phase Gating</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSessionMode('general')}
                    className={`px-3 py-2 rounded-lg border text-left text-xs flex flex-col gap-0.5 transition-colors ${
                      sessionMode === 'general'
                        ? 'bg-purple-950/60 border-purple-500 text-purple-200'
                        : 'bg-surface-2 border-border-default text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    <span className="font-semibold">🔬 Research (General)</span>
                    <span className="text-[10px] text-text-tertiary">Direct Conceptual Answers</span>
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3.5 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary bg-surface-2 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="create-session-submit"
                  className="px-4 py-1.5 text-xs font-medium text-white bg-accent hover:bg-accent-hover rounded-lg shadow-sm"
                >
                  Create Session
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
