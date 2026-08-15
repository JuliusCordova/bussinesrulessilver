from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status

from modules.platform_availability.dependencies import get_alloydb_availability_service
from modules.platform_availability.models import (
    AlloyDBAvailabilityState,
    BusinessAvailabilityContext,
)
from modules.platform_availability.service import AlloyDBAvailabilityService

from .memory_service import SharedMemoryService


@dataclass
class MemoryBusinessOperation:
    operation: str
    correlation_id: str
    requested_by: str
    idempotency_key: str
    context: BusinessAvailabilityContext
    availability_service: AlloyDBAvailabilityService
    memory_service: SharedMemoryService

    def record_success(self) -> bool:
        return self.availability_service.record_business_activity(
            self.context,
            domain="shared-memory",
        )


def _clean_header(value: str | None, fallback: str) -> str:
    cleaned = (value or "").strip()
    return cleaned or fallback


def _business_context(request: Request, operation: str) -> BusinessAvailabilityContext:
    correlation_id = _clean_header(
        request.headers.get("X-Correlation-ID")
        or request.headers.get("X-Request-ID"),
        f"corr-{uuid4().hex}",
    )[:256]
    requested_by = _clean_header(
        request.headers.get("X-Requested-By")
        or request.headers.get("X-Authenticated-User"),
        "silver-refinement-agent",
    )[:256]
    idempotency_key = _clean_header(
        request.headers.get("X-Idempotency-Key"),
        f"{correlation_id}:{operation}",
    )[:256]
    if len(idempotency_key) < 8:
        idempotency_key = f"memory:{idempotency_key}"[:256]
    return BusinessAvailabilityContext(
        operation=operation,
        correlation_id=correlation_id,
        requested_by=requested_by,
        idempotency_key=idempotency_key,
    )


def memory_business_operation(
    operation: str,
) -> Callable[..., MemoryBusinessOperation]:
    def dependency(
        request: Request,
        availability_service: AlloyDBAvailabilityService = Depends(
            get_alloydb_availability_service
        ),
    ) -> MemoryBusinessOperation:
        context = _business_context(request, operation)
        availability = availability_service.ensure_ready(context)
        if not availability.ready:
            error_code = (
                "ALLOYDB_STARTING"
                if availability.state == AlloyDBAvailabilityState.STARTING
                else "ALLOYDB_UNAVAILABLE"
            )
            headers = {"X-Correlation-ID": context.correlation_id}
            if availability.retry_after_seconds:
                headers["Retry-After"] = str(availability.retry_after_seconds)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                headers=headers,
                detail={
                    "code": error_code,
                    "message": availability.reason,
                    "state": availability.state.value,
                    "retryable": availability.retryable,
                    "retry_after_seconds": availability.retry_after_seconds,
                    "request_id": availability.request_id,
                    "correlation_id": context.correlation_id,
                },
            )

        # The repository is constructed only after AlloyDB is READY or the feature
        # is safely bypassed. This avoids opening a PostgreSQL pool while stopped.
        return MemoryBusinessOperation(
            operation=operation,
            correlation_id=context.correlation_id,
            requested_by=context.requested_by,
            idempotency_key=context.idempotency_key,
            context=context,
            availability_service=availability_service,
            memory_service=SharedMemoryService(),
        )

    dependency.__name__ = f"require_{operation}"
    return dependency
