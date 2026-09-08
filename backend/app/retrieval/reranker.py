"""Cross-encoder reranking.

The ``Reranker`` protocol lets tests inject a deterministic fake. The real
``CrossEncoderReranker`` lazily loads ``sentence-transformers`` (installed via the optional
``rerank`` extra) and caches one model instance per process.
"""

from typing import Protocol

from app.core.config import Settings


class Reranker(Protocol):
    def rank(self, query: str, passages: list[str]) -> list[float]:
        """Return one relevance score per passage (higher is better)."""
        ...


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
        return self._model

    def rank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        model = self._ensure_model()
        scores = model.predict([(query, passage) for passage in passages])
        return [float(score) for score in scores]


_cached: CrossEncoderReranker | None = None


def build_reranker(settings: Settings) -> CrossEncoderReranker:
    global _cached
    if _cached is None or _cached.model_name != settings.reranker_model:
        _cached = CrossEncoderReranker(settings.reranker_model)
    return _cached
