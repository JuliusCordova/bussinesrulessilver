from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from google.cloud import bigquery


class GovernanceRollbackRepository:
    def __init__(self, client: bigquery.Client | None = None, project_id: str | None = None, dataset: str | None = None) -> None:
        self.project_id = project_id or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("PROJECT_ID es obligatorio")
        self.dataset = dataset or os.getenv("DATAOPS_DATASET", "dataops_control")
        self.client = client or bigquery.Client(project=self.project_id)
        self.artifacts_table = f"{self.project_id}.{self.dataset}.silver_artifacts"
        self.reviews_table = f"{self.project_id}.{self.dataset}.governance_artifact_reviews"
        self.promotions_table = f"{self.project_id}.{self.dataset}.governance_artifact_promotions"
        self.rollbacks_table = f"{self.project_id}.{self.dataset}.governance_artifact_rollbacks"

    def ensure_rollbacks_table(self) -> None:
        table = bigquery.Table(self.rollbacks_table, schema=[
            bigquery.SchemaField("rollback_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("artifact_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("spec_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("artifact_version", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("source_environment", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("target_environment", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("rolled_back_by", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("rolled_back_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("comment", "STRING", mode="REQUIRED"),
        ])
        self.client.create_table(table, exists_ok=True)

    def fetch_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        sql = f"""
        SELECT a.artifact_id, a.spec_id, a.artifact_version, a.artifact_type,
               a.generation_status, r.decision
        FROM `{self.artifacts_table}` a
        LEFT JOIN `{self.reviews_table}` r ON a.artifact_id = r.artifact_id
        WHERE a.artifact_id = @artifact_id
        LIMIT 1
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id)
        ])
        rows = list(self.client.query(sql, job_config=config).result())
        return dict(rows[0].items()) if rows else None

    def fetch_environment_events(self, artifact_id: str) -> list[dict[str, Any]]:
        self.ensure_rollbacks_table()
        sql = f"""
        SELECT target_environment, event_at
        FROM (
          SELECT target_environment, promoted_at AS event_at
          FROM `{self.promotions_table}`
          WHERE artifact_id = @artifact_id
          UNION ALL
          SELECT target_environment, rolled_back_at AS event_at
          FROM `{self.rollbacks_table}`
          WHERE artifact_id = @artifact_id
        )
        ORDER BY event_at ASC
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id)
        ])
        return [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]

    def fetch_history(self, artifact_id: str) -> list[dict[str, Any]]:
        self.ensure_rollbacks_table()
        sql = f"""
        SELECT rollback_id, artifact_id, spec_id, artifact_version,
               source_environment, target_environment, rolled_back_by,
               rolled_back_at, comment
        FROM `{self.rollbacks_table}`
        WHERE artifact_id = @artifact_id
        ORDER BY rolled_back_at ASC
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id)
        ])
        return [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]

    def create_rollback(self, **values: Any) -> bool:
        self.ensure_rollbacks_table()
        sql = f"""
        INSERT INTO `{self.rollbacks_table}`
          (rollback_id, artifact_id, spec_id, artifact_version, source_environment,
           target_environment, rolled_back_by, rolled_back_at, comment)
        VALUES
          (@rollback_id, @artifact_id, @spec_id, @artifact_version, @source_environment,
           @target_environment, @rolled_back_by, @rolled_back_at, @comment)
        """
        params = [
            bigquery.ScalarQueryParameter("rollback_id", "STRING", values["rollback_id"]),
            bigquery.ScalarQueryParameter("artifact_id", "STRING", values["artifact_id"]),
            bigquery.ScalarQueryParameter("spec_id", "STRING", values["spec_id"]),
            bigquery.ScalarQueryParameter("artifact_version", "INT64", values["artifact_version"]),
            bigquery.ScalarQueryParameter("source_environment", "STRING", values["source_environment"]),
            bigquery.ScalarQueryParameter("target_environment", "STRING", values["target_environment"]),
            bigquery.ScalarQueryParameter("rolled_back_by", "STRING", values["rolled_back_by"]),
            bigquery.ScalarQueryParameter("rolled_back_at", "TIMESTAMP", values["rolled_back_at"]),
            bigquery.ScalarQueryParameter("comment", "STRING", values["comment"]),
        ]
        job = self.client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
        job.result()
        return bool(getattr(job, "num_dml_affected_rows", 0))
