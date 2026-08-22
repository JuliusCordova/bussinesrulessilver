import pytest

from modules.silver_intelligent_mapping.compiler import compile_pyspark_expression
from modules.silver_intelligent_mapping.models import (
    IntelligentMappingColumn, MappingTransformation, TransformationType,
)
from modules.silver_workflow.models import SilverMappingColumn


def test_arithmetic_derivation_compiles_from_structured_contract_only():
    column = IntelligentMappingColumn(
        source_column=None,
        target_column="monto_neto",
        target_type="NUMERIC",
        nullable=True,
        transformation=MappingTransformation(
            type=TransformationType.ARITHMETIC,
            source_columns=["monto_bruto", "descuento"],
            parameters={"operator": "SUBTRACT"},
        ),
        requires_approval=True,
    )

    expression = compile_pyspark_expression(column)

    assert 'F.col("monto_bruto") - F.col("descuento")' in expression
    assert '.alias("monto_neto")' in expression
    assert 'decimal(38,9)' in expression


def test_arithmetic_rejects_non_whitelisted_operator():
    with pytest.raises(ValueError, match="ARITHMETIC requiere operator"):
        MappingTransformation(
            type=TransformationType.ARITHMETIC,
            source_columns=["monto_bruto", "descuento"],
            parameters={"operator": "EVAL"},
        )


def test_workflow_mapping_preserves_derived_nl_traceability():
    column = SilverMappingColumn(
        name="monto_neto",
        data_type="NUMERIC",
        source_columns=["monto_bruto", "descuento"],
        transformation={
            "type": "ARITHMETIC",
            "source_columns": ["monto_bruto", "descuento"],
            "parameters": {"operator": "SUBTRACT"},
        },
        derivation_mode="DERIVED_NL",
        natural_rule="Crear monto_neto restando descuento a monto_bruto",
    )

    payload = column.model_dump(mode="json")
    assert payload["derivation_mode"] == "DERIVED_NL"
    assert payload["natural_rule"].startswith("Crear monto_neto")
    assert payload["transformation"]["parameters"]["operator"] == "SUBTRACT"
