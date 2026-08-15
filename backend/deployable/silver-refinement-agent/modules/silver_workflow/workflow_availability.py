from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from fastapi import Request

from modules.platform_availability.models import BusinessAvailabilityContext

from .repository_factory import get_workflow_repository
from .service import SilverWorkflowService


@dataclass
class WorkflowBusinessOperation:
    operation: str
    correlation_id: str
    requested_by: str
    idempotency_key: str
    context: BusinessAvailabilityContext
    workflow_service: SilverWorkflowService

    def record_success(self, *, workflow_id: str | None = None) -> bool:
        """Compatibility no-op after retiring AlloyDB activity tracking."""
        return True


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
        idempotency_key = f"workflow:{idempotency_key}"[:256]
    return BusinessAvailabilityContext(
        operation=operation,
        correlation_id=correlation_id,
        requested_by=requested_by,
        idempotency_key=idempotency_key,
    )


def workflow_business_operation(
    operation: str,
) -> Callable[..., WorkflowBusinessOperation]:
    def dependency(request: Request) -> WorkflowBusinessOperation:
        context = _business_context(request, operation)
        return WorkflowBusinessOperation(
            operation=operation,
            correlation_id=context.correlation_id,
            requested_by=context.requested_by,
            idempotency_key=context.idempotency_key,
            context=context,
            workflow_service=SilverWorkflowService(
                repository=get_workflow_repository()
            ),
        )

    dependency.__name__ = f"require_{operation}"
    return dependency
