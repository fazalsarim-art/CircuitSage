"""Embedding generation via OpenAI with batching and transient-failure retry.

The ``Embedder`` protocol lets tests inject a deterministic fake, so automated tests never
touch the network. Live embedding is exercised only via the RUN_LIVE_AI_TESTS smoke test.
"""

import random
import time
from typing import Protocol

from app.core.config import Settings

EMBED_BATCH_SIZE = 96
_MAX_RETRIES = 4
_BASE_DELAY_S = 0.5


class Embedder(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _transient_errors() -> tuple[type[Exception], ...]:
    import openai

    candidates = (
        getattr(openai, "RateLimitError", None),
        getattr(openai, "APITimeoutError", None),
        getattr(openai, "APIConnectionError", None),
        getattr(openai, "InternalServerError", None),
    )
    return tuple(c for c in candidates if isinstance(c, type))


class OpenAIEmbedder:
    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
        self.dimensions = settings.embedding_dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            vectors.extend(self._embed_batch(texts[start : start + EMBED_BATCH_SIZE]))
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        if not batch:
            return []
        transient = _transient_errors()
        attempt = 0
        while True:
            try:
                response = self._client.embeddings.create(model=self.model, input=batch)
                return [item.embedding for item in response.data]
            except transient:
                attempt += 1
                if attempt > _MAX_RETRIES:
                    raise
                delay = _BASE_DELAY_S * (2 ** (attempt - 1)) + random.uniform(0, _BASE_DELAY_S)
                time.sleep(delay)


def build_embedder(settings: Settings) -> Embedder:
    return OpenAIEmbedder(settings)
