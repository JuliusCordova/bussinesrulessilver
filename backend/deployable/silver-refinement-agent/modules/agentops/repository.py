from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from google.cloud import bigquery


class AgentOpsRepository:
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
        self.executions_table = f"{self.project_id}.{self.dataset}.silver_executions"
        self.artifacts_table = f"{self.project_id}.{self.dataset}.silver_artifacts"

    def fetch_dashboard(self) -> dict[str, Any]:
        sql = f"""
        WITH execution_metrics AS (
          SELECT
            COUNT(*) AS total_executions,
            COUNT(DISTINCT spec_id) AS execution_specs,
            COUNTIF(status = 'PENDING') AS pending,
            COUNTIF(status = 'VALIDATED') AS validated,
            COUNTIF(status = 'QUEUED') AS queued,
            COUNTIF(status = 'RUNNING') AS running,
            COUNTIF(status = 'SUCCEEDED') AS succeeded,
            COUNTIF(status = 'FAILED') AS failed,
            COUNTIF(status = 'CANCELLED') AS cancelled,
            MAX(created_at) AS last_execution_at,
            COUNTIF(DATE(created_at) = CURRENT_DATE('UTC')) AS executions_today,
            COALESCE(SUM(IF(DATE(created_at) = CURRENT_DATE('UTC'), rows_read, 0)), 0) AS rows_read_today,
            COALESCE(SUM(IF(DATE(created_at) = CURRENT_DATE('UTC'), rows_written, 0)), 0) AS rows_written_today,
            COALESCE(AVG(IF(
              DATE(created_at) = CURRENT_DATE('UTC')
              AND started_at IS NOT NULL
              AND finished_at IS NOT NULL,
              TIMESTAMP_DIFF(finished_at, started_at, SECOND),
              NULL
            )), 0) AS avg_runtime_seconds
          FROM `{self.executions_table}`
        ),
        artifact_metrics AS (
          SELECT
            COUNT(*) AS total_artifacts,
            COUNT(DISTINCT spec_id) AS artifact_specs,
            COUNTIF(artifact_type = 'ARTIFACT_PACKAGE' AND is_current) AS current_packages,
            COALESCE(MAX(IF(artifact_type = 'ARTIFACT_PACKAGE', artifact_version, NULL)), 0) AS latest_package_version
          FROM `{self.artifacts_table}`
        )
        SELECT
          GREATEST(e.execution_specs, a.artifact_specs) AS total_specs,
          e.total_executions,
          e.pending,
          e.validated,
          e.queued,
          e.running,
          e.succeeded,
          e.failed,
          e.cancelled,
          e.last_execution_at,
          e.executions_today,
          e.rows_read_today,
          e.rows_written_today,
          e.avg_runtime_seconds,
          a.total_artifacts,
          a.current_packages,
          a.latest_package_version
        FROM execution_metrics e
        CROSS JOIN artifact_metrics a
        """
        rows = list(self.client.query(sql).result())
        if not rows:
            raise RuntimeError("No fue posible obtener métricas AgentOps")
        return dict(rows[0].items())

    def fetch_executions(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        spec_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = []
        parameters: list[bigquery.ScalarQueryParameter] = [
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("offset", "INT64", offset),
        ]
        if status:
            filters.append("status = @status")
            parameters.append(bigquery.ScalarQueryParameter("status", "STRING", status))
        if spec_id:
            filters.append("spec_id = @spec_id")
            parameters.append(bigquery.ScalarQueryParameter("spec_id", "STRING", spec_id))
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        sql = f"""
        SELECT
          execution_id,
          spec_id,
          package_version,
          status,
          requested_by,
          created_at,
          started_at,
          finished_at,
          IF(started_at IS NOT NULL AND finished_at IS NOT NULL,
             TIMESTAMP_DIFF(finished_at, started_at, SECOND), NULL) AS duration_seconds,
          dataproc_batch_id,
          rows_read,
          rows_written,
          logs_uri,
          error_message,
          COUNT(*) OVER() AS total_count
        FROM `{self.executions_table}`
        {where_clause}
        ORDER BY created_at DESC
        LIMIT @limit OFFSET @offset
        """
        config = bigquery.QueryJobConfig(query_parameters=parameters)
        rows = [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]
        total = int(rows[0]["total_count"]) if rows else 0
        for row in rows:
            row.pop("total_count", None)
        return rows, total

    def fetch_execution_log_reference(self, execution_id: str) -> dict[str, Any] | None:
        sql = f"""
        SELECT
          execution_id,
          spec_id,
          status,
          dataproc_batch_id,
          logs_uri,
          load_strategy,
          watermark_column
        FROM `{self.executions_table}`
        WHERE execution_id = @execution_id
        LIMIT 1
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id)
            ]
        )
        rows = list(self.client.query(sql, job_config=config).result())
        return dict(rows[0].items()) if rows else None

    def update_execution_metrics(
        self,
        execution_id: str,
        *,
        rows_read: int,
        rows_written: int,
        started_at: datetime | None,
        finished_at: datetime | None,
        next_watermark: datetime | None,
    ) -> bool:
        sql = f"""
        UPDATE `{self.executions_table}`
        SET
          rows_read = @rows_read,
          rows_written = @rows_written,
          started_at = COALESCE(@started_at, started_at),
          finished_at = COALESCE(@finished_at, finished_at),
          next_watermark = COALESCE(@next_watermark, next_watermark)
        WHERE execution_id = @execution_id
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id),
                bigquery.ScalarQueryParameter("rows_read", "INT64", rows_read),
                bigquery.ScalarQueryParameter("rows_written", "INT64", rows_written),
                bigquery.ScalarQueryParameter("started_at", "TIMESTAMP", started_at),
                bigquery.ScalarQueryParameter("finished_at", "TIMESTAMP", finished_at),
                bigquery.ScalarQueryParameter(
                    "next_watermark",
                    "TIMESTAMP",
                    next_watermark,
                ),
            ]
        )
        job = self.client.query(sql, job_config=config)
        job.result()
        return bool(getattr(job, "num_dml_affected_rows", 0))
