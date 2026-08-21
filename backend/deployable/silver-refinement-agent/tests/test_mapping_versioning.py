from datetime import datetime, timezone

from modules.silver_workflow.models import (
    BronzeSourceReference, BusinessRule, BusinessRulesSection, BusinessRuleSeverity,
    BusinessRuleStatus, BusinessRuleType, SaveSilverMappingRequest, SchemaColumnEvidence,
    SchemaContextEvidence, SilverMappingColumn, SilverTargetReference, SilverWorkflowRecord,
    WorkflowStatus,
)
from modules.silver_workflow.repository import InMemoryWorkflowRepository
from modules.silver_workflow.service import SilverWorkflowService


def test_mapping_edit_creates_new_version_and_invalidates_downstream():
    now = datetime.now(timezone.utc)
    repo = InMemoryWorkflowRepository()
    record = SilverWorkflowRecord(
        workflow_id="workflow_test", version=7, status=WorkflowStatus.SUCCEEDED, active_step=8,
        source=BronzeSourceReference(connection_id="bq", project_id="p", dataset_id="bronze", table_id="ventas"),
        source_confirmed=True,
        schema_context=SchemaContextEvidence(columns=[
            SchemaColumnEvidence(name="id", data_type="INT64", nullable=False),
            SchemaColumnEvidence(name="monto", data_type="NUMERIC", nullable=True),
        ]),
        business_rules=BusinessRulesSection(
            status=BusinessRuleStatus.CONFIRMED,
            rules=[BusinessRule(
                rule_id="r1", name="id valido", description="id requerido",
                rule_type=BusinessRuleType.VALIDATION, expression="id IS NOT NULL",
                severity=BusinessRuleSeverity.ERROR, source_columns=["id"],
                target_columns=["id"], rationale="clave",
            )],
            confirmed_by="tester", confirmed_at=now,
        ),
        mapping_rules=[{"name": "id", "data_type": "INT64", "source_column": "id"}],
        mapping_version=3, silver_target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),
        quality_rules=[{"rule_name": "id_not_null"}], quality_review={"decision": "APPROVED"},
        artifact_package={"package_version": 2}, governance={"decision": "APPROVED"},
        execution={"status": "SUCCEEDED"}, validation={"status": "SUCCEEDED"},
        spec_id="spec_old", execution_id="exec_old", correlation_id="corr", created_by="tester",
        created_at=now, updated_at=now,
    )
    repo.create(record)
    service = SilverWorkflowService(repository=repo)

    updated = service.save_mapping_version("workflow_test", SaveSilverMappingRequest(
        expected_version=7,
        target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),
        columns=[
            SilverMappingColumn(name="id", data_type="INT64", nullable=False, source_column="id"),
            SilverMappingColumn(name="monto", data_type="NUMERIC", nullable=True, source_column="monto"),
        ],
        edited_by="tester", change_reason="agregar monto",
    ))

    assert updated.version == 8
    assert updated.mapping_version == 4
    assert updated.status == WorkflowStatus.IN_PROGRESS
    assert updated.active_step == 4
    assert updated.spec_id is None
    assert updated.quality_review is None
    assert updated.artifact_package is None
    assert updated.execution is None
    assert updated.execution_id is None
    assert updated.metadata["superseded_spec_id"] == "spec_old"
    assert updated.metadata["superseded_execution_id"] == "exec_old"
    assert updated.metadata["superseded_mapping_version"] == 3
