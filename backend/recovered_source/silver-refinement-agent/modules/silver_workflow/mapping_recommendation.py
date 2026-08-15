from __future__ import annotations

from pydantic import BaseModel, Field

from modules.silver_intelligent_mapping.models import (
    IntelligentMappingColumn,
    LoadStrategy,
    LoadStrategyType,
    MappingTransformation,
    PartitioningDesign,
    PhysicalDesign,
    TransformationType,
)

from .models import SchemaColumnEvidence, SilverWorkflowRecord


class GenerateMappingRecommendationRequest(BaseModel):
    expected_version: int = Field(ge=1)
    target_project: str = Field(min_length=1, max_length=300)
    target_dataset: str = Field(min_length=1, max_length=300)
    target_table: str = Field(min_length=1, max_length=300)


class MappingRecommendationResponse(BaseModel):
    workflow_id: str
    source_workflow_version: int = Field(ge=1)
    target_project: str
    target_dataset: str
    target_table: str
    columns: list[IntelligentMappingColumn]
    load_strategy: LoadStrategy
    physical_design: PhysicalDesign
    recommendation_engine: str = "deterministic-v1"
    requires_human_approval: bool = True


_STRING_TYPES = {"STRING"}
_TEMPORAL_TYPES = {"DATE", "DATETIME", "TIMESTAMP"}
_NUMERIC_TYPES = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC"}


def _transformation_for(column: SchemaColumnEvidence) -> tuple[MappingTransformation, float, str, str | None, bool]:
    name = column.name.lower()
    data_type = column.data_type.upper()

    if data_type in _STRING_TYPES and (name.endswith("_id") or name in {"id", "codigo", "code"}):
        return (
            MappingTransformation(type=TransformationType.TRIM, source_columns=[column.name]),
            0.96,
            "Identificador textual: se recomienda eliminar espacios laterales antes de persistir Silver.",
            None,
            False,
        )
    if data_type in _STRING_TYPES and any(token in name for token in ("tipo", "estado", "status", "categoria")):
        return (
            MappingTransformation(type=TransformationType.UPPER, source_columns=[column.name]),
            0.84,
            "Atributo categórico textual: se recomienda normalizar a mayúsculas.",
            "La normalización puede alterar valores sensibles a mayúsculas y minúsculas.",
            True,
        )
    if data_type in _NUMERIC_TYPES and any(token in name for token in ("monto", "importe", "amount", "saldo", "total")):
        return (
            MappingTransformation(type=TransformationType.DIRECT, source_columns=[column.name]),
            0.91,
            "Métrica numérica: se conserva el valor original y se deja la validación de rango a calidad.",
            None,
            False,
        )
    return (
        MappingTransformation(type=TransformationType.DIRECT, source_columns=[column.name]),
        0.99,
        "Mapeo directo por coincidencia exacta de nombre y tipo.",
        None,
        False,
    )


def _choose_watermark(columns: list[SchemaColumnEvidence]) -> str | None:
    priority = ("fecha_carga", "updated_at", "update_timestamp", "fecha_actualizacion", "created_at", "fecha_creacion")
    by_name = {column.name.lower(): column for column in columns}
    for candidate in priority:
        column = by_name.get(candidate)
        if column and column.data_type.upper() in _TEMPORAL_TYPES:
            return column.name
    temporal = [column.name for column in columns if column.data_type.upper() in _TEMPORAL_TYPES]
    return temporal[0] if temporal else None


def _choose_partition_column(columns: list[SchemaColumnEvidence], watermark: str | None) -> str | None:
    priority = ("fecha_movimiento", "fecha_evento", "event_date", "transaction_date")
    by_name = {column.name.lower(): column for column in columns}
    for candidate in priority:
        column = by_name.get(candidate)
        if column and column.data_type.upper() in _TEMPORAL_TYPES:
            return column.name
    return watermark


def _choose_business_key(columns: list[SchemaColumnEvidence]) -> str | None:
    exact = [column.name for column in columns if column.name.lower() in {"id", "movimiento_id", "siniestro_id", "transaction_id"}]
    if exact:
        return exact[0]
    ids = [column.name for column in columns if column.name.lower().endswith("_id")]
    return ids[0] if ids else None


def build_mapping_recommendation(
    workflow: SilverWorkflowRecord,
    request: GenerateMappingRecommendationRequest,
) -> MappingRecommendationResponse:
    if workflow.version != request.expected_version:
        raise ValueError("La versión del workflow cambió; recargue antes de generar recomendaciones")
    if not workflow.source_confirmed or workflow.schema_context is None:
        raise ValueError("La fuente y el esquema deben estar confirmados antes de recomendar el mapping")

    columns = workflow.schema_context.columns
    recommendations: list[IntelligentMappingColumn] = []
    for column in columns:
        transformation, confidence, reason, risk, requires_approval = _transformation_for(column)
        recommendations.append(
            IntelligentMappingColumn(
                source_column=column.name,
                target_column=column.name,
                target_type=column.data_type.upper(),
                nullable=column.nullable,
                include=True,
                transformation=transformation,
                confidence=confidence,
                reason=reason,
                risk=risk,
                requires_approval=requires_approval,
            )
        )

    watermark = _choose_watermark(columns)
    business_key = _choose_business_key(columns)
    partition_column = _choose_partition_column(columns, watermark)

    if watermark:
        load_strategy = LoadStrategy(
            type=LoadStrategyType.INCREMENTAL_WATERMARK,
            watermark_column=watermark,
            tie_breaker_column=business_key,
            business_keys=[business_key] if business_key else [],
            lookback_value=1,
            lookback_unit="DAY",
            late_arrival_policy="REPROCESS_LOOKBACK_WINDOW",
        )
    else:
        load_strategy = LoadStrategy(type=LoadStrategyType.FULL)

    clustering = [
        column.name
        for column in columns
        if column.name != partition_column
        and (column.name.lower().endswith("_id") or "tipo" in column.name.lower())
    ][:4]

    physical_design = PhysicalDesign(
        partitioning=PartitioningDesign(
            enabled=partition_column is not None,
            column=partition_column,
        ),
        clustering_columns=clustering,
    )

    return MappingRecommendationResponse(
        workflow_id=workflow.workflow_id,
        source_workflow_version=workflow.version,
        target_project=request.target_project,
        target_dataset=request.target_dataset,
        target_table=request.target_table,
        columns=recommendations,
        load_strategy=load_strategy,
        physical_design=physical_design,
    )
