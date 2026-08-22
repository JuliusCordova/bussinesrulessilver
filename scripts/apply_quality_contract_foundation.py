from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1))


MODELS = "backend/deployable/silver-refinement-agent/modules/silver_workflow/models.py"
SERVICE = "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py"
REPO = "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py"
GCS = "backend/deployable/silver-refinement-agent/modules/silver_workflow/gcs_repository.py"
API = "src/api.ts"
TEST = ROOT / "backend/deployable/silver-refinement-agent/tests/test_quality_contract_foundation.py"

replace(
    MODELS,
    '''class QualityReviewDecision(str, Enum):\n    APPROVED = "APPROVED"\n    APPROVED_WITH_OBSERVATIONS = "APPROVED_WITH_OBSERVATIONS"\n''',
    '''class QualityReviewDecision(str, Enum):\n    APPROVED = "APPROVED"\n    APPROVED_WITH_OBSERVATIONS = "APPROVED_WITH_OBSERVATIONS"\n\n\nclass QualityDimension(str, Enum):\n    COMPLETENESS = "COMPLETENESS"\n    UNIQUENESS = "UNIQUENESS"\n    VALIDITY = "VALIDITY"\n    CONSISTENCY = "CONSISTENCY"\n    REFERENTIAL = "REFERENTIAL"\n    TIMELINESS = "TIMELINESS"\n    AGGREGATE = "AGGREGATE"\n    BUSINESS = "BUSINESS"\n\n\nclass QualityRuleStatus(str, Enum):\n    DRAFT = "DRAFT"\n    PENDING_APPROVAL = "PENDING_APPROVAL"\n    APPROVED = "APPROVED"\n    REJECTED = "REJECTED"\n    BLOCKED = "BLOCKED"\n    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"\n\n\nclass QualityRuleSource(str, Enum):\n    AI_RECOMMENDED = "AI_RECOMMENDED"\n    MANUAL = "MANUAL"\n    DERIVED_NL = "DERIVED_NL"\n\n\nclass QualityRuntimeAction(str, Enum):\n    OBSERVE_ONLY = "OBSERVE_ONLY"\n    WARN = "WARN"\n    QUARANTINE = "QUARANTINE"\n    BLOCK_LOAD = "BLOCK_LOAD"\n\n\nclass GovernedQualityRule(BaseModel):\n    rule_id: str = Field(min_length=1, max_length=300)\n    name: str = Field(min_length=1, max_length=300)\n    version: int = Field(default=1, ge=1)\n    dimension: QualityDimension\n    rule_type: str = Field(min_length=1, max_length=200)\n    columns: list[str] = Field(default_factory=list)\n    parameters: dict[str, Any] = Field(default_factory=dict)\n    expression: str | None = Field(default=None, max_length=8000)\n    warning_threshold: float = Field(default=0.0, ge=0)\n    critical_threshold: float = Field(default=1.0, ge=0)\n    severity: str = Field(default="MEDIUM", min_length=1, max_length=100)\n    runtime_action: QualityRuntimeAction = QualityRuntimeAction.WARN\n    evidence: str | None = Field(default=None, max_length=8000)\n    confidence: float | None = Field(default=None, ge=0, le=1)\n    source: QualityRuleSource = QualityRuleSource.MANUAL\n    status: QualityRuleStatus = QualityRuleStatus.PENDING_APPROVAL\n    active: bool = True\n    approved_by: str | None = Field(default=None, max_length=320)\n    approved_at: datetime | None = None\n    metadata: dict[str, Any] = Field(default_factory=dict)\n\n    @model_validator(mode="before")\n    @classmethod\n    def promote_legacy_rule(cls, value: Any) -> Any:\n        if not isinstance(value, dict):\n            return value\n        if "name" in value and "dimension" in value and "rule_type" in value:\n            return value\n        data = dict(value)\n        name = str(data.get("rule_name") or data.get("name") or data.get("rule_type") or "quality_rule")\n        rule_id = data.get("rule_id")\n        if not rule_id:\n            slug = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_") or "quality_rule"\n            rule_id = f"qr_{slug}"\n        columns: list[str] = []\n        for candidate in (data.get("column_name"), data.get("comparison_column")):\n            if candidate and str(candidate) not in columns:\n                columns.append(str(candidate))\n        source = data.get("source")\n        if not source:\n            source = "AI_RECOMMENDED" if data.get("agent_evidence") is not None else "MANUAL"\n        return {\n            "rule_id": rule_id,\n            "name": name,\n            "version": data.get("version", 1),\n            "dimension": data.get("rule_dimension") or data.get("dimension") or "VALIDITY",\n            "rule_type": data.get("rule_type") or "CUSTOM",\n            "columns": data.get("columns") or columns,\n            "parameters": data.get("rule_parameters") or data.get("parameters") or {},\n            "expression": data.get("expression"),\n            "warning_threshold": data.get("warning_threshold", 0.0),\n            "critical_threshold": data.get("critical_threshold", 1.0),\n            "severity": data.get("severity_level") or data.get("severity") or "MEDIUM",\n            "runtime_action": data.get("runtime_action") or "WARN",\n            "evidence": data.get("evidence") or data.get("agent_evidence"),\n            "confidence": data.get("confidence") if data.get("confidence") is not None else data.get("agent_confidence"),\n            "source": source,\n            "status": data.get("status") or "PENDING_APPROVAL",\n            "active": data.get("active_flag", data.get("active", True)),\n            "approved_by": data.get("approved_by"),\n            "approved_at": data.get("approved_at"),\n            "metadata": data.get("metadata") or {},\n        }\n\n    @field_validator("columns")\n    @classmethod\n    def normalize_quality_columns(cls, values: list[str]) -> list[str]:\n        normalized: list[str] = []\n        for raw in values:\n            value = raw.strip()\n            if not value:\n                raise ValueError("Las columnas de una regla de calidad no pueden estar vacías")\n            if value not in normalized:\n                normalized.append(value)\n        return normalized\n\n    @model_validator(mode="after")\n    def validate_thresholds_and_approval(self) -> "GovernedQualityRule":\n        if self.critical_threshold < self.warning_threshold:\n            raise ValueError("critical_threshold debe ser mayor o igual que warning_threshold")\n        if self.status == QualityRuleStatus.APPROVED and (not self.approved_by or self.approved_at is None):\n            raise ValueError("Una regla APPROVED requiere approved_by y approved_at")\n        return self\n'''
)

replace(
    MODELS,
    '''class ReviewQualityRequest(BaseModel):\n    expected_version: int = Field(ge=1)\n    decision: QualityReviewDecision\n    reviewed_by: str = Field(min_length=2, max_length=200)\n    review_notes: str = Field(min_length=2, max_length=4000)\n    quality_rules: list[dict[str, Any]] = Field(default_factory=list)\n''',
    '''class ReviewQualityRequest(BaseModel):\n    expected_version: int = Field(ge=1)\n    decision: QualityReviewDecision\n    reviewed_by: str = Field(min_length=2, max_length=200)\n    review_notes: str = Field(min_length=2, max_length=4000)\n    quality_rules: list[GovernedQualityRule] = Field(default_factory=list)\n\n    @model_validator(mode="after")\n    def validate_unique_quality_rules(self) -> "ReviewQualityRequest":\n        rule_ids = [rule.rule_id for rule in self.quality_rules]\n        if len(rule_ids) != len(set(rule_ids)):\n            raise ValueError("Cada regla de calidad debe tener un rule_id único")\n        return self\n'''
)

replace(
    MODELS,
    '''    quality_rules: list[dict[str, Any]] = Field(default_factory=list)\n    quality_review: dict[str, Any] | None = None\n''',
    '''    quality_rules: list[dict[str, Any]] = Field(default_factory=list)\n    quality_rules_version: int | None = Field(default=None, ge=1)\n    quality_review: dict[str, Any] | None = None\n'''
)

replace(
    MODELS,
    '''    mapping_version: int | None = Field(default=None, ge=1)\n    spec_id: str | None = None\n''',
    '''    mapping_version: int | None = Field(default=None, ge=1)\n    quality_rules_version: int | None = Field(default=None, ge=1)\n    spec_id: str | None = None\n'''
)

replace(
    SERVICE,
    '''                mapping_version=record.mapping_version,\n                spec_id=record.spec_id,\n''',
    '''                mapping_version=record.mapping_version,\n                quality_rules_version=record.quality_rules_version,\n                spec_id=record.spec_id,\n'''
)

replace(
    SERVICE,
    '''        reviewed_at = datetime.now(timezone.utc)\n        review = {\n            "decision": request.decision.value,\n            "reviewed_by": request.reviewed_by,\n            "review_notes": request.review_notes,\n            "reviewed_at": reviewed_at.isoformat(),\n            "source_workflow_version": current.version,\n        }\n        return self._with_actions(self.repository.review_quality(\n            workflow_id, expected_version=request.expected_version,\n            quality_rules=request.quality_rules, quality_review=review,\n            updated_at=reviewed_at,\n        ))\n''',
    '''        reviewed_at = datetime.now(timezone.utc)\n        next_quality_rules_version = (current.quality_rules_version or 0) + 1\n        approved_rules = [\n            rule.model_copy(deep=True, update={\n                "status": QualityRuleStatus.APPROVED,\n                "approved_by": request.reviewed_by,\n                "approved_at": reviewed_at,\n            }).model_dump(mode="json")\n            for rule in request.quality_rules\n            if rule.active\n        ]\n        review = {\n            "decision": request.decision.value,\n            "reviewed_by": request.reviewed_by,\n            "review_notes": request.review_notes,\n            "reviewed_at": reviewed_at.isoformat(),\n            "source_workflow_version": current.version,\n            "quality_rules_version": next_quality_rules_version,\n            "approved_rule_count": len(approved_rules),\n        }\n        return self._with_actions(self.repository.review_quality(\n            workflow_id, expected_version=request.expected_version,\n            quality_rules=approved_rules, quality_rules_version=next_quality_rules_version,\n            quality_review=review, updated_at=reviewed_at,\n        ))\n'''
)

replace(
    SERVICE,
    '''    QualityReviewDecision,\n''',
    '''    QualityReviewDecision,\n    QualityRuleStatus,\n'''
)

replace(
    REPO,
    '''    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord: ...\n''',
    '''    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_rules_version: int, quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord: ...\n'''
)
replace(
    REPO,
    '''    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:\n''',
    '''    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_rules_version: int, quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:\n'''
)
replace(
    REPO,
    '''                "version": record.version + 1, "active_step": 6,\n                "quality_rules": quality_rules, "quality_review": quality_review,\n''',
    '''                "version": record.version + 1, "active_step": 6,\n                "quality_rules": quality_rules, "quality_rules_version": quality_rules_version,\n                "quality_review": quality_review,\n'''
)

replace(
    GCS,
    '''    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:\n''',
    '''    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_rules_version: int, quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:\n'''
)
replace(
    GCS,
    '''            return record.model_copy(deep=True, update={"version": record.version + 1, "active_step": 6, "quality_rules": quality_rules, "quality_review": quality_review, "updated_at": updated_at, "metadata": metadata})\n''',
    '''            return record.model_copy(deep=True, update={"version": record.version + 1, "active_step": 6, "quality_rules": quality_rules, "quality_rules_version": quality_rules_version, "quality_review": quality_review, "updated_at": updated_at, "metadata": metadata})\n'''
)

replace(
    API,
    '''  quality_rules?: Array<Record<string, unknown>>;\n  quality_review?: Record<string, unknown> | null;\n''',
    '''  quality_rules?: Array<Record<string, unknown>>;\n  quality_rules_version?: number | null;\n  quality_review?: Record<string, unknown> | null;\n'''
)
replace(
    API,
    '''  mapping_version?: number | null;\n  spec_id?: string | null;\n''',
    '''  mapping_version?: number | null;\n  quality_rules_version?: number | null;\n  spec_id?: string | null;\n'''
)

if not TEST.exists():
    TEST.write_text('''from datetime import datetime, timezone\n\nimport pytest\n\nfrom modules.silver_workflow.models import (\n    BronzeSourceReference, BusinessRule, BusinessRuleSeverity, BusinessRulesSection,\n    BusinessRuleStatus, BusinessRuleType, GovernedQualityRule, QualityRuleSource,\n    QualityRuleStatus, QualityRuntimeAction, ReviewQualityRequest, SchemaColumnEvidence,\n    SchemaContextEvidence, SilverTargetReference, SilverWorkflowRecord, WorkflowStatus,\n)\nfrom modules.silver_workflow.repository import InMemoryWorkflowRepository\nfrom modules.silver_workflow.service import SilverWorkflowService\n\n\ndef test_legacy_quality_rule_promotes_to_governed_contract():\n    rule = GovernedQualityRule.model_validate({\n        "rule_name": "id_not_null",\n        "rule_dimension": "COMPLETENESS",\n        "rule_type": "NOT_NULL",\n        "column_name": "id",\n        "rule_parameters": {},\n        "warning_threshold": 0,\n        "critical_threshold": 1,\n        "severity_level": "CRITICAL",\n        "active_flag": True,\n        "agent_evidence": "Campo crítico sin nulos.",\n        "agent_confidence": 0.95,\n    })\n    assert rule.rule_id == "qr_id_not_null"\n    assert rule.columns == ["id"]\n    assert rule.source == QualityRuleSource.AI_RECOMMENDED\n    assert rule.status == QualityRuleStatus.PENDING_APPROVAL\n    assert rule.runtime_action == QualityRuntimeAction.WARN\n\n\ndef test_quality_thresholds_are_ordered():\n    with pytest.raises(ValueError, match="critical_threshold"):\n        GovernedQualityRule(\n            rule_id="qr_bad", name="bad", dimension="VALIDITY", rule_type="VALUE_RANGE",\n            warning_threshold=5, critical_threshold=1,\n        )\n\n\ndef test_quality_review_versions_and_approves_rules():\n    now = datetime.now(timezone.utc)\n    repo = InMemoryWorkflowRepository()\n    record = SilverWorkflowRecord(\n        workflow_id="workflow_quality", version=5, status=WorkflowStatus.IN_PROGRESS, active_step=5,\n        source=BronzeSourceReference(connection_id="bq", project_id="p", dataset_id="bronze", table_id="ventas"),\n        source_confirmed=True,\n        schema_context=SchemaContextEvidence(columns=[SchemaColumnEvidence(name="id", data_type="INT64", nullable=False)]),\n        business_rules=BusinessRulesSection(\n            status=BusinessRuleStatus.CONFIRMED,\n            rules=[BusinessRule(\n                rule_id="br1", name="id requerido", description="id requerido",\n                rule_type=BusinessRuleType.VALIDATION, expression="id IS NOT NULL",\n                severity=BusinessRuleSeverity.ERROR, source_columns=["id"], target_columns=["id"], rationale="clave",\n            )],\n            confirmed_by="tester", confirmed_at=now,\n        ),\n        mapping_rules=[{"name": "id", "data_type": "INT64", "source_column": "id"}],\n        mapping_version=1, silver_target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),\n        spec_id="spec_1", correlation_id="corr", created_by="tester", created_at=now, updated_at=now,\n    )\n    repo.create(record)\n    service = SilverWorkflowService(repository=repo)\n    request = ReviewQualityRequest(\n        expected_version=5, decision="APPROVED", reviewed_by="reviewer@example.com", review_notes="Reglas revisadas",\n        quality_rules=[{\n            "rule_name": "id_not_null", "rule_dimension": "COMPLETENESS", "rule_type": "NOT_NULL",\n            "column_name": "id", "warning_threshold": 0, "critical_threshold": 1,\n            "severity_level": "CRITICAL", "active_flag": True,\n        }],\n    )\n    updated = service.review_quality("workflow_quality", request)\n    assert updated.version == 6\n    assert updated.quality_rules_version == 1\n    assert updated.quality_review["quality_rules_version"] == 1\n    assert updated.quality_review["approved_rule_count"] == 1\n    assert updated.quality_rules[0]["status"] == "APPROVED"\n    assert updated.quality_rules[0]["approved_by"] == "reviewer@example.com"\n    assert updated.quality_rules[0]["runtime_action"] == "WARN"\n\n\ndef test_duplicate_quality_rule_ids_are_rejected():\n    base = {"rule_id": "same", "name": "r", "dimension": "VALIDITY", "rule_type": "REGEX"}\n    with pytest.raises(ValueError, match="rule_id único"):\n        ReviewQualityRequest(\n            expected_version=1, decision="APPROVED", reviewed_by="reviewer", review_notes="ok",\n            quality_rules=[base, base],\n        )\n''')

print("PASS: Quality Contract Foundation aplicado.")
print("Reglas legacy se normalizan; conjunto versionado; aprobación y runtime gate quedan trazables.")
