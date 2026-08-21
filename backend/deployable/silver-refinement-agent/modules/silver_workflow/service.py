from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from .business_rule_generator import BusinessRuleProposalGenerator, DeterministicBusinessRuleProposalGenerator
from .business_rule_validation import build_draft_section, validate_rules_against_schema
from .models import (
    BusinessRulesSection,
    BusinessRuleStatus,
    ConfirmBusinessRulesRequest,
    ConfirmWorkflowSourceRequest,
    CreateSilverWorkflowRequest,
    GenerateBusinessRulesRequest,
    ReviewQualityRequest,
    SaveBusinessRulesDraftRequest,
    SaveSilverMappingRequest,
    SaveSilverSpecificationRequest,
    SilverWorkflowListResponse,
    SilverWorkflowRecord,
    WorkflowAction,
    WorkflowRepositoryHealth,
    WorkflowStatus,
)
from .repository import WorkflowNotFoundError, WorkflowRepository, WorkflowVersionConflictError


class WorkflowStateConflictError(RuntimeError):
    pass


class SilverWorkflowService:
    def __init__(self, repository: WorkflowRepository, proposal_generator: BusinessRuleProposalGenerator | None = None) -> None:
        self.repository = repository
        self.proposal_generator = proposal_generator or DeterministicBusinessRuleProposalGenerator()

    def health(self) -> WorkflowRepositoryHealth:
        return WorkflowRepositoryHealth.model_validate(self.repository.health())

    def create(self, request: CreateSilverWorkflowRequest, *, correlation_id: str | None) -> SilverWorkflowRecord:
        now = datetime.now(timezone.utc)
        record = SilverWorkflowRecord(
            workflow_id=f"workflow_{uuid4().hex}", version=1, status=WorkflowStatus.DRAFT,
            active_step=1, source=request.source, source_confirmed=False,
            correlation_id=correlation_id or f"corr_{uuid4().hex}", created_by=request.requested_by,
            created_at=now, updated_at=now, metadata=request.metadata,
        )
        return self._with_actions(self.repository.create(record))

    def get(self, workflow_id: str) -> SilverWorkflowRecord:
        record = self.repository.get(workflow_id)
        if record is None:
            raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}")
        return self._with_actions(record)

    def get_business_rules(self, workflow_id: str) -> BusinessRulesSection:
        return self.get(workflow_id).business_rules

    def list(self, *, limit: int, status: WorkflowStatus | None) -> SilverWorkflowListResponse:
        records = [self._with_actions(record) for record in self.repository.list(limit=limit, status=status)]
        return SilverWorkflowListResponse(total=len(records), workflows=records)

    def confirm_source(self, workflow_id: str, request: ConfirmWorkflowSourceRequest) -> SilverWorkflowRecord:
        current = self.repository.get(workflow_id)
        if current is None:
            raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}")
        if current.source_confirmed or current.active_step > 2:
            raise WorkflowStateConflictError("La fuente Bronze ya fue confirmada para este workflow")
        if current.status != WorkflowStatus.DRAFT:
            raise WorkflowStateConflictError(f"No se puede confirmar la fuente desde el estado {current.status.value}")
        if current.version != request.expected_version:
            raise WorkflowVersionConflictError("La versión del workflow cambió; recargue antes de confirmar la fuente")
        return self._with_actions(self.repository.confirm_source(
            workflow_id, expected_version=request.expected_version,
            schema_context=request.schema_context, confirmed_by=request.confirmed_by,
            updated_at=datetime.now(timezone.utc),
        ))

    def validate_business_rules_draft(self, workflow_id: str, request: SaveBusinessRulesDraftRequest) -> BusinessRulesSection:
        current = self._require_business_rules_step(workflow_id, expected_version=request.expected_version)
        assert current.schema_context is not None
        return build_draft_section(request, schema_context=current.schema_context, updated_at=datetime.now(timezone.utc))

    def save_business_rules_draft(self, workflow_id: str, request: SaveBusinessRulesDraftRequest) -> SilverWorkflowRecord:
        section = self.validate_business_rules_draft(workflow_id, request)
        return self._with_actions(self.repository.save_business_rules_draft(
            workflow_id, expected_version=request.expected_version, section=section,
            authored_by=request.authored_by, change_reason=request.change_reason,
            updated_at=section.last_modified_at or datetime.now(timezone.utc),
        ))

    def generate_business_rules_proposal(self, workflow_id: str, request: GenerateBusinessRulesRequest, *, generated_by: str, idempotency_key: str) -> SilverWorkflowRecord:
        existing = self.repository.get(workflow_id)
        if existing is None:
            raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}")
        fingerprint = self._proposal_request_fingerprint(request)
        metadata = existing.business_rules.proposal_metadata
        if existing.business_rules.status == BusinessRuleStatus.PROPOSED and metadata and metadata.idempotency_key == idempotency_key:
            stored = metadata.metadata.get("request_fingerprint")
            if stored and stored != fingerprint:
                raise WorkflowVersionConflictError("La misma idempotency key fue reutilizada con un payload distinto")
            return self._with_actions(existing)
        current = self._require_business_rules_step(workflow_id, expected_version=request.expected_version)
        generated_at = datetime.now(timezone.utc)
        section = self.proposal_generator.generate(current, request, generated_by=generated_by, idempotency_key=idempotency_key, generated_at=generated_at)
        if section.proposal_metadata is None:
            raise ValueError("La propuesta generada no contiene proposal_metadata")
        section = section.model_copy(deep=True, update={"proposal_metadata": section.proposal_metadata.model_copy(deep=True, update={"metadata": {**section.proposal_metadata.metadata, "request_fingerprint": fingerprint}})})
        assert current.schema_context is not None
        validate_rules_against_schema(section.rules, current.schema_context, require_enabled=True)
        return self._with_actions(self.repository.save_business_rules_proposal(
            workflow_id, expected_version=request.expected_version, section=section,
            generated_by=generated_by, generation_reason=request.generation_reason,
            idempotency_key=idempotency_key, updated_at=generated_at,
        ))

    def validate_business_rules_confirmation(self, workflow_id: str, request: ConfirmBusinessRulesRequest) -> BusinessRulesSection:
        current = self._require_business_rules_step(workflow_id, expected_version=request.expected_version)
        section = current.business_rules
        if not section.is_confirmable:
            raise WorkflowStateConflictError("El workflow no contiene un borrador o propuesta confirmable")
        if section.status == BusinessRuleStatus.PROPOSED and request.selected_proposal_id != section.proposal_id:
            raise WorkflowStateConflictError("La propuesta seleccionada no coincide con la propuesta vigente")
        if section.status != BusinessRuleStatus.PROPOSED and request.selected_proposal_id is not None:
            raise WorkflowStateConflictError("Un borrador manual no admite selected_proposal_id")
        assert current.schema_context is not None
        validate_rules_against_schema(section.rules, current.schema_context, require_enabled=True)
        return section

    def confirm_business_rules(self, workflow_id: str, request: ConfirmBusinessRulesRequest) -> SilverWorkflowRecord:
        section = self.validate_business_rules_confirmation(workflow_id, request)
        confirmed_at = datetime.now(timezone.utc)
        confirmed = section.model_copy(deep=True, update={
            "status": BusinessRuleStatus.CONFIRMED, "confirmed_by": request.confirmed_by,
            "confirmed_at": confirmed_at, "confirmation_reason": request.confirmation_reason,
        })
        return self._with_actions(self.repository.confirm_business_rules(
            workflow_id, expected_version=request.expected_version, section=confirmed,
            confirmed_by=request.confirmed_by, confirmation_reason=request.confirmation_reason,
            updated_at=confirmed_at,
        ))

    def save_mapping_version(self, workflow_id: str, request: SaveSilverMappingRequest) -> SilverWorkflowRecord:
        current = self._require_version(workflow_id, request.expected_version)
        if not current.source_confirmed or current.schema_context is None:
            raise WorkflowStateConflictError("La fuente y el esquema deben estar confirmados antes de editar el mapping")
        if current.business_rules.status != BusinessRuleStatus.CONFIRMED:
            raise WorkflowStateConflictError("Las Business Rules deben estar confirmadas antes de versionar el mapping")
        if current.status == WorkflowStatus.EXECUTING:
            raise WorkflowStateConflictError("No se puede editar el mapping mientras el proceso está ejecutándose")

        source_columns = {column.name for column in current.schema_context.columns}
        unknown = sorted({
            column.source_column
            for column in request.columns
            if column.source_column and column.source_column not in source_columns
        })
        if unknown:
            raise ValueError("Las columnas de origen no existen en el esquema confirmado: " + ", ".join(unknown))

        next_mapping_version = (current.mapping_version or 0) + 1
        return self._with_actions(self.repository.save_mapping_version(
            workflow_id,
            expected_version=request.expected_version,
            mapping_version=next_mapping_version,
            target=request.target,
            mapping_rules=[column.model_dump(mode="json") for column in request.columns],
            edited_by=request.edited_by,
            change_reason=request.change_reason,
            updated_at=datetime.now(timezone.utc),
        ))

    def save_specification(self, workflow_id: str, request: SaveSilverSpecificationRequest) -> SilverWorkflowRecord:
        current = self._require_specification_step(workflow_id, expected_version=request.expected_version)
        assert current.schema_context is not None
        source_columns = {column.name for column in current.schema_context.columns}
        unknown = sorted({column.source_column for column in request.columns if column.source_column and column.source_column not in source_columns})
        if unknown:
            raise ValueError("Las columnas de origen no existen en el esquema confirmado: " + ", ".join(unknown))
        return self._with_actions(self.repository.save_specification(
            workflow_id, expected_version=request.expected_version, spec_id=f"spec_{uuid4().hex}",
            mapping_version=request.mapping_version, target=request.target,
            mapping_rules=[column.model_dump(mode="json") for column in request.columns],
            created_by=request.created_by, change_reason=request.change_reason,
            updated_at=datetime.now(timezone.utc),
        ))

    def review_quality(self, workflow_id: str, request: ReviewQualityRequest) -> SilverWorkflowRecord:
        current = self._require_quality_step(workflow_id, expected_version=request.expected_version)
        reviewed_at = datetime.now(timezone.utc)
        review = {
            "decision": request.decision.value,
            "reviewed_by": request.reviewed_by,
            "review_notes": request.review_notes,
            "reviewed_at": reviewed_at.isoformat(),
            "source_workflow_version": current.version,
        }
        return self._with_actions(self.repository.review_quality(
            workflow_id, expected_version=request.expected_version,
            quality_rules=request.quality_rules, quality_review=review,
            updated_at=reviewed_at,
        ))

    def _require_business_rules_step(self, workflow_id: str, *, expected_version: int) -> SilverWorkflowRecord:
        current = self._require_version(workflow_id, expected_version)
        if current.status != WorkflowStatus.IN_PROGRESS or current.active_step != 3:
            raise WorkflowStateConflictError(f"Las Business Rules requieren el paso 3; paso actual: {current.active_step}")
        if not current.source_confirmed or current.schema_context is None:
            raise WorkflowStateConflictError("La fuente y el esquema deben estar confirmados antes de definir reglas")
        return current

    def _require_specification_step(self, workflow_id: str, *, expected_version: int) -> SilverWorkflowRecord:
        current = self._require_version(workflow_id, expected_version)
        if current.status != WorkflowStatus.IN_PROGRESS or current.active_step != 4:
            raise WorkflowStateConflictError(f"La especificación Silver requiere el paso 4; paso actual: {current.active_step}")
        if current.business_rules.status != BusinessRuleStatus.CONFIRMED:
            raise WorkflowStateConflictError("Las Business Rules deben estar confirmadas antes de guardar el mapping")
        if current.spec_id is not None:
            raise WorkflowStateConflictError("El workflow ya tiene una especificación Silver")
        return current

    def _require_quality_step(self, workflow_id: str, *, expected_version: int) -> SilverWorkflowRecord:
        current = self._require_version(workflow_id, expected_version)
        if current.status != WorkflowStatus.IN_PROGRESS or current.active_step != 5:
            raise WorkflowStateConflictError(f"La revisión de calidad requiere el paso 5; paso actual: {current.active_step}")
        if not current.spec_id or not current.mapping_rules or current.silver_target is None:
            raise WorkflowStateConflictError("El contrato Silver debe estar persistido antes de revisar calidad")
        if current.quality_review is not None:
            raise WorkflowStateConflictError("La revisión de calidad ya fue confirmada")
        return current

    def _require_version(self, workflow_id: str, expected_version: int) -> SilverWorkflowRecord:
        current = self.repository.get(workflow_id)
        if current is None:
            raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}")
        if current.version != expected_version:
            raise WorkflowVersionConflictError("La versión del workflow cambió; recargue antes de continuar")
        return current

    @staticmethod
    def _proposal_request_fingerprint(request: GenerateBusinessRulesRequest) -> str:
        canonical = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _with_actions(record: SilverWorkflowRecord) -> SilverWorkflowRecord:
        actions: list[WorkflowAction] = []
        if record.status == WorkflowStatus.DRAFT and not record.source_confirmed:
            actions.append(WorkflowAction.CONFIRM_SOURCE)
        elif record.status == WorkflowStatus.IN_PROGRESS:
            if record.active_step == 3:
                actions.extend([WorkflowAction.DEFINE_BUSINESS_RULES, WorkflowAction.GENERATE_BUSINESS_RULES])
                if record.business_rules.is_confirmable:
                    actions.append(WorkflowAction.CONFIRM_BUSINESS_RULES)
            elif record.active_step == 4:
                actions.append(WorkflowAction.REVIEW_MAPPING)
            elif record.active_step == 5:
                actions.append(WorkflowAction.REVIEW_QUALITY)
            elif record.active_step == 6:
                actions.extend([WorkflowAction.GENERATE_ARTIFACTS, WorkflowAction.REVIEW_GOVERNANCE])
            elif record.active_step == 7:
                actions.append(WorkflowAction.CREATE_EXECUTION)
            elif record.active_step == 8:
                actions.extend([WorkflowAction.MONITOR_EXECUTION, WorkflowAction.VALIDATE_SILVER])
        elif record.status in {WorkflowStatus.SUCCEEDED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}:
            actions.append(WorkflowAction.VIEW_RESULT)
        return record.model_copy(update={"available_actions": actions})
