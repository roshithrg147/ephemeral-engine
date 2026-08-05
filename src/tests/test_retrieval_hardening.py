"""Deterministic benchmark & regression test suite for SC-EVM Retrieval Hardening.

Validates:
1. AdaptiveThresholdEngine gating mechanism.
2. BM25 Lexical exact-match retrieval.
3. AST Symbol lookup (classes, functions, interfaces).
4. API Route lookup (HTTP routes & handlers).
5. Cross-file dependency resolution.
6. 3-Way Hybrid RRF fusion & RetrievalEvaluator benchmarks.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.config import settings
from src.sc_evm import SCEVMEngine
from src.services.ast_indexer import ASTIndexer
from src.services.bm25_indexer import BM25Indexer
from src.services.fusion_engine import RetrievalFusionEngine
from src.services.retrieval_evaluator import RetrievalEvaluator
from src.thresholds import AdaptiveThresholdEngine


class TestRetrievalHardening(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "thresholds.json"
        self.threshold_engine = AdaptiveThresholdEngine(
            store_path=str(self.store_path), window_maxlen=500
        )
        self.bm25 = BM25Indexer()
        self.ast_idx = ASTIndexer(root_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_adaptive_threshold_gating(self):
        """Verify AdaptiveThresholdEngine is the sole source of truth for percentile bounds and gating."""
        model = "test-model"
        distances = [0.10, 0.15, 0.22, 0.28, 0.35, 0.42, 0.50, 0.65, 0.80, 0.95]
        repo, sess = "repo-a", "sess-1"
        self.threshold_engine.add_observation(model, repo, sess, distances)

        stats = self.threshold_engine.get_stats(model, repo, sess)
        self.assertIn("mean", stats)
        self.assertIn("percentiles", stats)

        p10 = self.threshold_engine.get_percentile(model, 10, repo, sess)
        p90 = self.threshold_engine.get_percentile(model, 90, repo, sess)
        acc_thresh = self.threshold_engine.get_acceptance_threshold(model, repo, sess)

        self.assertIsNotNone(p10)
        self.assertIsNotNone(p90)
        self.assertIsNotNone(acc_thresh)
        self.assertLess(p10, p90)

        # Test SCEVMEngine filter_documents_via_gating using threshold engine values
        docs = ["doc1", "doc2", "doc3", "doc4"]
        test_dists = [0.05, 0.20, 0.30, 0.99]
        test_embs = [[0.1] * 10, [0.2] * 10, [0.3] * 10, [0.9] * 10]

        filtered = SCEVMEngine.filter_documents_via_gating(
            query_vector=[0.1] * 10,
            documents=docs,
            distances=test_dists,
            embeddings=test_embs,
            base_threshold=acc_thresh,
            absolute_ceiling=p90,
            absolute_floor=p10,
        )

        # Outlier distance 0.99 > p90 must be filtered out
        self.assertNotIn("doc4", filtered)
        self.assertIn("doc1", filtered)

    def test_02_lexical_exact_match(self):
        """Verify BM25Indexer exact token matching for code symbols, routes, and config terms."""
        self.bm25.add_document("doc-1", "def initialize_session(tenant_id: str, owner: str): pass")
        self.bm25.add_document("doc-2", "RETRIEVAL_BASE_DISTANCE_THRESHOLD = 0.45")
        self.bm25.add_document("doc-3", "class MultiTenantSessionRegistry: def purge(self): pass")

        res1 = self.bm25.search("initialize_session", top_k=2)
        self.assertTrue(len(res1) > 0)
        self.assertEqual(res1[0].doc_id, "doc-1")

        res2 = self.bm25.search("RETRIEVAL_BASE_DISTANCE_THRESHOLD", top_k=2)
        self.assertTrue(len(res2) > 0)
        self.assertEqual(res2[0].doc_id, "doc-2")

        res3 = self.bm25.search("MultiTenantSessionRegistry", top_k=2)
        self.assertTrue(len(res3) > 0)
        self.assertEqual(res3[0].doc_id, "doc-3")

    def test_03_ast_symbol_lookup(self):
        """Verify ASTIndexer extracts classes, functions, and interfaces accurately."""
        py_code = '''
from pydantic import BaseModel

class SessionConfig(BaseModel):
    token_budget: int = 8192

async def compute_context_budget(session_id: str) -> int:
    """Calculate remaining context budget for current session."""
    return 4096
'''
        symbols = self.ast_idx.index_file("src/services/budget.py", content=py_code)
        sym_types = {s.symbol_type for s in symbols}
        self.assertIn("interface", sym_types)  # BaseModel inherits -> interface
        self.assertIn("function", sym_types)
        self.assertIn("import", sym_types)

        search_res = self.ast_idx.search_symbols("SessionConfig", top_k=3)
        self.assertTrue(len(search_res) > 0)
        self.assertEqual(search_res[0].symbol.symbol_name, "SessionConfig")

        search_func = self.ast_idx.search_symbols("compute_context_budget", top_k=3)
        self.assertTrue(len(search_func) > 0)
        self.assertEqual(search_func[0].symbol.symbol_name, "compute_context_budget")

    def test_04_route_lookup(self):
        """Verify ASTIndexer extracts API route endpoints and signatures."""
        py_route_code = '''
@app.post("/api/session/initialize")
async def init_session_endpoint(req: SessionInitRequest):
    return {"status": "ok"}

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}
'''
        symbols = self.ast_idx.index_file("src/routes.py", content=py_route_code)
        routes = [s for s in symbols if s.symbol_type == "route"]
        self.assertEqual(len(routes), 2)
        route_signatures = {r.signature for r in routes}
        self.assertIn("@POST /api/session/initialize -> init_session_endpoint", route_signatures)
        self.assertIn("@GET /api/health -> health_check", route_signatures)

    def test_05_cross_file_dependencies(self):
        """Verify ASTIndexer maps imported symbols into symbol cross-file relationships."""
        code_a = '''
from src.memory import MultiTenantSessionRegistry
from src.config import settings

class SessionManager:
    def __init__(self):
        self.registry = MultiTenantSessionRegistry()
'''
        self.ast_idx.index_file("src/services/manager.py", content=code_a)
        search_res = self.ast_idx.search_symbols("SessionManager", top_k=1)
        self.assertTrue(len(search_res) > 0)
        node = search_res[0]
        self.assertEqual(node.symbol.symbol_name, "SessionManager")
        self.assertIn("src.memory.MultiTenantSessionRegistry", node.relationships)
        self.assertIn("src.config.settings", node.relationships)

    def test_06_hybrid_fusion_benchmark_evaluation(self):
        """Verify 3-way RRF fusion and evaluate precision, recall, MRR, hit rate with RetrievalEvaluator."""
        sem_cands = [
            {"doc_id": "doc-1", "text": "Session isolation and memory management in RAM"},
            {"doc_id": "doc-2", "text": "Adaptive threshold calibration engine"},
        ]
        lex_cands = [
            {"doc_id": "doc-1", "text": "Session isolation and memory management in RAM"},
            {"doc_id": "doc-3", "text": "BM25 exact token matching index"},
        ]
        struct_cands = [
            {"doc_id": "doc-1", "text": "class MultiTenantSessionRegistry(BaseModel)"},
            {"doc_id": "doc-4", "text": "ASTIndexer search_symbols route lookup"},
        ]

        fusion_engine = RetrievalFusionEngine()
        fused_cands, fusion_lat = fusion_engine.fuse(
            sem_cands, lex_cands, struct_cands, limit=5
        )

        self.assertTrue(len(fused_cands) > 0)
        # doc-1 appears in all 3 pipelines, so it MUST be ranked #1
        self.assertEqual(fused_cands[0].doc_id, "doc-1")
        self.assertIn("semantic", fused_cands[0].pipeline_sources)
        self.assertIn("lexical", fused_cands[0].pipeline_sources)
        self.assertIn("structural", fused_cands[0].pipeline_sources)

        # Benchmark evaluation using RetrievalEvaluator
        evaluator = RetrievalEvaluator(k=5)
        benchmark_sample = {
            "retrieved_ids": [c.doc_id for c in fused_cands],
            "relevant_ids": ["doc-1", "doc-2"],
            "latency_ms": fusion_lat,
            "tokens_used": 150,
            "context_utilization": 0.92,
        }
        metrics = evaluator.evaluate_benchmark_suite([benchmark_sample])

        self.assertGreaterEqual(metrics.precision_at_k, 0.4)
        self.assertGreaterEqual(metrics.recall_at_k, 0.5)
        self.assertEqual(metrics.hit_rate, 1.0)
        self.assertEqual(metrics.mrr, 1.0)


if __name__ == "__main__":
    unittest.main()
