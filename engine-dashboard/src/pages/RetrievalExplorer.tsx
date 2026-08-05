import React, { useState } from 'react';
import { Search, Layers, Cpu, Code2, Database, ShieldCheck, HelpCircle, Download } from 'lucide-react';

interface RetrievalCandidate {
  docId: string;
  file: string;
  text: string;
  fusionScore: number;
  semanticScore: number;
  bm25Score: number;
  astScore: number;
  accepted: boolean;
  reason: string;
  bm25Contribution: number;
  astContribution: number;
}

export function RetrievalExplorer() {
  const [selectedQuery, setSelectedQuery] = useState("How does MultiTenantSessionRegistry handle session purging?");
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>("sem-1");

  const candidates: RetrievalCandidate[] = [
    {
      docId: "sem-1",
      file: "src/memory.py",
      text: "class MultiTenantSessionRegistry: def purge_session(self, session_id: str, tenant_id: str): ...",
      fusionScore: 0.88,
      semanticScore: 0.92,
      bm25Score: 0.85,
      astScore: 0.78,
      accepted: true,
      reason: "High semantic similarity + AST class match",
      bm25Contribution: 0.42,
      astContribution: 0.31,
    },
    {
      docId: "lex-2",
      file: "src/services/session_lifecycle.py",
      text: "class SessionLifecycleService: async def burn(self, session_id: str): ...",
      fusionScore: 0.79,
      semanticScore: 0.75,
      bm25Score: 0.89,
      astScore: 0.65,
      accepted: true,
      reason: "Exact BM25 token match on 'burn' and 'session_id'",
      bm25Contribution: 0.51,
      astContribution: 0.18,
    },
    {
      docId: "ast-3",
      file: "src/sc_evm.py",
      text: "def filter_documents_via_gating(self, query_vector, documents, distances): ...",
      fusionScore: 0.64,
      semanticScore: 0.60,
      bm25Score: 0.55,
      astScore: 0.82,
      accepted: false,
      reason: "Distance exceeds adaptive acceptance threshold (0.45)",
      bm25Contribution: 0.20,
      astContribution: 0.44,
    },
  ];

  const selectedBlock = candidates.find((c) => c.docId === selectedBlockId) || candidates[0];

  const exportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ query: selectedQuery, candidates }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `retrieval_trace_${Date.now()}.json`);
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
            <Layers className="w-5 h-5 text-accent" />
            Retrieval Explorer
          </h1>
          <p className="text-xs text-text-tertiary mt-1">
            Explainable 3-way RRF fusion across Semantic Vector, BM25 Lexical, and AST Structural search.
          </p>
        </div>
        <button
          onClick={exportJSON}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-2 hover:bg-surface-3 border border-border-subtle rounded-md text-xs font-medium text-text-primary transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          Export JSON
        </button>
      </div>

      {/* Query Bar */}
      <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg flex items-center gap-3">
        <Search className="w-4 h-4 text-text-tertiary" />
        <input
          type="text"
          value={selectedQuery}
          onChange={(e) => setSelectedQuery(e.target.value)}
          className="flex-1 bg-transparent text-sm text-text-primary focus:outline-none font-mono"
        />
        <span className="text-[11px] font-mono px-2.5 py-1 bg-surface-2 border border-border-subtle rounded text-accent uppercase">
          Intent: CODE_QUERY
        </span>
      </div>

      {/* Pipeline Flowchart */}
      <div className="grid grid-cols-7 gap-2 text-center text-xs">
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded flex flex-col items-center justify-center">
          <span className="text-text-tertiary text-[10px]">1. Query</span>
          <span className="font-semibold text-text-primary text-[11px]">User Input</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded flex flex-col items-center justify-center">
          <span className="text-text-tertiary text-[10px]">2. Intent</span>
          <span className="font-semibold text-accent text-[11px]">Code Query</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded flex flex-col items-center justify-center">
          <span className="text-text-tertiary text-[10px]">3. Vector</span>
          <span className="font-semibold text-purple-400 text-[11px]">Semantic (0.92)</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded flex flex-col items-center justify-center">
          <span className="text-text-tertiary text-[10px]">4. BM25</span>
          <span className="font-semibold text-cyan-400 text-[11px]">Lexical (0.85)</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded flex flex-col items-center justify-center">
          <span className="text-text-tertiary text-[10px]">5. AST</span>
          <span className="font-semibold text-emerald-400 text-[11px]">Structural (0.78)</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded flex flex-col items-center justify-center">
          <span className="text-text-tertiary text-[10px]">6. RRF Fusion</span>
          <span className="font-semibold text-amber-400 text-[11px]">Score: 0.88</span>
        </div>
        <div className="bg-surface-1 border border-border-subtle p-2.5 rounded flex flex-col items-center justify-center">
          <span className="text-text-tertiary text-[10px]">7. Threshold</span>
          <span className="font-semibold text-emerald-400 text-[11px]">Admitted</span>
        </div>
      </div>

      {/* Main Grid: Candidate Table + Explainability Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        {/* Candidates List */}
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Retrieved Context Candidates ({candidates.length})
          </h2>
          <div className="space-y-2">
            {candidates.map((c) => {
              const isSelected = c.docId === selectedBlockId;
              return (
                <div
                  key={c.docId}
                  onClick={() => setSelectedBlockId(c.docId)}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-surface-2 border-accent'
                      : 'bg-surface-1 border-border-subtle hover:bg-surface-2'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-text-primary">{c.file}</span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                          c.accepted
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}
                      >
                        {c.accepted ? 'Admitted' : 'Rejected'}
                      </span>
                    </div>
                    <span className="font-mono text-xs font-bold text-accent">
                      Fusion: {c.fusionScore}
                    </span>
                  </div>
                  <p className="font-mono text-xs text-text-secondary truncate bg-canvas/50 p-1.5 rounded border border-border-subtle">
                    {c.text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Explainability Panel */}
        <div className="bg-surface-1 border border-border-subtle p-4 rounded-lg space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary flex items-center gap-1.5">
            <HelpCircle className="w-4 h-4 text-accent" />
            Explainability Panel
          </h3>

          <div className="space-y-3 text-xs">
            <div>
              <span className="text-text-tertiary block mb-1">Target File</span>
              <span className="font-mono font-medium text-text-primary">{selectedBlock.file}</span>
            </div>

            <div>
              <span className="text-text-tertiary block mb-1">Admission Decision Rationale</span>
              <p className="text-text-secondary bg-surface-2 p-2 rounded border border-border-subtle">
                {selectedBlock.reason}
              </p>
            </div>

            <div>
              <span className="text-text-tertiary block mb-2">Score Decomposition</span>
              <div className="space-y-2 font-mono">
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-purple-400">Semantic Vector</span>
                    <span>{selectedBlock.semanticScore}</span>
                  </div>
                  <div className="w-full bg-surface-2 h-1.5 rounded overflow-hidden">
                    <div className="bg-purple-500 h-full" style={{ width: `${selectedBlock.semanticScore * 100}%` }} />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-cyan-400">BM25 Lexical Contribution</span>
                    <span>{selectedBlock.bm25Contribution}</span>
                  </div>
                  <div className="w-full bg-surface-2 h-1.5 rounded overflow-hidden">
                    <div className="bg-cyan-500 h-full" style={{ width: `${selectedBlock.bm25Contribution * 100}%` }} />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-emerald-400">AST Structural Contribution</span>
                    <span>{selectedBlock.astContribution}</span>
                  </div>
                  <div className="w-full bg-surface-2 h-1.5 rounded overflow-hidden">
                    <div className="bg-emerald-500 h-full" style={{ width: `${selectedBlock.astContribution * 100}%` }} />
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-border-subtle pt-3 font-mono">
              <div className="flex justify-between text-text-secondary">
                <span>Acceptance Threshold</span>
                <span>0.45</span>
              </div>
              <div className="flex justify-between text-text-secondary mt-1">
                <span>Rejection Threshold</span>
                <span>0.90</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
