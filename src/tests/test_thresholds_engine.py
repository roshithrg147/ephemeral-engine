import os
import tempfile

from src.thresholds import AdaptiveThresholdEngine


def test_engine_compute_stats_and_persistence(tmp_path):
    store = tmp_path / "calib.json"
    engine = AdaptiveThresholdEngine(store_path=str(store), window_maxlen=100)
    model = "test-embed"
    engine.add_observation(model, "repo1", "sess1", [0.1, 0.2, 0.15, 0.12])
    stats = engine.get_stats(model, "repo1", "sess1")
    assert stats["count"] == 4
    assert stats["median"] is not None
    # save invoked implicitly
    engine._save()
    assert store.exists()
    # load new instance
    engine2 = AdaptiveThresholdEngine(store_path=str(store), window_maxlen=100)
    stats2 = engine2.get_stats(model, "repo1", "sess1")
    assert stats2["count"] == 4
