from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from google.cloud import bigquery


class AgentGovernanceRepository:
    """Persistent audit trail for every Gemini ADK invocation."""

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
        self.table = f"{self.project_id}.{self.dataset}.silver_agent_governance_runs"
        self._ensure_table()

    def _ensure_table(self) -> None:
        sql = f"""
        CREATE TABLE IF NOT EXISTS `{self.table}` (
          run_id STRING NOT NULL,
          agent_name STRING NOT NULL,
          session_id STRING,
          status STRING NOT NULL,
          requested_by STRING,
          source_table STRING,
          target_table STRING,
          event_count INT64,
          duration_ms INT64,
          started_at TIMESTAMP NOT NULL,
          finished_at TIMESTAMP NOT NULL,
          evidence_json STRING,
          error_message STRING,
          created_at TIMESTAMP NOT NULL
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY agent_name, status
        OPTIONS (
          description = 'Gobierno persistente de ejecuciones Gemini ADK Silver'
        )
        """
        self.client.query(sql).result()

    def save_run(
        self,
        *,
        run_id: str,
        agent_name: str,
        session_id: str | None,
        status: str,
        requested_by: str | None,
        source_table: str,
        target_table: str,
        event_count: int,
        duration_ms: int,
        started_at: datetime,
        finished_at: datetime,
        evidence: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        row = {
            "run_id": run_id,
            "agent_name": agent_name,
            "session_id": session_id,
            "status": status,
            "requested_by": requested_by,
            "source_table": source_table,
            "target_table": target_table,
            "event_count": event_count,
            "duration_ms": duration_ms,
            "started_at": started_at.astimezone(timezone.utc).isoformat(),
            "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
            "evidence_json": (
                json.dumps(evidence, ensure_ascii=False, default=str)
                if evidence is not None
                else None
            ),
            "error_message": error_message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        errors = self.client.insert_rows_json(self.table, [row], row_ids=[run_id])
        if errors:
            raise RuntimeError(f"No fue posible persistir gobierno agéntico: {errors}")

    def fetch_summary(self) -> dict[str, Any]:
        sql = f"""
        SELECT
          COUNT(*) AS total_runs,
          COUNT(DISTINCT agent_name) AS active_agents,
          COUNTIF(status = 'COMPLETED') AS completed,
          COUNTIF(status = 'FAILED') AS failed,
          COUNTIF(DATE(created_at) = CURRENT_DATE('UTC')) AS runs_today,
          COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
          MAX(finished_at) AS last_run_at
        FROM `{self.table}`
        """
        rows = list(self.client.query(sql).result())
        return dict(rows[0].items()) if rows else {}

    def fetch_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        sql = f"""
        SELECT
          run_id,
          agent_name,
          session_id,
          status,
          requested_by,
          source_table,
          target_table,
          event_count,
          duration_ms,
          started_at,
          finished_at,
          error_message
        FROM `{self.table}`
        ORDER BY created_at DESC
        LIMIT @limit
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("limit", "INT64", limit)
            ]
        )
        return [
            dict(row.items())
            for row in self.client.query(sql, job_config=config).result()
        ]
