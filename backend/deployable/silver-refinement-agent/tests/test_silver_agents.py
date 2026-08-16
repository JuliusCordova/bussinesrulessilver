from __future__ import annotations

import json

from modules.silver_agents.agents import (
    build_business_rule_validator_agent,
    build_mapping_advisor_agent,
    build_notebook_generator_agent,
    build_quality_rule_advisor_agent,
    build_silver_orchestrator,
    build_table_profiler_agent,
)
from modules.silver_agents.models import AgentRunRequest
from modules.silver_agents.profile_report import ProfileReportService
from modules.silver_agents.service import SilverAgentRunner
from modules.silver_agents.tools import (
    build_notebook_blueprint,
    quality_rule_evidence,
    recommend_column_mappings,
    validate_business_rules,
)


def test_builds_all_adk_agents() -> None:
    agents = [
        build_table_profiler_agent(),
        build_mapping_advisor_agent(),
        build_quality_rule_advisor_agent(),
        build_business_rule_validator_agent(),
        build_notebook_generator_agent(),
    ]
    assert [agent.name for agent in agents] == [
        "silver_table_profiler",
        "silver_mapping_advisor",
        "silver_quality_rule_advisor",
        "silver_business_rule_validator",
        "silver_notebook_generator",
    ]
    orchestrator = build_silver_orchestrator()
    assert orchestrator.name == "silver_design_orchestrator"
    assert len(orchestrator.sub_agents) == 5


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


def test_runner_builds_complete_shared_state() -> None:
    request = AgentRunRequest(
        project_id="project",
        source_dataset="bronze",
        source_table="customer",
        target_dataset="silver",
        target_table="customer",
        columns=[{"name": "customer_id", "data_type": "STRING"}],
        business_keys=["customer_id"],
        watermark_column="ingestion_timestamp",
        business_rules=[{
            "rule_type": "NOT_NULL",
            "column_name": "customer_id",
            "rule_parameters": {},
        }],
    )
    payload = SilverAgentRunner._payload(request)
    state = SilverAgentRunner._initial_state(payload)
    notebook_spec = json.loads(state["notebook_spec_json"])

    assert payload["load_strategy"]["type"] == "MERGE"
    assert notebook_spec["columns"][0]["name"] == "customer_id"
    assert notebook_spec["load_strategy"]["business_keys"] == ["customer_id"]
    assert json.loads(state["business_rules_json"])[0]["rule_type"] == "NOT_NULL"


def test_profile_report_is_a_valid_pdf() -> None:
    profile = {
        "table": "project.bronze.customer",
        "row_count": 10,
        "business_key_candidates": ["customer_id"],
        "critical_columns": ["customer_id"],
        "partitioning": "ingestion_timestamp",
        "columns": [{
            "name": "customer_id",
            "type": "STRING",
            "mode": "REQUIRED",
            "null_count": 0,
            "null_ratio": 0.0,
            "distinct_count": 10,
            "unique_ratio": 1.0,
            "critical_candidate": True,
            "business_key_candidate": True,
        }],
    }
    content = ProfileReportService().build(profile)
    assert content.startswith(b"%PDF-")
    assert len(content) > 1500


def test_mapping_advisor_uses_only_selected_schema_columns() -> None:
    columns = [
        {"name": "pago_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "monto_pago", "type": "NUMERIC", "mode": "NULLABLE"},
    ]
    profile = {
        "table": "project.bronze.pagos_primas",
        "columns": [
            {"name": "pago_id", "null_count": 2, "distinct_count": 98},
            {"name": "monto_pago", "null_count": 0, "distinct_count": 40},
        ],
    }
    result = recommend_column_mappings(
        json.dumps(columns),
        json.dumps(profile),
    )
    assert [item["source_column"] for item in result["columns"]] == [
        "pago_id",
        "monto_pago",
    ]
    assert result["columns"][0]["transformation"]["type"] == "TRIM"
    assert "producto_id" not in json.dumps(result)
    assert result["requires_human_approval"] is True
