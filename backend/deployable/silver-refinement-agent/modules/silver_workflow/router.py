from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .business_rule_validation import BusinessRuleValidationError
from .destination_catalog import register_destination_catalog_routes
from .mapping_recommendation import (
    GenerateMappingRecommendationRequest,
    MappingRecommendationResponse,
    build_mapping_recommendation,
)
from .models import (
    BusinessRulesSection,
    ConfirmBusinessRulesRequest,
    ConfirmWorkflowSourceRequest,
    CreateSilverWorkflowRequest,
    GenerateBusinessRulesRequest,
    MappingImpactRequest,
    MappingImpactResponse,
    ReviewQualityRequest,
    SaveBusinessRulesDraftRequest,
    SaveSilverMappingRequest,
    SaveSilverSpecificationRequest,
    SilverWorkflowListResponse,
    SilverWorkflowRecord,
    SilverWorkflowVersionListResponse,
    WorkflowRepositoryHealth,
    WorkflowStatus,
)
from .repository import WorkflowNotFoundError, WorkflowVersionConflictError
from .repository_factory import get_workflow_repository
from .service import SilverWorkflowService, WorkflowStateConflictError
from .workflow_availability import WorkflowBusinessOperation, workflow_business_operation

router = APIRouter(prefix="/silver-workflows", tags=["silver-workflows"])
register_destination_catalog_routes(router)

require_workflow_create = workflow_business_operation("workflow_create")
require_workflow_list = workflow_business_operation("workflow_list")
require_workflow_get = workflow_business_operation("workflow_get")
require_workflow_mapping = workflow_business_operation("workflow_mapping")
require_workflow_confirm_source = workflow_business_operation("workflow_confirm_source")
require_business_rules_get = workflow_business_operation("business_rules_get")
require_business_rules_draft = workflow_business_operation("business_rules_draft")
require_business_rules_generate = workflow_business_operation("business_rules_generate")
require_business_rules_confirm = workflow_business_operation("business_rules_confirm")
require_specification_save = workflow_business_operation("specification_save")
require_quality_review = workflow_business_operation("quality_review")


def get_workflow_service() -> SilverWorkflowService:
    return SilverWorkflowService(repository=get_workflow_repository())


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/health", response_model=WorkflowRepositoryHealth)
def workflow_health(service: SilverWorkflowService = Depends(get_workflow_service)) -> WorkflowRepositoryHealth:
    return service.health()


@router.post("", response_model=SilverWorkflowRecord, status_code=status.HTTP_201_CREATED)
def create_workflow(request: CreateSilverWorkflowRequest, business: WorkflowBusinessOperation = Depends(require_workflow_create)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.create(request, correlation_id=business.correlation_id)
        business.record_success(workflow_id=record.workflow_id)
        return record
    except WorkflowVersionConflictError as exc:
        raise _conflict(exc) from exc


@router.get("", response_model=SilverWorkflowListResponse)
def list_workflows(limit: int = Query(default=50, ge=1, le=200), workflow_status: WorkflowStatus | None = Query(default=None, alias="status"), business: WorkflowBusinessOperation = Depends(require_workflow_list)) -> SilverWorkflowListResponse:
    result = business.workflow_service.list(limit=limit, status=workflow_status)
    business.record_success()
    return result


@router.get("/{workflow_id}/versions", response_model=SilverWorkflowVersionListResponse)
def list_workflow_versions(workflow_id: str, business: WorkflowBusinessOperation = Depends(require_workflow_get)) -> SilverWorkflowVersionListResponse:
    try:
        result = business.workflow_service.list_versions(workflow_id)
        business.record_success(workflow_id=workflow_id)
        return result
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{workflow_id}/business-rules", response_model=BusinessRulesSection)
def get_workflow_business_rules(workflow_id: str, business: WorkflowBusinessOperation = Depends(require_business_rules_get)) -> BusinessRulesSection:
    try:
        section = business.workflow_service.get_business_rules(workflow_id)
        business.record_success(workflow_id=workflow_id)
        return section
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc


@router.put("/{workflow_id}/business-rules/draft", response_model=SilverWorkflowRecord)
def save_workflow_business_rules_draft(workflow_id: str, request: SaveBusinessRulesDraftRequest, business: WorkflowBusinessOperation = Depends(require_business_rules_draft)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.save_business_rules_draft(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
    except BusinessRuleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{workflow_id}/business-rules/generate", response_model=SilverWorkflowRecord)
def generate_workflow_business_rules(workflow_id: str, request: GenerateBusinessRulesRequest, business: WorkflowBusinessOperation = Depends(require_business_rules_generate)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.generate_business_rules_proposal(workflow_id, request, generated_by=business.requested_by, idempotency_key=business.idempotency_key)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
    except (BusinessRuleValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{workflow_id}/business-rules/confirm", response_model=SilverWorkflowRecord)
def confirm_workflow_business_rules(workflow_id: str, request: ConfirmBusinessRulesRequest, business: WorkflowBusinessOperation = Depends(require_business_rules_confirm)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.confirm_business_rules(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
    except BusinessRuleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{workflow_id}/mapping/impact", response_model=MappingImpactResponse)
def analyze_workflow_mapping_impact(workflow_id: str, request: MappingImpactRequest, business: WorkflowBusinessOperation = Depends(require_workflow_mapping)) -> MappingImpactResponse:
    try:
        result = business.workflow_service.analyze_mapping_impact(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return result
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.put("/{workflow_id}/mapping", response_model=SilverWorkflowRecord)
def save_workflow_mapping(workflow_id: str, request: SaveSilverMappingRequest, business: WorkflowBusinessOperation = Depends(require_workflow_mapping)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.save_mapping_version(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{workflow_id}/mapping-recommendations", response_model=MappingRecommendationResponse)
def generate_mapping_recommendations(workflow_id: str, request: GenerateMappingRecommendationRequest, business: WorkflowBusinessOperation = Depends(require_workflow_get)) -> MappingRecommendationResponse:
    try:
        workflow = business.workflow_service.get(workflow_id)
        recommendation = build_mapping_recommendation(workflow, request)
        business.record_success(workflow_id=workflow_id)
        return recommendation
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{workflow_id}/specification", response_model=SilverWorkflowRecord)
def save_workflow_specification(workflow_id: str, request: SaveSilverSpecificationRequest, business: WorkflowBusinessOperation = Depends(require_specification_save)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.save_specification(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{workflow_id}/quality-review", response_model=SilverWorkflowRecord)
def review_workflow_quality(workflow_id: str, request: ReviewQualityRequest, business: WorkflowBusinessOperation = Depends(require_quality_review)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.review_quality(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc


@router.get("/{workflow_id}", response_model=SilverWorkflowRecord)
def get_workflow(workflow_id: str, business: WorkflowBusinessOperation = Depends(require_workflow_get)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.get(workflow_id)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/{workflow_id}/confirm-source", response_model=SilverWorkflowRecord)
def confirm_workflow_source(workflow_id: str, request: ConfirmWorkflowSourceRequest, business: WorkflowBusinessOperation = Depends(require_workflow_confirm_source)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.confirm_source(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
