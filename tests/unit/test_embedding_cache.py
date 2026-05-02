import numpy as np

from src.embeddings.cache import EmbeddingCache


def test_cache_roundtrip(tmp_path):
    cache = EmbeddingCache(tmp_path, dim=4)
    vec = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

    assert cache.get("hello") is None
    cache.put("hello", vec)
    out = cache.get("hello")

    assert out is not None
    np.testing.assert_allclose(out, vec)


def test_cache_get_many(tmp_path):
    cache = EmbeddingCache(tmp_path, dim=2)
    cache.put("a", np.array([1.0, 0.0], dtype=np.float32))

    cached, missing_idx, missing_texts = cache.get_many(["a", "b", "c"])

    assert cached[0] is not None
    assert cached[1] is None and cached[2] is None
    assert missing_idx == [1, 2]
    assert missing_texts == ["b", "c"]
