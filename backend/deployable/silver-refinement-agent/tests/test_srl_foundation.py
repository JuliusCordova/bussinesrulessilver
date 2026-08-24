from __future__ import annotations

import pytest

from modules.silver_rules import CheckRuleAst, TransformRuleAst, compile_srl, parse_srl, validate_srl


SCHEMA = [
    {"name": "ramo_id", "type": "STRING"},
    {"name": "moneda", "type": "STRING"},
    {"name": "edad", "type": "INT64"},
    {"name": "correo", "type": "STRING"},
    {"name": "monto_reclamado", "type": "NUMERIC"},
    {"name": "impuesto", "type": "NUMERIC"},
]


def test_check_not_null_block_load_parses_validates_and_compiles() -> None:
    rule = parse_srl("CHECK ramo_id NOT_NULL\nON_FAIL BLOCK_LOAD")
    assert isinstance(rule, CheckRuleAst)
    validate_srl(rule, SCHEMA)

    compiled = compile_srl(rule, SCHEMA)
    assert compiled["rule_type"] == "NOT_NULL"
    assert compiled["columns"] == ["ramo_id"]
    assert compiled["dimension"] == "COMPLETENESS"
    assert compiled["runtime_action"] == "BLOCK_LOAD"
    assert compiled["status"] == "PENDING_APPROVAL"
    assert compiled["metadata"]["srl_version"] == "1.0"


def test_check_in_warn_compiles_to_allowed_values() -> None:
    rule = parse_srl('CHECK moneda IN ["PEN", "USD"] ON_FAIL WARN')
    compiled = compile_srl(rule, SCHEMA)

    assert compiled["rule_type"] == "ALLOWED_VALUES"
    assert compiled["parameters"] == {"allowed_values": ["PEN", "USD"]}
    assert compiled["runtime_action"] == "WARN"


def test_derive_column_scalar_compiles_to_existing_arithmetic_contract() -> None:
    rule = parse_srl("DERIVE monto_comision = monto_reclamado * 0.10")
    assert isinstance(rule, TransformRuleAst)
    compiled = compile_srl(rule, SCHEMA)

    assert compiled["target_column"] == "monto_comision"
    assert compiled["target_type"] == "NUMERIC"
    assert compiled["transformation"]["type"] == "ARITHMETIC"
    assert compiled["transformation"]["source_columns"] == ["monto_reclamado"]
    assert compiled["transformation"]["parameters"] == {
        "operator": "MULTIPLY",
        "scalar": 0.1,
    }
    assert compiled["derivation_mode"] == "SRL"
    assert compiled["requires_approval"] is True


def test_derive_column_column_compiles_to_two_source_columns() -> None:
    rule = parse_srl("DERIVE total = monto_reclamado + impuesto")
    compiled = compile_srl(rule, SCHEMA)

    assert compiled["transformation"]["source_columns"] == ["monto_reclamado", "impuesto"]
    assert compiled["transformation"]["parameters"] == {"operator": "ADD"}


def test_between_and_matches_compile_to_existing_quality_contracts() -> None:
    between = compile_srl(parse_srl("CHECK edad BETWEEN 18 AND 100 ON_FAIL QUARANTINE"), SCHEMA)
    regex = compile_srl(parse_srl(r'CHECK correo MATCHES "^[^@]+@[^@]+$" ON_FAIL WARN'), SCHEMA)

    assert between["rule_type"] == "VALUE_RANGE"
    assert between["parameters"] == {"min": 18, "max": 100}
    assert regex["rule_type"] == "REGEX"
    assert regex["parameters"] == {"pattern": "^[^@]+@[^@]+$"}


def test_unknown_column_is_rejected_before_compilation() -> None:
    rule = parse_srl("CHECK columna_fantasma NOT_NULL ON_FAIL BLOCK_LOAD")
    with pytest.raises(ValueError, match="Columna inexistente"):
        compile_srl(rule, SCHEMA)


def test_check_requires_explicit_on_fail() -> None:
    with pytest.raises(ValueError, match="ON_FAIL explícito"):
        parse_srl("CHECK ramo_id NOT_NULL")


def test_unknown_operator_is_rejected() -> None:
    with pytest.raises(ValueError, match="Sintaxis CHECK SRL no soportada"):
        parse_srl("CHECK ramo_id MAGIC ON_FAIL WARN")


def test_between_rejects_non_numeric_column() -> None:
    rule = parse_srl("CHECK moneda BETWEEN 1 AND 2 ON_FAIL WARN")
    with pytest.raises(ValueError, match="columnas numéricas"):
        validate_srl(rule, SCHEMA)


def test_divide_by_zero_scalar_is_rejected() -> None:
    rule = parse_srl("DERIVE ratio = monto_reclamado / 0")
    with pytest.raises(ValueError, match="scalar 0"):
        validate_srl(rule, SCHEMA)
