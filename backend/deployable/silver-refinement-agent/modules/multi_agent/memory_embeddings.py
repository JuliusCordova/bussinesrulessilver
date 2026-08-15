from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from functools import lru_cache

from .memory_config import MemorySettings, get_memory_settings


class MemoryEmbeddingProvider(ABC):
    @abstractmethod
    def embed_document(self, text: str) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class DeterministicLocalEmbeddingProvider(MemoryEmbeddingProvider):
    """Deterministic embeddings for tests and local development only."""

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class VertexMemoryEmbeddingProvider(MemoryEmbeddingProvider):
    def __init__(self, settings: MemorySettings) -> None:
        from google import genai

        self.settings = settings
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )

    def _embed(self, text: str, task_type: str) -> list[float]:
        from google.genai import types

        response = self.client.models.embed_content(
            model=self.settings.embedding_model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.settings.embedding_dimensions,
            ),
        )
        if not response.embeddings or not response.embeddings[0].values:
            raise RuntimeError("Vertex AI devolvió un embedding vacío")

        values = list(response.embeddings[0].values)
        if len(values) != self.settings.embedding_dimensions:
            raise RuntimeError(
                "Dimensión de embedding inválida: "
                f"esperada={self.settings.embedding_dimensions}, "
                f"recibida={len(values)}"
            )
        return values

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, "RETRIEVAL_QUERY")


@lru_cache
def get_memory_embedding_provider() -> MemoryEmbeddingProvider:
    settings = get_memory_settings()
    if settings.embedding_provider == "vertex":
        return VertexMemoryEmbeddingProvider(settings)
    return DeterministicLocalEmbeddingProvider(
        settings.embedding_dimensions
    )
