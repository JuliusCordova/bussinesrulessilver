from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


SUPPORTED_WORKFLOW_REPOSITORIES = {"in_memory", "gcs"}


def _normalize_prefix(value: str) -> str:
    return value.strip().strip("/")


@dataclass(frozen=True)
class WorkflowSettings:
    repository_provider: str
    gcs_bucket: str | None
    gcs_prefix: str

    @property
    def gcs_enabled(self) -> bool:
        return self.repository_provider == "gcs"


@lru_cache
def get_workflow_settings() -> WorkflowSettings:
    repository_provider = os.getenv(
        "WORKFLOW_REPOSITORY_PROVIDER",
        os.getenv("MEMORY_REPOSITORY_PROVIDER", "in_memory"),
    ).strip().lower()
    if repository_provider not in SUPPORTED_WORKFLOW_REPOSITORIES:
        supported = ", ".join(sorted(SUPPORTED_WORKFLOW_REPOSITORIES))
        raise ValueError(
            f"WORKFLOW_REPOSITORY_PROVIDER debe ser uno de: {supported}; "
            "AlloyDB fue retirado del runtime"
        )

    gcs_bucket_raw = os.getenv("WORKFLOW_GCS_BUCKET")
    gcs_bucket = gcs_bucket_raw.strip() if gcs_bucket_raw else None
    if repository_provider == "gcs" and not gcs_bucket:
        raise ValueError(
            "WORKFLOW_GCS_BUCKET es obligatorio cuando "
            "WORKFLOW_REPOSITORY_PROVIDER=gcs"
        )
    gcs_prefix = _normalize_prefix(
        os.getenv("WORKFLOW_GCS_PREFIX", "silver-workflows")
    )
    if repository_provider == "gcs" and not gcs_prefix:
        raise ValueError("WORKFLOW_GCS_PREFIX no puede estar vacío")

    return WorkflowSettings(
        repository_provider=repository_provider,
        gcs_bucket=gcs_bucket,
        gcs_prefix=gcs_prefix,
    )
