"""Unit tests for the embedder: FakeEmbedder semantics and OpenAIEmbedder batching/retry."""

import types

import pytest

from app.services.embeddings import OpenAIEmbedder
from tests._fakes import FakeEmbedder


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_embedder_dimensions_and_determinism():
    embedder = FakeEmbedder(dimensions=128)
    first = embedder.embed(["SPI clock polarity"])[0]
    second = embedder.embed(["SPI clock polarity"])[0]
    assert len(first) == 128
    assert first == second


def test_fake_embedder_overlap_scores_higher():
    embedder = FakeEmbedder(dimensions=256)
    doc = embedder.embed(["spi clock polarity register mode"])[0]
    related = embedder.embed(["spi clock register"])[0]
    unrelated = embedder.embed(["totally different unrelated words"])[0]
    assert _dot(doc, related) > _dot(doc, unrelated)


class _Resp:
    def __init__(self, vectors):
        self.data = [types.SimpleNamespace(embedding=v) for v in vectors]


class _StubEmbeddings:
    def __init__(self, behavior):
        self._behavior = behavior
        self.calls: list[list[str]] = []

    def create(self, *, model, input):
        self.calls.append(list(input))
        return self._behavior(input)


class _StubClient:
    def __init__(self, behavior):
        self.embeddings = _StubEmbeddings(behavior)


def _make_embedder(behavior) -> OpenAIEmbedder:
    embedder = OpenAIEmbedder.__new__(OpenAIEmbedder)
    embedder.model = "test-model"
    embedder.dimensions = 3
    embedder._client = _StubClient(behavior)
    return embedder


def test_openai_embedder_batches(monkeypatch):
    from app.services import embeddings as emb_mod

    monkeypatch.setattr(emb_mod, "EMBED_BATCH_SIZE", 2)
    embedder = _make_embedder(lambda inp: _Resp([[0.0, 0.0, 0.0] for _ in inp]))
    vectors = embedder.embed(["a", "b", "c", "d", "e"])
    assert len(vectors) == 5
    assert len(embedder._client.embeddings.calls) == 3  # 2 + 2 + 1


def test_openai_embedder_retries_transient_then_succeeds(monkeypatch):
    from app.services import embeddings as emb_mod

    class Transient(Exception):
        pass

    monkeypatch.setattr(emb_mod, "_transient_errors", lambda: (Transient,))
    monkeypatch.setattr(emb_mod.time, "sleep", lambda _seconds: None)

    state = {"n": 0}

    def behavior(inp):
        state["n"] += 1
        if state["n"] < 3:
            raise Transient()
        return _Resp([[0.1, 0.2, 0.3] for _ in inp])

    embedder = _make_embedder(behavior)
    vectors = embedder.embed(["x"])
    assert len(vectors) == 1
    assert state["n"] == 3


def test_openai_embedder_gives_up_after_max_retries(monkeypatch):
    from app.services import embeddings as emb_mod

    class Transient(Exception):
        pass

    monkeypatch.setattr(emb_mod, "_transient_errors", lambda: (Transient,))
    monkeypatch.setattr(emb_mod.time, "sleep", lambda _seconds: None)

    def behavior(_inp):
        raise Transient()

    embedder = _make_embedder(behavior)
    with pytest.raises(Transient):
        embedder.embed(["x"])
