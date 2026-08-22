import pytest

from modules.silver_refinement.execution_artifact_generator import ExecutionArtifactGeneratorService


def test_governed_rule_normalization_preserves_runtime_action_and_contract():
    normalized = ExecutionArtifactGeneratorService.normalize_quality_rules([{
        "rule_id": "qr_amount_range",
        "name": "amount_range",
        "version": 2,
        "dimension": "VALIDITY",
        "rule_type": "VALUE_RANGE",
        "columns": ["amount"],
        "parameters": {"min": 0, "max": 100},
        "warning_threshold": 1,
        "critical_threshold": 5,
        "severity": "HIGH",
        "runtime_action": "QUARANTINE",
        "source": "DERIVED_NL",
        "status": "APPROVED",
        "active": True,
        "metadata": {"natural_rule": "amount entre 0 y 100"},
    }])[0]

    assert normalized["rule_id"] == "qr_amount_range"
    assert normalized["rule_version"] == 2
    assert normalized["column_name"] == "amount"
    assert normalized["rule_parameters"]["min_value"] == 0
    assert normalized["rule_parameters"]["max_value"] == 100
    assert normalized["runtime_action"] == "QUARANTINE"
    assert normalized["status"] == "APPROVED"


def test_governed_regex_alias_is_executable_contract():
    normalized = ExecutionArtifactGeneratorService.normalize_quality_rules([{
        "rule_id": "qr_code_regex",
        "name": "code_regex",
        "dimension": "VALIDITY",
        "rule_type": "REGEX",
        "columns": ["code"],
        "parameters": {"pattern": "^[A-Z]+$"},
        "runtime_action": "WARN",
        "status": "APPROVED",
    }])[0]
    assert normalized["rule_type"] == "REGEX_MATCH"
    assert normalized["rule_parameters"]["regex"] == "^[A-Z]+$"
    assert normalized["runtime_action"] == "WARN"


def test_pending_governed_rule_cannot_enter_executable_package():
    with pytest.raises(ValueError, match="no está aprobada"):
        ExecutionArtifactGeneratorService.normalize_quality_rules([{
            "rule_id": "qr_pending",
            "name": "pending",
            "dimension": "COMPLETENESS",
            "rule_type": "NOT_NULL",
            "columns": ["id"],
            "parameters": {},
            "runtime_action": "BLOCK_LOAD",
            "status": "PENDING_APPROVAL",
        }])


def test_table_level_quarantine_is_rejected():
    with pytest.raises(ValueError, match="nivel tabla"):
        ExecutionArtifactGeneratorService.normalize_quality_rules([{
            "rule_name": "row_count",
            "rule_type": "ROW_COUNT_MIN",
            "rule_parameters": {"min_rows": 10},
            "runtime_action": "QUARANTINE",
        }])


def test_generated_script_contains_all_runtime_gate_paths():
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "modules/silver_refinement/execution_artifact_generator.py"
    ).read_text()
    assert 'action == "BLOCK_LOAD"' in source
    assert 'action == "QUARANTINE"' in source
    assert 'action == "WARN"' in source
    assert 'action == "OBSERVE_ONLY"' in source
    assert "silver_output_df" in source
    assert "_exclude_quarantined_rows" in source
