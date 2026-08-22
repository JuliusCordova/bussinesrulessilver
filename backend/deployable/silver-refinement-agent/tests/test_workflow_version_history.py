from datetime import datetime, timezone

from modules.silver_workflow.models import (
    BronzeSourceReference, CreateSilverWorkflowRequest, ConfirmWorkflowSourceRequest,
    SchemaColumnEvidence, SchemaContextEvidence,
)
from modules.silver_workflow.repository import InMemoryWorkflowRepository
from modules.silver_workflow.service import SilverWorkflowService


def test_workflow_version_history_returns_current_and_superseded_snapshots():
    repo = InMemoryWorkflowRepository()
    service = SilverWorkflowService(repository=repo)
    created = service.create(CreateSilverWorkflowRequest(
        source=BronzeSourceReference(
            connection_id="bq", project_id="p", dataset_id="bronze", table_id="ventas"
        ),
        requested_by="tester",
    ), correlation_id="corr")
    confirmed = service.confirm_source(created.workflow_id, ConfirmWorkflowSourceRequest(
        expected_version=created.version,
        schema_context=SchemaContextEvidence(columns=[
            SchemaColumnEvidence(name="id", data_type="INT64", nullable=False),
        ]),
        confirmed_by="tester",
    ))

    history = service.list_versions(created.workflow_id)

    assert history.total == 2
    assert history.current_version == confirmed.version
    assert history.versions[0].workflow_version == confirmed.version
    assert history.versions[0].lifecycle_status == "CURRENT"
    assert history.versions[1].workflow_version == created.version
    assert history.versions[1].lifecycle_status == "SUPERSEDED"
