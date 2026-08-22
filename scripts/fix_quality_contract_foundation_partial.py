from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:160]!r}")
    file.write_text(text.replace(old, new, 1))


def ensure_contains(path: str, needle: str, anchor: str) -> None:
    file = ROOT / path
    text = file.read_text()
    if needle in text:
        return
    if anchor not in text:
        raise SystemExit(f"Anchor not found in {path}: {anchor!r}")
    file.write_text(text.replace(anchor, anchor + needle, 1))


SERVICE = "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py"
REPO = "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py"
GCS = "backend/deployable/silver-refinement-agent/modules/silver_workflow/gcs_repository.py"
API = "src/api.ts"
TEST = ROOT / "backend/deployable/silver-refinement-agent/tests/test_quality_contract_foundation.py"

# The original patch expected QualityReviewDecision in service.py, but that symbol was
# never imported there. Anchor on ReviewQualityRequest, which is present in the real file.
ensure_contains(
    SERVICE,
    "    QualityRuleStatus,\n",
    "    ReviewQualityRequest,\n",
)

replace_once(
    REPO,
    "    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord: ...\n",
    "    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_rules_version: int, quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord: ...\n",
)
replace_once(
    REPO,
    "    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:\n",
    "    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_rules_version: int, quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:\n",
)
replace_once(
    REPO,
    "                \"version\": record.version + 1, \"active_step\": 6,\n                \"quality_rules\": quality_rules, \"quality_review\": quality_review,\n",
    "                \"version\": record.version + 1, \"active_step\": 6,\n                \"quality_rules\": quality_rules, \"quality_rules_version\": quality_rules_version,\n                \"quality_review\": quality_review,\n",
)

replace_once(
    GCS,
    "    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:\n",
    "    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_rules_version: int, quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:\n",
)
replace_once(
    GCS,
    "            return record.model_copy(deep=True, update={\"version\": record.version + 1, \"active_step\": 6, \"quality_rules\": quality_rules, \"quality_review\": quality_review, \"updated_at\": updated_at, \"metadata\": metadata})\n",
    "            return record.model_copy(deep=True, update={\"version\": record.version + 1, \"active_step\": 6, \"quality_rules\": quality_rules, \"quality_rules_version\": quality_rules_version, \"quality_review\": quality_review, \"updated_at\": updated_at, \"metadata\": metadata})\n",
)

replace_once(
    API,
    "  quality_rules?: Array<Record<string, unknown>>;\n  quality_review?: Record<string, unknown> | null;\n",
    "  quality_rules?: Array<Record<string, unknown>>;\n  quality_rules_version?: number | null;\n  quality_review?: Record<string, unknown> | null;\n",
)
replace_once(
    API,
    "  mapping_version?: number | null;\n  spec_id?: string | null;\n",
    "  mapping_version?: number | null;\n  quality_rules_version?: number | null;\n  spec_id?: string | null;\n",
)

if not TEST.exists():
    TEST.write_text('''from datetime import datetime, timezone\n\nimport pytest\n\nfrom modules.silver_workflow.models import (\n    BronzeSourceReference, BusinessRule, BusinessRuleSeverity, BusinessRulesSection,\n    BusinessRuleStatus, BusinessRuleType, GovernedQualityRule, QualityRuleSource,\n    QualityRuleStatus, QualityRuntimeAction, ReviewQualityRequest, SchemaColumnEvidence,\n    SchemaContextEvidence, SilverTargetReference, SilverWorkflowRecord, WorkflowStatus,\n)\nfrom modules.silver_workflow.repository import InMemoryWorkflowRepository\nfrom modules.silver_workflow.service import SilverWorkflowService\n\n\ndef test_legacy_quality_rule_promotes_to_governed_contract():\n    rule = GovernedQualityRule.model_validate({\n        \"rule_name\": \"id_not_null\",\n        \"rule_dimension\": \"COMPLETENESS\",\n        \"rule_type\": \"NOT_NULL\",\n        \"column_name\": \"id\",\n        \"rule_parameters\": {},\n        \"warning_threshold\": 0,\n        \"critical_threshold\": 1,\n        \"severity_level\": \"CRITICAL\",\n        \"active_flag\": True,\n        \"agent_evidence\": \"Campo crítico sin nulos.\",\n        \"agent_confidence\": 0.95,\n    })\n    assert rule.rule_id == \"qr_id_not_null\"\n    assert rule.columns == [\"id\"]\n    assert rule.source == QualityRuleSource.AI_RECOMMENDED\n    assert rule.status == QualityRuleStatus.PENDING_APPROVAL\n    assert rule.runtime_action == QualityRuntimeAction.WARN\n\n\ndef test_quality_thresholds_are_governed():\n    with pytest.raises(ValueError, match=\"critical_threshold\"):\n        GovernedQualityRule.model_validate({\n            \"rule_id\": \"qr_bad\",\n            \"name\": \"bad thresholds\",\n            \"dimension\": \"VALIDITY\",\n            \"rule_type\": \"VALUE_RANGE\",\n            \"columns\": [\"monto\"],\n            \"warning_threshold\": 5,\n            \"critical_threshold\": 1,\n        })\n\n\ndef _workflow_ready_for_quality():\n    now = datetime.now(timezone.utc)\n    return SilverWorkflowRecord(\n        workflow_id=\"workflow_quality\", version=5, status=WorkflowStatus.IN_PROGRESS, active_step=5,\n        source=BronzeSourceReference(connection_id=\"bq\", project_id=\"p\", dataset_id=\"bronze\", table_id=\"ventas\"),\n        source_confirmed=True,\n        schema_context=SchemaContextEvidence(columns=[\n            SchemaColumnEvidence(name=\"id\", data_type=\"INT64\", nullable=False),\n        ]),\n        business_rules=BusinessRulesSection(\n            status=BusinessRuleStatus.CONFIRMED,\n            rules=[BusinessRule(\n                rule_id=\"br1\", name=\"id requerido\", description=\"id requerido\",\n                rule_type=BusinessRuleType.VALIDATION, expression=\"id IS NOT NULL\",\n                severity=BusinessRuleSeverity.ERROR, source_columns=[\"id\"], target_columns=[\"id\"],\n                rationale=\"clave\",\n            )],\n            confirmed_by=\"tester\", confirmed_at=now,\n        ),\n        mapping_rules=[{\"name\": \"id\", \"data_type\": \"INT64\", \"source_column\": \"id\"}],\n        mapping_version=1,\n        silver_target=SilverTargetReference(project_id=\"p\", dataset_id=\"silver\", table_id=\"ventas\"),\n        spec_id=\"spec_quality\", correlation_id=\"corr\", created_by=\"tester\", created_at=now, updated_at=now,\n    )\n\n\ndef test_review_quality_versions_and_approves_governed_rules():\n    repo = InMemoryWorkflowRepository()\n    repo.create(_workflow_ready_for_quality())\n    service = SilverWorkflowService(repository=repo)\n\n    updated = service.review_quality(\"workflow_quality\", ReviewQualityRequest(\n        expected_version=5,\n        decision=\"APPROVED\",\n        reviewed_by=\"reviewer@example.com\",\n        review_notes=\"Reglas revisadas y aprobadas\",\n        quality_rules=[{\n            \"rule_name\": \"id_not_null\",\n            \"rule_dimension\": \"COMPLETENESS\",\n            \"rule_type\": \"NOT_NULL\",\n            \"column_name\": \"id\",\n            \"warning_threshold\": 0,\n            \"critical_threshold\": 1,\n            \"severity_level\": \"CRITICAL\",\n            \"runtime_action\": \"BLOCK_LOAD\",\n            \"active_flag\": True,\n        }],\n    ))\n\n    assert updated.quality_rules_version == 1\n    assert updated.quality_review[\"quality_rules_version\"] == 1\n    assert updated.quality_review[\"approved_rule_count\"] == 1\n    assert updated.quality_rules[0][\"status\"] == \"APPROVED\"\n    assert updated.quality_rules[0][\"approved_by\"] == \"reviewer@example.com\"\n    assert updated.quality_rules[0][\"runtime_action\"] == \"BLOCK_LOAD\"\n\n\ndef test_review_quality_rejects_duplicate_rule_ids():\n    legacy = {\n        \"rule_name\": \"id_not_null\", \"rule_dimension\": \"COMPLETENESS\",\n        \"rule_type\": \"NOT_NULL\", \"column_name\": \"id\",\n    }\n    with pytest.raises(ValueError, match=\"rule_id único\"):\n        ReviewQualityRequest(\n            expected_version=1, decision=\"APPROVED\", reviewed_by=\"reviewer\",\n            review_notes=\"duplicate check\", quality_rules=[legacy, legacy],\n        )\n''')

print("PASS: recovery Quality Contract Foundation aplicado desde estado parcial.")
print("Se completaron import, repositorios, API y tests sin repetir cambios ya aplicados.")
