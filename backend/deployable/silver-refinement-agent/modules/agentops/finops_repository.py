from __future__ import annotations

import os
from typing import Any

from google.cloud import bigquery


SILVER_LLM_AGENTS = (
    "table-profiler",
    "mapping-advisor",
    "quality-rule-advisor",
    "business-rule-validator",
    "notebook-generator",
)


class SilverFinOpsRepository:
    """Read-only FinOps projections over real Silver LLM telemetry.

    USD billing values are intentionally not derived here. They remain unavailable
    until a validated Cloud Billing Export source exists.
    """

    def __init__(self, project_id: str | None = None) -> None:
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT/PROJECT_ID no configurado")
        self.client = bigquery.Client(project=self.project_id)
        self.table_id = f"{self.project_id}.agentops.fact_llm_calls"

    @staticmethod
    def _agents_sql() -> str:
        return ",".join(f"'{name}'" for name in SILVER_LLM_AGENTS)

    def _query(self, sql: str, *, days: int = 30) -> list[dict[str, Any]]:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days),
            ]
        )
        return [dict(row.items()) for row in self.client.query(sql, job_config=job_config).result()]

    def fetch_summary(self, *, days: int = 30) -> dict[str, Any]:
        sql = f"""
        SELECT
          COUNT(*) AS llm_calls,
          COUNT(DISTINCT trace_id) AS governed_runs,
          COUNT(DISTINCT agent_name) AS active_agents,
          COUNT(DISTINCT model_name) AS models,
          COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
          COALESCE(SUM(response_tokens), 0) AS response_tokens,
          COALESCE(SUM(total_tokens), 0) AS total_tokens,
          SAFE_DIVIDE(SUM(latency_ms), COUNT(*)) AS avg_latency_ms,
          COUNTIF(status = 'SUCCESS') AS successful_calls,
          COUNTIF(status != 'SUCCESS') AS failed_calls,
          MIN(call_ts) AS first_call_ts,
          MAX(call_ts) AS last_call_ts
        FROM `{self.table_id}`
        WHERE agent_name IN ({self._agents_sql()})
          AND call_ts IS NOT NULL
          AND call_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        """
        rows = self._query(sql, days=days)
        result = rows[0] if rows else {}
        result.update({
            "period_days": days,
            "billing_cost_available": False,
            "cost_usd": None,
            "cost_source": "CLOUD_BILLING_EXPORT_NOT_CONFIGURED",
        })
        return result

    def fetch_daily(self, *, days: int = 30) -> list[dict[str, Any]]:
        sql = f"""
        SELECT
          DATE(call_ts) AS call_date,
          COUNT(*) AS llm_calls,
          COUNT(DISTINCT trace_id) AS governed_runs,
          COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
          COALESCE(SUM(response_tokens), 0) AS response_tokens,
          COALESCE(SUM(total_tokens), 0) AS total_tokens,
          SAFE_DIVIDE(SUM(latency_ms), COUNT(*)) AS avg_latency_ms
        FROM `{self.table_id}`
        WHERE agent_name IN ({self._agents_sql()})
          AND call_ts IS NOT NULL
          AND call_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        GROUP BY call_date
        ORDER BY call_date
        """
        return self._query(sql, days=days)

    def fetch_agents(self, *, days: int = 30) -> list[dict[str, Any]]:
        sql = f"""
        SELECT
          agent_name,
          ARRAY_AGG(DISTINCT model_name IGNORE NULLS) AS models,
          COUNT(*) AS llm_calls,
          COUNT(DISTINCT trace_id) AS governed_runs,
          COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
          COALESCE(SUM(response_tokens), 0) AS response_tokens,
          COALESCE(SUM(total_tokens), 0) AS total_tokens,
          SAFE_DIVIDE(SUM(latency_ms), COUNT(*)) AS avg_latency_ms,
          COUNTIF(status = 'SUCCESS') AS successful_calls,
          COUNTIF(status != 'SUCCESS') AS failed_calls,
          MAX(call_ts) AS last_call_ts
        FROM `{self.table_id}`
        WHERE agent_name IN ({self._agents_sql()})
          AND call_ts IS NOT NULL
          AND call_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        GROUP BY agent_name
        ORDER BY total_tokens DESC, agent_name
        """
        return self._query(sql, days=days)

    def fetch_runs(self, *, days: int = 30, limit: int = 100) -> list[dict[str, Any]]:
        sql = f"""
        SELECT
          trace_id AS run_id,
          ANY_VALUE(session_id HAVING MAX call_ts) AS session_id,
          ARRAY_AGG(DISTINCT agent_name ORDER BY agent_name) AS agents,
          ARRAY_AGG(DISTINCT model_name IGNORE NULLS ORDER BY model_name) AS models,
          COUNT(*) AS llm_calls,
          COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
          COALESCE(SUM(response_tokens), 0) AS response_tokens,
          COALESCE(SUM(total_tokens), 0) AS total_tokens,
          SAFE_DIVIDE(SUM(latency_ms), COUNT(*)) AS avg_latency_ms,
          COUNTIF(status = 'SUCCESS') AS successful_calls,
          COUNTIF(status != 'SUCCESS') AS failed_calls,
          MIN(call_ts) AS started_at,
          MAX(call_ts) AS finished_at,
          ANY_VALUE(user_email HAVING MAX call_ts) AS requested_by
        FROM `{self.table_id}`
        WHERE agent_name IN ({self._agents_sql()})
          AND call_ts IS NOT NULL
          AND trace_id IS NOT NULL
          AND call_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        GROUP BY trace_id
        ORDER BY finished_at DESC
        LIMIT {int(limit)}
        """
        return self._query(sql, days=days)
