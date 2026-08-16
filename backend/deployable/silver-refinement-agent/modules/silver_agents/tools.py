from __future__ import annotations

import json
from typing import Any

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


def quality_rule_evidence(profile_json: str) -> dict[str, Any]:
    """Derive evidence-backed rule candidates from a table profile."""
    profile = json.loads(profile_json)
    row_count = int(profile.get("row_count", 0) or 0)
    candidates: list[dict[str, Any]] = []
    for column in profile.get("columns", []):
        name = column["name"]
        nulls = int(column.get("null_count", 0) or 0)
        distinct = int(column.get("distinct_count", 0) or 0)
        if row_count and nulls == 0:
            candidates.append({
                "rule_type": "NOT_NULL",
                "column_name": name,
                "evidence": "No se observaron nulos.",
                "confidence": 0.85,
            })
        if row_count and distinct == row_count:
            candidates.append({
                "rule_type": "UNIQUE",
                "column_name": name,
                "evidence": "La cardinalidad coincide con el total de filas.",
                "confidence": 0.8,
            })
        if 0 < distinct <= 20:
            candidates.append({
                "rule_type": "ALLOWED_VALUES",
                "column_name": name,
                "evidence": f"Dominio observado de baja cardinalidad: {distinct}.",
                "confidence": 0.7,
                "requires_value_sampling": True,
            })
    return {
        "table": profile.get("table"),
        "row_count": row_count,
        "candidates": candidates,
        "policy": "Toda propuesta requiere aprobación humana.",
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
