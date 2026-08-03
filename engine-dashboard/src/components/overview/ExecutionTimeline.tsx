import React, { useMemo } from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectRecentEvents } from '../../runtime/selectors';
import { Activity, Clock, Zap, AlertTriangle, Info } from 'lucide-react';
import { formatDistanceToNowStrict } from 'date-fns';

export function ExecutionTimeline() {
  const { state } = useRuntime();
  const recentEvents = selectRecentEvents(state, 20);
  
  // Sort descending (newest left, if scrolling horizontal) or just newest right
  // The brief says "newest right", so we keep ascending
  
  return (
    <div className="bg-surface-1 border border-border-default rounded-xl p-4 mb-6">
      <h3 className="text-sm font-semibold mb-3">Execution Timeline</h3>
      
      {recentEvents.length === 0 ? (
        <div className="h-16 flex items-center justify-center text-text-tertiary text-sm">
          Awaiting events...
        </div>
      ) : (
        <div 
          className="flex gap-4 overflow-x-auto pb-4 scrollbar-none snap-x"
          aria-label="Timeline of recent events"
        >
          {recentEvents.map(event => (
            <TimelineItem key={event.id} event={event} />
          ))}
          {/* spacer to ensure last item is fully visible */}
          <div className="min-w-4 flex-none" />
        </div>
      )}
    </div>
  );
}

function TimelineItem({ event }: { event: any }) {
  let Icon = Info;
  let colorClass = 'text-text-secondary border-border-default';
  
  if (event.type.startsWith('request')) {
    Icon = Zap;
    colorClass = 'text-accent border-accent/30 bg-accent/5';
  } else if (event.type.startsWith('error') || event.type.endsWith('failed')) {
    Icon = AlertTriangle;
    colorClass = 'text-status-error border-status-error/30 bg-status-error/5';
  } else if (event.type.startsWith('session')) {
    Icon = Activity;
    colorClass = 'text-status-healthy border-status-healthy/30 bg-status-healthy/5';
  } else if (event.type.startsWith('stream')) {
    Icon = Clock;
    colorClass = 'text-status-retrying border-status-retrying/30 bg-status-retrying/5';
  }
  
  const timeAgo = formatDistanceToNowStrict(event.timestamp, { addSuffix: true });

  return (
    <div className={`flex-none w-48 p-3 rounded-lg border ${colorClass} flex flex-col gap-2 snap-start slide-in-from-right-2 animate-in duration-fast ease-default`}>
      <div className="flex items-center justify-between">
        <Icon className="w-4 h-4" />
        <span className="text-[10px] font-mono opacity-80">{timeAgo}</span>
      </div>
      <div className="text-xs font-medium truncate" title={event.type}>
        {event.type}
      </div>
      <div className="text-[10px] font-mono opacity-60 truncate">
        {event.sessionId.substring(0, 8)}...
      </div>
    </div>
  );
}
