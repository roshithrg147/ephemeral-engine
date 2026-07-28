import React from 'react';
import { MetricsGrid } from '../components/overview/MetricsGrid';
import { ExecutionTimeline } from '../components/overview/ExecutionTimeline';
import { Charts } from '../components/overview/Charts';
import { EventFeed } from '../components/overview/EventFeed';
import { SessionsPanel } from '../components/overview/SessionsPanel';

export function Overview() {
  return (
    <div className="h-full overflow-y-auto p-4 lg:p-8">
      <div className="max-w-[1440px] mx-auto">
        <header className="mb-6">
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">Overview</h2>
          <p className="text-sm text-text-secondary mt-1">
            Real-time telemetry and execution state for the ephemeral cluster.
          </p>
        </header>

        <MetricsGrid />
        <ExecutionTimeline />
        <Charts />
        
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <SessionsPanel />
          <EventFeed />
        </div>
      </div>
    </div>
  );
}
