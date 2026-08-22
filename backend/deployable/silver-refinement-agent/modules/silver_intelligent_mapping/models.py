from __future__ import annotations

from datetime import datetime

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class TransformationType(str, Enum):
    DIRECT = "DIRECT"
    TRIM = "TRIM"
    COALESCE = "COALESCE"
    CAST = "CAST"
    UPPER = "UPPER"
    LOWER = "LOWER"
    CONCAT = "CONCAT"
    DATE_PARSE = "DATE_PARSE"
    ARITHMETIC = "ARITHMETIC"
    EXCLUDE = "EXCLUDE"


class LoadStrategyType(str, Enum):
    FULL = "FULL"
    APPEND = "APPEND"
    INCREMENTAL_WATERMARK = "INCREMENTAL_WATERMARK"
    MERGE = "MERGE"
    CDC = "CDC"


class PartitionGranularity(str, Enum):
    DAY = "DAY"
    MONTH = "MONTH"
    YEAR = "YEAR"
    HOUR = "HOUR"


class MappingTransformation(BaseModel):
    type: TransformationType = TransformationType.DIRECT
    source_columns: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_parameters(self) -> "MappingTransformation":
        if self.type == TransformationType.COALESCE and "default_value" not in self.parameters:
            raise ValueError("COALESCE requiere parameters.default_value")
        if self.type == TransformationType.CAST and not self.parameters.get("target_type"):
            raise ValueError("CAST requiere parameters.target_type")
        if self.type == TransformationType.CONCAT and len(self.source_columns) < 2:
            raise ValueError("CONCAT requiere al menos dos source_columns")
        if self.type == TransformationType.DATE_PARSE and not self.parameters.get("format"):
            raise ValueError("DATE_PARSE requiere parameters.format")
        if self.type == TransformationType.ARITHMETIC:
            operator = str(self.parameters.get("operator") or "").upper()
            if operator not in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}:
                raise ValueError("ARITHMETIC requiere operator ADD, SUBTRACT, MULTIPLY o DIVIDE")
            scalar = self.parameters.get("scalar")
            has_scalar = scalar is not None
            if has_scalar and (isinstance(scalar, bool) or not isinstance(scalar, (int, float))):
                raise ValueError("ARITHMETIC parameters.scalar debe ser numérico")
            if has_scalar:
                if len(self.source_columns) != 1:
                    raise ValueError("ARITHMETIC con scalar requiere exactamente un source_column")
            elif len(self.source_columns) != 2:
                raise ValueError("ARITHMETIC requiere dos source_columns o un source_column más parameters.scalar")
        return self


class IntelligentMappingColumn(BaseModel):
    source_column: str | None = Field(default=None, max_length=300)
    target_column: str = Field(min_length=1, max_length=300)
    target_type: str = Field(min_length=1, max_length=200)
    nullable: bool = True
    include: bool = True
    transformation: MappingTransformation = Field(default_factory=MappingTransformation)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = Field(default=None, max_length=4000)
    risk: str | None = Field(default=None, max_length=4000)
    requires_approval: bool = False

    @model_validator(mode="after")
    def validate_source(self) -> "IntelligentMappingColumn":
        if self.include and self.transformation.type != TransformationType.EXCLUDE:
            if not self.source_column and not self.transformation.source_columns:
                raise ValueError("El mapping incluido requiere source_column o source_columns")
        return self


class LoadStrategy(BaseModel):
    type: LoadStrategyType = LoadStrategyType.FULL
    watermark_column: str | None = Field(default=None, max_length=300)
    initial_watermark: datetime | None = None
    tie_breaker_column: str | None = Field(default=None, max_length=300)
    business_keys: list[str] = Field(default_factory=list)
    sequence_column: str | None = Field(default=None, max_length=300)
    lookback_value: int | None = Field(default=None, ge=0)
    lookback_unit: str | None = Field(default=None, max_length=50)
    late_arrival_policy: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_strategy(self) -> "LoadStrategy":
        if self.type == LoadStrategyType.INCREMENTAL_WATERMARK and not self.watermark_column:
            raise ValueError("INCREMENTAL_WATERMARK requiere watermark_column")
        if self.initial_watermark is not None and (
            self.initial_watermark.tzinfo is None
            or self.initial_watermark.utcoffset() is None
        ):
            raise ValueError("initial_watermark debe incluir zona horaria")
        if self.type == LoadStrategyType.MERGE and not self.business_keys:
            raise ValueError("MERGE requiere business_keys")
        if self.type == LoadStrategyType.CDC and not self.business_keys:
            raise ValueError("CDC requiere business_keys")
        return self


class PartitioningDesign(BaseModel):
    enabled: bool = False
    column: str | None = Field(default=None, max_length=300)
    granularity: PartitionGranularity = PartitionGranularity.DAY

    @model_validator(mode="after")
    def validate_partitioning(self) -> "PartitioningDesign":
        if self.enabled and not self.column:
            raise ValueError("El particionamiento habilitado requiere column")
        return self


class PhysicalDesign(BaseModel):
    partitioning: PartitioningDesign = Field(default_factory=PartitioningDesign)
    clustering_columns: list[str] = Field(default_factory=list, max_length=4)


class IntelligentSilverSpecification(BaseModel):
    mapping_version: int = Field(ge=1)
    columns: list[IntelligentMappingColumn] = Field(min_length=1)
    load_strategy: LoadStrategy = Field(default_factory=LoadStrategy)
    physical_design: PhysicalDesign = Field(default_factory=PhysicalDesign)

    @model_validator(mode="after")
    def validate_unique_targets(self) -> "IntelligentSilverSpecification":
        targets = [column.target_column for column in self.columns if column.include]
        if len(targets) != len(set(targets)):
            raise ValueError("Cada columna destino incluida debe ser única")
        return self
