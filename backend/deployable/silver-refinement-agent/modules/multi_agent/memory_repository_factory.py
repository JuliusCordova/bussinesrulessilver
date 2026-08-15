from __future__ import annotations

from functools import lru_cache

from .memory_config import get_memory_settings
from .memory_embeddings import get_memory_embedding_provider
from .memory_repository import MemoryRepository, SharedMemoryRepository


@lru_cache
def get_memory_repository() -> MemoryRepository:
    settings = get_memory_settings()
    if settings.repository_provider != "in_memory":
        raise ValueError(
            "Solo se admite MEMORY_REPOSITORY_PROVIDER=in_memory"
        )
    return SharedMemoryRepository()


def reset_memory_dependencies() -> None:
    """Clear cached configuration/providers for tests and controlled restarts."""

    get_memory_repository.cache_clear()
    get_memory_embedding_provider.cache_clear()
    get_memory_settings.cache_clear()
