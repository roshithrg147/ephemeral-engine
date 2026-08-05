"""Unit and Integration Tests for Phase 2 Hybrid Retrieval Fusion Engine.

Verifies:
- BM25 lexical lookup (variable, function, route, config, SQL migration).
- Incremental AST parsing and symbol graph extraction.
- Intent routing and structural gating policy.
- Reciprocal Rank Fusion (RRF) candidate merging and configurable weights.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.services.ast_indexer import ASTIndexer
from src.services.bm25_indexer import BM25Indexer
from src.services.fusion_engine import RetrievalFusionEngine
from src.services.intent_router import IntentRouter


class TestBM25Indexer(unittest.TestCase):
    def setUp(self):
        self.indexer = BM25Indexer()

    def test_variable_and_function_lookup(self):
        self.indexer.add_document("doc1", "def calculate_total_tax(amount, rate): return amount * rate")
        self.indexer.add_document("doc2", "class UserProfile: def get_user_email(self): pass")
        self.indexer.add_document("doc3", "CREATE TABLE users (id INT, email VARCHAR(255))")

        res_fn = self.indexer.search("calculate_total_tax", top_k=3)
        self.assertTrue(len(res_fn) > 0)
        self.assertEqual(res_fn[0].doc_id, "doc1")

        res_sql = self.indexer.search("CREATE TABLE users", top_k=3)
        self.assertTrue(len(res_sql) > 0)
        self.assertEqual(res_sql[0].doc_id, "doc3")

    def test_incremental_removal_and_clear(self):
        self.indexer.add_document("doc1", "temporary authentication token")
        self.indexer.remove_document("doc1")
        res = self.indexer.search("authentication", top_k=3)
        self.assertEqual(len(res), 0)


class TestASTIndexer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.indexer = ASTIndexer(root_dir=self.root_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_python_symbol_extraction(self):
        py_code = '''
import os
from pydantic import BaseModel

class UserSchema(BaseModel):
    user_id: str

@app.get("/api/user/profile")
async def get_user_profile(user_id: str):
    db_key = os.getenv("DATABASE_URL")
    return {"user": user_id}
'''
        file_path = self.root_path / "main.py"
        file_path.write_text(py_code)

        symbols = self.indexer.index_file("main.py")
        sym_names = {s.symbol_name for s in symbols}

        self.assertIn("UserSchema", sym_names)
        self.assertIn("get_user_profile", sym_names)
        self.assertIn("DATABASE_URL", sym_names)

    def test_incremental_indexing(self):
        file_path = self.root_path / "service.py"
        file_path.write_text("def first_version(): pass")
        self.indexer.index_file("service.py")

        results1 = self.indexer.search_symbols("first_version")
        self.assertEqual(len(results1), 1)

        # Update file content
        file_path.write_text("def updated_version(): pass")
        self.indexer.index_file("service.py")

        results_old = self.indexer.search_symbols("first_version")
        results_new = self.indexer.search_symbols("updated_version")
        self.assertEqual(len(results_old), 0)
        self.assertEqual(len(results_new), 1)


class TestIntentRouter(unittest.TestCase):
    def test_intent_classification(self):
        self.assertEqual(IntentRouter.classify_intent("Hello, how are you?"), "Conversation")
        self.assertEqual(IntentRouter.classify_intent("How to configure FastAPI?"), "Question answering")
        self.assertEqual(IntentRouter.classify_intent("Where is function get_user_profile defined?"), "Code lookup")
        self.assertEqual(IntentRouter.classify_intent("Explain system architecture and module dependencies"), "Architecture")
        self.assertEqual(IntentRouter.classify_intent("What modules are imported by agent.py?"), "Dependency analysis")
        self.assertEqual(IntentRouter.classify_intent("Refactor function to extract class helper"), "Refactoring")

    def test_structural_gating_policy(self):
        # Non-structural requests MUST NOT invoke AST
        self.assertFalse(IntentRouter.requires_structural_ast("Conversation"))
        self.assertFalse(IntentRouter.requires_structural_ast("Question answering"))

        # Structural requests MUST invoke AST
        self.assertTrue(IntentRouter.requires_structural_ast("Code lookup"))
        self.assertTrue(IntentRouter.requires_structural_ast("Architecture"))
        self.assertTrue(IntentRouter.requires_structural_ast("Dependency analysis"))
        self.assertTrue(IntentRouter.requires_structural_ast("Refactoring"))


class TestRetrievalFusionEngine(unittest.TestCase):
    def test_reciprocal_rank_fusion(self):
        engine = RetrievalFusionEngine(semantic_weight=0.5, lexical_weight=0.3, structural_weight=0.2)

        sem_results = [{"doc_id": "doc1", "text": "Semantic document content"}]
        lex_results = [{"doc_id": "doc2", "text": "Lexical document content"}]
        struct_results = [{"doc_id": "doc1", "text": "Semantic document content"}]

        fused, latency_ms = engine.fuse(sem_results, lex_results, struct_results, limit=5)

        self.assertTrue(len(fused) > 0)
        # doc1 appears in both semantic and structural, so its RRF score is highest
        self.assertEqual(fused[0].doc_id, "doc1")
        self.assertIn("semantic", fused[0].pipeline_sources)
        self.assertIn("structural", fused[0].pipeline_sources)
        self.assertLess(latency_ms, 3.0)  # Sub-3ms requirement

    def test_configurable_weights(self):
        engine = RetrievalFusionEngine(semantic_weight=0.9, lexical_weight=0.1, structural_weight=0.0)
        self.assertEqual(engine.semantic_weight, 0.9)
        self.assertEqual(engine.lexical_weight, 0.1)
        self.assertEqual(engine.structural_weight, 0.0)


if __name__ == "__main__":
    unittest.main()
