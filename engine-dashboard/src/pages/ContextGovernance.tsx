import React, { useState } from 'react';
import { ShieldCheck, CheckCircle2, XCircle, Clock, FileText, Download } from 'lucide-react';

interface GovernedBlock {
  id: string;
  source: string;
  text: string;
  admitted: boolean;
  reason: string;
  tokens: number;
}

export function ContextGovernance() {
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>("sem-mem-1");

  const totalLimit = 4096;
  const usedTokens = 3124;
  const reservedOutput = 900;
  const remainingTokens = totalLimit - usedTokens - reservedOutput; // 72 tokens

  const blocks: GovernedBlock[] = [
    {
      id: "sys-1",
      source: "System Prompt",
      text: "You are an AI coding assistant.",
      admitted: true,
      reason: "System floor guarantee (Priority 100)",
      tokens: 25,
    },
    {
      id: "sem-mem-1",
      source: "Semantic Memory",
      text: "class MultiTenantSessionRegistry: def purge_session(self): ...",
      admitted: true,
      reason: "High similarity score (0.92) within source budget cap",
      tokens: 450,
    },
    {
      id: "ast-1",
      source: "AST Structural",
      text: "interface SessionRecord { session_id: string; last_accessed: float }",
      admitted: true,
      reason: "Required structural interface symbol",
      tokens: 310,
    },
    {
      id: "evict-1",
      source: "Semantic Memory",
      text: "Historical prompt expansion context from previous turn",
      admitted: false,
      reason: "Source ceiling limit exceeded (semantic_memory max cap 1500 tokens)",
      tokens: 600,
    },
    {
      id: "evict-2",
      source: "Lexical BM25",
      text: "Unrelated docstring token match from vendor package",
      admitted: false,
      reason: "Budget exhausted (total input limit 3196 tokens reached)",
      tokens: 420,
    },
    {
      id: "evict-3",
      source: "History",
      text: "Turn 1 user request from 15 minutes ago",
      admitted: false,
      reason: "TTL expired (Expiration timestamp < current time)",
      tokens: 210,
    },
  ];

  const selectedBlock = blocks.find((b) => b.id === selectedBlockId) || blocks[0];

  const exportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ totalLimit, usedTokens, blocks }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `governance_report_${Date.now()}.json`);
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
            <ShieldCheck className="w-5 h-5 text-accent" />
            Context Governance
          </h1>
          <p className="text-xs text-text-tertiary mt-1">
            Authoritative policy layer deciding prompt admissions, evictions, and machine-readable audit rationale.
          </p>
        </div>
        <button
          onClick={exportJSON}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-2 hover:bg-surface-3 border border-border-subtle rounded-md text-xs font-medium text-text-primary transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          Export Governance Report
        </button>
      </div>

      {/* Prompt Budget Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg">
          <span className="text-xs text-text-tertiary">Total Token Budget</span>
          <div className="text-xl font-bold font-mono text-text-primary mt-1">{totalLimit.toLocaleString()}</div>
        </div>

        <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg">
          <span className="text-xs text-text-tertiary">Admitted Input Used</span>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-1">{usedTokens.toLocaleString()}</div>
        </div>

        <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg">
          <span className="text-xs text-text-tertiary">Reserved Output Buffer</span>
          <div className="text-xl font-bold font-mono text-cyan-400 mt-1">{reservedOutput.toLocaleString()}</div>
        </div>

        <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg">
          <span className="text-xs text-text-tertiary">Remaining Elastic Token Capacity</span>
          <div className="text-xl font-bold font-mono text-amber-400 mt-1">{remainingTokens.toLocaleString()}</div>
        </div>
      </div>

      {/* Governance Timeline */}
      <div className="grid grid-cols-5 gap-2 text-center text-xs">
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded">
          <span className="text-text-tertiary text-[10px] block">Stage 1</span>
          <span className="font-semibold text-text-primary">Retrieve Candidates</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded">
          <span className="text-text-tertiary text-[10px] block">Stage 2</span>
          <span className="font-semibold text-accent">Policy Bounds Check</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded">
          <span className="text-text-tertiary text-[10px] block">Stage 3</span>
          <span className="font-semibold text-purple-400">Knapsack Optimization</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded">
          <span className="text-text-tertiary text-[10px] block">Stage 4</span>
          <span className="font-semibold text-emerald-400">Assemble Governed Prompt</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded">
          <span className="text-text-tertiary text-[10px] block">Stage 5</span>
          <span className="font-semibold text-cyan-400">Stream LLM Synthesis</span>
        </div>
      </div>

      {/* Main Grid: Admitted vs Evicted List + Audit Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        {/* Admitted & Evicted Lists */}
        <div className="lg:col-span-2 space-y-4">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-2 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              Admitted Context Blocks ({blocks.filter((b) => b.admitted).length})
            </h2>
            <div className="space-y-2">
              {blocks.filter((b) => b.admitted).map((b) => (
                <div
                  key={b.id}
                  onClick={() => setSelectedBlockId(b.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedBlockId === b.id
                      ? 'bg-surface-2 border-emerald-500'
                      : 'bg-surface-1 border-border-subtle hover:bg-surface-2'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-xs font-semibold text-text-primary">{b.source} ({b.id})</span>
                    <span className="font-mono text-xs text-emerald-400 font-bold">+{b.tokens} tokens</span>
                  </div>
                  <p className="font-mono text-xs text-text-secondary truncate bg-canvas/50 p-1.5 rounded border border-border-subtle">
                    {b.text}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-red-400 mb-2 flex items-center gap-1.5">
              <XCircle className="w-4 h-4 text-red-400" />
              Evicted Context Blocks ({blocks.filter((b) => !b.admitted).length})
            </h2>
            <div className="space-y-2">
              {blocks.filter((b) => !b.admitted).map((b) => (
                <div
                  key={b.id}
                  onClick={() => setSelectedBlockId(b.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedBlockId === b.id
                      ? 'bg-surface-2 border-red-500'
                      : 'bg-surface-1 border-border-subtle hover:bg-surface-2'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-xs font-semibold text-text-primary">{b.source} ({b.id})</span>
                    <span className="font-mono text-xs text-red-400 font-bold">{b.tokens} tokens</span>
                  </div>
                  <p className="font-mono text-xs text-text-tertiary truncate bg-canvas/50 p-1.5 rounded border border-border-subtle">
                    {b.text}
                  </p>
                  <span className="text-[10px] text-red-400 font-mono block mt-1">Reason: {b.reason}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Audit Details Panel */}
        <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary flex items-center gap-1.5">
            <FileText className="w-4 h-4 text-accent" />
            Governance Audit Rationale
          </h3>

          <div className="space-y-3 text-xs">
            <div>
              <span className="text-text-tertiary block mb-1">Block ID & Source</span>
              <span className="font-mono font-bold text-text-primary">{selectedBlock.id} ({selectedBlock.source})</span>
            </div>

            <div>
              <span className="text-text-tertiary block mb-1">Policy Outcome</span>
              <span
                className={`font-mono text-xs font-bold px-2 py-0.5 rounded border uppercase inline-block ${
                  selectedBlock.admitted
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : 'bg-red-500/10 text-red-400 border-red-500/20'
                }`}
              >
                {selectedBlock.admitted ? 'ADMITTED' : 'EVICTED'}
              </span>
            </div>

            <div>
              <span className="text-text-tertiary block mb-1">Decision Rationale</span>
              <p className="text-text-secondary bg-surface-2 p-2 rounded border border-border-subtle font-mono text-[11px]">
                {selectedBlock.reason}
              </p>
            </div>

            <div>
              <span className="text-text-tertiary block mb-1">Content Snippet</span>
              <pre className="text-[10px] font-mono text-text-secondary bg-canvas p-2 rounded border border-border-subtle overflow-x-auto">
                {selectedBlock.text}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
