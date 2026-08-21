from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import bigquery

from .finops_repository import BILLING_DETAILED_PREFIX, SILVER_LLM_AGENTS


PRODUCT_CODE = "BUSINESS_RULES_SILVER"
PRODUCT_RESOURCE_PATTERNS = (
    "silver-refinement",
    "business-rules-silver",
)


class SilverProductAttributionRepository:
    """Product-level FinOps attribution without cross-region BigQuery joins.

    Billing export lives in the US multi-region while AgentOps lives in
    us-central1. Queries are deliberately executed independently in each
    location and correlated in Python only after temporal coverage is verified.
    """

    def __init__(self, project_id: str | None = None) -> None:
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT/PROJECT_ID no configurado")
        self.client = bigquery.Client(project=self.project_id)
        self.billing_dataset = os.getenv("BILLING_EXPORT_DATASET", "cloud_billing_export")
        self.agentops_table = f"{self.project_id}.agentops.fact_llm_calls"

    @staticmethod
    def _agents_sql() -> str:
        return ",".join(f"'{name}'" for name in SILVER_LLM_AGENTS)

    def _billing_table_id(self) -> str | None:
        try:
            tables = self.client.list_tables(f"{self.project_id}.{self.billing_dataset}")
            matches = sorted(t.table_id for t in tables if t.table_id.startswith(BILLING_DETAILED_PREFIX))
        except Exception:
            return None
        return f"{self.project_id}.{self.billing_dataset}.{matches[0]}" if matches else None

    def _query(self, sql: str, *, location: str, parameters: list[bigquery.ScalarQueryParameter] | None = None) -> list[dict[str, Any]]:
        config = bigquery.QueryJobConfig(query_parameters=parameters or [])
        return [dict(row.items()) for row in self.client.query(sql, job_config=config, location=location).result()]

    def fetch_product_attribution(self, *, days: int = 30) -> dict[str, Any]:
        table_id = self._billing_table_id()
        now = datetime.now(timezone.utc)
        requested_start = now - timedelta(days=days)

        telemetry_sql = f"""
        SELECT
          MIN(call_ts) AS first_call_at,
          MAX(call_ts) AS last_call_at,
          COUNT(*) AS llm_calls,
          COUNT(DISTINCT trace_id) AS governed_runs,
          COALESCE(SUM(total_tokens), 0) AS total_tokens
        FROM `{self.agentops_table}`
        WHERE agent_name IN ({self._agents_sql()})
          AND call_ts IS NOT NULL
          AND call_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        """
        telemetry_rows = self._query(
            telemetry_sql,
            location="us-central1",
            parameters=[bigquery.ScalarQueryParameter("days", "INT64", days)],
        )
        telemetry = telemetry_rows[0] if telemetry_rows else {}

        base: dict[str, Any] = {
            "product": PRODUCT_CODE,
            "period_days": days,
            "requested_period_start": requested_start,
            "requested_period_end": now,
            "telemetry_location": "us-central1",
            "billing_location": "US",
            "silver_first_call_at": telemetry.get("first_call_at"),
            "silver_last_call_at": telemetry.get("last_call_at"),
            "silver_llm_calls": int(telemetry.get("llm_calls") or 0),
            "silver_governed_runs": int(telemetry.get("governed_runs") or 0),
            "silver_tokens": int(telemetry.get("total_tokens") or 0),
            "direct_cost_usd": None,
            "attributed_ai_cost_usd": None,
            "product_cost_usd": None,
            "attribution_coverage_pct": 0.0,
            "direct_resources": [],
            "attribution_semantics": "ATRIBUCION_PENDIENTE_COBERTURA",
            "confidence": "PENDING",
        }

        if not table_id:
            return {
                **base,
                "billing_source_available": False,
                "billing_table": None,
                "billing_first_usage_at": None,
                "billing_last_usage_at": None,
                "temporal_overlap": False,
                "status": "BILLING_EXPORT_PENDING",
            }

        coverage_sql = f"""
        SELECT
          MIN(usage_start_time) AS first_usage_at,
          MAX(usage_start_time) AS last_usage_at,
          COUNT(*) AS rows_total
        FROM `{table_id}`
        WHERE project.id = @project_id
        """
        coverage_rows = self._query(
            coverage_sql,
            location="US",
            parameters=[bigquery.ScalarQueryParameter("project_id", "STRING", self.project_id)],
        )
        coverage = coverage_rows[0] if coverage_rows else {}
        billing_first = coverage.get("first_usage_at")
        billing_last = coverage.get("last_usage_at")
        silver_first = telemetry.get("first_call_at")
        silver_last = telemetry.get("last_call_at")
        overlap = bool(billing_last and silver_first and billing_last >= silver_first)

        result = {
            **base,
            "billing_source_available": True,
            "billing_table": table_id,
            "billing_first_usage_at": billing_first,
            "billing_last_usage_at": billing_last,
            "temporal_overlap": overlap,
        }

        if not overlap:
            return {
                **result,
                "status": "WAITING_TEMPORAL_OVERLAP",
                "attribution_semantics": "ATRIBUCION_PENDIENTE_COBERTURA",
                "confidence": "PENDING",
            }

        direct_sql = f"""
        SELECT
          service.description AS service,
          resource.name AS resource_name,
          resource.global_name AS resource_global_name,
          ANY_VALUE(currency) AS billing_currency,
          COALESCE(SUM(cost), 0) AS net_cost_billing_currency,
          COALESCE(SUM(SAFE_DIVIDE(cost, NULLIF(currency_conversion_rate, 0))), 0) AS cost_usd,
          MIN(usage_start_time) AS first_usage_at,
          MAX(usage_start_time) AS last_usage_at
        FROM `{table_id}`
        WHERE project.id = @project_id
          AND usage_start_time >= @period_start
          AND (
            LOWER(IFNULL(resource.name, '')) LIKE '%silver-refinement%'
            OR LOWER(IFNULL(resource.global_name, '')) LIKE '%silver-refinement%'
            OR LOWER(IFNULL(resource.name, '')) LIKE '%business-rules-silver%'
            OR LOWER(IFNULL(resource.global_name, '')) LIKE '%business-rules-silver%'
          )
        GROUP BY service, resource_name, resource_global_name
        ORDER BY cost_usd DESC
        """
        direct_resources = self._query(
            direct_sql,
            location="US",
            parameters=[
                bigquery.ScalarQueryParameter("project_id", "STRING", self.project_id),
                bigquery.ScalarQueryParameter("period_start", "TIMESTAMP", requested_start),
            ],
        )
        direct_cost_usd = sum(float(row.get("cost_usd") or 0) for row in direct_resources)

        # AI attribution remains intentionally pending until we can prove a
        # complete denominator for project-wide Vertex AI usage. We expose the
        # directly attributable cost now and keep AI as an explicit backlog.
        return {
            **result,
            "status": "DIRECT_ATTRIBUTION_AVAILABLE",
            "direct_resources": direct_resources,
            "direct_cost_usd": direct_cost_usd,
            "attributed_ai_cost_usd": None,
            "product_cost_usd": direct_cost_usd,
            "attribution_semantics": "ATRIBUIDO_DIRECTO_PARCIAL",
            "confidence": "HIGH_DIRECT_ONLY",
            "attribution_coverage_pct": None,
            "ai_attribution_status": "DENOMINATOR_VALIDATION_PENDING",
        }
