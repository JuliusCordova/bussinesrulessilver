from __future__ import annotations

import json
import re
from typing import Any

from modules.silver_intelligent_mapping.models import (
    IntelligentMappingColumn,
    LoadStrategy,
    LoadStrategyType,
    MappingTransformation,
    PhysicalDesign,
    TransformationType,
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")
_SPARK_TYPES = {
    "STRING": "string",
    "BYTES": "binary",
    "INT64": "long",
    "INTEGER": "long",
    "FLOAT64": "double",
    "FLOAT": "double",
    "NUMERIC": "decimal(38,9)",
    "BIGNUMERIC": "decimal(76,38)",
    "BOOL": "boolean",
    "BOOLEAN": "boolean",
    "DATE": "date",
    "DATETIME": "timestamp",
    "TIME": "string",
    "TIMESTAMP": "timestamp",
    "JSON": "string",
    "GEOGRAPHY": "string",
}


def _identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} contiene caracteres no permitidos: {value}")
    return value


def _spark_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in _SPARK_TYPES:
        raise ValueError(f"Tipo no soportado para PySpark: {value}")
    return _SPARK_TYPES[normalized]


def _literal(value: Any) -> str:
    return f"F.lit({value!r})"


def compile_pyspark_expression(column: IntelligentMappingColumn) -> str:
    transformation = column.transformation
    source = column.source_column or (
        transformation.source_columns[0] if transformation.source_columns else None
    )
    target = _identifier(column.target_column, "target_column")
    spark_type = _spark_type(column.target_type)

    if transformation.type == TransformationType.EXCLUDE or not column.include:
        raise ValueError(f"La columna {target} está excluida")
    if source is None and transformation.type not in {TransformationType.CONCAT, TransformationType.ARITHMETIC}:
        raise ValueError(f"La columna {target} no tiene fuente")
    if source is not None:
        source = _identifier(source, "source_column")

    if transformation.type == TransformationType.DIRECT:
        expression = f'F.col("{source}")'
    elif transformation.type == TransformationType.TRIM:
        expression = f'F.trim(F.col("{source}"))'
    elif transformation.type == TransformationType.COALESCE:
        expression = (
            f'F.coalesce(F.col("{source}"), '
            f'{_literal(transformation.parameters["default_value"])})'
        )
    elif transformation.type == TransformationType.CAST:
        cast_type = _spark_type(str(transformation.parameters["target_type"]))
        expression = f'F.col("{source}").cast("{cast_type}")'
    elif transformation.type == TransformationType.UPPER:
        expression = f'F.upper(F.col("{source}"))'
    elif transformation.type == TransformationType.LOWER:
        expression = f'F.lower(F.col("{source}"))'
    elif transformation.type == TransformationType.CONCAT:
        separator = transformation.parameters.get("separator", "")
        sources = ", ".join(
            f'F.col("{_identifier(item, "source_column")}")'
            for item in transformation.source_columns
        )
        expression = f'F.concat_ws({separator!r}, {sources})'
    elif transformation.type == TransformationType.DATE_PARSE:
        fmt = transformation.parameters["format"]
        expression = f'F.to_date(F.col("{source}"), {fmt!r})'
    elif transformation.type == TransformationType.ARITHMETIC:
        operator = str(transformation.parameters["operator"]).upper()
        symbols = {"ADD": "+", "SUBTRACT": "-", "MULTIPLY": "*", "DIVIDE": "/"}
        left = _identifier(transformation.source_columns[0], "source_column")
        right = _identifier(transformation.source_columns[1], "source_column")
        expression = f'(F.col("{left}") {symbols[operator]} F.col("{right}"))'
    else:
        raise ValueError(f"Transformación no soportada: {transformation.type.value}")

    if transformation.type != TransformationType.CAST:
        expression = f'{expression}.cast("{spark_type}")'
    return f'{expression}.alias("{target}")'


def compile_select(columns: list[IntelligentMappingColumn]) -> str:
    expressions = [
        compile_pyspark_expression(column)
        for column in columns
        if column.include and column.transformation.type != TransformationType.EXCLUDE
    ]
    if not expressions:
        raise ValueError("El mapping no contiene columnas incluidas")
    return "df.select(\n        " + ",\n        ".join(expressions) + "\n    )"


def compile_write_mode(strategy: LoadStrategy) -> str:
    if strategy.type == LoadStrategyType.FULL:
        return "overwrite"
    if strategy.type in {LoadStrategyType.APPEND, LoadStrategyType.INCREMENTAL_WATERMARK}:
        return "append"
    if strategy.type in {LoadStrategyType.MERGE, LoadStrategyType.CDC}:
        return "merge"
    raise ValueError(f"Estrategia no soportada: {strategy.type.value}")


def compile_incremental_filter(strategy: LoadStrategy) -> str | None:
    if strategy.type != LoadStrategyType.INCREMENTAL_WATERMARK:
        return None
    return (
        f'F.col("{_identifier(strategy.watermark_column or "", "watermark_column")}") > '
        'F.lit(runtime_watermark)'
    )


def compile_bigquery_ddl(
    *,
    project_id: str,
    dataset_id: str,
    table_id: str,
    columns: list[IntelligentMappingColumn],
    physical_design: PhysicalDesign,
) -> str:
    ddl_columns = []
    included_names: set[str] = set()
    included_types: dict[str, str] = {}

    for column in columns:
        if not column.include or column.transformation.type == TransformationType.EXCLUDE:
            continue

        target = _identifier(column.target_column, "target_column")
        target_type = column.target_type.strip().upper()

        included_names.add(target)
        included_types[target] = target_type

        nullable = "" if column.nullable else " NOT NULL"
        ddl_columns.append(
            f"  `{target}` {target_type}{nullable}"
        )

    if not ddl_columns:
        raise ValueError("El DDL requiere al menos una columna")

    statement = (
        f"CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.{table_id}` (\n"
        + ",\n".join(ddl_columns)
        + "\n)"
    )

    partition = physical_design.partitioning
    if partition.enabled:
        partition_column = _identifier(
            partition.column or "",
            "partition_column",
        )

        if partition_column not in included_names:
            raise ValueError(
                "La columna de partición debe estar incluida en el mapping"
            )

        partition_type = included_types[partition_column]
        granularity = partition.granularity.value

        if partition_type == "TIMESTAMP":
            partition_expression = (
                f"TIMESTAMP_TRUNC(`{partition_column}`, {granularity})"
            )

        elif partition_type == "DATETIME":
            partition_expression = (
                f"DATETIME_TRUNC(`{partition_column}`, {granularity})"
            )

        elif partition_type == "DATE":
            if granularity == "HOUR":
                raise ValueError(
                    "Una columna DATE no soporta particionamiento HOUR"
                )

            if granularity == "DAY":
                # Preserve the existing DDL contract for DATE/DAY while
                # TIMESTAMP and DATETIME use explicit TRUNC expressions.
                partition_expression = partition_column
            else:
                partition_expression = (
                    f"DATE_TRUNC(`{partition_column}`, {granularity})"
                )

        else:
            raise ValueError(
                "La columna de partición debe ser DATE, DATETIME o TIMESTAMP"
            )

        statement += f"\nPARTITION BY {partition_expression}"
    if physical_design.clustering_columns:
        clusters = [
            _identifier(column, "clustering_column")
            for column in physical_design.clustering_columns
        ]
        missing = [column for column in clusters if column not in included_names]
        if missing:
            raise ValueError(
                "Las columnas de clustering deben estar incluidas en el mapping: "
                + ", ".join(missing)
            )
        statement += "\nCLUSTER BY " + ", ".join(clusters)
    return statement + ";\n"


def recommendation_payload(
    *,
    source_column: str,
    target_column: str,
    target_type: str,
    transformation: MappingTransformation,
    confidence: float,
    reason: str,
    risk: str | None = None,
    requires_approval: bool = False,
) -> dict[str, Any]:
    return {
        "source_column": source_column,
        "target_column": target_column,
        "target_type": target_type,
        "transformation": transformation.model_dump(mode="json"),
        "confidence": confidence,
        "reason": reason,
        "risk": risk,
        "requires_approval": requires_approval,
    }


def serialize_contract(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
