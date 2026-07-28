import React from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectUsageSummary, selectSessionList } from '../../runtime/selectors';

export function MetricsGrid() {
  const { state } = useRuntime();
  const summary = selectUsageSummary(state);
  const sessions = selectSessionList(state);
  
  const activeSessions = sessions.filter(s => s.tier !== 'burned');
  const healthyCount = activeSessions.filter(s => s.tier === 'healthy').length;
  const expiringCount = activeSessions.filter(s => s.tier === 'expiring_soon' || s.tier === 'critical').length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
      <MetricTile 
        label="Total Tokens" 
        value={summary.totalTokens.toLocaleString()} 
        description="Prompt + Completion"
      />
      <MetricTile 
        label="Active Sessions" 
        value={activeSessions.length.toString()} 
        description={`${healthyCount} healthy, ${expiringCount} expiring`}
      />
      <MetricTile 
        label="Avg P50 Latency" 
        value={`${summary.avgLatency.toFixed(0)} ms`} 
      />
      <MetricTile 
        label="Request Success" 
        value={`${((1 - summary.errorRate) * 100).toFixed(1)}%`} 
        statusColor={summary.errorRate > 0.05 ? 'status-error' : 'status-healthy'}
      />
      <MetricTile 
        label="Context Utilization" 
        value={`${(state.telemetry[state.telemetry.length - 1]?.contextUtilization * 100 || 0).toFixed(1)}%`} 
      />
      <MetricTile 
        label="Error Rate" 
        value={`${(summary.errorRate * 100).toFixed(2)}%`} 
        statusColor={summary.errorRate > 0.05 ? 'status-error' : 'text-primary'}
      />
    </div>
  );
}

function MetricTile({ label, value, description, statusColor }: { label: string, value: string, description?: string, statusColor?: string }) {
  return (
    <article 
      className="p-4 rounded-xl border border-border-default bg-surface-1 shadow-sm flex flex-col justify-between"
      aria-label={`${label}: ${value}`}
    >
      <h3 className="text-xs font-medium text-text-secondary tracking-wide uppercase mb-1">{label}</h3>
      <div className={`text-2xl font-mono ${statusColor ? `text-${statusColor}` : 'text-text-primary'}`}>
        {value}
      </div>
      {description && <p className="text-[11px] text-text-tertiary mt-1">{description}</p>}
    </article>
  );
}
