import React, { useEffect, useState } from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectActiveSession } from '../../runtime/selectors';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';
import { format } from 'date-fns';
import { fetchSessionMemory, MemoryData } from '../../runtime/apiService';

export function Inspector() {
  const { state, dispatch } = useRuntime();
  const session = selectActiveSession(state);

  if (!state.inspectorOpen) {
    return (
      <button
        onClick={() => dispatch({ type: 'INSPECTOR_TOGGLE' })}
        data-testid="inspector-toggle"
        className="absolute top-4 right-4 z-10 p-2 bg-surface-1 border border-border-default rounded-md text-text-secondary hover:text-text-primary hover:bg-surface-2 shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-ring"
        aria-label="Open Inspector"
      >
        <PanelRightOpen className="w-5 h-5" />
      </button>
    );
  }

  return (
    <aside className="w-[320px] flex-none border-l border-border-subtle bg-surface-1 flex flex-col shadow-[-4px_0_15px_rgba(0,0,0,0.05)] absolute right-0 inset-y-0 z-20 md:relative">
      <div className="h-[48px] border-b border-border-subtle flex items-center justify-between px-3">
        <div className="flex space-x-1">
          <button
            onClick={() => dispatch({ type: 'INSPECTOR_TAB_CHANGED', tab: 'context' })}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${state.inspectorTab === 'context' ? 'bg-surface-2 text-text-primary' : 'text-text-tertiary hover:text-text-secondary'}`}
          >
            Context
          </button>
          <button
            onClick={() => dispatch({ type: 'INSPECTOR_TAB_CHANGED', tab: 'events' })}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${state.inspectorTab === 'events' ? 'bg-surface-2 text-text-primary' : 'text-text-tertiary hover:text-text-secondary'}`}
          >
            Events
          </button>
        </div>
        <button
          onClick={() => dispatch({ type: 'INSPECTOR_TOGGLE' })}
          className="p-1.5 text-text-tertiary hover:text-text-primary rounded-md hover:bg-surface-2 transition-colors"
          aria-label="Close Inspector"
        >
          <PanelRightClose className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {state.inspectorTab === 'context' ? (
          <ContextTab session={session} />
        ) : (
          <EventsTab sessionId={session?.id} />
        )}
      </div>
    </aside>
  );
}

function ContextTab({ session }: { session: any }) {
  const [memoryData, setMemoryData] = useState<MemoryData | null>(null);

  useEffect(() => {
    if (session?.id) {
      fetchSessionMemory(session.id)
        .then(setMemoryData)
        .catch(() => setMemoryData(null));
    }
  }, [session?.id]);

  if (!session) return <div className="text-sm text-text-tertiary text-center mt-10">No session selected.</div>;

  return (
    <div className="space-y-6">
      <section>
        <h4 className="text-[11px] font-semibold tracking-wider text-text-tertiary uppercase mb-3">Metadata</h4>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">ID</dt>
            <dd className="font-mono text-[11px]">{session.id}</dd>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Created</dt>
            <dd className="font-mono text-[11px]">{format(session.createdAt, 'HH:mm:ss')}</dd>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Tier</dt>
            <dd className="font-mono text-[11px] uppercase">{session.tier}</dd>
          </div>
        </dl>
      </section>

      <section>
        <h4 className="text-[11px] font-semibold tracking-wider text-text-tertiary uppercase mb-3">Usage</h4>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Total Tokens</dt>
            <dd className="font-mono text-[11px]">{session.tokenUsage.total.toLocaleString()}</dd>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Prompt Tokens</dt>
            <dd className="font-mono text-[11px] text-text-tertiary">{session.tokenUsage.prompt.toLocaleString()}</dd>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Completion Tokens</dt>
            <dd className="font-mono text-[11px] text-text-tertiary">{session.tokenUsage.completion.toLocaleString()}</dd>
          </div>
        </dl>
      </section>

      <section>
        <h4 className="text-[11px] font-semibold tracking-wider text-text-tertiary uppercase mb-3">SC-EVM Memory State</h4>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Token Budget</dt>
            <dd className="font-mono text-[11px]">{memoryData?.token_budget ?? 8000}</dd>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Base Distance Threshold</dt>
            <dd className="font-mono text-[11px]">{memoryData?.base_threshold ?? 0.8}</dd>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Indexed Documents</dt>
            <dd className="font-mono text-[11px]">{memoryData?.indexed_documents?.length ?? 0}</dd>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt className="text-text-secondary">Pending Commit Buffer</dt>
            <dd className="font-mono text-[11px]">{memoryData?.pending_commit_buffer?.length ?? 0}</dd>
          </div>
        </dl>
      </section>

      <section>
        <h4 className="text-[11px] font-semibold tracking-wider text-text-tertiary uppercase mb-3">Engine Config</h4>
        <dl className="space-y-2 text-sm text-text-tertiary">
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt>Model 1</dt>
            <dd className="font-mono text-[11px]">meta/llama-3.1-8b-instruct</dd>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <dt>Model 2</dt>
            <dd className="font-mono text-[11px]">meta/llama-3.3-70b-instruct</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

function EventsTab({ sessionId }: { sessionId?: string }) {
  const { state } = useRuntime();

  if (!sessionId) return <div className="text-sm text-text-tertiary text-center mt-10">No session selected.</div>;

  const events = state.events.filter((e) => e.sessionId === sessionId || e.sessionId === 'system').slice(-20).reverse();

  if (events.length === 0) {
    return <div className="text-sm text-text-tertiary text-center mt-10">No events for this session.</div>;
  }

  return (
    <div className="space-y-3">
      {events.map((e) => (
        <div key={e.id} className="text-sm border-l-2 border-border-strong pl-3 py-1">
          <div className="flex items-center justify-between mb-0.5">
            <span className="font-medium text-text-primary text-[11px]">{e.type}</span>
            <span className="font-mono text-[10px] text-text-tertiary">{format(e.timestamp, 'HH:mm:ss.SSS')}</span>
          </div>
          {Object.keys(e.payload || {}).length > 0 && (
            <pre className="text-[10px] font-mono text-text-tertiary mt-1 bg-surface-2 p-1.5 rounded overflow-x-auto border border-border-subtle">
              {JSON.stringify(e.payload, null, 2)}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
