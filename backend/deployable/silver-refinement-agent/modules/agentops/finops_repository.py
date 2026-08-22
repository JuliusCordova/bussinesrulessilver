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

BILLING_DETAILED_PREFIX = "gcp_billing_export_resource_v1_"


class SilverFinOpsRepository:
    """Read-only FinOps projections over real Silver telemetry and Cloud Billing.

    LLM usage is sourced from AgentOps. Billing values are exposed only from the
    real Google Cloud Detailed Usage Cost Export. The export keeps its original
    billing currency and is additionally normalized to USD with Google's own
    currency_conversion_rate. No token-to-price or synthetic USD calculation is
    performed here.
    """

    def __init__(self, project_id: str | None = None) -> None:
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT/PROJECT_ID no configurado")
        self.client = bigquery.Client(project=self.project_id)
        self.table_id = f"{self.project_id}.agentops.fact_llm_calls"
        self.billing_dataset = os.getenv("BILLING_EXPORT_DATASET", "cloud_billing_export")

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

    def _billing_table_id(self) -> str | None:
        """Return the real Detailed Usage Cost Export table when materialized."""
        try:
            tables = self.client.list_tables(f"{self.project_id}.{self.billing_dataset}")
            matches = sorted(
                table.table_id for table in tables if table.table_id.startswith(BILLING_DETAILED_PREFIX)
            )
        except Exception:
            return None
        if not matches:
            return None
        return f"{self.project_id}.{self.billing_dataset}.{matches[0]}"

    def _billing_query(self, sql: str, *, days: int) -> list[dict[str, Any]]:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days),
                bigquery.ScalarQueryParameter("project_id", "STRING", self.project_id),
            ]
        )
        return [dict(row.items()) for row in self.client.query(sql, job_config=job_config).result()]

    def _billing_coverage(self, table_id: str, *, days: int) -> dict[str, Any]:
        sql = f"""
        SELECT
          MIN(usage_start_time) AS first_usage_at,
          MAX(usage_start_time) AS last_usage_at,
          COUNTIF(
            usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
          ) AS rows_in_period
        FROM `{table_id}`
        WHERE project.id = @project_id
        """
        rows = self._billing_query(sql, days=days)
        return rows[0] if rows else {}

    @staticmethod
    def _pending_billing_payload(
        *,
        table_id: str | None,
        cost_source: str,
        first_usage_at: Any = None,
        last_usage_at: Any = None,
    ) -> dict[str, Any]:
        return {
            "billing_source_available": table_id is not None,
            "billing_cost_available": False,
            "billing_data_in_period": False,
            "cost_usd": None,
            "gross_cost_usd": None,
            "credits_usd": None,
            "billing_currency": None,
            "gross_cost_billing_currency": None,
            "credits_billing_currency": None,
            "net_cost_billing_currency": None,
            "cost_semantics": "NO_DISPONIBLE",
            "cost_source": cost_source,
            "billing_table": table_id,
            "first_usage_at": first_usage_at,
            "last_usage_at": last_usage_at,
        }

    def fetch_billing_summary(self, *, days: int = 30) -> dict[str, Any]:
        table_id = self._billing_table_id()
        if not table_id:
            return self._pending_billing_payload(
                table_id=None,
                cost_source="CLOUD_BILLING_EXPORT_PENDING",
            )

        coverage = self._billing_coverage(table_id, days=days)
        if int(coverage.get("rows_in_period") or 0) == 0:
            return self._pending_billing_payload(
                table_id=table_id,
                cost_source="CLOUD_BILLING_EXPORT_NOT_YET_COVERING_PERIOD",
                first_usage_at=coverage.get("first_usage_at"),
                last_usage_at=coverage.get("last_usage_at"),
            )

        sql = f"""
        SELECT
          ANY_VALUE(currency) AS billing_currency,
          COALESCE(SUM(cost), 0) AS gross_cost_billing_currency,
          COALESCE(
            SUM((SELECT COALESCE(SUM(c.amount), 0) FROM UNNEST(credits) AS c)),
            0
          ) AS credits_billing_currency,
          COALESCE(SUM(cost), 0)
            + COALESCE(
                SUM((SELECT COALESCE(SUM(c.amount), 0) FROM UNNEST(credits) AS c)),
                0
              ) AS net_cost_billing_currency,
          COALESCE(
            SUM(SAFE_DIVIDE(cost, NULLIF(currency_conversion_rate, 0))),
            0
          ) AS gross_cost_usd,
          COALESCE(
            SUM((
              SELECT COALESCE(
                SUM(SAFE_DIVIDE(c.amount, NULLIF(currency_conversion_rate, 0))),
                0
              )
              FROM UNNEST(credits) AS c
            )),
            0
          ) AS credits_usd,
          COALESCE(
            SUM(SAFE_DIVIDE(cost, NULLIF(currency_conversion_rate, 0))),
            0
          ) + COALESCE(
            SUM((
              SELECT COALESCE(
                SUM(SAFE_DIVIDE(c.amount, NULLIF(currency_conversion_rate, 0))),
                0
              )
              FROM UNNEST(credits) AS c
            )),
            0
          ) AS cost_usd,
          MIN(usage_start_time) AS first_usage_at,
          MAX(usage_start_time) AS last_usage_at
        FROM `{table_id}`
        WHERE project.id = @project_id
          AND usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        """
        rows = self._billing_query(sql, days=days)
        row = rows[0] if rows else {}
        row.update({
            "billing_source_available": True,
            "billing_cost_available": True,
            "billing_data_in_period": True,
            "cost_semantics": "FACTURADO",
            "cost_source": "CLOUD_BILLING_DETAILED_USAGE_EXPORT",
            "billing_table": table_id,
        })
        return row

    def fetch_billing_services(self, *, days: int = 30) -> dict[str, Any]:
        table_id = self._billing_table_id()
        if not table_id:
            pending = self._pending_billing_payload(
                table_id=None,
                cost_source="CLOUD_BILLING_EXPORT_PENDING",
            )
            return {"period_days": days, "services": [], "total": 0, **pending}

        coverage = self._billing_coverage(table_id, days=days)
        if int(coverage.get("rows_in_period") or 0) == 0:
            pending = self._pending_billing_payload(
                table_id=table_id,
                cost_source="CLOUD_BILLING_EXPORT_NOT_YET_COVERING_PERIOD",
                first_usage_at=coverage.get("first_usage_at"),
                last_usage_at=coverage.get("last_usage_at"),
            )
            return {"period_days": days, "services": [], "total": 0, **pending}

        sql = f"""
        SELECT
          service.description AS service,
          COUNT(DISTINCT sku.id) AS sku_count,
          ANY_VALUE(currency) AS billing_currency,
          COALESCE(SUM(cost), 0) AS gross_cost_billing_currency,
          COALESCE(
            SUM((SELECT COALESCE(SUM(c.amount), 0) FROM UNNEST(credits) AS c)),
            0
          ) AS credits_billing_currency,
          COALESCE(SUM(cost), 0)
            + COALESCE(
                SUM((SELECT COALESCE(SUM(c.amount), 0) FROM UNNEST(credits) AS c)),
                0
              ) AS net_cost_billing_currency,
          COALESCE(
            SUM(SAFE_DIVIDE(cost, NULLIF(currency_conversion_rate, 0))),
            0
          ) AS gross_cost_usd,
          COALESCE(
            SUM((
              SELECT COALESCE(
                SUM(SAFE_DIVIDE(c.amount, NULLIF(currency_conversion_rate, 0))),
                0
              )
              FROM UNNEST(credits) AS c
            )),
            0
          ) AS credits_usd,
          COALESCE(
            SUM(SAFE_DIVIDE(cost, NULLIF(currency_conversion_rate, 0))),
            0
          ) + COALESCE(
            SUM((
              SELECT COALESCE(
                SUM(SAFE_DIVIDE(c.amount, NULLIF(currency_conversion_rate, 0))),
                0
              )
              FROM UNNEST(credits) AS c
            )),
            0
          ) AS cost_usd,
          MIN(usage_start_time) AS first_usage_at,
          MAX(usage_start_time) AS last_usage_at
        FROM `{table_id}`
        WHERE project.id = @project_id
          AND usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        GROUP BY service
        HAVING ABS(net_cost_billing_currency) > 0
        ORDER BY cost_usd DESC, service
        """
        services = self._billing_query(sql, days=days)
        total_cost_usd = sum(float(row.get("cost_usd") or 0) for row in services)
        billing_currency = next(
            (row.get("billing_currency") for row in services if row.get("billing_currency")),
            None,
        )
        total_net_billing_currency = sum(
            float(row.get("net_cost_billing_currency") or 0) for row in services
        )
        return {
            "billing_source_available": True,
            "billing_cost_available": True,
            "billing_data_in_period": True,
            "period_days": days,
            "services": services,
            "total": len(services),
            "cost_usd": total_cost_usd,
            "billing_currency": billing_currency,
            "net_cost_billing_currency": total_net_billing_currency,
            "cost_semantics": "FACTURADO",
            "cost_source": "CLOUD_BILLING_DETAILED_USAGE_EXPORT",
            "billing_table": table_id,
            "first_usage_at": min(
                (row.get("first_usage_at") for row in services if row.get("first_usage_at")),
                default=None,
            ),
            "last_usage_at": max(
                (row.get("last_usage_at") for row in services if row.get("last_usage_at")),
                default=None,
            ),
        }

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
        result["period_days"] = days
        result.update(self.fetch_billing_summary(days=days))
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
