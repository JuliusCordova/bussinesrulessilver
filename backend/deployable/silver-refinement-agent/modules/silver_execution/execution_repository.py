from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from google.cloud import bigquery

from .execution_models import ExecutionRecord, ExecutionStatus


class ExecutionRepository:
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
        self.table_id = f"{self.project_id}.{self.dataset}.silver_executions"

    def create(self, record: ExecutionRecord) -> ExecutionRecord:
        sql = f"""
        INSERT INTO `{self.table_id}` (
          execution_id, spec_id, mapping_version, package_version,
          artifact_package_uri, load_strategy, watermark_column,
          runtime_watermark, next_watermark, lookback_value, lookback_unit,
          status, created_at, started_at, finished_at,
          dataproc_batch_id, rows_read, rows_written, error_message, logs_uri,
          requested_by
        ) VALUES (
          @execution_id, @spec_id, @mapping_version, @package_version,
          @artifact_package_uri, @load_strategy, @watermark_column,
          @runtime_watermark, @next_watermark, @lookback_value, @lookback_unit,
          @status, @created_at, @started_at, @finished_at,
          @dataproc_batch_id, @rows_read, @rows_written, @error_message, @logs_uri,
          @requested_by
        )
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("execution_id", "STRING", record.execution_id),
            bigquery.ScalarQueryParameter("spec_id", "STRING", record.spec_id),
            bigquery.ScalarQueryParameter("mapping_version", "INT64", record.mapping_version),
            bigquery.ScalarQueryParameter("package_version", "INT64", record.package_version),
            bigquery.ScalarQueryParameter("artifact_package_uri", "STRING", record.artifact_package_uri),
            bigquery.ScalarQueryParameter("load_strategy", "STRING", record.load_strategy),
            bigquery.ScalarQueryParameter("watermark_column", "STRING", record.watermark_column),
            bigquery.ScalarQueryParameter("runtime_watermark", "TIMESTAMP", record.runtime_watermark),
            bigquery.ScalarQueryParameter("next_watermark", "TIMESTAMP", record.next_watermark),
            bigquery.ScalarQueryParameter("lookback_value", "INT64", record.lookback_value),
            bigquery.ScalarQueryParameter("lookback_unit", "STRING", record.lookback_unit),
            bigquery.ScalarQueryParameter("status", "STRING", record.status.value),
            bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", record.created_at),
            bigquery.ScalarQueryParameter("started_at", "TIMESTAMP", record.started_at),
            bigquery.ScalarQueryParameter("finished_at", "TIMESTAMP", record.finished_at),
            bigquery.ScalarQueryParameter("dataproc_batch_id", "STRING", record.dataproc_batch_id),
            bigquery.ScalarQueryParameter("rows_read", "INT64", record.rows_read),
            bigquery.ScalarQueryParameter("rows_written", "INT64", record.rows_written),
            bigquery.ScalarQueryParameter("error_message", "STRING", record.error_message),
            bigquery.ScalarQueryParameter("logs_uri", "STRING", record.logs_uri),
            bigquery.ScalarQueryParameter("requested_by", "STRING", record.requested_by),
        ])
        self.client.query(sql, job_config=config).result()
        return record

    def update_status(
        self,
        execution_id: str,
        status: ExecutionStatus,
        error_message: str | None = None,
    ) -> ExecutionRecord:
        sql = f"""
        UPDATE `{self.table_id}`
        SET status = @status,
            error_message = @error_message
        WHERE execution_id = @execution_id
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("status", "STRING", status.value),
            bigquery.ScalarQueryParameter("error_message", "STRING", error_message),
            bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id),
        ])
        self.client.query(sql, job_config=config).result()
        return self._require(execution_id)

    def mark_queued(self, execution_id: str, dataproc_batch_id: str) -> ExecutionRecord:
        sql = f"""
        UPDATE `{self.table_id}`
        SET status = 'QUEUED',
            dataproc_batch_id = @dataproc_batch_id,
            error_message = NULL
        WHERE execution_id = @execution_id
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("dataproc_batch_id", "STRING", dataproc_batch_id),
            bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id),
        ])
        self.client.query(sql, job_config=config).result()
        return self._require(execution_id)

    def update_monitoring(
        self,
        execution_id: str,
        *,
        status: ExecutionStatus,
        state_time: datetime | None,
        logs_uri: str | None,
        error_message: str | None,
    ) -> ExecutionRecord:
        terminal = status in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        }
        running = status == ExecutionStatus.RUNNING
        sql = f"""
        UPDATE `{self.table_id}`
        SET status = @status,
            started_at = CASE
              WHEN @is_running AND started_at IS NULL THEN COALESCE(@state_time, CURRENT_TIMESTAMP())
              ELSE started_at
            END,
            finished_at = CASE
              WHEN @is_terminal THEN COALESCE(@state_time, CURRENT_TIMESTAMP())
              ELSE finished_at
            END,
            logs_uri = COALESCE(@logs_uri, logs_uri),
            error_message = @error_message
        WHERE execution_id = @execution_id
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("status", "STRING", status.value),
            bigquery.ScalarQueryParameter("is_running", "BOOL", running),
            bigquery.ScalarQueryParameter("is_terminal", "BOOL", terminal),
            bigquery.ScalarQueryParameter("state_time", "TIMESTAMP", state_time),
            bigquery.ScalarQueryParameter("logs_uri", "STRING", logs_uri),
            bigquery.ScalarQueryParameter("error_message", "STRING", error_message),
            bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id),
        ])
        self.client.query(sql, job_config=config).result()
        return self._require(execution_id)

    def _require(self, execution_id: str) -> ExecutionRecord:
        record = self.get(execution_id)
        if record is None:
            raise ValueError("Ejecución no encontrada")
        return record

    def get(self, execution_id: str) -> ExecutionRecord | None:
        sql = f"""
        SELECT *
        FROM `{self.table_id}`
        WHERE execution_id = @execution_id
        LIMIT 1
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id),
        ])
        rows = list(self.client.query(sql, job_config=config).result())
        return self._to_record(rows[0]) if rows else None

    def list(self, limit: int = 50) -> list[ExecutionRecord]:
        sql = f"""
        SELECT *
        FROM `{self.table_id}`
        ORDER BY created_at DESC
        LIMIT @limit
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ])
        return [self._to_record(row) for row in self.client.query(sql, job_config=config).result()]

    @staticmethod
    def _to_record(row: Any) -> ExecutionRecord:
        return ExecutionRecord.model_validate(dict(row.items()))
