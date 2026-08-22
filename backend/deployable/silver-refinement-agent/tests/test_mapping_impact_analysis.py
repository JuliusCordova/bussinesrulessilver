from datetime import datetime, timezone

from modules.silver_workflow.models import (
    BronzeSourceReference, MappingImpactRequest, SchemaColumnEvidence, SchemaContextEvidence,
    SilverMappingColumn, SilverTargetReference, SilverWorkflowRecord, WorkflowStatus,
)
from modules.silver_workflow.repository import InMemoryWorkflowRepository
from modules.silver_workflow.service import SilverWorkflowService


def test_mapping_impact_is_read_only_and_marks_downstream_invalidation():
    now = datetime.now(timezone.utc)
    repo = InMemoryWorkflowRepository()
    record = SilverWorkflowRecord(
        workflow_id="workflow_impact", version=7, status=WorkflowStatus.SUCCEEDED, active_step=8,
        source=BronzeSourceReference(connection_id="bq", project_id="p", dataset_id="bronze", table_id="ventas"),
        source_confirmed=True,
        schema_context=SchemaContextEvidence(columns=[
            SchemaColumnEvidence(name="id", data_type="INT64", nullable=False),
            SchemaColumnEvidence(name="monto", data_type="NUMERIC", nullable=True),
        ]),
        mapping_rules=[{"name": "id", "data_type": "INT64", "nullable": False, "source_column": "id", "transformation": "DIRECT"}],
        mapping_version=3, silver_target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),
        quality_rules=[{"rule_name": "id_not_null", "column_name": "id"}],
        spec_id="spec_old", execution_id="exec_old", correlation_id="corr", created_by="tester",
        created_at=now, updated_at=now,
    )
    repo.create(record)
    service = SilverWorkflowService(repository=repo)

    impact = service.analyze_mapping_impact("workflow_impact", MappingImpactRequest(
        expected_version=7,
        target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),
        columns=[
            SilverMappingColumn(name="id", data_type="INT64", nullable=False, source_column="id", transformation="DIRECT"),
            SilverMappingColumn(name="monto", data_type="NUMERIC", nullable=True, source_column="monto", transformation="DIRECT"),
        ],
    ))

    assert impact.has_changes is True
    assert impact.added_columns == ["monto"]
    assert impact.proposed_mapping_version == 4
    assert "SPECIFICATION" in impact.downstream_invalidations
    assert repo.get("workflow_impact").version == 7
