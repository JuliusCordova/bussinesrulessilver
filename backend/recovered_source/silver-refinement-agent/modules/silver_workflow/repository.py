from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Protocol

from .models import (
    BusinessRulesSection,
    BusinessRuleStatus,
    SchemaContextEvidence,
    SilverTargetReference,
    SilverWorkflowRecord,
    WorkflowStatus,
)


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowVersionConflictError(RuntimeError):
    pass


class WorkflowRepository(Protocol):
    @property
    def provider(self) -> str: ...
    def health(self) -> dict[str, object]: ...
    def create(self, record: SilverWorkflowRecord) -> SilverWorkflowRecord: ...
    def get(self, workflow_id: str) -> SilverWorkflowRecord | None: ...
    def list(self, *, limit: int, status: WorkflowStatus | None = None) -> list[SilverWorkflowRecord]: ...
    def confirm_source(self, workflow_id: str, *, expected_version: int, schema_context: SchemaContextEvidence, confirmed_by: str, updated_at: datetime) -> SilverWorkflowRecord: ...
    def save_business_rules_draft(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, authored_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord: ...
    def save_business_rules_proposal(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, generated_by: str, generation_reason: str, idempotency_key: str, updated_at: datetime) -> SilverWorkflowRecord: ...
    def confirm_business_rules(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, confirmed_by: str, confirmation_reason: str, updated_at: datetime) -> SilverWorkflowRecord: ...
    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord: ...
    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord: ...


class InMemoryWorkflowRepository:
    def __init__(self) -> None:
        self._records: dict[str, SilverWorkflowRecord] = {}
        self._lock = RLock()

    @property
    def provider(self) -> str:
        return "IN_MEMORY"

    def health(self) -> dict[str, object]:
        return {"status": "ok", "provider": self.provider, "schema_ready": True}

    def create(self, record: SilverWorkflowRecord) -> SilverWorkflowRecord:
        with self._lock:
            if record.workflow_id in self._records:
                raise WorkflowVersionConflictError(f"El workflow ya existe: {record.workflow_id}")
            self._records[record.workflow_id] = deepcopy(record)
            return deepcopy(record)

    def get(self, workflow_id: str) -> SilverWorkflowRecord | None:
        with self._lock:
            record = self._records.get(workflow_id)
            return deepcopy(record) if record else None

    def list(self, *, limit: int, status: WorkflowStatus | None = None) -> list[SilverWorkflowRecord]:
        with self._lock:
            records = list(self._records.values())
            if status is not None:
                records = [record for record in records if record.status == status]
            records.sort(key=lambda record: record.updated_at, reverse=True)
            return [deepcopy(record) for record in records[:limit]]

    def confirm_source(self, workflow_id: str, *, expected_version: int, schema_context: SchemaContextEvidence, confirmed_by: str, updated_at: datetime) -> SilverWorkflowRecord:
        with self._lock:
            record = self._require_record(workflow_id)
            self._require_version(record, expected_version, "confirmar la fuente")
            metadata = dict(record.metadata)
            metadata["source_confirmed_by"] = confirmed_by
            return self._store(record.model_copy(deep=True, update={
                "version": record.version + 1, "status": WorkflowStatus.IN_PROGRESS,
                "active_step": 3, "source_confirmed": True, "schema_context": schema_context,
                "updated_at": updated_at, "metadata": metadata,
            }))

    def save_business_rules_draft(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, authored_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
        with self._lock:
            record = self._require_record(workflow_id)
            self._require_version(record, expected_version, "editar reglas")
            metadata = dict(record.metadata)
            metadata.update({"business_rules_last_authored_by": authored_by, "business_rules_last_change_reason": change_reason})
            return self._store(record.model_copy(deep=True, update={"version": record.version + 1, "business_rules": section, "updated_at": updated_at, "metadata": metadata}))

    def save_business_rules_proposal(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, generated_by: str, generation_reason: str, idempotency_key: str, updated_at: datetime) -> SilverWorkflowRecord:
        with self._lock:
            record = self._require_record(workflow_id)
            current_key = record.business_rules.proposal_metadata.idempotency_key if record.business_rules.proposal_metadata else None
            if record.business_rules.status == BusinessRuleStatus.PROPOSED and current_key == idempotency_key:
                return deepcopy(record)
            self._require_version(record, expected_version, "generar reglas")
            metadata = dict(record.metadata)
            metadata.update({"business_rules_last_generated_by": generated_by, "business_rules_last_generation_reason": generation_reason, "business_rules_last_idempotency_key": idempotency_key})
            return self._store(record.model_copy(deep=True, update={"version": record.version + 1, "business_rules": section, "updated_at": updated_at, "metadata": metadata}))

    def confirm_business_rules(self, workflow_id: str, *, expected_version: int, section: BusinessRulesSection, confirmed_by: str, confirmation_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
        with self._lock:
            record = self._require_record(workflow_id)
            self._require_version(record, expected_version, "confirmar reglas")
            if record.status != WorkflowStatus.IN_PROGRESS or record.active_step != 3 or not record.business_rules.is_confirmable:
                raise WorkflowVersionConflictError("El workflow cambió; recargue antes de confirmar reglas")
            metadata = dict(record.metadata)
            metadata.update({"business_rules_confirmed_by": confirmed_by, "business_rules_confirmation_reason": confirmation_reason, "business_rules_confirmed_at": updated_at.isoformat()})
            return self._store(record.model_copy(deep=True, update={"version": record.version + 1, "active_step": 4, "business_rules": section, "updated_at": updated_at, "metadata": metadata}))

    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
        with self._lock:
            record = self._require_record(workflow_id)
            self._require_version(record, expected_version, "guardar el contrato Silver")
            if record.spec_id is not None:
                raise WorkflowVersionConflictError("El workflow ya tiene una especificación Silver")
            metadata = dict(record.metadata)
            metadata.update({"specification_created_by": created_by, "specification_change_reason": change_reason, "specification_created_at": updated_at.isoformat(), "silver_target_fqn": target.fully_qualified_name})
            return self._store(record.model_copy(deep=True, update={
                "version": record.version + 1, "active_step": 5, "spec_id": spec_id,
                "mapping_version": mapping_version, "silver_target": target,
                "mapping_rules": mapping_rules, "updated_at": updated_at, "metadata": metadata,
            }))

    def review_quality(self, workflow_id: str, *, expected_version: int, quality_rules: list[dict[str, object]], quality_review: dict[str, object], updated_at: datetime) -> SilverWorkflowRecord:
        with self._lock:
            record = self._require_record(workflow_id)
            self._require_version(record, expected_version, "confirmar la revisión de calidad")
            if record.active_step != 5 or not record.spec_id:
                raise WorkflowVersionConflictError("El workflow no está listo para revisión de calidad")
            metadata = dict(record.metadata)
            metadata.update({
                "quality_reviewed_by": quality_review["reviewed_by"],
                "quality_review_decision": quality_review["decision"],
                "quality_reviewed_at": updated_at.isoformat(),
            })
            return self._store(record.model_copy(deep=True, update={
                "version": record.version + 1, "active_step": 6,
                "quality_rules": quality_rules, "quality_review": quality_review,
                "updated_at": updated_at, "metadata": metadata,
            }))

    def _require_record(self, workflow_id: str) -> SilverWorkflowRecord:
        record = self._records.get(workflow_id)
        if record is None:
            raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}")
        return record

    @staticmethod
    def _require_version(record: SilverWorkflowRecord, expected_version: int, operation: str) -> None:
        if record.version != expected_version:
            raise WorkflowVersionConflictError(f"La versión del workflow cambió; recargue antes de {operation}")

    def _store(self, updated: SilverWorkflowRecord) -> SilverWorkflowRecord:
        self._records[updated.workflow_id] = deepcopy(updated)
        return deepcopy(updated)
