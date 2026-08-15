from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .assistant_models import IntelligentAssistantRequest, IntelligentAssistantResponse
from .assistant_service import IntelligentAssistantService
from .context_router import get_context_service
from .context_service import IntelligenceContextService, IntelligenceExecutionNotFoundError


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def get_assistant_service(
    context_service: IntelligenceContextService = Depends(get_context_service),
) -> IntelligentAssistantService:
    return IntelligentAssistantService(context_service=context_service)


@router.post(
    "/assistant/query",
    response_model=IntelligentAssistantResponse,
)
def query_intelligent_assistant(
    request: IntelligentAssistantRequest,
    service: IntelligentAssistantService = Depends(get_assistant_service),
) -> IntelligentAssistantResponse:
    try:
        return service.ask(request)
    except IntelligenceExecutionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible responder la consulta inteligente: {exc}",
        ) from exc
