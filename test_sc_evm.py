import asyncio
from src.sc_evm import SCEVMEngine

async def test_sc_evm():
    print("Testing SCEVMEngine components...")
    
    engine = SCEVMEngine()
    
    # Test 1: Query Reformulator Logic
    print("\n--- Test: Query Reformulator ---")
    current_input = "how does the dual-anchor gating work?"
    history = [
        {"role": "user", "content": "I am looking at sc_evm.py"},
        {"role": "assistant", "content": "I can help with that file. What part are you looking at?"}
    ]
    
    compiled_prompt = engine.reformulate_query(current_input, history)
    print("Reformulated Query Prompt:\n", compiled_prompt)
    print("---")

    # Test 2: Dual-Anchor Confidence Gating Math
    print("\n--- Test: Dual-Anchor Confidence Gating ---")
    
    query_vector = [1.0, 0.0, 0.0]
    
    # We want to test the filter gating logic.
    # absolute_floor = 0.38
    # absolute_ceiling = 0.48
    # neighboring_delta_limit = 0.12
    # top_anchor_delta_limit = 0.18
    # base_threshold = 0.52 (cosine similarity threshold)

    docs = ["doc1_below_floor", "doc2_gated_accepted", "doc3_gated_rejected"]
    
    # doc1 is below floor (e.g. dist 0.30) -> auto accepted
    # doc2 is dist 0.40 -> delta from doc1 = 0.10 (<= 0.12). anchor delta = 0.10 (<= 0.18).
    # doc2 needs to pass confidence gate. Let's make it highly similar: [0.9, 0.1, 0.0]
    # doc3 is dist 0.46 -> delta from doc2 = 0.06 (<= 0.12). anchor delta = 0.16 (<= 0.18).
    # doc3 needs to fail confidence gate. Let's make its similarity low: [0.0, 1.0, 0.0]
    
    dists = [0.30, 0.40, 0.46]
    
    embs = [
        [1.0, 0.0, 0.0],  # doc1 (Anchor A initially)
        [0.9, 0.1, 0.0],  # doc2 (similar, should pass > 0.52 cosine sim)
        [0.0, 1.0, 0.0]   # doc3 (dissimilar, should fail <= 0.52 cosine sim)
    ]
    
    print("Running filter_documents_via_gating with floor 0.38...")
    matched = engine.filter_documents_via_gating(
        query_vector=query_vector,
        documents=docs,
        distances=dists,
        embeddings=embs
    )
    
    print("Matched Documents:", matched)
    
    assert "doc1_below_floor" in matched, "doc1 should be accepted by absolute floor"
    assert "doc2_gated_accepted" in matched, "doc2 should be accepted by dual-anchor gating"
    assert "doc3_gated_rejected" not in matched, "doc3 should be rejected by dual-anchor gating"
    
    print("\nSuccess: Technical query hit the correct confidence gates!")

if __name__ == "__main__":
    asyncio.run(test_sc_evm())
