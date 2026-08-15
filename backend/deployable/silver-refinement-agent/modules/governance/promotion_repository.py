from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from google.cloud import bigquery


class GovernancePromotionRepository:
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
        self.promotions_table = f"{self.project_id}.{self.dataset}.governance_artifact_promotions"

    def ensure_promotions_table(self) -> None:
        table = bigquery.Table(
            self.promotions_table,
            schema=[
                bigquery.SchemaField("promotion_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("artifact_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("spec_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("artifact_version", "INT64", mode="REQUIRED"),
                bigquery.SchemaField("source_environment", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("target_environment", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("promoted_by", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("promoted_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("comment", "STRING", mode="NULLABLE"),
            ],
        )
        self.client.create_table(table, exists_ok=True)

    def fetch_approved_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        sql = f"""
        SELECT
          a.artifact_id,
          a.spec_id,
          a.artifact_version,
          a.artifact_type,
          a.generation_status,
          a.is_current,
          r.decision
        FROM `{self.artifacts_table}` a
        LEFT JOIN `{self.reviews_table}` r
          ON a.artifact_id = r.artifact_id
        WHERE a.artifact_id = @artifact_id
        LIMIT 1
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id)
            ]
        )
        rows = list(self.client.query(sql, job_config=config).result())
        return dict(rows[0].items()) if rows else None

    def fetch_history(self, artifact_id: str) -> list[dict[str, Any]]:
        self.ensure_promotions_table()
        sql = f"""
        SELECT
          promotion_id,
          artifact_id,
          spec_id,
          artifact_version,
          source_environment,
          target_environment,
          promoted_by,
          promoted_at,
          comment
        FROM `{self.promotions_table}`
        WHERE artifact_id = @artifact_id
        ORDER BY promoted_at ASC
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id)
            ]
        )
        return [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]

    def create_promotion(
        self,
        *,
        promotion_id: str,
        artifact_id: str,
        spec_id: str,
        artifact_version: int,
        source_environment: str,
        target_environment: str,
        promoted_by: str,
        promoted_at: datetime,
        comment: str | None,
    ) -> bool:
        self.ensure_promotions_table()
        sql = f"""
        MERGE `{self.promotions_table}` AS target
        USING (
          SELECT
            @promotion_id AS promotion_id,
            @artifact_id AS artifact_id,
            @spec_id AS spec_id,
            @artifact_version AS artifact_version,
            @source_environment AS source_environment,
            @target_environment AS target_environment,
            @promoted_by AS promoted_by,
            @promoted_at AS promoted_at,
            @comment AS comment
        ) AS source
        ON target.artifact_id = source.artifact_id
           AND target.target_environment = source.target_environment
        WHEN NOT MATCHED THEN
          INSERT (
            promotion_id,
            artifact_id,
            spec_id,
            artifact_version,
            source_environment,
            target_environment,
            promoted_by,
            promoted_at,
            comment
          )
          VALUES (
            source.promotion_id,
            source.artifact_id,
            source.spec_id,
            source.artifact_version,
            source.source_environment,
            source.target_environment,
            source.promoted_by,
            source.promoted_at,
            source.comment
          )
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("promotion_id", "STRING", promotion_id),
                bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id),
                bigquery.ScalarQueryParameter("spec_id", "STRING", spec_id),
                bigquery.ScalarQueryParameter("artifact_version", "INT64", artifact_version),
                bigquery.ScalarQueryParameter("source_environment", "STRING", source_environment),
                bigquery.ScalarQueryParameter("target_environment", "STRING", target_environment),
                bigquery.ScalarQueryParameter("promoted_by", "STRING", promoted_by),
                bigquery.ScalarQueryParameter("promoted_at", "TIMESTAMP", promoted_at),
                bigquery.ScalarQueryParameter("comment", "STRING", comment),
            ]
        )
        job = self.client.query(sql, job_config=config)
        job.result()
        return bool(getattr(job, "num_dml_affected_rows", 0))
