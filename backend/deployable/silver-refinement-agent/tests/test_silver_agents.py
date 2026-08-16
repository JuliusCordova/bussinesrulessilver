from __future__ import annotations

import json

from modules.silver_agents.agents import (
    build_business_rule_validator_agent,
    build_notebook_generator_agent,
    build_quality_rule_advisor_agent,
    build_silver_orchestrator,
    build_table_profiler_agent,
)
from modules.silver_agents.tools import (
    build_notebook_blueprint,
    quality_rule_evidence,
    validate_business_rules,
)


def test_builds_all_adk_agents() -> None:
    agents = [
        build_table_profiler_agent(),
        build_quality_rule_advisor_agent(),
        build_business_rule_validator_agent(),
        build_notebook_generator_agent(),
    ]
    assert [agent.name for agent in agents] == [
        "silver_table_profiler",
        "silver_quality_rule_advisor",
        "silver_business_rule_validator",
        "silver_notebook_generator",
    ]
    orchestrator = build_silver_orchestrator()
    assert orchestrator.name == "silver_design_orchestrator"
    assert len(orchestrator.sub_agents) == 4


def test_quality_advisor_flags_nulls_and_duplicates_on_business_key() -> None:
    profile = {
        "table": "project.bronze.customer",
        "row_count": 10,
        "critical_columns": ["customer_id"],
        "business_key_candidates": [],
        "columns": [
            {
                "name": "customer_id",
                "type": "STRING",
                "null_count": 2,
                "distinct_count": 8,
                "critical_candidate": True,
            }
        ],
    }
    result = quality_rule_evidence(
        json.dumps(profile),
        json.dumps(["customer_id"]),
    )
    rules = {item["rule_type"]: item for item in result["candidates"]}
    assert rules["NOT_NULL"]["current_status"] == "FAILING"
    assert rules["NOT_NULL"]["severity_level"] == "CRITICAL"
    assert rules["UNIQUE"]["current_status"] == "FAILING"


def test_business_rule_validator_rejects_unknown_columns() -> None:
    schema = {"columns": [{"name": "customer_id", "type": "STRING"}]}
    rules = [{
        "rule_type": "NOT_NULL",
        "column_name": "missing_column",
        "rule_parameters": {},
    }]
    result = validate_business_rules(json.dumps(schema), json.dumps(rules))
    assert result["valid"] is False
    assert result["findings"][0]["status"] == "ERROR"


def test_notebook_blueprint_requires_business_key_for_merge() -> None:
    spec = {
        "source_project": "project",
        "source_dataset": "bronze",
        "source_table": "customer",
        "target_project": "project",
        "target_dataset": "silver",
        "target_table": "customer",
        "columns": [{"source": "customer_id", "target": "customer_id"}],
        "load_strategy": {"type": "MERGE", "business_keys": []},
    }
    result = build_notebook_blueprint(json.dumps(spec))
    assert result["valid"] is False
    assert "load_strategy.business_keys" in result["missing_fields"]
