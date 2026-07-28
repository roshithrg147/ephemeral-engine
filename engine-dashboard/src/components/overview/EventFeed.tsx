import React, { useState } from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectFilteredEvents, selectUnreadCount } from '../../runtime/selectors';
import { Filter, ChevronRight, ChevronDown } from 'lucide-react';
import { format } from 'date-fns';

export function EventFeed() {
  const { state, dispatch } = useRuntime();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  
  const events = selectFilteredEvents(state, state.eventFilter);
  const unreadCount = selectUnreadCount(state);
  
  // Show max 50
  const displayEvents = events.slice(-50).reverse();

  const toggleExpand = (id: string) => {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setExpanded(next);
  };

  const filters = ['all', 'request', 'stream', 'session', 'system', 'error'];

  return (
    <div className="flex flex-col h-[500px] border border-border-default bg-surface-1 rounded-xl shadow-sm">
      <div className="flex-none p-3 border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Event Feed</h3>
          {unreadCount > 0 && (
            <span className="bg-accent text-accent-fg text-[10px] font-bold px-1.5 py-0.5 rounded-full">
              {unreadCount} new
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none">
          <Filter className="w-3 h-3 text-text-tertiary mr-1" />
          {filters.map(f => (
            <button
              key={f}
              onClick={() => dispatch({ type: 'EVENT_FILTER_CHANGED', filter: f as any })}
              className={`px-2 py-1 text-[11px] font-medium rounded capitalize transition-colors
                ${state.eventFilter === f ? 'bg-surface-2 text-text-primary' : 'text-text-tertiary hover:text-text-secondary'}
              `}
              data-testid={`event-feed-filter-${f}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-0">
        {displayEvents.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-text-tertiary">
            No events match this filter.
          </div>
        ) : (
          <div className="divide-y divide-border-subtle">
            {displayEvents.map(event => {
              const isExp = expanded.has(event.id);
              return (
                <div key={event.id} className="text-sm" data-testid={`event-row-${event.id}`}>
                  <button 
                    onClick={() => toggleExpand(event.id)}
                    className="w-full text-left p-3 hover:bg-surface-2 flex items-start gap-3 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-ring"
                    aria-expanded={isExp}
                  >
                    <div className="mt-0.5 text-text-tertiary flex-none">
                      {isExp ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-text-primary truncate pr-2">{event.type}</span>
                        <span className="font-mono text-[11px] text-text-tertiary flex-none whitespace-nowrap">
                          {format(event.timestamp, 'HH:mm:ss.SSS')}
                        </span>
                      </div>
                      <div className="font-mono text-[11px] text-text-secondary truncate">
                        {event.sessionId}
                      </div>
                    </div>
                  </button>
                  {isExp && (
                    <div className="p-3 pt-0 pl-10 bg-surface-2/50 border-t border-border-subtle/50">
                      <pre className="text-[11px] font-mono text-text-code overflow-x-auto p-2 bg-code-bg rounded border border-border-subtle mt-2">
                        {JSON.stringify(event.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
