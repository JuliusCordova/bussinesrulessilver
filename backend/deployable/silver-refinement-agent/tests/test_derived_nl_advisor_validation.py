import json

import pytest

from modules.silver_agents.tools import validate_derived_nl_mapping_proposal
from modules.silver_refinement.artifact_models import SilverColumn


COLUMNS = [
    {"name": "monto_bruto", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "descuento", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "cliente", "type": "STRING", "mode": "NULLABLE"},
]


def _proposal(source_columns=None, operator="SUBTRACT"):
    return {
        "target_column": "monto_neto",
        "target_type": "NUMERIC",
        "nullable": True,
        "transformation": {
            "type": "ARITHMETIC",
            "source_columns": source_columns or ["monto_bruto", "descuento"],
            "parameters": {"operator": operator},
        },
        "confidence": 0.91,
        "reason": "Interpretación de la regla solicitada.",
    }


def test_validator_preserves_exact_natural_rule_and_requires_human_confirmation():
    natural_rule = "Crear monto_neto restando descuento a monto_bruto"
    result = validate_derived_nl_mapping_proposal(
        json.dumps(COLUMNS), natural_rule, json.dumps(_proposal())
    )

    assert result["valid"] is True
    assert result["human_confirmation_required"] is True
    assert result["proposal"]["derivation_mode"] == "DERIVED_NL"
    assert result["proposal"]["natural_rule"] == natural_rule
    assert result["proposal"]["transformation"]["parameters"]["operator"] == "SUBTRACT"
    assert 'F.col("monto_bruto") - F.col("descuento")' in result["compiled_preview"]
    assert result["interpretation"].startswith("Entendí tu regla así:")


def test_validator_rejects_unknown_source_column():
    with pytest.raises(ValueError, match="columnas inexistentes"):
        validate_derived_nl_mapping_proposal(
            json.dumps(COLUMNS),
            "Crear monto_neto",
            json.dumps(_proposal(["monto_bruto", "columna_inventada"])),
        )


def test_validator_rejects_non_numeric_arithmetic_source():
    with pytest.raises(ValueError, match="solo admite columnas numéricas"):
        validate_derived_nl_mapping_proposal(
            json.dumps(COLUMNS),
            "Restar cliente a monto bruto",
            json.dumps(_proposal(["monto_bruto", "cliente"])),
        )


def test_artifact_column_preserves_structured_derived_nl_transformation():
    column = SilverColumn(
        name="monto_neto",
        data_type="NUMERIC",
        source_column="monto_bruto",
        source_columns=["monto_bruto", "descuento"],
        transformation={
            "type": "ARITHMETIC",
            "source_columns": ["monto_bruto", "descuento"],
            "parameters": {"operator": "SUBTRACT"},
        },
        derivation_mode="DERIVED_NL",
        natural_rule="Crear monto_neto restando descuento a monto_bruto",
        requires_approval=True,
    )

    normalized = column.normalized_transformation()
    assert normalized.type.value == "ARITHMETIC"
    assert normalized.source_columns == ["monto_bruto", "descuento"]
    assert normalized.parameters["operator"] == "SUBTRACT"
