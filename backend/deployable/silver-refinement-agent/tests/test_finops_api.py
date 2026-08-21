from __future__ import annotations

from modules.agentops.finops_repository import SILVER_LLM_AGENTS
from modules.agentops.finops_router import (
    get_finops_agents,
    get_finops_daily,
    get_finops_runs,
)


class FakeFinOpsRepository:
    def fetch_daily(self, *, days: int):
        return [{"call_date": "2026-08-21", "llm_calls": 5, "total_tokens": 26853}]

    def fetch_agents(self, *, days: int):
        return [{"agent_name": "mapping-advisor", "llm_calls": 3, "total_tokens": 21743}]

    def fetch_runs(self, *, days: int, limit: int):
        return [{"run_id": "agent-run-123", "llm_calls": 2, "total_tokens": 5110}]


def test_silver_finops_agent_scope_is_canonical() -> None:
    assert SILVER_LLM_AGENTS == (
        "table-profiler",
        "mapping-advisor",
        "quality-rule-advisor",
        "business-rule-validator",
        "notebook-generator",
    )


def test_finops_daily_never_presents_unverified_usd_cost() -> None:
    result = get_finops_daily(days=30, repository=FakeFinOpsRepository())
    assert result["series"][0]["total_tokens"] == 26853
    assert result["billing_cost_available"] is False
    assert result["cost_usd"] is None


def test_finops_agents_exposes_real_usage_contract_without_cost() -> None:
    result = get_finops_agents(days=30, repository=FakeFinOpsRepository())
    assert result["agents"][0]["agent_name"] == "mapping-advisor"
    assert result["agents"][0]["total_tokens"] == 21743
    assert result["billing_cost_available"] is False
    assert result["cost_usd"] is None


def test_finops_runs_preserves_governance_trace_id() -> None:
    result = get_finops_runs(days=30, limit=100, repository=FakeFinOpsRepository())
    assert result["runs"][0]["run_id"] == "agent-run-123"
    assert result["billing_cost_available"] is False
    assert result["cost_usd"] is None
