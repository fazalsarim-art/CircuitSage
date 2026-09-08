"""Deterministic test doubles (not collected as tests).

FakeEmbedder produces unit vectors from a bag-of-words hashing trick, so lexical overlap
between a query and a chunk yields higher cosine similarity — letting dense retrieval be
tested deterministically offline against the real local Qdrant.
"""

import hashlib
import math
import re

from app.core.config import Settings
from app.services.vector_store import VectorStore, build_vector_store

TEST_COLLECTION = "circuitsage_test"
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class FakeEmbedder:
    def __init__(self, dimensions: int = 1536, model: str = "fake-embedding") -> None:
        self.dimensions = dimensions
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in _TOKEN_RE.findall(text.lower()):
            index = int(hashlib.sha1(token.encode()).hexdigest(), 16) % self.dimensions
            vec[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vec)) or 1.0
        return [value / norm for value in vec]


def make_test_vector_store(settings: Settings) -> VectorStore:
    return build_vector_store(settings, collection=TEST_COLLECTION)


class FakeReranker:
    """Deterministic reranker scoring by query/passage word overlap."""

    def rank(self, query: str, passages: list[str]) -> list[float]:
        query_words = set(_TOKEN_RE.findall(query.lower()))
        scores = []
        for passage in passages:
            passage_words = _TOKEN_RE.findall(passage.lower())
            overlap = sum(1 for word in passage_words if word in query_words)
            scores.append(float(overlap))
        return scores


class FakeAnswerClient:
    """Returns a fixed answer body, or raises to simulate a model outage."""

    def __init__(self, text: str = "The overrun flag clears on read [C1].", *, fail: bool = False):
        self.text = text
        self.fail = fail
        self.calls: list[list[dict]] = []

    def generate(self, messages: list[dict], model: str):
        from app.services.answers import AnswerResult

        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("simulated model outage")
        return AnswerResult(text=self.text, input_tokens=11, output_tokens=7)
