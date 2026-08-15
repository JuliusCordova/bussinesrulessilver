from __future__ import annotations

from functools import lru_cache

from .config import get_workflow_settings
from .repository import InMemoryWorkflowRepository, WorkflowRepository


@lru_cache
def get_workflow_repository() -> WorkflowRepository:
    settings = get_workflow_settings()
    if settings.repository_provider == "gcs":
        from .gcs_repository import CloudStorageWorkflowRepository

        return CloudStorageWorkflowRepository(settings=settings)
    if settings.repository_provider == "in_memory":
        return InMemoryWorkflowRepository()
    raise ValueError(
        f"Proveedor de workflow no soportado: {settings.repository_provider}"
    )


def reset_workflow_dependencies() -> None:
    get_workflow_repository.cache_clear()
    get_workflow_settings.cache_clear()
