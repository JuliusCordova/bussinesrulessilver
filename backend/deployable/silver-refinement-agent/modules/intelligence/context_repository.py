from __future__ import annotations

import os
from typing import Any

from google.cloud import bigquery


class IntelligenceContextRepository:
    def __init__(self, client: bigquery.Client | None = None, project_id: str | None = None, dataset: str | None = None) -> None:
        self.project_id = project_id or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("PROJECT_ID es obligatorio")
        self.dataset = dataset or os.getenv("DATAOPS_DATASET", "dataops_control")
        self.client = client or bigquery.Client(project=self.project_id)
        prefix = f"{self.project_id}.{self.dataset}"
        self.executions_table = f"{prefix}.silver_executions"
        self.artifacts_table = f"{prefix}.silver_artifacts"
        self.reviews_table = f"{prefix}.governance_artifact_reviews"
        self.promotions_table = f"{prefix}.governance_artifact_promotions"
        self.rollbacks_table = f"{prefix}.governance_artifact_rollbacks"

    def fetch_execution(self, execution_id: str) -> dict[str, Any] | None:
        sql = f"SELECT * FROM `{self.executions_table}` WHERE execution_id=@execution_id LIMIT 1"
        config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id)])
        rows = list(self.client.query(sql, job_config=config).result())
        return dict(rows[0].items()) if rows else None

    def fetch_artifacts(self, spec_id: str, package_version: int) -> list[dict[str, Any]]:
        sql = f"""
        SELECT artifact_id, artifact_type, artifact_name, artifact_version, storage_uri,
               content_hash, generation_status, validation_status, generated_at, metadata
        FROM `{self.artifacts_table}`
        WHERE spec_id=@spec_id
          AND (artifact_version=@package_version OR is_current=TRUE)
        ORDER BY artifact_type, artifact_version DESC
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("spec_id", "STRING", spec_id),
            bigquery.ScalarQueryParameter("package_version", "INT64", package_version),
        ])
        return [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]

    def fetch_governance(self, artifact_ids: list[str]) -> dict[str, Any]:
        if not artifact_ids:
            return {"reviews": [], "promotions": [], "rollbacks": []}
        parameter = bigquery.ArrayQueryParameter("artifact_ids", "STRING", artifact_ids)
        config = bigquery.QueryJobConfig(query_parameters=[parameter])
        result: dict[str, Any] = {}
        for key, table, order_column in (
            ("reviews", self.reviews_table, "reviewed_at"),
            ("promotions", self.promotions_table, "promoted_at"),
            ("rollbacks", self.rollbacks_table, "rolled_back_at"),
        ):
            sql = f"SELECT * FROM `{table}` WHERE artifact_id IN UNNEST(@artifact_ids) ORDER BY {order_column} DESC"
            try:
                result[key] = [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]
            except Exception as exc:
                result[key] = []
                result[f"{key}_error"] = str(exc)
        return result
