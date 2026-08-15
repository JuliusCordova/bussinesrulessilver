from __future__ import annotations

import json
import os
from typing import Any

from google.cloud import bigquery

from .artifact_models import ArtifactRecord, ArtifactStatus, ArtifactType


class ArtifactRepository:
    def __init__(
        self,
        client: bigquery.Client | None = None,
        project_id: str | None = None,
        dataset: str | None = None,
    ) -> None:
        self.project_id = project_id or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("PROJECT_ID es obligatorio")
        self.dataset = dataset or os.getenv("DATAOPS_DATASET", "dataops_control")
        self.client = client or bigquery.Client(project=self.project_id)
        self.table_id = f"{self.project_id}.{self.dataset}.silver_artifacts"

    def next_version(self, spec_id: str, artifact_type: ArtifactType) -> int:
        sql = f"""
        SELECT COALESCE(MAX(artifact_version), 0) + 1 AS next_version
        FROM `{self.table_id}`
        WHERE spec_id = @spec_id
          AND artifact_type = @artifact_type
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("spec_id", "STRING", spec_id),
            bigquery.ScalarQueryParameter("artifact_type", "STRING", artifact_type.value),
        ])
        row = next(iter(self.client.query(sql, job_config=config).result()))
        return int(row.next_version)

    def save_as_current(self, record: ArtifactRecord) -> ArtifactRecord:
        sql = f"""
        BEGIN TRANSACTION;

        UPDATE `{self.table_id}`
        SET is_current = FALSE,
            generation_status = IF(generation_status = 'FAILED', generation_status, 'SUPERSEDED')
        WHERE spec_id = @spec_id
          AND artifact_type = @artifact_type
          AND is_current = TRUE;

        INSERT INTO `{self.table_id}` (
          artifact_id, spec_id, mapping_version, artifact_type, artifact_name,
          artifact_version, generation_status, validation_status, content_text,
          storage_uri, content_hash, template_name, template_version, generated_by,
          generated_at, approved_by, approved_at, is_current, metadata
        ) VALUES (
          @artifact_id, @spec_id, @mapping_version, @artifact_type, @artifact_name,
          @artifact_version, @generation_status, @validation_status, @content_text,
          @storage_uri, @content_hash, @template_name, @template_version, @generated_by,
          @generated_at, @approved_by, @approved_at, TRUE, PARSE_JSON(@metadata_json)
        );

        COMMIT TRANSACTION;
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("artifact_id", "STRING", record.artifact_id),
            bigquery.ScalarQueryParameter("spec_id", "STRING", record.spec_id),
            bigquery.ScalarQueryParameter("mapping_version", "INT64", record.mapping_version),
            bigquery.ScalarQueryParameter("artifact_type", "STRING", record.artifact_type.value),
            bigquery.ScalarQueryParameter("artifact_name", "STRING", record.artifact_name),
            bigquery.ScalarQueryParameter("artifact_version", "INT64", record.artifact_version),
            bigquery.ScalarQueryParameter("generation_status", "STRING", record.generation_status.value),
            bigquery.ScalarQueryParameter("validation_status", "STRING", record.validation_status),
            bigquery.ScalarQueryParameter("content_text", "STRING", record.content_text),
            bigquery.ScalarQueryParameter("storage_uri", "STRING", record.storage_uri),
            bigquery.ScalarQueryParameter("content_hash", "STRING", record.content_hash),
            bigquery.ScalarQueryParameter("template_name", "STRING", record.template_name),
            bigquery.ScalarQueryParameter("template_version", "STRING", record.template_version),
            bigquery.ScalarQueryParameter("generated_by", "STRING", record.generated_by),
            bigquery.ScalarQueryParameter("generated_at", "TIMESTAMP", record.generated_at),
            bigquery.ScalarQueryParameter("approved_by", "STRING", record.approved_by),
            bigquery.ScalarQueryParameter("approved_at", "TIMESTAMP", record.approved_at),
            bigquery.ScalarQueryParameter("metadata_json", "STRING", json.dumps(record.metadata)),
        ])
        self.client.query(sql, job_config=config).result()
        return record

    def get_current(self, spec_id: str, artifact_type: ArtifactType) -> ArtifactRecord | None:
        sql = f"""
        SELECT *
        FROM `{self.table_id}`
        WHERE spec_id = @spec_id
          AND artifact_type = @artifact_type
          AND is_current = TRUE
        ORDER BY artifact_version DESC
        LIMIT 1
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("spec_id", "STRING", spec_id),
            bigquery.ScalarQueryParameter("artifact_type", "STRING", artifact_type.value),
        ])
        rows = list(self.client.query(sql, job_config=config).result())
        return self._to_record(rows[0]) if rows else None

    def list_for_spec(self, spec_id: str) -> list[ArtifactRecord]:
        sql = f"""
        SELECT *
        FROM `{self.table_id}`
        WHERE spec_id = @spec_id
        ORDER BY artifact_type, artifact_version DESC
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("spec_id", "STRING", spec_id),
        ])
        return [self._to_record(row) for row in self.client.query(sql, job_config=config).result()]

    @staticmethod
    def _to_record(row: Any) -> ArtifactRecord:
        data = dict(row.items())
        metadata = data.get("metadata")
        if isinstance(metadata, str):
            data["metadata"] = json.loads(metadata)
        elif metadata is None:
            data["metadata"] = {}
        return ArtifactRecord.model_validate(data)
