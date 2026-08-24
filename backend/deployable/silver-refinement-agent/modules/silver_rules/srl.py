from __future__ import annotations

import ast as py_ast
import hashlib
import re
from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, Field, model_validator

from modules.silver_intelligent_mapping.models import (
    IntelligentMappingColumn,
    MappingTransformation,
    TransformationType,
)
from modules.silver_workflow.models import GovernedQualityRule


SRL_VERSION = "1.0"
NUMERIC_TYPES = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC", "DECIMAL"}
STRING_TYPES = {"STRING", "BYTES"}


class SrlFamily(str, Enum):
    CHECK = "CHECK"
    TRANSFORM = "TRANSFORM"


class RuntimeAction(str, Enum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    WARN = "WARN"
    QUARANTINE = "QUARANTINE"
    BLOCK_LOAD = "BLOCK_LOAD"


class CheckOperator(str, Enum):
    NOT_NULL = "NOT_NULL"
    UNIQUE = "UNIQUE"
    IN = "IN"
    BETWEEN = "BETWEEN"
    MATCHES = "MATCHES"


class ArithmeticOperator(str, Enum):
    ADD = "ADD"
    SUBTRACT = "SUBTRACT"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"


class SrlOperand(BaseModel):
    column: str | None = None
    scalar: int | float | None = None

    @model_validator(mode="after")
    def exactly_one_operand_kind(self) -> "SrlOperand":
        if (self.column is None) == (self.scalar is None):
            raise ValueError("Un operando SRL debe contener exactamente column o scalar")
        return self


class CheckRuleAst(BaseModel):
    srl_version: str = SRL_VERSION
    family: SrlFamily = SrlFamily.CHECK
    column: str = Field(min_length=1, max_length=300)
    operator: CheckOperator
    arguments: list[Any] = Field(default_factory=list)
    runtime_action: RuntimeAction
    source_text: str = Field(min_length=1, max_length=8000)


class TransformRuleAst(BaseModel):
    srl_version: str = SRL_VERSION
    family: SrlFamily = SrlFamily.TRANSFORM
    target_column: str = Field(min_length=1, max_length=300)
    operation: ArithmeticOperator
    operands: list[SrlOperand] = Field(min_length=2, max_length=2)
    source_text: str = Field(min_length=1, max_length=8000)


SrlAst = CheckRuleAst | TransformRuleAst


def _normalize(text: str) -> str:
    return " ".join(part.strip() for part in text.strip().splitlines() if part.strip())


def _parse_runtime_action(text: str) -> tuple[str, RuntimeAction]:
    match = re.search(r"\s+ON_FAIL\s+(OBSERVE_ONLY|WARN|QUARANTINE|BLOCK_LOAD)\s*$", text, re.IGNORECASE)
    if not match:
        raise ValueError("SRL CHECK requiere ON_FAIL explícito")
    action = RuntimeAction(match.group(1).upper())
    return text[: match.start()].strip(), action


def _literal_list(raw: str) -> list[Any]:
    try:
        value = py_ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise ValueError("IN requiere una lista literal válida") from exc
    if not isinstance(value, list) or not value:
        raise ValueError("IN requiere una lista no vacía")
    if any(isinstance(item, (list, dict, tuple, set)) for item in value):
        raise ValueError("IN solo acepta valores escalares")
    return value


def _literal_scalar(raw: str) -> Any:
    raw = raw.strip()
    try:
        return py_ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"Literal SRL inválido: {raw}") from exc


def parse_srl(srl_text: str) -> SrlAst:
    text = _normalize(srl_text)
    if not text:
        raise ValueError("SRL vacío")

    if text.upper().startswith("CHECK "):
        rule_text, runtime_action = _parse_runtime_action(text)
        body = rule_text[6:].strip()

        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s+(NOT_NULL|UNIQUE)", body, re.IGNORECASE)
        if match:
            return CheckRuleAst(
                column=match.group(1),
                operator=CheckOperator(match.group(2).upper()),
                runtime_action=runtime_action,
                source_text=text,
            )

        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s+IN\s+(\[.*\])", body, re.IGNORECASE)
        if match:
            return CheckRuleAst(
                column=match.group(1),
                operator=CheckOperator.IN,
                arguments=_literal_list(match.group(2)),
                runtime_action=runtime_action,
                source_text=text,
            )

        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s+BETWEEN\s+(.+?)\s+AND\s+(.+)", body, re.IGNORECASE)
        if match:
            return CheckRuleAst(
                column=match.group(1),
                operator=CheckOperator.BETWEEN,
                arguments=[_literal_scalar(match.group(2)), _literal_scalar(match.group(3))],
                runtime_action=runtime_action,
                source_text=text,
            )

        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s+MATCHES\s+(.+)", body, re.IGNORECASE)
        if match:
            pattern = _literal_scalar(match.group(2))
            if not isinstance(pattern, str) or not pattern:
                raise ValueError("MATCHES requiere un patrón STRING no vacío")
            return CheckRuleAst(
                column=match.group(1),
                operator=CheckOperator.MATCHES,
                arguments=[pattern],
                runtime_action=runtime_action,
                source_text=text,
            )

        raise ValueError("Sintaxis CHECK SRL no soportada")

    match = re.fullmatch(
        r"DERIVE\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*([+\-*/])\s*([A-Za-z_][A-Za-z0-9_]*|[-+]?\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if match:
        symbol_to_operator = {
            "+": ArithmeticOperator.ADD,
            "-": ArithmeticOperator.SUBTRACT,
            "*": ArithmeticOperator.MULTIPLY,
            "/": ArithmeticOperator.DIVIDE,
        }
        right_raw = match.group(4)
        right: SrlOperand
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", right_raw):
            scalar = float(right_raw) if "." in right_raw else int(right_raw)
            right = SrlOperand(scalar=scalar)
        else:
            right = SrlOperand(column=right_raw)
        return TransformRuleAst(
            target_column=match.group(1),
            operation=symbol_to_operator[match.group(3)],
            operands=[SrlOperand(column=match.group(2)), right],
            source_text=text,
        )

    raise ValueError("Sintaxis SRL no soportada")


def _schema_map(schema: Mapping[str, str] | list[dict[str, Any]]) -> dict[str, str]:
    if isinstance(schema, Mapping):
        return {str(name): str(data_type).upper() for name, data_type in schema.items()}
    result: dict[str, str] = {}
    for item in schema:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        data_type = item.get("type") or item.get("data_type")
        if data_type:
            result[str(item["name"])] = str(data_type).upper()
    return result


def validate_srl(rule: SrlAst, schema: Mapping[str, str] | list[dict[str, Any]]) -> SrlAst:
    columns = _schema_map(schema)
    if not columns:
        raise ValueError("El schema SRL no contiene columnas tipadas")

    if isinstance(rule, CheckRuleAst):
        if rule.column not in columns:
            raise ValueError(f"Columna inexistente: {rule.column}")
        column_type = columns[rule.column]
        if rule.operator == CheckOperator.IN and not rule.arguments:
            raise ValueError("IN requiere valores permitidos")
        if rule.operator == CheckOperator.BETWEEN:
            if column_type not in NUMERIC_TYPES:
                raise ValueError("BETWEEN solo está habilitado para columnas numéricas en SRL v1.0")
            if len(rule.arguments) != 2 or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in rule.arguments):
                raise ValueError("BETWEEN requiere límites numéricos")
            if rule.arguments[0] > rule.arguments[1]:
                raise ValueError("BETWEEN requiere límite mínimo <= máximo")
        if rule.operator == CheckOperator.MATCHES and column_type not in STRING_TYPES:
            raise ValueError("MATCHES solo está habilitado para STRING/BYTES en SRL v1.0")
        return rule

    referenced_columns = [operand.column for operand in rule.operands if operand.column]
    unknown = [name for name in referenced_columns if name not in columns]
    if unknown:
        raise ValueError("Columnas inexistentes: " + ", ".join(sorted(set(unknown))))
    non_numeric = [name for name in referenced_columns if columns[name] not in NUMERIC_TYPES]
    if non_numeric:
        raise ValueError("DERIVE aritmético solo admite columnas numéricas: " + ", ".join(non_numeric))
    if rule.operation == ArithmeticOperator.DIVIDE:
        right = rule.operands[1]
        if right.scalar == 0:
            raise ValueError("DIVIDE no admite scalar 0")
    return rule


def _rule_id(rule: CheckRuleAst) -> str:
    digest = hashlib.sha256(rule.source_text.encode("utf-8")).hexdigest()[:12]
    return f"srl_{rule.operator.value.lower()}_{rule.column}_{digest}"


def compile_srl(rule: SrlAst, schema: Mapping[str, str] | list[dict[str, Any]]) -> dict[str, Any]:
    rule = validate_srl(rule, schema)
    columns = _schema_map(schema)

    if isinstance(rule, CheckRuleAst):
        rule_type = rule.operator.value
        parameters: dict[str, Any] = {}
        dimension = "VALIDITY"
        if rule.operator == CheckOperator.NOT_NULL:
            dimension = "COMPLETENESS"
        elif rule.operator == CheckOperator.UNIQUE:
            dimension = "UNIQUENESS"
        elif rule.operator == CheckOperator.IN:
            rule_type = "ALLOWED_VALUES"
            parameters = {"allowed_values": rule.arguments}
        elif rule.operator == CheckOperator.BETWEEN:
            rule_type = "VALUE_RANGE"
            parameters = {"min": rule.arguments[0], "max": rule.arguments[1]}
        elif rule.operator == CheckOperator.MATCHES:
            rule_type = "REGEX"
            parameters = {"pattern": rule.arguments[0]}

        governed = GovernedQualityRule(
            rule_id=_rule_id(rule),
            name=f"SRL {rule.operator.value} {rule.column}",
            dimension=dimension,
            rule_type=rule_type,
            columns=[rule.column],
            parameters=parameters,
            expression=rule.source_text,
            runtime_action=rule.runtime_action.value,
            source="MANUAL",
            status="PENDING_APPROVAL",
            metadata={"srl_version": SRL_VERSION, "srl_family": SrlFamily.CHECK.value},
        )
        return governed.model_dump(mode="json")

    left, right = rule.operands
    source_columns = [left.column] if left.column else []
    parameters: dict[str, Any] = {"operator": rule.operation.value}
    if right.column:
        source_columns.append(right.column)
    else:
        parameters["scalar"] = right.scalar

    left_type = columns[left.column] if left.column else "FLOAT64"
    if right.column and columns[right.column] != left_type:
        target_type = "FLOAT64"
    else:
        target_type = left_type

    column = IntelligentMappingColumn(
        source_column=left.column,
        target_column=rule.target_column,
        target_type=target_type,
        nullable=True,
        include=True,
        transformation=MappingTransformation(
            type=TransformationType.ARITHMETIC,
            source_columns=source_columns,
            parameters=parameters,
        ),
        confidence=None,
        reason="Compilado determinísticamente desde SRL v1.0.",
        risk="Requiere aprobación humana antes de persistirse o ejecutarse.",
        requires_approval=True,
    )
    payload = column.model_dump(mode="json")
    payload["derivation_mode"] = "SRL"
    payload["srl_version"] = SRL_VERSION
    payload["srl_expression"] = rule.source_text
    return payload
