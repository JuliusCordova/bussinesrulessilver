from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from google.cloud import bigquery


class GovernanceRepository:
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
        self.artifacts_table = f"{self.project_id}.{self.dataset}.silver_artifacts"
        self.reviews_table = f"{self.project_id}.{self.dataset}.governance_artifact_reviews"

    def ensure_reviews_table(self) -> None:
        table = bigquery.Table(
            self.reviews_table,
            schema=[
                bigquery.SchemaField("artifact_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("decision", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("reviewed_by", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("reviewed_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("comment", "STRING", mode="NULLABLE"),
            ],
        )
        self.client.create_table(table, exists_ok=True)

    def fetch_pending(self, *, limit: int) -> tuple[list[dict[str, Any]], int]:
        self.ensure_reviews_table()
        sql = f"""
        SELECT
          a.artifact_id,
          a.spec_id,
          a.mapping_version,
          a.artifact_type,
          a.artifact_version,
          a.storage_uri,
          a.content_hash,
          a.generation_status,
          a.validation_status,
          a.generated_by,
          a.generated_at,
          a.is_current,
          r.decision,
          r.reviewed_by,
          r.reviewed_at,
          r.comment,
          COUNT(*) OVER() AS total_count
        FROM `{self.artifacts_table}` a
        LEFT JOIN `{self.reviews_table}` r
          ON a.artifact_id = r.artifact_id
        WHERE a.artifact_type = 'ARTIFACT_PACKAGE'
          AND a.is_current = TRUE
          AND a.generation_status = 'GENERATED'
          AND r.artifact_id IS NULL
        ORDER BY a.generated_at DESC
        LIMIT @limit
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        )
        rows = [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]
        total = int(rows[0]["total_count"]) if rows else 0
        for row in rows:
            row.pop("total_count", None)
        return rows, total

    def fetch_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        sql = f"""
        SELECT
          artifact_id,
          spec_id,
          mapping_version,
          artifact_type,
          artifact_version,
          storage_uri,
          content_hash,
          generation_status,
          validation_status,
          generated_by,
          generated_at,
          is_current
        FROM `{self.artifacts_table}`
        WHERE artifact_id = @artifact_id
        LIMIT 1
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id)
            ]
        )
        rows = list(self.client.query(sql, job_config=config).result())
        return dict(rows[0].items()) if rows else None

    def fetch_decision(self, artifact_id: str) -> dict[str, Any] | None:
        self.ensure_reviews_table()
        sql = f"""
        SELECT artifact_id, decision, reviewed_by, reviewed_at, comment
        FROM `{self.reviews_table}`
        WHERE artifact_id = @artifact_id
        LIMIT 1
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id)
            ]
        )
        rows = list(self.client.query(sql, job_config=config).result())
        return dict(rows[0].items()) if rows else None

    def create_decision(
        self,
        *,
        artifact_id: str,
        decision: str,
        reviewed_by: str,
        reviewed_at: datetime,
        comment: str | None,
    ) -> bool:
        self.ensure_reviews_table()
        sql = f"""
        MERGE `{self.reviews_table}` AS target
        USING (
          SELECT
            @artifact_id AS artifact_id,
            @decision AS decision,
            @reviewed_by AS reviewed_by,
            @reviewed_at AS reviewed_at,
            @comment AS comment
        ) AS source
        ON target.artifact_id = source.artifact_id
        WHEN NOT MATCHED THEN
          INSERT (artifact_id, decision, reviewed_by, reviewed_at, comment)
          VALUES (
            source.artifact_id,
            source.decision,
            source.reviewed_by,
            source.reviewed_at,
            source.comment
          )
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id),
                bigquery.ScalarQueryParameter("decision", "STRING", decision),
                bigquery.ScalarQueryParameter("reviewed_by", "STRING", reviewed_by),
                bigquery.ScalarQueryParameter("reviewed_at", "TIMESTAMP", reviewed_at),
                bigquery.ScalarQueryParameter("comment", "STRING", comment),
            ]
        )
        job = self.client.query(sql, job_config=config)
        job.result()
        return bool(getattr(job, "num_dml_affected_rows", 0))
