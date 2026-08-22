import json

import pytest

from modules.silver_agents.tools import validate_quality_nl_rule_proposal


COLUMNS = [
    {"name": "monto_total", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "estado", "type": "STRING", "mode": "NULLABLE"},
    {"name": "cliente_id", "type": "STRING", "mode": "NULLABLE"},
]


def test_quality_nl_value_range_is_structured_and_requires_confirmation():
    result = validate_quality_nl_rule_proposal(
        json.dumps(COLUMNS),
        "monto_total debe estar entre 0 y 100000",
        json.dumps({
            "rule_type": "VALUE_RANGE",
            "columns": ["monto_total"],
            "parameters": {"min": 0, "max": 100000},
            "severity": "HIGH",
            "runtime_action": "QUARANTINE",
            "confidence": 0.93,
        }),
    )
    assert result["valid"] is True
    assert result["human_confirmation_required"] is True
    assert result["proposal"]["source"] == "DERIVED_NL"
    assert result["proposal"]["status"] == "PENDING_APPROVAL"
    assert result["proposal"]["expression"] is None
    assert result["proposal"]["metadata"]["natural_rule"] == "monto_total debe estar entre 0 y 100000"
    assert result["interpretation"].startswith("Entendí tu regla así:")


def test_quality_nl_rejects_unknown_column():
    with pytest.raises(ValueError, match="columnas inexistentes"):
        validate_quality_nl_rule_proposal(
            json.dumps(COLUMNS),
            "campo_falso no debe ser nulo",
            json.dumps({"rule_type": "NOT_NULL", "columns": ["campo_falso"]}),
        )


def test_quality_nl_rejects_unsupported_free_expression_type():
    with pytest.raises(ValueError, match="Tipo de regla no soportado"):
        validate_quality_nl_rule_proposal(
            json.dumps(COLUMNS),
            "ejecuta esta expresión libre",
            json.dumps({"rule_type": "SQL_EXPRESSION", "columns": ["monto_total"], "expression": "DROP TABLE x"}),
        )


def test_quality_nl_regex_requires_string_column():
    with pytest.raises(ValueError, match="REGEX solo admite"):
        validate_quality_nl_rule_proposal(
            json.dumps(COLUMNS),
            "monto_total debe cumplir un patrón",
            json.dumps({"rule_type": "REGEX", "columns": ["monto_total"], "parameters": {"pattern": "^[0-9]+$"}}),
        )
