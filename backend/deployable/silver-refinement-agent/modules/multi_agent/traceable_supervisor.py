from __future__ import annotations

from datetime import datetime, timezone

from .memory_models import MemoryEventCreate
from .models import OrchestratorRequest
from .reasoning_trace import ReasoningTraceBuilder
from .supervisor import AgentSupervisor
from .trace_models import ReasoningTrace, TraceableOrchestratorResponse


class TraceableAgentSupervisor(AgentSupervisor):
    """Add audit-ready provenance without changing orchestration decisions."""

    def __init__(self, *args, trace_builder: ReasoningTraceBuilder | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.trace_builder = trace_builder or ReasoningTraceBuilder()

    def orchestrate(self, request: OrchestratorRequest) -> TraceableOrchestratorResponse:
        started_at = datetime.now(timezone.utc)
        response = super().orchestrate(request)
        completed_at = datetime.now(timezone.utc)

        trace = self.trace_builder.build(
            request=request,
            response=response,
            started_at=started_at,
            completed_at=completed_at,
        )
        self._redact_trace(trace)
        trace_memory_id: str | None = None

        if request.persist_memory:
            trace.persistence_status = "PERSISTED"
            try:
                trace_memory = self.memory_service.add_event(
                    MemoryEventCreate(
                        session_id=response.session_id,
                        execution_id=request.execution_id,
                        tenant_id=request.tenant_id,
                        project_id=request.project_id,
                        pipeline_id=request.pipeline_id,
                        agent_id="agent-supervisor",
                        memory_type="EPISODIC",
                        content=(
                            f"Traza auditable {trace.trace_id} para la ejecución "
                            f"{request.execution_id}; conclusión "
                            f"{response.conclusion_status}."
                        ),
                        importance_score=0.9,
                        confidence_score=1.0,
                        # Trace events are audit artifacts. They must never be
                        # retrieved as reusable agent memory or injected as evidence.
                        is_shared=False,
                        metadata={
                            "kind": "reasoning-trace",
                            "trace_id": trace.trace_id,
                            "schema_version": trace.schema_version,
                            "redaction_applied": True,
                            "private_chain_of_thought_stored": False,
                            "trace": trace.model_dump(mode="json"),
                        },
                    )
                )
                trace_memory_id = trace_memory.memory_id
                trace.reasoning_trace_memory_id = trace_memory_id
                response.persisted_memory_ids.append(trace_memory_id)
                trace.final_provenance["reasoning_trace_memory_id"] = trace_memory_id
            except Exception:
                # The business response remains available; the trace reports the
                # persistence failure without exposing database or credential details.
                trace.persistence_status = "FAILED"
        else:
            trace.persistence_status = "NOT_REQUESTED"

        payload = response.model_dump(mode="python")
        payload.update(
            {
                "reasoning_trace_used": True,
                "trace_id": trace.trace_id,
                "reasoning_trace": trace,
                "reasoning_trace_memory_id": trace_memory_id,
                "persisted_memory_ids": response.persisted_memory_ids,
            }
        )
        return TraceableOrchestratorResponse.model_validate(payload)

    @staticmethod
    def _redact_trace(trace: ReasoningTrace) -> None:
        """Normalize free-text summaries into non-sensitive audit descriptions."""

        for stage in trace.stages:
            decision = stage.decision or "NONE"
            stage.summary = (
                f"{stage.stage_type} registrado por {stage.actor}; "
                f"estado={stage.status}; decisión={decision}."
            )
        trace.redaction_applied = True
        trace.private_chain_of_thought_stored = False
