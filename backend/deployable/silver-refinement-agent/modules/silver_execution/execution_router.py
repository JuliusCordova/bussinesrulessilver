from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status

from modules.silver_refinement.artifact_repository import ArtifactRepository

from .dataproc_launcher import DataprocLauncher
from .execution_models import (
    BigQueryValidationResponse,
    CreateExecutionRequest,
    DataprocSubmissionResponse,
    ExecutionListResponse,
    ExecutionMonitoringResponse,
    ExecutionRecord,
    PackageValidationResponse,
)
from .execution_repository import ExecutionRepository
from .execution_service import ExecutionService
from .package_resolver import PackageResolver
from .physical_design_materializer import PhysicalDesignMaterializer
from .watermark_repository import WatermarkRepository

router = APIRouter(prefix="/executions", tags=["silver-executions"])


def get_execution_service() -> ExecutionService:
    return ExecutionService(
        execution_repository=ExecutionRepository(),
        artifact_repository=ArtifactRepository(),
        package_resolver=PackageResolver(),
        dataproc_launcher=DataprocLauncher(),
        watermark_repository=(
            WatermarkRepository() if os.getenv("ARTIFACT_BUCKET") else None
        ),
        physical_design_materializer=PhysicalDesignMaterializer(),
    )


@router.post("", response_model=ExecutionRecord, status_code=status.HTTP_201_CREATED)
def create_execution(
    request: CreateExecutionRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionRecord:
    try:
        return service.create_execution(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{execution_id}/validate-package", response_model=PackageValidationResponse)
def validate_package(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> PackageValidationResponse:
    try:
        return service.validate_package(execution_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{execution_id}/submit", response_model=DataprocSubmissionResponse)
def submit_execution(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> DataprocSubmissionResponse:
    try:
        return service.submit_execution(execution_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{execution_id}/sync-status", response_model=ExecutionMonitoringResponse)
def sync_execution_status(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionMonitoringResponse:
    try:
        return service.sync_execution_status(execution_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/{execution_id}/result", response_model=BigQueryValidationResponse)
def validate_execution_result(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> BigQueryValidationResponse:
    try:
        return service.validate_execution_result(execution_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=ExecutionListResponse)
def list_executions(
    limit: int = Query(default=50, ge=1, le=200),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionListResponse:
    return ExecutionListResponse(executions=service.list_executions(limit=limit))


@router.get("/{execution_id}", response_model=ExecutionRecord)
def get_execution(
    execution_id: str,
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionRecord:
    record = service.get_execution(execution_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ejecución no encontrada")
    return record
