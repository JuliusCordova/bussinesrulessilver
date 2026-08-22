from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class WorkflowStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowAction(str, Enum):
    CONFIRM_SOURCE = "CONFIRM_SOURCE"
    DEFINE_BUSINESS_RULES = "DEFINE_BUSINESS_RULES"
    GENERATE_BUSINESS_RULES = "GENERATE_BUSINESS_RULES"
    CONFIRM_BUSINESS_RULES = "CONFIRM_BUSINESS_RULES"
    REVIEW_MAPPING = "REVIEW_MAPPING"
    REVIEW_QUALITY = "REVIEW_QUALITY"
    GENERATE_ARTIFACTS = "GENERATE_ARTIFACTS"
    REVIEW_GOVERNANCE = "REVIEW_GOVERNANCE"
    CREATE_EXECUTION = "CREATE_EXECUTION"
    MONITOR_EXECUTION = "MONITOR_EXECUTION"
    VALIDATE_SILVER = "VALIDATE_SILVER"
    VIEW_RESULT = "VIEW_RESULT"


class BusinessRuleType(str, Enum):
    FILTER = "FILTER"
    DERIVATION = "DERIVATION"
    STANDARDIZATION = "STANDARDIZATION"
    DEDUPLICATION = "DEDUPLICATION"
    REFERENCE_LOOKUP = "REFERENCE_LOOKUP"
    DEFAULT_VALUE = "DEFAULT_VALUE"
    VALIDATION = "VALIDATION"
    AGGREGATION = "AGGREGATION"
    TRANSFORMATION = "TRANSFORMATION"


class BusinessRuleSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BusinessRuleStatus(str, Enum):
    EMPTY = "EMPTY"
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"


class QualityReviewDecision(str, Enum):
    APPROVED = "APPROVED"
    APPROVED_WITH_OBSERVATIONS = "APPROVED_WITH_OBSERVATIONS"


class BronzeSourceReference(BaseModel):
    connection_id: str = Field(min_length=1, max_length=300)
    project_id: str | None = Field(default=None, max_length=300)
    dataset_id: str = Field(min_length=1, max_length=300)
    table_id: str = Field(min_length=1, max_length=300)
    fully_qualified_name: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def populate_fully_qualified_name(self) -> "BronzeSourceReference":
        if not self.fully_qualified_name:
            self.fully_qualified_name = ".".join(
                part for part in [self.project_id, self.dataset_id, self.table_id] if part
            )
        return self


class SchemaColumnEvidence(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    data_type: str = Field(min_length=1, max_length=200)
    nullable: bool = True
    description: str | None = Field(default=None, max_length=2000)
    ordinal_position: int | None = Field(default=None, ge=1)


class SchemaContextEvidence(BaseModel):
    columns: list[SchemaColumnEvidence] = Field(min_length=1)
    profile_reference: str | None = Field(default=None, max_length=2000)
    schema_reference: str | None = Field(default=None, max_length=2000)
    source_api: str = "jarvis-reconciliation-agent"
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessRule(BaseModel):
    rule_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=2, max_length=4000)
    rule_type: BusinessRuleType
    expression: str = Field(min_length=1, max_length=8000)
    severity: BusinessRuleSeverity = BusinessRuleSeverity.ERROR
    enabled: bool = True
    source_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    business_owner: str | None = Field(default=None, max_length=300)
    technical_owner: str | None = Field(default=None, max_length=300)
    rationale: str = Field(min_length=2, max_length=4000)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_columns", "target_columns")
    @classmethod
    def normalize_column_references(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw_value in values:
            value = raw_value.strip()
            if not value:
                raise ValueError("Las referencias de columnas no pueden estar vacías")
            if value not in normalized:
                normalized.append(value)
        return normalized


class BusinessRuleProposalMetadata(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=300)
    model_name: str = Field(min_length=1, max_length=300)
    prompt_template_version: str = Field(min_length=1, max_length=200)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by: str = Field(min_length=2, max_length=200)
    source_workflow_version: int = Field(ge=1)
    idempotency_key: str | None = Field(default=None, max_length=500)
    latency_ms: int | None = Field(default=None, ge=0)
    token_usage: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessRulesSection(BaseModel):
    status: BusinessRuleStatus = BusinessRuleStatus.EMPTY
    rules: list[BusinessRule] = Field(default_factory=list)
    proposal_id: str | None = Field(default=None, max_length=300)
    proposal_metadata: BusinessRuleProposalMetadata | None = None
    last_modified_by: str | None = Field(default=None, max_length=200)
    last_modified_at: datetime | None = None
    confirmed_by: str | None = Field(default=None, max_length=200)
    confirmed_at: datetime | None = None
    confirmation_reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_section_consistency(self) -> "BusinessRulesSection":
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Cada Business Rule debe tener un rule_id único")
        if self.status == BusinessRuleStatus.EMPTY and self.rules:
            raise ValueError("El estado EMPTY no puede contener reglas")
        if self.status != BusinessRuleStatus.EMPTY and not self.rules:
            raise ValueError(f"El estado {self.status.value} requiere al menos una regla")
        if self.status == BusinessRuleStatus.PROPOSED and (
            not self.proposal_id or self.proposal_metadata is None
        ):
            raise ValueError("El estado PROPOSED requiere proposal_id y proposal_metadata")
        if self.status == BusinessRuleStatus.CONFIRMED and (
            not self.confirmed_by or self.confirmed_at is None
        ):
            raise ValueError("El estado CONFIRMED requiere confirmed_by y confirmed_at")
        return self

    @property
    def is_confirmable(self) -> bool:
        return self.status in {BusinessRuleStatus.DRAFT, BusinessRuleStatus.PROPOSED} and any(
            rule.enabled for rule in self.rules
        )


class CreateSilverWorkflowRequest(BaseModel):
    source: BronzeSourceReference
    requested_by: str = Field(min_length=2, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConfirmWorkflowSourceRequest(BaseModel):
    expected_version: int = Field(ge=1)
    schema_context: SchemaContextEvidence
    confirmed_by: str = Field(min_length=2, max_length=200)


class SaveBusinessRulesDraftRequest(BaseModel):
    expected_version: int = Field(ge=1)
    rules: list[BusinessRule] = Field(min_length=1)
    authored_by: str = Field(min_length=2, max_length=200)
    change_reason: str = Field(min_length=2, max_length=2000)


class GenerateBusinessRulesRequest(BaseModel):
    expected_version: int = Field(ge=1)
    generation_reason: str = Field(min_length=2, max_length=2000)
    max_rules: int = Field(default=5, ge=1, le=20)


class ConfirmBusinessRulesRequest(BaseModel):
    expected_version: int = Field(ge=1)
    confirmed_by: str = Field(min_length=2, max_length=200)
    confirmation_reason: str = Field(min_length=2, max_length=2000)
    selected_proposal_id: str | None = Field(default=None, max_length=300)


class SilverTargetReference(BaseModel):
    project_id: str = Field(min_length=1, max_length=300)
    dataset_id: str = Field(min_length=1, max_length=300)
    table_id: str = Field(min_length=1, max_length=300)

    @property
    def fully_qualified_name(self) -> str:
        return f"{self.project_id}.{self.dataset_id}.{self.table_id}"


class SilverMappingColumn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    data_type: str = Field(min_length=1, max_length=200)
    nullable: bool = True
    source_column: str | None = Field(default=None, max_length=300)
    transformation: str | None = Field(default=None, max_length=8000)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_mapping_source(self) -> "SilverMappingColumn":
        if not self.source_column and not self.transformation:
            raise ValueError("Cada columna Silver debe indicar source_column o transformation")
        return self


class SaveSilverSpecificationRequest(BaseModel):
    expected_version: int = Field(ge=1)
    mapping_version: int = Field(ge=1)
    target: SilverTargetReference
    columns: list[SilverMappingColumn] = Field(min_length=1)
    created_by: str = Field(min_length=2, max_length=200)
    change_reason: str = Field(min_length=2, max_length=2000)

    @model_validator(mode="after")
    def validate_unique_target_columns(self) -> "SaveSilverSpecificationRequest":
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Cada columna destino Silver debe tener un nombre único")
        return self


class SaveSilverMappingRequest(BaseModel):
    expected_version: int = Field(ge=1)
    target: SilverTargetReference
    columns: list[SilverMappingColumn] = Field(min_length=1)
    edited_by: str = Field(min_length=2, max_length=200)
    change_reason: str = Field(min_length=2, max_length=2000)

    @model_validator(mode="after")
    def validate_unique_target_columns(self) -> "SaveSilverMappingRequest":
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Cada columna destino Silver debe tener un nombre único")
        return self


class ReviewQualityRequest(BaseModel):
    expected_version: int = Field(ge=1)
    decision: QualityReviewDecision
    reviewed_by: str = Field(min_length=2, max_length=200)
    review_notes: str = Field(min_length=2, max_length=4000)
    quality_rules: list[dict[str, Any]] = Field(default_factory=list)


class SilverWorkflowRecord(BaseModel):
    workflow_id: str
    version: int = Field(ge=1)
    status: WorkflowStatus
    active_step: int = Field(ge=1, le=8)
    source: BronzeSourceReference
    source_confirmed: bool = False
    schema_context: SchemaContextEvidence | None = None
    business_rules: BusinessRulesSection = Field(default_factory=BusinessRulesSection)
    mapping_rules: list[dict[str, Any]] = Field(default_factory=list)
    mapping_version: int | None = Field(default=None, ge=1)
    silver_target: SilverTargetReference | None = None
    quality_rules: list[dict[str, Any]] = Field(default_factory=list)
    quality_review: dict[str, Any] | None = None
    artifact_package: dict[str, Any] | None = None
    governance: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    spec_id: str | None = None
    execution_id: str | None = None
    available_actions: list[WorkflowAction] = Field(default_factory=list)
    correlation_id: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_business_rules(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        legacy_rules = normalized.get("business_rules")
        if legacy_rules is None or legacy_rules == []:
            normalized["business_rules"] = {"status": BusinessRuleStatus.EMPTY.value, "rules": []}
        elif isinstance(legacy_rules, list):
            normalized["business_rules"] = {
                "status": BusinessRuleStatus.DRAFT.value,
                "rules": legacy_rules,
            }
        return normalized


class SilverWorkflowListResponse(BaseModel):
    total: int = Field(ge=0)
    workflows: list[SilverWorkflowRecord]


class SilverWorkflowVersionSummary(BaseModel):
    workflow_id: str
    workflow_version: int = Field(ge=1)
    mapping_version: int | None = Field(default=None, ge=1)
    spec_id: str | None = None
    package_version: int | None = Field(default=None, ge=1)
    execution_id: str | None = None
    status: WorkflowStatus
    updated_at: datetime
    lifecycle_status: str


class SilverWorkflowVersionListResponse(BaseModel):
    workflow_id: str
    current_version: int = Field(ge=1)
    total: int = Field(ge=0)
    versions: list[SilverWorkflowVersionSummary]


class WorkflowRepositoryHealth(BaseModel):
    status: str
    provider: str
    schema_ready: bool
    detail: str | None = None
