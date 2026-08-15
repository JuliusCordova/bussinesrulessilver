from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from modules.intelligence.context_router import get_context_service
from modules.intelligence.context_service import (
    IntelligenceContextService,
    IntelligenceExecutionNotFoundError,
)

from .memory_router import get_memory_service
from .memory_service import SharedMemoryService
from .models import AgentDescriptor, OrchestratorRequest, ToolDescriptor
from .reasoning_trace import trace_records_from_memories
from .registry import AgentRegistry, build_default_registry
from .tool_registry import ToolRegistry, build_default_tool_registry
from .trace_models import ReasoningTraceRecord, TraceableOrchestratorResponse
from .traceable_supervisor import TraceableAgentSupervisor

router = APIRouter(prefix="/agentops", tags=["multi-agent"])


def get_registry() -> AgentRegistry:
    return build_default_registry()


def get_tool_registry() -> ToolRegistry:
    return build_default_tool_registry()


def get_supervisor(
    context_service: IntelligenceContextService = Depends(get_context_service),
    registry: AgentRegistry = Depends(get_registry),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    memory_service: SharedMemoryService = Depends(get_memory_service),
) -> TraceableAgentSupervisor:
    return TraceableAgentSupervisor(
        context_service=context_service,
        registry=registry,
        tool_registry=tool_registry,
        memory_service=memory_service,
    )


@router.get("/agents", response_model=list[AgentDescriptor])
def list_agents(registry: AgentRegistry = Depends(get_registry)) -> list[AgentDescriptor]:
    return registry.list()


@router.get("/tools", response_model=list[ToolDescriptor])
def list_tools(tool_registry: ToolRegistry = Depends(get_tool_registry)) -> list[ToolDescriptor]:
    return tool_registry.list()


@router.get(
    "/traces/sessions/{session_id}",
    response_model=list[ReasoningTraceRecord],
)
def list_reasoning_traces(
    session_id: str,
    memory_service: SharedMemoryService = Depends(get_memory_service),
) -> list[ReasoningTraceRecord]:
    try:
        records = memory_service.list_memories(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return trace_records_from_memories(records)


@router.get(
    "/traces/sessions/{session_id}/{trace_id}",
    response_model=ReasoningTraceRecord,
)
def get_reasoning_trace(
    session_id: str,
    trace_id: str,
    memory_service: SharedMemoryService = Depends(get_memory_service),
) -> ReasoningTraceRecord:
    try:
        records = memory_service.list_memories(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    for item in trace_records_from_memories(records):
        if item.trace.trace_id == trace_id:
            return item
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Traza no encontrada: {trace_id}",
    )


@router.post("/orchestrator/query", response_model=TraceableOrchestratorResponse)
def orchestrate(
    request: OrchestratorRequest,
    supervisor: TraceableAgentSupervisor = Depends(get_supervisor),
) -> TraceableOrchestratorResponse:
    try:
        return supervisor.orchestrate(request)
    except IntelligenceExecutionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible orquestar los agentes: {exc}",
        ) from exc
