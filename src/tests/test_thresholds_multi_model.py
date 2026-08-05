from src.thresholds import AdaptiveThresholdEngine


def fake_embedding_fn_factory(dim=3, seed=0):
    def embed(texts):
        out = []
        for i, t in enumerate(texts):
            v = [(i + 1 + seed) / (j + 1 + seed) for j in range(dim)]
            out.append(v)
        return out

    return embed


def test_calibrate_multi_models(tmp_path):
    store = tmp_path / "calib_multi.json"
    engine = AdaptiveThresholdEngine(store_path=str(store), window_maxlen=100)
    models = ["m1", "m2", "m3"]
    for idx, m in enumerate(models):
        emb = fake_embedding_fn_factory(dim=4, seed=idx)
        base = engine.calibrate_from_anchors(m, "repo", "sess", emb, ["a", "b"], ["x"]) 
        assert base is not None
    # ensure persistence
    engine._save()
    assert store.exists()
