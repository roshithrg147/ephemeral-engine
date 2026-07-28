import React from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectSessionList } from '../../runtime/selectors';
import { Plus } from 'lucide-react';
import { StatusBadge } from '../shared/LifecycleCountdown';

export function SessionRail() {
  const { state, dispatch } = useRuntime();
  const sessions = selectSessionList(state);

  const handleNewSession = () => {
    const id = 'sess-' + Math.random().toString(36).substring(2, 9);
    dispatch({
      type: 'SESSION_CREATED',
      session: {
        id,
        name: 'New Session ' + id.substring(5, 8),
        createdAt: Date.now(),
        expiresAt: Date.now() + 4 * 60 * 60 * 1000,
        tier: 'healthy',
        messages: [],
        tokenUsage: { prompt: 0, completion: 0, total: 0 },
        lastActivity: Date.now()
      }
    });
    dispatch({ type: 'SESSION_SELECTED', sessionId: id });
  };

  return (
    <aside className="w-[240px] flex-none border-r border-border-subtle bg-surface-1 flex flex-col hidden md:flex">
      <div className="p-3 border-b border-border-subtle">
        <button
          onClick={handleNewSession}
          data-testid="session-rail-new"
          className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-surface-2 hover:bg-[rgba(255,255,255,0.05)] border border-border-default rounded-md text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-ring"
        >
          <Plus className="w-4 h-4" />
          New Session
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto py-2">
        {sessions.map(session => {
          const isActive = session.id === state.activeSessionId;
          const isBurned = session.tier === 'burned';
          
          return (
            <button
              key={session.id}
              data-testid={`session-rail-item-${session.id}`}
              onClick={() => dispatch({ type: 'SESSION_SELECTED', sessionId: session.id })}
              className={`
                w-full text-left px-4 py-3 border-l-2 transition-colors flex items-center gap-3
                ${isActive 
                  ? 'border-accent bg-surface-2 text-text-primary' 
                  : 'border-transparent text-text-secondary hover:bg-[rgba(255,255,255,0.02)] hover:text-text-primary'
                }
                ${isBurned ? 'opacity-50' : ''}
              `}
            >
              <StatusBadge tier={session.tier} dotOnly />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate mb-0.5">{session.name}</div>
                <div className="text-[10px] font-mono text-text-tertiary truncate">{session.id}</div>
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
