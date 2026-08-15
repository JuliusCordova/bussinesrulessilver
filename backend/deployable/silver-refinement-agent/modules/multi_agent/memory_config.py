from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un entero") from exc


@dataclass(frozen=True)
class MemorySettings:
    repository_provider: str
    embedding_provider: str
    embedding_dimensions: int
    embedding_model: str
    gcp_project_id: str
    gcp_location: str


@lru_cache
def get_memory_settings() -> MemorySettings:
    repository_provider = os.getenv(
        "MEMORY_REPOSITORY_PROVIDER",
        "in_memory",
    ).strip().lower()
    if repository_provider != "in_memory":
        raise ValueError(
            "MEMORY_REPOSITORY_PROVIDER debe ser in_memory; "
            "AlloyDB fue retirado del runtime"
        )

    embedding_provider = os.getenv(
        "MEMORY_EMBEDDING_PROVIDER",
        "local",
    ).strip().lower()
    if embedding_provider not in {"local", "vertex"}:
        raise ValueError(
            "MEMORY_EMBEDDING_PROVIDER debe ser local o vertex"
        )

    dimensions = _as_int("MEMORY_EMBEDDING_DIMENSIONS", 768)
    if dimensions < 128 or dimensions > 3072:
        raise ValueError(
            "MEMORY_EMBEDDING_DIMENSIONS debe estar entre 128 y 3072"
        )

    return MemorySettings(
        repository_provider=repository_provider,
        embedding_provider=embedding_provider,
        embedding_dimensions=dimensions,
        embedding_model=os.getenv(
            "MEMORY_EMBEDDING_MODEL",
            "gemini-embedding-001",
        ),
        gcp_project_id=os.getenv(
            "PROJECT_ID",
            os.getenv("GOOGLE_CLOUD_PROJECT", "proyectopersonal-480420"),
        ),
        gcp_location=os.getenv(
            "MEMORY_EMBEDDING_LOCATION",
            os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        ),
    )
