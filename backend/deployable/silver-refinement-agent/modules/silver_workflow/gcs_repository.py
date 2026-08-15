from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage

from .config import WorkflowSettings
from .models import (
    BusinessRulesSection,
    BusinessRuleStatus,
    SchemaContextEvidence,
    SilverTargetReference,
    SilverWorkflowRecord,
    WorkflowStatus,
)
from .repository import WorkflowNotFoundError, WorkflowRepository, WorkflowVersionConflictError


class CloudStorageWorkflowRepository(WorkflowRepository):
    """Persistent repository backed by versioned JSON objects in Cloud Storage."""

    def __init__(self, *, settings: WorkflowSettings, client: storage.Client | None = None) -> None:
        if not settings.gcs_bucket:
            raise ValueError("WORKFLOW_GCS_BUCKET es obligatorio para el repositorio GCS")
        self._settings = settings
        self._client = client or storage.Client()
        self._bucket = self._client.bucket(settings.gcs_bucket)
        self._prefix = settings.gcs_prefix.strip("/")

    @property
    def provider(self) -> str:
        return "GCS"

    def health(self) -> dict[str, object]:
        try:
            self._bucket.reload()
            return {"status": "ok", "provider": self.provider, "schema_ready": True, "detail": f"gs://{self._bucket.name}/{self._prefix}"}
        except Exception as exc:  # pragma: no cover
            return {"status": "degraded", "provider": self.provider, "schema_ready": False, "detail": str(exc)}

    def create(self, record: SilverWorkflowRecord) -> SilverWorkflowRecord:
        blob = self._bucket.blob(self._current_path(record.workflow_id))
        try:
            blob.upload_from_string(self._serialize(record), content_type="application/json", if_generation_match=0)
        except PreconditionFailed as exc:
            raise WorkflowVersionConflictError(f"El workflow ya existe: {record.workflow_id}") from exc
        self._write_snapshot(record)
        return record.model_copy(deep=True)

    def get(self, workflow_id: str) -> SilverWorkflowRecord | None:
        blob = self._bucket.blob(self._current_path(workflow_id))
        try:
            return SilverWorkflowRecord.model_validate_json(blob.download_as_text())
        except NotFound:
            return None

    def list(self, *, limit: int, status: WorkflowStatus | None = None) -> list[SilverWorkflowRecord]:
        records: list[SilverWorkflowRecord] = []
        for blob in self._client.list_blobs(self._bucket, prefix=self._join("workflows/")):
            if not blob.name.endswith("/current.json"):
                continue
            record = SilverWorkflowRecord.model_validate_json(blob.download_as_text())
            if status is None or record.status == status:
                records.append(record)
        records.sort(key=lambda item: item.updated_at, reverse=True)
        return [record.model_copy(deep=True) for record in records[:limit]]

    def confirm_source(self, workflow_id: str, *, expected_version: int, schema_context: SchemaContextEvidence, confirmed_by: str, updated_at: datetime) -> SilverWorkflowRecord:
        def mutate(record: SilverWorkflowRecord) -> SilverWorkflowRecord:
            metadata = dict(record.metadata)
            metadata["source_confirmed_by"] = confirmed_by
            return record.model_copy(deep=True, update={"version": record.version + 1, "status": WorkflowStatus.IN_PROGRESS, "active_step": 3, "source_confirmed": True, "schema_context": schema_context, "updated_at": updated_at, "metadata": metadata})
        return self._update(workflow_id, expected_version, mutate)

    def save_business_rules_draft(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, authored_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
        def mutate(record: SilverWorkflowRecord) -> SilverWorkflowRecord:
            metadata = dict(record.metadata)
            metadata.update({"business_rules_last_authored_by": authored_by, "business_rules_last_change_reason": change_reason})
            return record.model_copy(deep=True, update={"version": record.version + 1, "business_rules": section, "updated_at": updated_at, "metadata": metadata})
        return self._update(workflow_id, expected_version, mutate)

    def save_business_rules_proposal(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, generated_by: str, generation_reason: str, idempotency_key: str, updated_at: datetime) -> SilverWorkflowRecord:
        current = self.get(workflow_id)
        if current is None:
            raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}")
        current_key = current.business_rules.proposal_metadata.idempotency_key if current.business_rules.proposal_metadata else None
        if current.business_rules.status == BusinessRuleStatus.PROPOSED and current_key == idempotency_key:
            return current
        def mutate(record: SilverWorkflowRecord) -> SilverWorkflowRecord:
            metadata = dict(record.metadata)
            metadata.update({"business_rules_last_generated_by": generated_by, "business_rules_last_generation_reason": generation_reason, "business_rules_last_idempotency_key": idempotency_key})
            return record.model_copy(deep=True, update={"version": record.version + 1, "business_rules": section, "updated_at": updated_at, "metadata": metadata})
        return self._update(workflow_id, expected_version, mutate)

    def confirm_business_rules(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, confirmed_by: str, confirmation_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
        def mutate(record: SilverWorkflowRecord) -> SilverWorkflowRecord:
            if record.status != WorkflowStatus.IN_PROGRESS or record.active_step != 3 or not record.business_rules.is_confirmable:
                raise WorkflowVersionConflictError("El workflow cambió; recargue antes de confirmar reglas")
            metadata = dict(record.metadata)
            metadata.update({"business_rules_confirmed_by": confirmed_by, "business_rules_confirmation_reason": confirmation_reason, "business_rules_confirmed_at": updated_at.isoformat()})
            return record.model_copy(deep=True, update={"version": record.version + 1, "active_step": 4, "business_rules": section, "updated_at": updated_at, "metadata": metadata})
        return self._update(workflow_id, expected_version, mutate)

    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
        def mutate(record: SilverWorkflowRecord) -> SilverWorkflowRecord:
            if record.spec_id is not None:
                raise WorkflowVersionConflictError("El workflow ya tiene una especificación Silver")
            metadata = dict(record.metadata)
            metadata.update({"specification_created_by": created_by, "specification_change_reason": change_reason, "specification_created_at": updated_at.isoformat(), "silver_target_fqn": target.fully_qualified_name})
            return record.model_copy(deep=True, update={"version": record.version + 1, "active_step": 5, "spec_id": spec_id, "mapping_version": mapping_version, "silver_target": target, "mapping_rules": mapping_rules, "updated_at": updated_at, "metadata": metadata})
        return self._update(workflow_id, expected_version, mutate)

    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:
        def mutate(record: SilverWorkflowRecord) -> SilverWorkflowRecord:
            if record.active_step != 5 or not record.spec_id:
                raise WorkflowVersionConflictError("El workflow no está listo para revisión de calidad")
            metadata = dict(record.metadata)
            metadata.update({"quality_reviewed_by": quality_review["reviewed_by"], "quality_review_decision": quality_review["decision"], "quality_reviewed_at": updated_at.isoformat()})
            return record.model_copy(deep=True, update={"version": record.version + 1, "active_step": 6, "quality_rules": quality_rules, "quality_review": quality_review, "updated_at": updated_at, "metadata": metadata})
        return self._update(workflow_id, expected_version, mutate)

    def _update(self, workflow_id: str, expected_version: int, mutate: Callable[[SilverWorkflowRecord], SilverWorkflowRecord]) -> SilverWorkflowRecord:
        blob = self._bucket.blob(self._current_path(workflow_id))
        try:
            blob.reload()
            generation = int(blob.generation)
            current = SilverWorkflowRecord.model_validate_json(blob.download_as_text())
        except NotFound as exc:
            raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}") from exc
        if current.version != expected_version:
            raise WorkflowVersionConflictError("La versión del workflow cambió; recargue antes de continuar")
        updated = mutate(current)
        self._write_snapshot(updated)
        try:
            blob.upload_from_string(self._serialize(updated), content_type="application/json", if_generation_match=generation)
        except PreconditionFailed as exc:
            raise WorkflowVersionConflictError("El workflow fue actualizado concurrentemente; recargue antes de continuar") from exc
        return updated.model_copy(deep=True)

    def _write_snapshot(self, record: SilverWorkflowRecord) -> None:
        blob = self._bucket.blob(self._snapshot_path(record.workflow_id, record.version))
        try:
            blob.upload_from_string(self._serialize(record), content_type="application/json", if_generation_match=0)
        except PreconditionFailed:
            existing = SilverWorkflowRecord.model_validate_json(blob.download_as_text())
            if existing != record:
                raise WorkflowVersionConflictError(f"Ya existe un snapshot distinto para la versión {record.version}")

    @staticmethod
    def _serialize(record: SilverWorkflowRecord) -> str:
        return json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

    def _current_path(self, workflow_id: str) -> str:
        return self._join(f"workflows/{workflow_id}/current.json")

    def _snapshot_path(self, workflow_id: str, version: int) -> str:
        return self._join(f"workflows/{workflow_id}/versions/{version:06d}.json")

    def _join(self, suffix: str) -> str:
        return f"{self._prefix}/{suffix}" if self._prefix else suffix
