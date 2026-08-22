from datetime import datetime, timezone

import pytest

from modules.silver_workflow.models import (
    BronzeSourceReference, BusinessRule, BusinessRuleSeverity, BusinessRulesSection,
    BusinessRuleStatus, BusinessRuleType, GovernedQualityRule, QualityRuleSource,
    QualityRuleStatus, QualityRuntimeAction, ReviewQualityRequest, SchemaColumnEvidence,
    SchemaContextEvidence, SilverTargetReference, SilverWorkflowRecord, WorkflowStatus,
)
from modules.silver_workflow.repository import InMemoryWorkflowRepository
from modules.silver_workflow.service import SilverWorkflowService


def test_legacy_quality_rule_promotes_to_governed_contract():
    rule = GovernedQualityRule.model_validate({
        "rule_name": "id_not_null",
        "rule_dimension": "COMPLETENESS",
        "rule_type": "NOT_NULL",
        "column_name": "id",
        "rule_parameters": {},
        "warning_threshold": 0,
        "critical_threshold": 1,
        "severity_level": "CRITICAL",
        "active_flag": True,
        "agent_evidence": "Campo crítico sin nulos.",
        "agent_confidence": 0.95,
    })
    assert rule.rule_id == "qr_id_not_null"
    assert rule.columns == ["id"]
    assert rule.source == QualityRuleSource.AI_RECOMMENDED
    assert rule.status == QualityRuleStatus.PENDING_APPROVAL
    assert rule.runtime_action == QualityRuntimeAction.WARN


def test_quality_thresholds_are_governed():
    with pytest.raises(ValueError, match="critical_threshold"):
        GovernedQualityRule.model_validate({
            "rule_id": "qr_bad",
            "name": "bad thresholds",
            "dimension": "VALIDITY",
            "rule_type": "VALUE_RANGE",
            "columns": ["monto"],
            "warning_threshold": 5,
            "critical_threshold": 1,
        })


def _workflow_ready_for_quality():
    now = datetime.now(timezone.utc)
    return SilverWorkflowRecord(
        workflow_id="workflow_quality", version=5, status=WorkflowStatus.IN_PROGRESS, active_step=5,
        source=BronzeSourceReference(connection_id="bq", project_id="p", dataset_id="bronze", table_id="ventas"),
        source_confirmed=True,
        schema_context=SchemaContextEvidence(columns=[
            SchemaColumnEvidence(name="id", data_type="INT64", nullable=False),
        ]),
        business_rules=BusinessRulesSection(
            status=BusinessRuleStatus.CONFIRMED,
            rules=[BusinessRule(
                rule_id="br1", name="id requerido", description="id requerido",
                rule_type=BusinessRuleType.VALIDATION, expression="id IS NOT NULL",
                severity=BusinessRuleSeverity.ERROR, source_columns=["id"], target_columns=["id"],
                rationale="clave",
            )],
            confirmed_by="tester", confirmed_at=now,
        ),
        mapping_rules=[{"name": "id", "data_type": "INT64", "source_column": "id"}],
        mapping_version=1,
        silver_target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),
        spec_id="spec_quality", correlation_id="corr", created_by="tester", created_at=now, updated_at=now,
    )


def test_review_quality_versions_and_approves_governed_rules():
    repo = InMemoryWorkflowRepository()
    repo.create(_workflow_ready_for_quality())
    service = SilverWorkflowService(repository=repo)

    updated = service.review_quality("workflow_quality", ReviewQualityRequest(
        expected_version=5,
        decision="APPROVED",
        reviewed_by="reviewer@example.com",
        review_notes="Reglas revisadas y aprobadas",
        quality_rules=[{
            "rule_name": "id_not_null",
            "rule_dimension": "COMPLETENESS",
            "rule_type": "NOT_NULL",
            "column_name": "id",
            "warning_threshold": 0,
            "critical_threshold": 1,
            "severity_level": "CRITICAL",
            "runtime_action": "BLOCK_LOAD",
            "active_flag": True,
        }],
    ))

    assert updated.quality_rules_version == 1
    assert updated.quality_review["quality_rules_version"] == 1
    assert updated.quality_review["approved_rule_count"] == 1
    assert updated.quality_rules[0]["status"] == "APPROVED"
    assert updated.quality_rules[0]["approved_by"] == "reviewer@example.com"
    assert updated.quality_rules[0]["runtime_action"] == "BLOCK_LOAD"


def test_review_quality_rejects_duplicate_rule_ids():
    legacy = {
        "rule_name": "id_not_null", "rule_dimension": "COMPLETENESS",
        "rule_type": "NOT_NULL", "column_name": "id",
    }
    with pytest.raises(ValueError, match="rule_id único"):
        ReviewQualityRequest(
            expected_version=1, decision="APPROVED", reviewed_by="reviewer",
            review_notes="duplicate check", quality_rules=[legacy, legacy],
        )
