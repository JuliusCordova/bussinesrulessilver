from __future__ import annotations

from modules.agentops.finops_repository import BILLING_DETAILED_PREFIX, SILVER_LLM_AGENTS
from modules.agentops.finops_router import (
    get_finops_agents,
    get_finops_daily,
    get_finops_runs,
    get_finops_services,
)


class FakeFinOpsRepository:
    def fetch_daily(self, *, days: int):
        return [{"call_date": "2026-08-21", "llm_calls": 5, "total_tokens": 26853}]

    def fetch_agents(self, *, days: int):
        return [{"agent_name": "mapping-advisor", "llm_calls": 3, "total_tokens": 21743}]

    def fetch_runs(self, *, days: int, limit: int):
        return [{"run_id": "agent-run-123", "llm_calls": 2, "total_tokens": 5110}]

    def fetch_billing_services(self, *, days: int):
        return {
            "billing_source_available": True,
            "billing_cost_available": True,
            "billing_data_in_period": True,
            "period_days": days,
            "services": [
                {
                    "service": "Vertex AI",
                    "gross_cost_billing_currency": 3.705204,
                    "credits_billing_currency": 0.0,
                    "net_cost_billing_currency": 3.705204,
                    "gross_cost_usd": 1.085774,
                    "credits_usd": 0.0,
                    "cost_usd": 1.085774,
                    "billing_currency": "PEN",
                }
            ],
            "total": 1,
            "cost_usd": 1.085774,
            "billing_currency": "PEN",
            "net_cost_billing_currency": 3.705204,
            "cost_semantics": "FACTURADO",
            "cost_source": "CLOUD_BILLING_DETAILED_USAGE_EXPORT",
        }


def test_silver_finops_agent_scope_is_canonical() -> None:
    assert SILVER_LLM_AGENTS == (
        "table-profiler",
        "mapping-advisor",
        "quality-rule-advisor",
        "business-rule-validator",
        "notebook-generator",
    )
    assert BILLING_DETAILED_PREFIX == "gcp_billing_export_resource_v1_"


def test_finops_daily_exposes_usage_without_inventing_cost() -> None:
    result = get_finops_daily(days=30, repository=FakeFinOpsRepository())
    assert result["series"][0]["total_tokens"] == 26853
    assert "cost_usd" not in result


def test_finops_agents_marks_cost_attribution_as_pending() -> None:
    result = get_finops_agents(days=30, repository=FakeFinOpsRepository())
    assert result["agents"][0]["agent_name"] == "mapping-advisor"
    assert result["agents"][0]["total_tokens"] == 21743
    assert result["cost_semantics"] == "ATRIBUCION_PENDIENTE"
    assert result["cost_usd"] is None


def test_finops_runs_preserves_governance_trace_id_without_fake_usd() -> None:
    result = get_finops_runs(days=30, limit=100, repository=FakeFinOpsRepository())
    assert result["runs"][0]["run_id"] == "agent-run-123"
    assert result["cost_semantics"] == "ATRIBUCION_PENDIENTE"
    assert result["cost_usd"] is None


def test_finops_services_preserves_billing_currency_and_normalized_usd() -> None:
    result = get_finops_services(days=30, repository=FakeFinOpsRepository())
    assert result["billing_source_available"] is True
    assert result["billing_cost_available"] is True
    assert result["billing_data_in_period"] is True
    assert result["cost_semantics"] == "FACTURADO"
    assert result["services"][0]["service"] == "Vertex AI"
    assert result["services"][0]["billing_currency"] == "PEN"
    assert result["services"][0]["net_cost_billing_currency"] == 3.705204
    assert result["services"][0]["cost_usd"] == 1.085774
    assert result["billing_currency"] == "PEN"
