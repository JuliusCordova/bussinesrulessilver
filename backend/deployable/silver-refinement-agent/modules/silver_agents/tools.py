from __future__ import annotations

import json
from typing import Any

from modules.silver_intelligent_mapping.compiler import compile_pyspark_expression
from modules.silver_intelligent_mapping.models import (
    IntelligentMappingColumn,
    MappingTransformation,
    TransformationType,
)
from modules.silver_workflow.models import GovernedQualityRule

from .profile_service import BigQueryTableProfiler


SUPPORTED_RULE_TYPES = {
    "NOT_NULL",
    "UNIQUE",
    "ALLOWED_VALUES",
    "VALUE_RANGE",
    "REGEX",
}


def profile_selected_table(
    project_id: str,
    dataset_id: str,
    table_id: str,
) -> dict[str, Any]:
    """Profile the selected BigQuery table using factual metrics."""
    return BigQueryTableProfiler().profile(project_id, dataset_id, table_id)


def quality_rule_evidence(
    profile_json: str,
    business_keys_json: str = "[]",
) -> dict[str, Any]:
    """Derive evidence-backed null, uniqueness, and domain rule candidates."""
    profile = json.loads(profile_json)
    declared_keys = set(json.loads(business_keys_json))
    row_count = int(profile.get("row_count", 0) or 0)
    candidates: list[dict[str, Any]] = []

    for column in profile.get("columns", []):
        name = column["name"]
        nulls = int(column.get("null_count", 0) or 0)
        distinct = int(column.get("distinct_count", 0) or 0)
        critical = bool(column.get("critical_candidate")) or name in declared_keys

        if critical:
            candidates.append({
                "rule_type": "NOT_NULL",
                "column_name": name,
                "severity_level": "CRITICAL",
                "current_status": "FAILING" if nulls else "PASSING",
                "evidence": (
                    f"Campo crítico con {nulls} nulos observados."
                    if nulls
                    else "Campo crítico sin nulos observados; proteger preventivamente."
                ),
                "confidence": 0.95 if name in declared_keys else 0.85,
            })

        if row_count and (name in declared_keys or distinct == row_count):
            duplicate_count = max(row_count - distinct, 0)
            candidates.append({
                "rule_type": "UNIQUE",
                "column_name": name,
                "severity_level": "CRITICAL" if name in declared_keys else "HIGH",
                "current_status": "FAILING" if duplicate_count else "PASSING",
                "evidence": (
                    f"Business key declarada; se estiman {duplicate_count} duplicados."
                    if name in declared_keys
                    else "La cardinalidad observada coincide con el total de filas."
                ),
                "confidence": 0.98 if name in declared_keys else 0.8,
            })

        if 0 < distinct <= 20 and not critical:
            candidates.append({
                "rule_type": "ALLOWED_VALUES",
                "column_name": name,
                "severity_level": "MEDIUM",
                "current_status": "NEEDS_VALUE_SAMPLE",
                "evidence": f"Dominio observado de baja cardinalidad: {distinct}.",
                "confidence": 0.7,
                "requires_value_sampling": True,
            })

    return {
        "table": profile.get("table"),
        "row_count": row_count,
        "business_key_candidates": profile.get("business_key_candidates", []),
        "critical_columns": profile.get("critical_columns", []),
        "candidates": candidates,
        "policy": "Toda propuesta requiere aprobación humana.",
    }




def validate_quality_nl_rule_proposal(
    columns_json: str,
    natural_rule: str,
    proposal_json: str,
) -> dict[str, Any]:
    """Validate one LLM-interpreted quality rule against schema and an executable whitelist."""
    columns = json.loads(columns_json)
    proposal = json.loads(proposal_json)
    if not isinstance(proposal, dict):
        raise ValueError("La propuesta QUALITY_NL debe ser un objeto JSON")

    natural_rule = natural_rule.strip()
    if not natural_rule:
        raise ValueError("QUALITY_NL requiere una regla natural no vacía")

    schema = {
        str(item.get("name") or item.get("source_column") or ""): str(
            item.get("type") or item.get("data_type") or "STRING"
        ).upper()
        for item in columns
        if isinstance(item, dict) and (item.get("name") or item.get("source_column"))
    }

    rule_type = str(proposal.get("rule_type") or "").upper().strip()
    if rule_type not in SUPPORTED_RULE_TYPES:
        raise ValueError(
            "Tipo de regla no soportado para QUALITY_NL: " + (rule_type or "VACIO")
        )

    raw_columns = proposal.get("columns")
    if not isinstance(raw_columns, list):
        single = proposal.get("column_name")
        raw_columns = [single] if single else []
    rule_columns = [str(value).strip() for value in raw_columns if str(value).strip()]
    if len(rule_columns) != 1:
        raise ValueError("QUALITY_NL soporta exactamente una columna por regla en este checkpoint")
    unknown = sorted(set(rule_columns) - set(schema))
    if unknown:
        raise ValueError(
            "La propuesta QUALITY_NL referencia columnas inexistentes: " + ", ".join(unknown)
        )

    column_name = rule_columns[0]
    column_type = schema[column_name]
    parameters = proposal.get("parameters") or proposal.get("rule_parameters") or {}
    if not isinstance(parameters, dict):
        raise ValueError("QUALITY_NL requiere parameters como objeto")

    numeric_types = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC", "DECIMAL"}
    string_types = {"STRING", "BYTES"}

    if rule_type == "ALLOWED_VALUES":
        allowed = parameters.get("allowed_values")
        if not isinstance(allowed, list) or not allowed:
            raise ValueError("ALLOWED_VALUES requiere parameters.allowed_values no vacío")
    elif rule_type == "VALUE_RANGE":
        if column_type not in numeric_types:
            raise ValueError("VALUE_RANGE solo admite columnas numéricas")
        if parameters.get("min") is None and parameters.get("max") is None:
            raise ValueError("VALUE_RANGE requiere min y/o max")
        min_value = parameters.get("min")
        max_value = parameters.get("max")
        if min_value is not None and max_value is not None and float(min_value) > float(max_value):
            raise ValueError("VALUE_RANGE requiere min <= max")
    elif rule_type == "REGEX":
        if column_type not in string_types:
            raise ValueError("REGEX solo admite columnas STRING/BYTES")
        pattern = parameters.get("pattern")
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError("REGEX requiere parameters.pattern")

    dimension_default = {
        "NOT_NULL": "COMPLETENESS",
        "UNIQUE": "UNIQUENESS",
        "ALLOWED_VALUES": "VALIDITY",
        "VALUE_RANGE": "VALIDITY",
        "REGEX": "VALIDITY",
    }[rule_type]
    runtime_default = "BLOCK_LOAD" if rule_type in {"NOT_NULL", "UNIQUE"} else "WARN"
    warning_threshold = float(proposal.get("warning_threshold", 0))
    critical_threshold = float(proposal.get("critical_threshold", 1))
    if critical_threshold < warning_threshold:
        raise ValueError("critical_threshold debe ser mayor o igual que warning_threshold")

    name = str(proposal.get("name") or f"{column_name}_{rule_type.lower()}").strip()
    rule = GovernedQualityRule.model_validate({
        "rule_id": str(proposal.get("rule_id") or f"qr_nl_{column_name}_{rule_type.lower()}"),
        "name": name,
        "version": 1,
        "dimension": str(proposal.get("dimension") or dimension_default).upper(),
        "rule_type": rule_type,
        "columns": rule_columns,
        "parameters": parameters,
        "expression": None,
        "warning_threshold": warning_threshold,
        "critical_threshold": critical_threshold,
        "severity": str(proposal.get("severity") or proposal.get("severity_level") or "MEDIUM").upper(),
        "runtime_action": str(proposal.get("runtime_action") or runtime_default).upper(),
        "evidence": str(proposal.get("evidence") or "Regla interpretada desde lenguaje natural y validada contra el schema."),
        "confidence": float(proposal.get("confidence", 0.8)),
        "source": "DERIVED_NL",
        "status": "PENDING_APPROVAL",
        "active": True,
        "approved_by": None,
        "approved_at": None,
        "metadata": {
            **(proposal.get("metadata") if isinstance(proposal.get("metadata"), dict) else {}),
            "natural_rule": natural_rule,
            "validation_authority": "DETERMINISTIC_TOOL",
        },
    })

    if rule_type == "NOT_NULL":
        interpretation = f"Entendí tu regla así: {column_name} no debe contener valores nulos."
    elif rule_type == "UNIQUE":
        interpretation = f"Entendí tu regla así: {column_name} debe ser único."
    elif rule_type == "ALLOWED_VALUES":
        interpretation = (
            f"Entendí tu regla así: {column_name} solo puede tomar los valores "
            f"{parameters['allowed_values']}."
        )
    elif rule_type == "VALUE_RANGE":
        interpretation = (
            f"Entendí tu regla así: {column_name} debe cumplir el rango "
            f"min={parameters.get('min')} max={parameters.get('max')}."
        )
    else:
        interpretation = (
            f"Entendí tu regla así: {column_name} debe cumplir el patrón "
            f"{parameters.get('pattern')}."
        )

    return {
        "valid": True,
        "proposal": rule.model_dump(mode="json"),
        "interpretation": interpretation,
        "human_confirmation_required": True,
        "natural_rule": natural_rule,
        "policy": "El texto natural no es ejecutable; la propuesta estructurada requiere confirmación humana.",
    }


def recommend_column_mappings(
    columns_json: str,
    profile_json: str = "{}",
) -> dict[str, Any]:
    """Build editable mapping recommendations from the selected table contract."""
    columns = json.loads(columns_json)
    profile = json.loads(profile_json or "{}")
    profile_by_name = {
        str(item.get("name")): item
        for item in profile.get("columns", [])
        if isinstance(item, dict) and item.get("name")
    }
    mappings: list[dict[str, Any]] = []

    for column in columns:
        name = str(column.get("name") or column.get("source_column") or "")
        if not name:
            continue
        data_type = str(column.get("type") or column.get("data_type") or "STRING").upper()
        normalized = name.lower()
        transformation = "DIRECT"
        confidence = 0.99
        reason = "Mapeo directo por coincidencia exacta de nombre y tipo."
        risk = None
        requires_approval = False

        if data_type == "STRING" and (
            normalized.endswith("_id") or normalized in {"id", "codigo", "code"}
        ):
            transformation = "TRIM"
            confidence = 0.96
            reason = "Identificador textual: TRIM evita espacios laterales en Silver."
        elif data_type == "STRING" and any(
            token in normalized for token in ("tipo", "estado", "status", "categoria")
        ):
            transformation = "UPPER"
            confidence = 0.84
            reason = "Atributo categorico: UPPER propone normalizacion consistente."
            risk = "Puede alterar valores sensibles a mayusculas/minusculas."
            requires_approval = True

        metric = profile_by_name.get(name, {})
        mappings.append({
            "source_column": name,
            "target_column": name,
            "target_type": data_type,
            "nullable": str(column.get("mode") or "NULLABLE").upper() != "REQUIRED",
            "include": True,
            "transformation": {
                "type": transformation,
                "source_columns": [name],
                "parameters": {},
            },
            "confidence": confidence,
            "reason": reason,
            "risk": risk,
            "requires_approval": requires_approval,
            "profile_evidence": {
                "null_count": metric.get("null_count"),
                "distinct_count": metric.get("distinct_count"),
            } if metric else None,
        })

    return {
        "table": profile.get("table"),
        "columns": mappings,
        "recommendation_engine": "gemini-adk-with-deterministic-evidence",
        "requires_human_approval": True,
        "policy": "Toda recomendacion es editable y requiere confirmacion humana.",
    }



def validate_derived_nl_mapping_proposal(
    columns_json: str,
    natural_rule: str,
    proposal_json: str,
) -> dict[str, Any]:
    """Validate a Gemini-derived mapping against schema and executable whitelist."""
    columns = json.loads(columns_json)
    proposal = json.loads(proposal_json)
    if not isinstance(proposal, dict):
        raise ValueError("La propuesta DERIVED_NL debe ser un objeto JSON")

    natural_rule = natural_rule.strip()
    if not natural_rule:
        raise ValueError("DERIVED_NL requiere una regla natural no vacía")

    schema = {
        str(item.get("name") or item.get("source_column") or ""): str(
            item.get("type") or item.get("data_type") or "STRING"
        ).upper()
        for item in columns
        if isinstance(item, dict) and (item.get("name") or item.get("source_column"))
    }
    transformation_raw = proposal.get("transformation")
    if not isinstance(transformation_raw, dict):
        raise ValueError("DERIVED_NL requiere transformation estructurada")

    transformation = MappingTransformation.model_validate(transformation_raw)
    source_columns = list(transformation.source_columns)
    unknown = sorted(set(source_columns) - set(schema))
    if unknown:
        raise ValueError(
            "La propuesta DERIVED_NL referencia columnas inexistentes: " + ", ".join(unknown)
        )

    numeric_types = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC"}
    if transformation.type == TransformationType.ARITHMETIC:
        non_numeric = [name for name in source_columns if schema.get(name) not in numeric_types]
        if non_numeric:
            raise ValueError(
                "ARITHMETIC solo admite columnas numéricas: " + ", ".join(non_numeric)
            )

    target_column = str(proposal.get("target_column") or "").strip()
    target_type = str(proposal.get("target_type") or "").strip().upper()
    if not target_column or not target_type:
        raise ValueError("DERIVED_NL requiere target_column y target_type")

    column = IntelligentMappingColumn(
        source_column=source_columns[0] if source_columns else None,
        target_column=target_column,
        target_type=target_type,
        nullable=bool(proposal.get("nullable", True)),
        include=True,
        transformation=transformation,
        confidence=float(proposal.get("confidence", 0.8)),
        reason=str(proposal.get("reason") or "Interpretación DERIVED_NL validada contra el schema confirmado."),
        risk=str(proposal.get("risk") or "La derivación requiere aprobación humana antes de persistirse."),
        requires_approval=True,
    )
    compiled_preview = compile_pyspark_expression(column)

    symbol = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}.get(
        str(transformation.parameters.get("operator") or "").upper()
    )
    scalar = transformation.parameters.get("scalar")
    if transformation.type == TransformationType.ARITHMETIC and len(source_columns) == 1 and symbol and scalar is not None:
        interpretation = (
            f"Entendí tu regla así: {target_column} = "
            f"{source_columns[0]} {symbol} {scalar}."
        )
    elif transformation.type == TransformationType.ARITHMETIC and len(source_columns) == 2 and symbol:
        interpretation = (
            f"Entendí tu regla así: {target_column} = "
            f"{source_columns[0]} {symbol} {source_columns[1]}."
        )
    else:
        interpretation = (
            f"Entendí tu regla así: {target_column} se derivará con "
            f"{transformation.type.value} usando {', '.join(source_columns)}."
        )

    normalized = {
        "source_column": source_columns[0] if source_columns else None,
        "source_columns": source_columns,
        "target_column": target_column,
        "target_type": target_type,
        "nullable": column.nullable,
        "include": True,
        "transformation": transformation.model_dump(mode="json"),
        "derivation_mode": "DERIVED_NL",
        "natural_rule": natural_rule,
        "confidence": column.confidence,
        "reason": column.reason,
        "risk": column.risk,
        "requires_approval": True,
    }
    return {
        "valid": True,
        "proposal": normalized,
        "interpretation": interpretation,
        "compiled_preview": compiled_preview,
        "human_confirmation_required": True,
        "policy": "La propuesta no se persiste hasta confirmación humana explícita.",
    }


def validate_business_rules(
    schema_json: str,
    rules_json: str,
) -> dict[str, Any]:
    """Validate rule types, parameters, and column references."""
    schema = json.loads(schema_json)
    rules = json.loads(rules_json)
    columns = {
        item["name"]: item.get("type")
        for item in schema.get("columns", schema)
        if isinstance(item, dict) and item.get("name")
    }
    findings: list[dict[str, Any]] = []

    for index, rule in enumerate(rules, start=1):
        rule_type = str(rule.get("rule_type") or "").upper()
        column = rule.get("column_name")
        error = None
        if rule_type not in SUPPORTED_RULE_TYPES:
            error = f"Tipo no soportado: {rule_type or '<empty>'}"
        elif column not in columns:
            error = f"Columna inexistente: {column}"
        else:
            params = rule.get("rule_parameters") or {}
            if rule_type == "ALLOWED_VALUES" and not params.get("allowed_values"):
                error = "ALLOWED_VALUES requiere allowed_values."
            elif rule_type == "VALUE_RANGE" and not any(
                key in params for key in ("min_value", "max_value")
            ):
                error = "VALUE_RANGE requiere min_value o max_value."

        findings.append({
            "rule": index,
            "status": "ERROR" if error else "PASS",
            "message": error or "Regla válida.",
        })

    return {
        "valid": all(item["status"] == "PASS" for item in findings),
        "rule_count": len(rules),
        "findings": findings,
    }


def build_notebook_blueprint(spec_json: str) -> dict[str, Any]:
    """Build a governed notebook blueprint from an approved Silver spec."""
    spec = json.loads(spec_json)
    required = [
        "source_project",
        "source_dataset",
        "source_table",
        "target_project",
        "target_dataset",
        "target_table",
        "load_strategy",
        "columns",
    ]
    missing = [field for field in required if not spec.get(field)]
    if missing:
        return {"valid": False, "missing_fields": missing}

    strategy = spec["load_strategy"]
    keys = strategy.get("business_keys") or []
    if strategy.get("type") in {"MERGE", "CDC"} and not keys:
        return {
            "valid": False,
            "missing_fields": ["load_strategy.business_keys"],
        }

    return {
        "valid": True,
        "notebook_format": "JUPYTER_IPYNB_V4",
        "source": ".".join([
            spec["source_project"],
            spec["source_dataset"],
            spec["source_table"],
        ]),
        "target": ".".join([
            spec["target_project"],
            spec["target_dataset"],
            spec["target_table"],
        ]),
        "load_strategy": strategy,
        "quality_rules": spec.get("quality_rules", []),
        "cells": [
            "Configuración y SparkSession",
            "Lectura BigQuery Bronze",
            "Mapping y transformaciones aprobadas",
            "Quality gates y cuarentena",
            f"Escritura idempotente {strategy.get('type')}",
            "Validación BigQuery post-ejecución",
            "Evidencia y lineage",
        ],
        "generator": "silver_notebook_generator_agent",
    }
