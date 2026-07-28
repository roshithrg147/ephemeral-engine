import React, { useState } from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectSessionList } from '../../runtime/selectors';
import { Flame } from 'lucide-react';
import { Link } from 'wouter';
import { LifecycleCountdown, StatusBadge } from '../shared/LifecycleCountdown';
import { BurnConfirmDialog } from '../shared/BurnConfirmDialog';

export function SessionsPanel() {
  const { state, dispatch } = useRuntime();
  const sessions = selectSessionList(state);
  
  const [burnDialogId, setBurnDialogId] = useState<string | null>(null);

  const handleBurn = (id: string) => {
    dispatch({ type: 'SESSION_BURN_INITIATED', sessionId: id });
    // Simulate API latency
    setTimeout(() => {
      if (Math.random() > 0.8) {
        dispatch({ type: 'SESSION_BURN_FAILED', sessionId: id, error: 'Network timeout' });
      } else {
        dispatch({ type: 'SESSION_BURNED', sessionId: id, burnedAt: Date.now() });
      }
      setBurnDialogId(null);
    }, 1500);
  };

  return (
    <div className="flex flex-col h-[500px] border border-border-default bg-surface-1 rounded-xl shadow-sm">
      <div className="flex-none p-4 border-b border-border-subtle">
        <h3 className="text-sm font-semibold">Active Sessions</h3>
      </div>
      
      <div className="flex-1 overflow-y-auto p-0">
        {sessions.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-text-tertiary">
            No sessions active.
          </div>
        ) : (
          <div className="divide-y divide-border-subtle">
            {sessions.map(session => {
              const isBurned = session.tier === 'burned';
              const isBurning = state.pendingBurnSessionId === session.id;
              
              return (
                <div key={session.id} className={`p-4 flex items-center justify-between gap-4 ${isBurned ? 'opacity-50 grayscale' : ''}`}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Link 
                        href={`/workspace?session=${session.id}`}
                        className="font-medium text-sm text-text-primary hover:text-accent hover:underline truncate focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-ring rounded"
                      >
                        {session.name}
                      </Link>
                      <StatusBadge tier={session.tier} dotOnly />
                    </div>
                    <div className="font-mono text-[11px] text-text-secondary truncate">
                      {session.id}
                    </div>
                  </div>
                  
                  <div className="flex-none flex items-center gap-6">
                    <div className="hidden sm:block">
                      <LifecycleCountdown expiresAt={session.expiresAt} sessionId={session.id} />
                    </div>
                    <div className="text-right hidden md:block w-20">
                      <div className="text-xs text-text-secondary">Tokens</div>
                      <div className="font-mono text-[11px] text-text-primary">{session.tokenUsage.total.toLocaleString()}</div>
                    </div>
                    
                    {!isBurned && (
                      <button
                        data-testid={`session-burn-button-${session.id}`}
                        onClick={() => setBurnDialogId(session.id)}
                        disabled={isBurning}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border-strong text-status-expired hover:bg-[rgba(221,68,68,0.1)] transition-colors disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-ring text-[11px] font-medium"
                      >
                        {isBurning ? (
                          <span className="w-3 h-3 border border-status-expired border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <Flame className="w-3.5 h-3.5" />
                        )}
                        Burn
                      </button>
                    )}
                    {isBurned && (
                      <span className="text-[11px] font-medium text-text-tertiary px-2.5 py-1.5 border border-transparent">
                        Burned
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <BurnConfirmDialog 
        open={!!burnDialogId}
        onOpenChange={(open) => !open && setBurnDialogId(null)}
        sessionId={burnDialogId!}
        onConfirm={() => burnDialogId && handleBurn(burnDialogId)}
        isBurning={state.pendingBurnSessionId === burnDialogId}
        error={null} // We clear the dialog immediately on failure for now to keep it simple
      />
    </div>
  );
}
