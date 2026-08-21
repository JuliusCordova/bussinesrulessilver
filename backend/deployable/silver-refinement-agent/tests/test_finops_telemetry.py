from __future__ import annotations

from types import SimpleNamespace

from modules.silver_agents.agents import (
    build_business_rule_validator_agent,
    build_mapping_advisor_agent,
    build_notebook_generator_agent,
    build_quality_rule_advisor_agent,
    build_table_profiler_agent,
)
from modules.silver_agents.finops_telemetry import _usage_value
from modules.silver_agents.models import AgentRunRequest
from modules.silver_agents.service import SilverAgentRunner


def test_all_silver_llm_agents_have_finops_callbacks() -> None:
    agents = [
        build_table_profiler_agent(),
        build_mapping_advisor_agent(),
        build_quality_rule_advisor_agent(),
        build_business_rule_validator_agent(),
        build_notebook_generator_agent(),
    ]
    for agent in agents:
        assert agent.before_model_callback is not None
        assert agent.after_model_callback is not None


def test_runner_state_carries_governance_trace_and_requester() -> None:
    request = AgentRunRequest(
        project_id="project",
        source_dataset="bronze",
        source_table="customer",
        target_dataset="silver",
        target_table="customer",
        requested_by="owner@example.com",
    )
    payload = SilverAgentRunner._payload(request)
    state = SilverAgentRunner._initial_state(
        payload,
        trace_id="agent-run-123",
        requested_by=request.requested_by,
    )

    assert state["finops_trace_id"] == "agent-run-123"
    assert state["finops_requested_by"] == "owner@example.com"


def test_usage_metadata_reads_real_token_fields() -> None:
    usage = SimpleNamespace(
        prompt_token_count=101,
        candidates_token_count=23,
        total_token_count=150,
    )
    assert _usage_value(usage, "prompt_token_count") == 101
    assert _usage_value(usage, "candidates_token_count") == 23
    assert _usage_value(usage, "total_token_count") == 150
