import React, { useState } from 'react';
import { useRuntime } from '../runtime/RuntimeContext';
import { selectSessionList } from '../runtime/selectors';
import { SessionTier } from '../runtime/types';
import { format } from 'date-fns';
import { StatusBadge, LifecycleCountdown } from '../components/shared/LifecycleCountdown';
import { BurnConfirmDialog } from '../components/shared/BurnConfirmDialog';
import { Link } from 'wouter';
import { PanelRightClose, MoreVertical, Flame, ArrowRight } from 'lucide-react';

export function Sessions() {
  const { state, dispatch, createSession, burnSession } = useRuntime();
  const allSessions = selectSessionList(state);

  const [filter, setFilter] = useState<SessionTier | 'all'>('all');
  const [sortField, setSortField] = useState<'createdAt' | 'expiresAt' | 'tokens'>('createdAt');
  const [sortDesc, setSortDesc] = useState(true);

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [burnDialogId, setBurnDialogId] = useState<string | null>(null);

  const filtered = allSessions.filter((s) => filter === 'all' || s.tier === filter);
  const sorted = [...filtered].sort((a, b) => {
    let valA, valB;
    if (sortField === 'createdAt') {
      valA = a.createdAt;
      valB = b.createdAt;
    } else if (sortField === 'expiresAt') {
      valA = a.expiresAt;
      valB = b.expiresAt;
    } else {
      valA = a.tokenUsage.total;
      valB = b.tokenUsage.total;
    }

    return sortDesc ? valB - valA : valA - valB;
  });

  const selectedSession = selectedSessionId ? state.sessions[selectedSessionId] : null;

  const handleBurn = async (id: string) => {
    await burnSession(id);
    setBurnDialogId(null);
  };

  const handleNewSession = async () => {
    await createSession();
  };

  return (
    <div className="h-full flex relative overflow-hidden bg-canvas">
      <div className={`flex-1 flex flex-col min-w-0 transition-all ${selectedSessionId ? 'mr-0 lg:mr-[320px]' : ''}`}>
        <div className="p-4 lg:p-8 flex-1 overflow-y-auto">
          <div className="max-w-[1200px] mx-auto">
            <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-text-primary">Sessions</h2>
                <p className="text-sm text-text-secondary mt-1">
                  Manage {allSessions.length} active and historical sessions.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  className="px-3 py-1.5 border border-border-default rounded-md text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-surface-2 transition-colors cursor-not-allowed opacity-50"
                  title="Coming soon"
                >
                  Bulk Burn
                </button>
                <Link href="/workspace">
                  <button
                    onClick={handleNewSession}
                    className="px-4 py-1.5 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors"
                  >
                    New Session
                  </button>
                </Link>
              </div>
            </header>

            <div className="bg-surface-1 border border-border-default rounded-xl shadow-sm overflow-hidden flex flex-col">
              <div className="p-2 border-b border-border-subtle flex items-center gap-2 overflow-x-auto scrollbar-none">
                <span className="text-xs font-medium text-text-tertiary px-2 uppercase tracking-wider">Filter:</span>
                {['all', 'healthy', 'expiring_soon', 'critical', 'expired', 'burning', 'burned'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f as any)}
                    className={`px-3 py-1 text-xs font-medium rounded-md capitalize whitespace-nowrap transition-colors
                      ${filter === f ? 'bg-surface-2 text-text-primary' : 'text-text-tertiary hover:text-text-secondary hover:bg-surface-2/50'}
                    `}
                  >
                    {f.replace('_', ' ')}
                  </button>
                ))}
              </div>

              <div className="overflow-x-auto">
                {sorted.length === 0 ? (
                  <div className="p-12 text-center text-sm text-text-tertiary">
                    No sessions match this filter. Start one from the Workspace.
                  </div>
                ) : (
                  <table className="w-full text-sm text-left">
                    <thead className="text-xs text-text-tertiary uppercase tracking-wider bg-surface-2/50 border-b border-border-subtle">
                      <tr>
                        <th className="px-4 py-3 font-medium">Session</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                        <th
                          className="px-4 py-3 font-medium cursor-pointer hover:text-text-primary"
                          onClick={() => {
                            setSortField('createdAt');
                            setSortDesc(!sortDesc);
                          }}
                        >
                          Created {sortField === 'createdAt' && (sortDesc ? '↓' : '↑')}
                        </th>
                        <th
                          className="px-4 py-3 font-medium cursor-pointer hover:text-text-primary"
                          onClick={() => {
                            setSortField('expiresAt');
                            setSortDesc(!sortDesc);
                          }}
                        >
                          Expires {sortField === 'expiresAt' && (sortDesc ? '↓' : '↑')}
                        </th>
                        <th
                          className="px-4 py-3 font-medium cursor-pointer hover:text-text-primary text-right"
                          onClick={() => {
                            setSortField('tokens');
                            setSortDesc(!sortDesc);
                          }}
                        >
                          Tokens {sortField === 'tokens' && (sortDesc ? '↓' : '↑')}
                        </th>
                        <th className="px-4 py-3 font-medium text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-subtle">
                      {sorted.map((session) => {
                        const isBurned = session.tier === 'burned';
                        return (
                          <tr
                            key={session.id}
                            onClick={() => setSelectedSessionId(session.id)}
                            className={`group hover:bg-surface-2 transition-colors cursor-pointer ${isBurned ? 'opacity-50' : ''} ${selectedSessionId === session.id ? 'bg-surface-2' : ''}`}
                          >
                            <td className="px-4 py-3">
                              <div className="font-medium text-text-primary mb-0.5">{session.name}</div>
                              <div className="font-mono text-[11px] text-text-tertiary">{session.id}</div>
                            </td>
                            <td className="px-4 py-3">
                              <StatusBadge tier={session.tier} />
                            </td>
                            <td className="px-4 py-3 font-mono text-[11px] text-text-secondary">
                              {format(session.createdAt, 'MMM d, HH:mm')}
                            </td>
                            <td className="px-4 py-3">
                              {isBurned ? (
                                <span className="font-mono text-[11px] text-text-tertiary">Burned</span>
                              ) : (
                                <LifecycleCountdown expiresAt={session.expiresAt} sessionId={session.id} />
                              )}
                            </td>
                            <td className="px-4 py-3 text-right font-mono text-[11px] text-text-secondary">
                              {session.tokenUsage.total.toLocaleString()}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <button
                                className="p-1.5 text-text-tertiary hover:text-text-primary rounded hover:bg-surface-1 opacity-0 group-hover:opacity-100 transition-all"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedSessionId(session.id);
                                }}
                              >
                                <MoreVertical className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="mt-4 text-center">
              <span className="text-xs text-text-tertiary">
                Burned sessions are retained for 48 hours for audit purposes.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Detail Drawer */}
      {selectedSessionId && (
        <aside className="absolute right-0 inset-y-0 w-full md:w-[320px] bg-surface-1 border-l border-border-subtle shadow-2xl flex flex-col z-30 animate-in slide-in-from-right-full duration-fast">
          <div className="h-[48px] border-b border-border-subtle flex items-center justify-between px-4 flex-none">
            <h3 className="text-sm font-semibold tracking-tight">Session Details</h3>
            <button
              onClick={() => setSelectedSessionId(null)}
              className="p-1.5 text-text-tertiary hover:text-text-primary rounded-md hover:bg-surface-2 transition-colors"
            >
              <PanelRightClose className="w-4 h-4" />
            </button>
          </div>

          {selectedSession ? (
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
              <div>
                <h4 className="text-lg font-semibold text-text-primary mb-1">{selectedSession.name}</h4>
                <div className="font-mono text-xs text-text-tertiary mb-3">{selectedSession.id}</div>
                <StatusBadge tier={selectedSession.tier} />
              </div>

              <div className="space-y-4">
                <div className="bg-surface-2 p-3 rounded-lg border border-border-subtle">
                  <div className="text-[11px] font-medium text-text-tertiary uppercase mb-1">Time Remaining</div>
                  {selectedSession.tier === 'burned' ? (
                    <div className="text-sm text-text-secondary font-medium">Burned</div>
                  ) : (
                    <LifecycleCountdown expiresAt={selectedSession.expiresAt} sessionId={selectedSession.id} />
                  )}
                </div>

                <div className="bg-surface-2 p-3 rounded-lg border border-border-subtle grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-[11px] font-medium text-text-tertiary uppercase mb-1">Messages</div>
                    <div className="text-lg font-mono text-text-primary">{selectedSession.messages.length}</div>
                  </div>
                  <div>
                    <div className="text-[11px] font-medium text-text-tertiary uppercase mb-1">Total Tokens</div>
                    <div className="text-lg font-mono text-text-primary">
                      {selectedSession.tokenUsage.total.toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-border-subtle flex flex-col gap-3">
                <Link href={`/workspace?session=${selectedSession.id}`}>
                  <button className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-surface-2 border border-border-default rounded-md text-sm font-medium hover:bg-surface-1 transition-colors">
                    Open in Workspace <ArrowRight className="w-4 h-4" />
                  </button>
                </Link>

                {selectedSession.tier !== 'burned' && (
                  <button
                    onClick={() => setBurnDialogId(selectedSession.id)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-status-expired text-status-expired rounded-md text-sm font-medium hover:bg-status-expired hover:text-white transition-colors"
                  >
                    <Flame className="w-4 h-4" />
                    Burn Session
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="p-4 text-sm text-text-tertiary">Session not found.</div>
          )}
        </aside>
      )}

      <BurnConfirmDialog
        open={!!burnDialogId}
        onOpenChange={(open) => !open && setBurnDialogId(null)}
        sessionId={burnDialogId!}
        onConfirm={() => burnDialogId && handleBurn(burnDialogId)}
        isBurning={state.pendingBurnSessionId === burnDialogId}
        error={null}
      />
    </div>
  );
}
