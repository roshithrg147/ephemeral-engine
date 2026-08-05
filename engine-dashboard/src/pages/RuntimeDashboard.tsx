import React, { useState } from 'react';
import { Activity, Server, Zap, ShieldAlert, GitCommit, Download } from 'lucide-react';

export function RuntimeDashboard() {
  const [selectedTraceId, setSelectedTraceId] = useState("req-8f3e21a");

  const providers = [
    { name: "OpenAI API", status: "Healthy", successRate: "99.4%", avgLatency: "142 ms", rateLimits: 0 },
    { name: "Vertex AI / Gemini", status: "Healthy", successRate: "99.8%", avgLatency: "168 ms", rateLimits: 0 },
    { name: "Local Engine (Ollama/PyTorch)", status: "Healthy", successRate: "100%", avgLatency: "18 ms", rateLimits: 0 },
  ];

  const circuitBreakers = [
    { name: "OpenAI Breaker", state: "CLOSED", failures: 0, lastSuccess: "Just now" },
    { name: "NVIDIA NIM Breaker", state: "CLOSED", failures: 0, lastSuccess: "Just now" },
    { name: "Local Model Breaker", state: "CLOSED", failures: 0, lastSuccess: "Just now" },
  ];

  const traces = [
    {
      id: "req-8f3e21a",
      query: "How does MultiTenantSessionRegistry handle session purging?",
      totalLatencyMs: 245.8,
      status: "Succeeded",
      stages: [
        { stage: "Gateway", latencyMs: 2.1, status: "OK" },
        { stage: "Intent Router", latencyMs: 4.5, status: "OK" },
        { stage: "Hybrid Retrieval", latencyMs: 18.2, status: "OK" },
        { stage: "Context Planner", latencyMs: 3.8, status: "OK" },
        { stage: "LLM Streaming", latencyMs: 212.4, status: "OK" },
        { stage: "Memory Persistence", latencyMs: 4.8, status: "OK" },
      ],
    },
    {
      id: "req-7b2a19c",
      query: "Explain adaptive threshold percentile calculations",
      totalLatencyMs: 198.4,
      status: "Succeeded",
      stages: [
        { stage: "Gateway", latencyMs: 1.8, status: "OK" },
        { stage: "Intent Router", latencyMs: 3.9, status: "OK" },
        { stage: "Hybrid Retrieval", latencyMs: 15.6, status: "OK" },
        { stage: "Context Planner", latencyMs: 3.1, status: "OK" },
        { stage: "LLM Streaming", latencyMs: 169.2, status: "OK" },
        { stage: "Memory Persistence", latencyMs: 4.8, status: "OK" },
      ],
    },
  ];

  const selectedTrace = traces.find((t) => t.id === selectedTraceId) || traces[0];

  const exportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ providers, circuitBreakers, traces }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `runtime_resilience_trace_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto bg-canvas">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Activity className="w-5 h-5 text-accent" />
            Runtime Dashboard
          </h1>
          <p className="text-xs text-text-tertiary mt-1">
            Real-time provider health, circuit breaker state transitions, local/cloud routing split, and request traces.
          </p>
        </div>
        <button
          onClick={exportJSON}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-2 hover:bg-surface-3 border border-border-subtle rounded-md text-xs font-medium text-text-primary transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          Export Trace JSON
        </button>
      </div>

      {/* Provider Health Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {providers.map((p) => (
          <div key={p.name} className="bg-surface-1 border border-border-subtle p-4 rounded-lg space-y-2">
            <div className="flex justify-between items-center">
              <span className="font-semibold text-sm text-text-primary">{p.name}</span>
              <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">
                {p.status}
              </span>
            </div>
            <div className="grid grid-cols-2 text-xs pt-1 border-t border-border-subtle">
              <div>
                <span className="text-text-tertiary block">Success Rate</span>
                <span className="font-mono text-emerald-400 font-bold">{p.successRate}</span>
              </div>
              <div>
                <span className="text-text-tertiary block">Avg Latency</span>
                <span className="font-mono text-text-primary">{p.avgLatency}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Routing & Circuit Breaker Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Local vs Cloud Routing */}
        <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary flex items-center gap-1.5">
            <Zap className="w-4 h-4 text-accent" />
            Routing Distribution & Fallback Rates
          </h3>
          <div className="space-y-2 font-mono text-xs">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-cyan-400">Local Execution (Policy Driven)</span>
                <span>81%</span>
              </div>
              <div className="w-full bg-surface-2 h-2 rounded overflow-hidden">
                <div className="bg-cyan-400 h-full" style={{ width: '81%' }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-purple-400">Cloud Execution</span>
                <span>19%</span>
              </div>
              <div className="w-full bg-surface-2 h-2 rounded overflow-hidden">
                <div className="bg-purple-400 h-full" style={{ width: '19%' }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-amber-400">Fallback Rate</span>
                <span>2%</span>
              </div>
              <div className="w-full bg-surface-2 h-2 rounded overflow-hidden">
                <div className="bg-amber-400 h-full" style={{ width: '2%' }} />
              </div>
            </div>
          </div>
        </div>

        {/* Circuit Breaker 2.0 */}
        <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4 text-accent" />
            Circuit Breaker 2.0 States
          </h3>
          <div className="space-y-2 text-xs">
            {circuitBreakers.map((cb) => (
              <div key={cb.name} className="flex items-center justify-between bg-surface-2 p-2 rounded border border-border-subtle font-mono">
                <span>{cb.name}</span>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {cb.state}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* End-to-End Request Trace */}
      <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg space-y-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary flex items-center gap-1.5">
          <GitCommit className="w-4 h-4 text-accent" />
          End-to-End Distributed Request Trace ({selectedTrace.id})
        </h3>

        <div className="grid grid-cols-6 gap-2 text-center text-xs">
          {selectedTrace.stages.map((stg) => (
            <div key={stg.stage} className="bg-surface-2 border border-border-subtle p-2.5 rounded font-mono">
              <span className="text-text-tertiary text-[10px] block">{stg.stage}</span>
              <span className="font-bold text-emerald-400">{stg.latencyMs} ms</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
