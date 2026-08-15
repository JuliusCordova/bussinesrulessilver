from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from .memory_availability import MemoryBusinessOperation, memory_business_operation
from .memory_models import (
    MemoryEventCreate,
    MemoryRecord,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySession,
    MemorySessionCreate,
)
from .memory_service import SharedMemoryService


router = APIRouter(prefix="/agentops/memory", tags=["shared-memory"])


# Health is deliberately kept outside the business availability gate. It may
# report database degradation, but it must never request an AlloyDB start.
def get_memory_service() -> SharedMemoryService:
    return SharedMemoryService()


require_memory_session_create = memory_business_operation("memory_session_create")
require_memory_session_read = memory_business_operation("memory_session_read")
require_memory_event_create = memory_business_operation("memory_event_create")
require_memory_events_read = memory_business_operation("memory_events_read")
require_memory_search = memory_business_operation("memory_search")


@router.get("/health", response_model=dict[str, Any])
def memory_health(
    service: SharedMemoryService = Depends(get_memory_service),
) -> dict[str, Any]:
    return service.health()


@router.post("/sessions", response_model=MemorySession, status_code=status.HTTP_201_CREATED)
def create_session(
    request: MemorySessionCreate,
    operation: MemoryBusinessOperation = Depends(require_memory_session_create),
) -> MemorySession:
    result = operation.memory_service.create_session(request)
    operation.record_success()
    return result


@router.get("/sessions/{session_id}", response_model=MemorySession)
def get_session(
    session_id: str,
    operation: MemoryBusinessOperation = Depends(require_memory_session_read),
) -> MemorySession:
    try:
        result = operation.memory_service.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    operation.record_success()
    return result


@router.post("/events", response_model=MemoryRecord, status_code=status.HTTP_201_CREATED)
def add_event(
    request: MemoryEventCreate,
    operation: MemoryBusinessOperation = Depends(require_memory_event_create),
) -> MemoryRecord:
    try:
        result = operation.memory_service.add_event(request)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    operation.record_success()
    return result


@router.get("/sessions/{session_id}/events", response_model=list[MemoryRecord])
def list_events(
    session_id: str,
    operation: MemoryBusinessOperation = Depends(require_memory_events_read),
) -> list[MemoryRecord]:
    try:
        result = operation.memory_service.list_memories(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    operation.record_success()
    return result


@router.post("/search", response_model=MemorySearchResponse)
def search_memory(
    request: MemorySearchRequest,
    operation: MemoryBusinessOperation = Depends(require_memory_search),
) -> MemorySearchResponse:
    result = operation.memory_service.search(request)
    operation.record_success()
    return result
