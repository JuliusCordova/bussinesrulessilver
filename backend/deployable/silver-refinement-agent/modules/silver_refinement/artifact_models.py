from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from modules.silver_intelligent_mapping.models import (
    LoadStrategy,
    MappingTransformation,
    PhysicalDesign,
)


class ArtifactType(str, Enum):
    SILVER_DDL = "SILVER_DDL"
    SPECIFICATION_JSON = "SPECIFICATION_JSON"
    MAPPING_JSON = "MAPPING_JSON"
    TRANSFORMATIONS_JSON = "TRANSFORMATIONS_JSON"
    README = "README"
    MANIFEST_JSON = "MANIFEST_JSON"
    PYSPARK_SCRIPT = "PYSPARK_SCRIPT"
    NOTEBOOK = "NOTEBOOK"
    ARTIFACT_PACKAGE = "ARTIFACT_PACKAGE"


class ArtifactStatus(str, Enum):
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class SilverColumn(BaseModel):
    name: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    nullable: bool = True
    description: str | None = None
    source_column: str | None = None
    source_columns: list[str] = Field(default_factory=list)
    transformation: MappingTransformation | str | None = None
    derivation_mode: str | None = None
    natural_rule: str | None = None
    include: bool = True
    confidence: float | None = Field(default=None, ge=0, le=1)
    recommendation_reason: str | None = None
    recommendation_risk: str | None = None
    requires_approval: bool = False

    def normalized_transformation(self) -> MappingTransformation:
        if isinstance(self.transformation, MappingTransformation):
            return self.transformation

        legacy = (self.transformation or "DIRECT").strip().upper()
        aliases = {
            "TRIM_CAST": "TRIM",
        }
        legacy = aliases.get(legacy, legacy)

        payload: dict[str, Any] = {"type": legacy}
        source = self.source_column or self.name
        payload["source_columns"] = self.source_columns or [source]

        # The legacy CAST contract inferred its target type from SilverColumn.data_type.
        # Preserve that behavior while the frontend migrates to typed transformations.
        if legacy == "CAST":
            payload["parameters"] = {"target_type": self.data_type}

        return MappingTransformation.model_validate(payload)


class GenerateSilverDDLRequest(BaseModel):
    mapping_version: int = Field(ge=1)
    target_project: str = Field(min_length=1)
    target_dataset: str = Field(min_length=1)
    target_table: str = Field(min_length=1)
    columns: list[SilverColumn] = Field(min_length=1)
    load_strategy: LoadStrategy = Field(default_factory=LoadStrategy)
    physical_design: PhysicalDesign = Field(default_factory=PhysicalDesign)
    generated_by: str = "system"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerateArtifactPackageRequest(GenerateSilverDDLRequest):
    source_project: str = Field(min_length=1)
    source_dataset: str = Field(min_length=1)
    source_table: str = Field(min_length=1)
    specification: dict[str, Any] = Field(default_factory=dict)
    quality_rules: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def promote_legacy_specification_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        specification = data.get("specification") or {}
        if "load_strategy" not in data and specification.get("load_strategy"):
            raw = specification["load_strategy"]
            data["load_strategy"] = {"type": raw} if isinstance(raw, str) else raw
        if "physical_design" not in data and specification.get("physical_design"):
            data["physical_design"] = specification["physical_design"]
        return data


class ArtifactRecord(BaseModel):
    artifact_id: str
    spec_id: str
    mapping_version: int
    artifact_type: ArtifactType
    artifact_name: str
    artifact_version: int
    generation_status: ArtifactStatus
    validation_status: str | None = None
    content_text: str | None = None
    storage_uri: str | None = None
    content_hash: str | None = None
    template_name: str | None = None
    template_version: str | None = None
    generated_by: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by: str | None = None
    approved_at: datetime | None = None
    is_current: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactPackageResponse(BaseModel):
    spec_id: str
    mapping_version: int
    artifacts: list[ArtifactRecord]
