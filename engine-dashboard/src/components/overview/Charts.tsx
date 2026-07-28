import React, { useMemo } from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectTelemetryChart } from '../../runtime/selectors';
import { 
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, Legend
} from 'recharts';

export function Charts() {
  const { state } = useRuntime();
  const telemetry = selectTelemetryChart(state);

  // Recharts needs array of objects
  const data = useMemo(() => {
    return telemetry.timestamps.map((ts, i) => ({
      time: new Date(ts).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' }),
      tpm: telemetry.tpm[i],
      p50: telemetry.p50[i],
      p99: telemetry.p99[i],
      ctx: telemetry.ctx[i] * 100
    }));
  }, [telemetry]);

  if (data.length === 0) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="h-48 border border-border-default rounded-xl bg-surface-1 flex items-center justify-center text-sm text-text-tertiary">
          Telemetry data is loading...
        </div>
      </div>
    );
  }

  const currentTpm = data[data.length-1].tpm.toFixed(0);
  const currentP50 = data[data.length-1].p50.toFixed(0);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
      <ChartCard title="Tokens Per Minute" ariaDesc={`Tokens per minute: ${currentTpm}.`} testId="chart-tokens">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'var(--color-text-tertiary)' }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 10, fill: 'var(--color-text-tertiary)' }} tickLine={false} axisLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Area isAnimationActive={false} type="monotone" dataKey="tpm" stroke="var(--color-chart-1)" fillOpacity={0.2} fill="var(--color-chart-1)" />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Latency (P50 / P99)" ariaDesc={`Current P50 Latency: ${currentP50}ms.`} testId="chart-latency">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'var(--color-text-tertiary)' }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 10, fill: 'var(--color-text-tertiary)' }} tickLine={false} axisLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '10px' }} />
            <Line isAnimationActive={false} type="monotone" dataKey="p50" stroke="var(--color-chart-2)" dot={false} />
            <Line isAnimationActive={false} type="monotone" dataKey="p99" stroke="var(--color-chart-3)" dot={false} strokeDasharray="5 5" />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Context Utilization (%)" ariaDesc="Context utilization over time." testId="chart-context">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'var(--color-text-tertiary)' }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 10, fill: 'var(--color-text-tertiary)' }} tickLine={false} axisLine={false} domain={[0, 100]} />
            <Tooltip content={<CustomTooltip />} />
            <Area isAnimationActive={false} type="step" dataKey="ctx" stroke="var(--color-chart-5)" fillOpacity={0.2} fill="var(--color-chart-5)" />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}

function ChartCard({ title, children, ariaDesc, testId }: { title: string, children: React.ReactNode, ariaDesc: string, testId?: string }) {
  return (
    <figure data-testid={testId} className="h-56 p-4 rounded-xl border border-border-default bg-surface-1 shadow-sm flex flex-col">
      <figcaption className="text-xs font-medium text-text-secondary tracking-wide uppercase mb-4" aria-label={ariaDesc}>
        {title}
      </figcaption>
      <div className="flex-1 min-h-0">
        {children}
      </div>
    </figure>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-surface-2 border border-border-strong p-2 rounded shadow-lg">
        <p className="text-xs font-medium mb-1">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-xs font-mono" style={{ color: entry.color }}>
            {entry.name}: {entry.value.toFixed(0)}
          </p>
        ))}
      </div>
    );
  }
  return null;
};
