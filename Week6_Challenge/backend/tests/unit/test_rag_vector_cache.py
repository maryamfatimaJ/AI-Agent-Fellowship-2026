import json

import numpy as np

from app.rag.retrieval import _chunk_vector_cache, _get_cached_vector, _rank_by_cosine_similarity


class _FakeChunk:
    def __init__(self, id, embedding):
        self.id = id
        self.embedding = embedding


def setup_function():
    _chunk_vector_cache.clear()


def test_get_cached_vector_populates_cache_on_first_call():
    chunk = _FakeChunk(id="c1", embedding=json.dumps([1.0, 2.0, 3.0]))
    assert "c1" not in _chunk_vector_cache

    vector, norm = _get_cached_vector(chunk)
    assert np.allclose(vector, [1.0, 2.0, 3.0])
    assert norm == np.linalg.norm([1.0, 2.0, 3.0])
    assert "c1" in _chunk_vector_cache


def test_get_cached_vector_reuses_cache_without_reparsing(monkeypatch):
    chunk = _FakeChunk(id="c2", embedding=json.dumps([1.0, 0.0]))
    _get_cached_vector(chunk)  # populate

    calls = {"n": 0}
    original_loads = json.loads

    def _counting_loads(*args, **kwargs):
        calls["n"] += 1
        return original_loads(*args, **kwargs)

    monkeypatch.setattr(json, "loads", _counting_loads)
    _get_cached_vector(chunk)
    _get_cached_vector(chunk)

    assert calls["n"] == 0  # cache hit both times, json.loads never re-invoked


def test_get_cached_vector_returns_none_for_missing_embedding():
    chunk = _FakeChunk(id="c3", embedding=None)
    assert _get_cached_vector(chunk) is None


def test_rank_by_cosine_similarity_matches_expected_scores_and_order():
    chunks = [
        _FakeChunk(id="a", embedding=json.dumps([1.0, 0.0])),
        _FakeChunk(id="b", embedding=json.dumps([0.0, 1.0])),
        _FakeChunk(id="c", embedding=json.dumps([1.0, 1.0])),
    ]
    query = np.array([1.0, 0.0])

    ranked = _rank_by_cosine_similarity(query, chunks)
    ids_in_order = [chunk.id for _score, chunk in ranked]

    assert ids_in_order[0] == "a"  # identical direction -> score 1.0
    assert ids_in_order[-1] == "b"  # orthogonal -> score 0.0
    assert ranked[0][0] == 1.0
    assert ranked[-1][0] == 0.0


def test_rank_by_cosine_similarity_skips_chunks_without_embeddings():
    chunks = [
        _FakeChunk(id="a", embedding=json.dumps([1.0, 0.0])),
        _FakeChunk(id="b", embedding=None),
    ]
    ranked = _rank_by_cosine_similarity(np.array([1.0, 0.0]), chunks)
    assert len(ranked) == 1
    assert ranked[0][1].id == "a"
