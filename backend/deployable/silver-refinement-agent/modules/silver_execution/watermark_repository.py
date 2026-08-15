from __future__ import annotations

import json
import os
from datetime import datetime

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage
from pydantic import BaseModel, Field


class WatermarkCheckpoint(BaseModel):
    spec_id: str = Field(min_length=1)
    watermark_column: str = Field(min_length=1)
    current_watermark: datetime
    last_successful_execution_id: str = Field(min_length=1)
    updated_at: datetime
    version: int = Field(ge=1)


class WatermarkVersionConflictError(RuntimeError):
    pass


class WatermarkRepository:
    root_prefix = "silver-refinement/specs"

    def __init__(
        self,
        client: storage.Client | None = None,
        bucket_name: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name or os.getenv("ARTIFACT_BUCKET")
        if not self.bucket_name:
            raise ValueError("ARTIFACT_BUCKET es obligatorio")

        self.client = client or storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)

    def get(self, spec_id: str) -> WatermarkCheckpoint | None:
        blob = self.bucket.blob(self._path(spec_id))
        try:
            return WatermarkCheckpoint.model_validate_json(
                blob.download_as_text()
            )
        except NotFound:
            return None

    def save(
        self,
        checkpoint: WatermarkCheckpoint,
        *,
        expected_version: int | None,
    ) -> WatermarkCheckpoint:
        blob = self.bucket.blob(self._path(checkpoint.spec_id))
        payload = json.dumps(
            checkpoint.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )

        if expected_version is None:
            if checkpoint.version != 1:
                raise ValueError(
                    "El primer checkpoint debe tener version=1"
                )
            try:
                blob.upload_from_string(
                    payload,
                    content_type="application/json",
                    if_generation_match=0,
                )
            except PreconditionFailed as exc:
                raise WatermarkVersionConflictError(
                    "El checkpoint ya existe"
                ) from exc
            return checkpoint

        try:
            blob.reload()
            generation = int(blob.generation)
            current = WatermarkCheckpoint.model_validate_json(
                blob.download_as_text()
            )
        except NotFound as exc:
            raise WatermarkVersionConflictError(
                "El checkpoint esperado no existe"
            ) from exc

        if current.version != expected_version:
            raise WatermarkVersionConflictError(
                "La versión del watermark cambió"
            )

        if checkpoint.version != expected_version + 1:
            raise ValueError(
                "La nueva versión debe ser expected_version + 1"
            )

        try:
            blob.upload_from_string(
                payload,
                content_type="application/json",
                if_generation_match=generation,
            )
        except PreconditionFailed as exc:
            raise WatermarkVersionConflictError(
                "El watermark fue actualizado concurrentemente"
            ) from exc

        return checkpoint

    def _path(self, spec_id: str) -> str:
        return f"{self.root_prefix}/{spec_id}/state/watermark.json"
