import React from 'react';
import { Terminal, CheckCircle2, GitBranch, ShieldCheck, Cpu } from 'lucide-react';

export function DeveloperPage() {
  const capabilities = [
    { name: "Adaptive Outlier Thresholding", enabled: true, module: "src/thresholds.py" },
    { name: "3-Way Hybrid RRF Fusion", enabled: true, module: "src/services/fusion_engine.py" },
    { name: "AST & Symbol Graph Indexer", enabled: true, module: "src/services/ast_indexer.py" },
    { name: "BM25 Lexical Indexer", enabled: true, module: "src/services/bm25_indexer.py" },
    { name: "Authoritative Context Governance", enabled: true, module: "src/services/context_planner.py" },
    { name: "Local Vector & Embedding Engine", enabled: true, module: "src/services/local_embedding_engine.py" },
    { name: "Circuit Breaker 2.0 (6-State)", enabled: true, module: "src/services/circuit_breaker.py" },
    { name: "Provider Health Manager", enabled: true, module: "src/services/provider_health.py" },
    { name: "Policy-Driven Resilient Router", enabled: true, module: "src/services/resilient_router.py" },
    { name: "Multi-Tenant Volatile Isolation", enabled: true, module: "src/memory.py" },
  ];

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto bg-canvas">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
          <Terminal className="w-5 h-5 text-accent" />
          Developer & Engineering Metadata
        </h1>
        <p className="text-xs text-text-tertiary mt-1">
          Canonical capability status, build metadata, environment configuration, and test coverage metrics.
        </p>
      </div>

      {/* Engineering Build Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
        <div className="bg-surface-1 border border-border-subtle p-3.5 rounded-lg">
          <span className="text-text-tertiary block">Release Version</span>
          <span className="text-sm font-bold text-accent mt-0.5 block">2.0.0-rc1</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-3.5 rounded-lg">
          <span className="text-text-tertiary block">Git Commit</span>
          <span className="text-sm font-bold text-text-primary mt-0.5 block">8f3e21a</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-3.5 rounded-lg">
          <span className="text-text-tertiary block">Branch</span>
          <span className="text-sm font-bold text-text-primary mt-0.5 block">main</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-3.5 rounded-lg">
          <span className="text-text-tertiary block">CI Pipeline Status</span>
          <span className="text-sm font-bold text-emerald-400 mt-0.5 block">Passing (150/150)</span>
        </div>
      </div>

      {/* Enabled Capabilities Checklist */}
      <div className="bg-surface-1 border border-border-subtle p-5 rounded-lg space-y-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary flex items-center gap-1.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          Canonical System Capabilities Matrix
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
          {capabilities.map((cap) => (
            <div key={cap.name} className="flex items-center justify-between bg-surface-2 p-2.5 rounded border border-border-subtle">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-none" />
                <span className="text-text-primary font-medium">{cap.name}</span>
              </div>
              <span className="text-text-tertiary text-[11px]">{cap.module}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
