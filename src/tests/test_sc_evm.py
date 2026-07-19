import unittest

from src.config import settings
from src.sc_evm import SCEVMEngine


class TestSCEVMEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SCEVMEngine()

    def test_query_reformulator(self):
        print("Testing Query Reformulator Logic...")
        current_input = "how does the dual-anchor gating work?"
        history = [
            {"role": "user", "content": "I am looking at sc_evm.py"},
            {
                "role": "assistant",
                "content": "I can help with that file. What part are you looking at?",
            },
        ]

        compiled_prompt = self.engine.reformulate_query(current_input, history)
        self.assertIn("how does the dual-anchor gating work?", compiled_prompt)

    def test_dual_anchor_confidence_gating(self):
        print("Testing Dual-Anchor Confidence Gating...")

        query_vector = [1.0, 0.0, 0.0]
        docs = ["doc1_below_floor", "doc2_gated_accepted", "doc3_gated_rejected"]

        dists = [0.30, 0.40, 0.46]

        embs = [
            [1.0, 0.0, 0.0],  # doc1 (Anchor A initially)
            [0.9, 0.1, 0.0],  # doc2 (similar, should pass configured distance gate)
            [0.0, 1.0, 0.0],  # doc3 (dissimilar, should fail configured distance gate)
        ]

        matched = self.engine.filter_documents_via_gating(
            query_vector=query_vector,
            documents=docs,
            distances=dists,
            embeddings=embs,
            base_threshold=settings.RETRIEVAL_BASE_DISTANCE_THRESHOLD,
        )

        print("Matched Documents:", matched)
        self.assertIn("doc1_below_floor", matched, "doc1 should be accepted by absolute floor")
        self.assertIn(
            "doc2_gated_accepted", matched, "doc2 should be accepted by dual-anchor gating"
        )
        self.assertNotIn(
            "doc3_gated_rejected", matched, "doc3 should be rejected by dual-anchor gating"
        )

    def test_gating_boundary_identical(self):
        # Identical vectors (distance = 0.0)
        query = [1.0, 0.0, 0.0]
        doc = [1.0, 0.0, 0.0]
        dist = SCEVMEngine.cosine_distance(query, doc)
        self.assertAlmostEqual(dist, 0.0, places=6)

    def test_gating_boundary_borderline(self):
        # Borderline vectors
        query = [1.0, 0.0, 0.0]
        doc = [0.707106, 0.707106, 0.0]  # 45 degrees, similarity ~0.707, distance ~0.293
        dist = SCEVMEngine.cosine_distance(query, doc)
        self.assertAlmostEqual(dist, 0.292893, places=5)

    def test_gating_boundary_unrelated(self):
        # Unrelated orthogonal vectors (distance = 1.0)
        query = [1.0, 0.0, 0.0]
        doc = [0.0, 1.0, 0.0]
        dist = SCEVMEngine.cosine_distance(query, doc)
        self.assertAlmostEqual(dist, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
