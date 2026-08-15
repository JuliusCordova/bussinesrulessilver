from __future__ import annotations

from datetime import datetime, timezone

from modules.intelligence.context_service import IntelligenceContextService
from modules.intelligence.diagnosis_engine import IntelligentDiagnosisEngine
from modules.intelligence.remediation_engine import IntelligentRemediationEngine

from .adaptive_replanner import AdaptiveReplanner
from .critical_agent import CriticalConclusionAgent
from .memory_context import ControlledMemoryContextBuilder
from .memory_grounding import MemoryGroundingEngine
from .memory_models import MemoryEventCreate, MemorySearchRequest, MemorySessionCreate
from .memory_service import SharedMemoryService
from .models import (
    AdaptiveReplanTrace,
    AgentMemoryContext,
    AgentTaskResult,
    CriticalReview,
    MemoryInfluence,
    OrchestratorRequest,
    OrchestratorResponse,
)
from .planner import DynamicAgentPlanner
from .registry import AgentRegistry, build_default_registry
from .tool_registry import ToolRegistry, build_default_tool_registry


class AgentSupervisor:
    def __init__(
        self,
        context_service: IntelligenceContextService,
        registry: AgentRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        planner: DynamicAgentPlanner | None = None,
        memory_service: SharedMemoryService | None = None,
        memory_context_builder: ControlledMemoryContextBuilder | None = None,
        memory_grounding_engine: MemoryGroundingEngine | None = None,
        critical_agent: CriticalConclusionAgent | None = None,
        adaptive_replanner: AdaptiveReplanner | None = None,
    ) -> None:
        self.context_service = context_service
        self.registry = registry or build_default_registry()
        self.tool_registry = tool_registry or build_default_tool_registry()
        self.planner = planner or DynamicAgentPlanner(self.registry, self.tool_registry)
        self.memory_service = memory_service or SharedMemoryService()
        self.memory_context_builder = memory_context_builder or ControlledMemoryContextBuilder()
        self.memory_grounding_engine = memory_grounding_engine or MemoryGroundingEngine()
        self.critical_agent = critical_agent or CriticalConclusionAgent()
        self.adaptive_replanner = adaptive_replanner or AdaptiveReplanner(self.registry)
        self.diagnosis_engine = IntelligentDiagnosisEngine()
        self.remediation_engine = IntelligentRemediationEngine()

    def orchestrate(self, request: OrchestratorRequest) -> OrchestratorResponse:
        session = self.memory_service.ensure_session(
            MemorySessionCreate(
                session_id=request.session_id,
                execution_id=request.execution_id,
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                pipeline_id=request.pipeline_id,
                user_id=request.user_id,
                metadata={"source": "agent-supervisor"},
            )
        )

        memory_response = self._retrieve_memory(request)
        memory_influences = self._build_memory_influences(memory_response.hits)
        memory_agent_scores = self._build_memory_agent_scores(memory_response.hits)

        context = self.context_service.build(
            request.execution_id,
            include_logs=request.include_logs,
        )
        diagnosis = self.diagnosis_engine.diagnose(context)
        remediation = self.remediation_engine.build(diagnosis)
        plan = self.planner.plan(
            question=request.question,
            requested_agents=request.requested_agents,
            max_agents=request.max_agents,
            memory_agent_scores=memory_agent_scores,
        )
        selections_by_id = {item.agent_id: item for item in plan.selections}
        selected = [
            descriptor
            for descriptor in (
                self.registry.get(item.agent_id) for item in plan.selections
            )
            if descriptor is not None
            and descriptor.enabled
            and descriptor.execution_phase == "SPECIALIST"
        ]
        selected_agent_ids = [item.agent_id for item in selected]
        memory_contexts_by_agent = self.memory_context_builder.build_for_agents(
            agent_ids=selected_agent_ids,
            hits=memory_response.hits,
            mode=request.memory_context_mode,
            min_score=request.memory_context_min_score,
            max_items=request.memory_context_max_items_per_agent,
            max_chars=request.memory_context_max_chars_per_agent,
            enabled=request.memory_enabled and request.memory_injection_enabled,
        )
        memory_contexts = [
            memory_contexts_by_agent[agent_id] for agent_id in selected_agent_ids
        ]
        results: list[AgentTaskResult] = []

        for descriptor in selected:
            selection = selections_by_id[descriptor.agent_id]
            task_result = self._execute_specialist(
                descriptor=descriptor,
                tools_used=selection.selected_tools,
                context=context,
                diagnosis=diagnosis,
                remediation=remediation,
            )
            if task_result is None:
                continue
            results.append(
                self._attach_memory_context(
                    task_result,
                    memory_contexts_by_agent[descriptor.agent_id],
                    grounding_enabled=(
                        request.memory_enabled
                        and request.memory_injection_enabled
                        and request.memory_grounding_enabled
                    ),
                    grounding_max_items=request.memory_grounding_max_items_per_agent,
                )
            )

        initial_critical_review = self.critical_agent.review(
            results=results,
            enabled=request.critical_validation_enabled,
            mode=request.critical_validation_mode,
            min_live_evidence_sources=request.critical_min_live_evidence_sources,
            reject_on_contradiction=request.critical_reject_on_contradiction,
        )
        adaptive_replanning = self.adaptive_replanner.plan(
            review=initial_critical_review,
            selected_agent_ids=selected_agent_ids,
            enabled=(
                request.critical_validation_enabled
                and request.adaptive_replanning_enabled
            ),
            max_additional_agents=(
                request.adaptive_replanning_max_additional_agents
            ),
            max_rounds=request.adaptive_replanning_max_rounds,
        )

        critical_review = initial_critical_review
        if adaptive_replanning.status == "PLANNED":
            replan_agent_ids = [
                item.agent_id for item in adaptive_replanning.selections
            ]
            replan_contexts_by_agent = self.memory_context_builder.build_for_agents(
                agent_ids=replan_agent_ids,
                hits=memory_response.hits,
                mode=request.memory_context_mode,
                min_score=request.memory_context_min_score,
                max_items=request.memory_context_max_items_per_agent,
                max_chars=request.memory_context_max_chars_per_agent,
                enabled=request.memory_enabled and request.memory_injection_enabled,
            )
            added_agents: list[str] = []

            for replan_selection in adaptive_replanning.selections:
                descriptor = self.registry.get(replan_selection.agent_id)
                if (
                    descriptor is None
                    or not descriptor.enabled
                    or descriptor.execution_phase != "SPECIALIST"
                ):
                    continue
                task_result = self._execute_specialist(
                    descriptor=descriptor,
                    tools_used=replan_selection.selected_tools,
                    context=context,
                    diagnosis=diagnosis,
                    remediation=remediation,
                )
                if task_result is None:
                    continue
                results.append(
                    self._attach_memory_context(
                        task_result,
                        replan_contexts_by_agent[descriptor.agent_id],
                        grounding_enabled=(
                            request.memory_enabled
                            and request.memory_injection_enabled
                            and request.memory_grounding_enabled
                        ),
                        grounding_max_items=(
                            request.memory_grounding_max_items_per_agent
                        ),
                    )
                )
                selected_agent_ids.append(descriptor.agent_id)
                memory_contexts.append(replan_contexts_by_agent[descriptor.agent_id])
                added_agents.append(descriptor.agent_id)

            if added_agents:
                adaptive_replanning.status = "EXECUTED"
                adaptive_replanning.rounds_executed = 1
                adaptive_replanning.added_agents = added_agents
                critical_review = self.critical_agent.review(
                    results=results,
                    enabled=request.critical_validation_enabled,
                    mode=request.critical_validation_mode,
                    min_live_evidence_sources=(
                        request.critical_min_live_evidence_sources
                    ),
                    reject_on_contradiction=(
                        request.critical_reject_on_contradiction
                    ),
                )
                adaptive_replanning.final_conclusion_status = critical_review.status
                adaptive_replanning.unresolved_finding_ids = [
                    finding.finding_id
                    for finding in critical_review.findings
                    if finding.severity != "INFO"
                ]
                if adaptive_replanning.unresolved_finding_ids:
                    adaptive_replanning.summary = (
                        f"Se ejecutó una ronda adaptativa con {len(added_agents)} "
                        "especialistas. Persisten hallazgos que requieren revisión."
                    )
                else:
                    adaptive_replanning.summary = (
                        f"Se ejecutó una ronda adaptativa con {len(added_agents)} "
                        "especialistas y no quedaron hallazgos críticos pendientes."
                    )
            else:
                adaptive_replanning.status = "NO_ACTION"
                adaptive_replanning.strategy = "PLANNED_AGENTS_UNAVAILABLE"
                adaptive_replanning.unresolved_finding_ids = (
                    adaptive_replanning.trigger_finding_ids.copy()
                )
                adaptive_replanning.summary = (
                    "La ronda fue planificada, pero ningún especialista adicional "
                    "pudo ejecutarse."
                )

        injected_count = sum(item.injected_count for item in memory_contexts)
        agents_with_memory = sum(
            1 for item in memory_contexts if item.injected_count
        )
        grounded_results = [
            item
            for item in results
            if item.memory_grounding is not None
            and item.memory_grounding.applied_count > 0
        ]
        grounded_agent_count = len(grounded_results)
        grounded_memory_count = sum(
            item.memory_grounding.applied_count
            for item in grounded_results
            if item.memory_grounding is not None
        )

        effective_requires_human_review = (
            diagnosis.diagnosis.requires_human_review
            or initial_critical_review.requires_human_review
            or critical_review.requires_human_review
        )

        if injected_count:
            memory_clause = (
                f" Se inyectaron de forma controlada {injected_count} memorias "
                f"en {agents_with_memory} agentes."
            )
        elif memory_influences:
            memory_clause = (
                " Se recuperaron memorias, pero ninguna superó la política de "
                "inyección controlada."
            )
        else:
            memory_clause = " No se encontraron memorias previas relevantes."

        if grounded_memory_count:
            grounding_clause = (
                f" {grounded_memory_count} memorias fundamentaron el resultado de "
                f"{grounded_agent_count} agentes con precedencia de evidencia actual."
            )
        elif injected_count and request.memory_grounding_enabled:
            grounding_clause = (
                " Ninguna memoria inyectada fue aplicada al razonamiento final."
            )
        else:
            grounding_clause = ""

        if request.critical_validation_enabled:
            critical_clause = (
                f" Validación crítica final: {critical_review.status}; "
                f"{critical_review.contradiction_count} contradicciones, "
                f"{critical_review.conditioned_count} conclusiones condicionadas y "
                f"{critical_review.rejected_count} rechazadas."
            )
        else:
            critical_clause = " La validación crítica fue deshabilitada."

        if adaptive_replanning.status == "EXECUTED":
            replanning_clause = (
                f" Replanificación adaptativa ejecutada con "
                f"{len(adaptive_replanning.added_agents)} agentes adicionales; "
                f"estado inicial {adaptive_replanning.initial_conclusion_status} y "
                f"estado final {adaptive_replanning.final_conclusion_status}."
            )
        elif adaptive_replanning.status == "NO_ACTION":
            replanning_clause = (
                " La replanificación adaptativa no encontró una acción adicional "
                "segura; se mantiene el gate de revisión humana."
            )
        elif adaptive_replanning.status == "NOT_REQUIRED":
            replanning_clause = (
                " La validación crítica no requirió replanificación adaptativa."
            )
        else:
            replanning_clause = ""

        consolidated = (
            f"El supervisor seleccionó dinámicamente {len(results)} agentes "
            f"mediante {plan.strategy}. Diagnóstico consolidado: "
            f"{diagnosis.diagnosis.category}, severidad "
            f"{diagnosis.diagnosis.severity}, estrategia "
            f"{remediation.strategy}."
            f"{memory_clause}"
            f"{grounding_clause}"
            f"{critical_clause}"
            f"{replanning_clause}"
        )

        persisted_memory_ids = self._persist_orchestration_memory(
            request=request,
            session_id=session.session_id,
            plan_strategy=plan.strategy,
            selected_agents=selected_agent_ids,
            results=results,
            memory_contexts=memory_contexts,
            initial_critical_review=initial_critical_review,
            critical_review=critical_review,
            adaptive_replanning=adaptive_replanning,
            consolidated_summary=consolidated,
            requires_human_review=effective_requires_human_review,
        )

        return OrchestratorResponse(
            execution_id=request.execution_id,
            session_id=session.session_id,
            generated_at=datetime.now(timezone.utc),
            question=request.question,
            selection_mode=plan.strategy,
            plan=plan,
            selected_agents=selected_agent_ids,
            results=results,
            consolidated_summary=consolidated,
            requires_human_review=effective_requires_human_review,
            missing_sources=diagnosis.missing_sources,
            memory_used=bool(memory_influences),
            memory_provider=self.memory_service.provider,
            memory_influences=memory_influences,
            memory_injection_used=bool(injected_count),
            memory_context_mode=request.memory_context_mode,
            memory_contexts=memory_contexts,
            memory_grounding_used=bool(grounded_memory_count),
            grounded_agent_count=grounded_agent_count,
            critical_validation_used=request.critical_validation_enabled,
            conclusion_status=critical_review.status,
            critical_review=critical_review,
            adaptive_replanning_used=adaptive_replanning.status == "EXECUTED",
            adaptive_replanning=adaptive_replanning,
            persisted_memory_ids=persisted_memory_ids,
        )

    def _execute_specialist(
        self,
        *,
        descriptor,
        tools_used: list[str],
        context,
        diagnosis,
        remediation,
    ) -> AgentTaskResult | None:
        if descriptor.domain == "execution":
            return AgentTaskResult(
                agent_id=descriptor.agent_id,
                status="COMPLETED",
                summary=(
                    "Estado de ejecución: "
                    f"{context.execution.get('status', 'UNKNOWN')}."
                ),
                tools_used=tools_used,
                evidence=[
                    {
                        "source": "silver_execution",
                        "payload": context.execution,
                    }
                ],
                warnings=[],
            )

        if descriptor.domain == "quality":
            missing = [
                name
                for name, payload in (
                    ("data_quality", context.data_quality),
                    ("profiling", context.profiling),
                    ("reconciliation", context.reconciliation),
                )
                if payload is None
            ]
            return AgentTaskResult(
                agent_id=descriptor.agent_id,
                status="PARTIAL" if missing else "COMPLETED",
                summary=(
                    "Se analizaron las señales disponibles de calidad, "
                    "profiling y reconciliación."
                ),
                tools_used=tools_used,
                evidence=[
                    {
                        "source": "execution_metrics",
                        "payload": context.metrics or {},
                    }
                ],
                warnings=["Fuentes faltantes: " + ", ".join(missing)]
                if missing
                else [],
            )

        if descriptor.domain == "governance":
            return AgentTaskResult(
                agent_id=descriptor.agent_id,
                status="COMPLETED",
                summary=(
                    "Se revisaron aprobaciones, promociones y rollbacks asociados."
                ),
                tools_used=tools_used,
                evidence=[
                    {
                        "source": "governance",
                        "payload": context.governance,
                    }
                ],
            )

        if descriptor.domain == "platform":
            task_status = "COMPLETED" if context.platform_health else "PARTIAL"
            return AgentTaskResult(
                agent_id=descriptor.agent_id,
                status=task_status,
                summary="Se evaluó la salud de la plataforma.",
                tools_used=tools_used,
                evidence=[
                    {
                        "source": "platform_health",
                        "payload": context.platform_health or {},
                    }
                ],
            )

        if descriptor.domain == "remediation":
            return AgentTaskResult(
                agent_id=descriptor.agent_id,
                status="COMPLETED",
                summary=(
                    f"Diagnóstico {diagnosis.diagnosis.category}; "
                    f"estrategia {remediation.strategy}."
                ),
                tools_used=tools_used,
                evidence=[
                    {
                        "source": "diagnosis",
                        "payload": diagnosis.model_dump(mode="json"),
                    }
                ],
                recommendations=[item.title for item in remediation.actions],
            )

        return None

    def _retrieve_memory(self, request: OrchestratorRequest):
        if not request.memory_enabled:
            return self.memory_service.search(
                MemorySearchRequest(
                    query=request.question,
                    execution_id="__memory_disabled__",
                    limit=1,
                )
            )

        return self.memory_service.search(
            MemorySearchRequest(
                query=request.question,
                session_id=request.session_id,
                execution_id=request.execution_id,
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                pipeline_id=request.pipeline_id,
                memory_types=request.memory_types,
                shared_only=True,
                limit=request.memory_limit,
            )
        )

    @staticmethod
    def _build_memory_influences(hits) -> list[MemoryInfluence]:
        return [
            MemoryInfluence(
                memory_id=hit.memory.memory_id,
                agent_id=hit.memory.agent_id,
                memory_type=hit.memory.memory_type,
                score=hit.score,
                match_type=hit.match_type,
                excerpt=hit.memory.content[:240],
            )
            for hit in hits
        ]

    def _build_memory_agent_scores(self, hits) -> dict[str, float]:
        scores: dict[str, float] = {}
        for hit in hits:
            agent_id = hit.memory.agent_id
            descriptor = self.registry.get(agent_id) if agent_id else None
            if descriptor is None or descriptor.execution_phase != "SPECIALIST":
                continue
            scores[agent_id] = max(scores.get(agent_id, 0.0), hit.score)
        return scores

    def _attach_memory_context(
        self,
        result: AgentTaskResult,
        memory_context: AgentMemoryContext,
        *,
        grounding_enabled: bool,
        grounding_max_items: int,
    ) -> AgentTaskResult:
        result.memory_context = memory_context
        if memory_context.injected_count:
            result.evidence.append(
                {
                    "source": "controlled_memory_context",
                    "payload": memory_context.model_dump(mode="json"),
                }
            )
        return self.memory_grounding_engine.ground(
            result=result,
            memory_context=memory_context,
            enabled=grounding_enabled,
            max_items=grounding_max_items,
        )

    def _persist_orchestration_memory(
        self,
        request: OrchestratorRequest,
        session_id: str,
        plan_strategy: str,
        selected_agents: list[str],
        results: list[AgentTaskResult],
        memory_contexts: list[AgentMemoryContext],
        initial_critical_review: CriticalReview,
        critical_review: CriticalReview,
        adaptive_replanning: AdaptiveReplanTrace,
        consolidated_summary: str,
        requires_human_review: bool,
    ) -> list[str]:
        if not request.persist_memory:
            return []

        common = {
            "session_id": session_id,
            "execution_id": request.execution_id,
            "tenant_id": request.tenant_id,
            "project_id": request.project_id,
            "pipeline_id": request.pipeline_id,
        }
        injected_memory_ids_by_agent = {
            item.agent_id: [memory.memory_id for memory in item.memories]
            for item in memory_contexts
            if item.memories
        }
        injected_memory_count = sum(
            len(items) for items in injected_memory_ids_by_agent.values()
        )
        grounded_memory_ids_by_agent = {
            result.agent_id: [
                decision.memory_id
                for decision in result.memory_grounding.decisions
                if decision.status == "APPLIED"
            ]
            for result in results
            if result.memory_grounding is not None
            and result.memory_grounding.applied_count > 0
        }
        grounded_memory_count = sum(
            len(items) for items in grounded_memory_ids_by_agent.values()
        )
        persisted: list[str] = []

        question_memory = self.memory_service.add_event(
            MemoryEventCreate(
                **common,
                agent_id="agent-supervisor",
                memory_type="WORKING",
                content=request.question,
                importance_score=0.4,
                confidence_score=1.0,
                is_shared=False,
                metadata={
                    "kind": "user-question",
                    "plan_strategy": plan_strategy,
                    "selected_agents": selected_agents,
                    "memory_context_mode": request.memory_context_mode,
                    "memory_injection_enabled": request.memory_injection_enabled,
                    "memory_grounding_enabled": request.memory_grounding_enabled,
                    "memory_grounding_max_items_per_agent": (
                        request.memory_grounding_max_items_per_agent
                    ),
                    "critical_validation_enabled": (
                        request.critical_validation_enabled
                    ),
                    "critical_validation_mode": request.critical_validation_mode,
                    "adaptive_replanning_enabled": (
                        request.adaptive_replanning_enabled
                    ),
                    "adaptive_replanning_max_additional_agents": (
                        request.adaptive_replanning_max_additional_agents
                    ),
                    "adaptive_replanning_max_rounds": (
                        request.adaptive_replanning_max_rounds
                    ),
                },
            )
        )
        persisted.append(question_memory.memory_id)

        for result in results:
            agent_memory = self.memory_service.add_event(
                MemoryEventCreate(
                    **common,
                    agent_id=result.agent_id,
                    memory_type="AGENT",
                    content=result.summary,
                    importance_score=0.65,
                    confidence_score=0.85,
                    is_shared=True,
                    metadata={
                        "kind": "agent-result",
                        "status": result.status,
                        "tools_used": result.tools_used,
                        "recommendations": result.recommendations,
                        "warnings": result.warnings,
                        "injected_memory_ids": injected_memory_ids_by_agent.get(
                            result.agent_id,
                            [],
                        ),
                        "memory_grounding": (
                            result.memory_grounding.model_dump(mode="json")
                            if result.memory_grounding is not None
                            else None
                        ),
                    },
                )
            )
            persisted.append(agent_memory.memory_id)

        if request.critical_validation_enabled:
            critical_memory = self.memory_service.add_event(
                MemoryEventCreate(
                    **common,
                    agent_id="critical-agent",
                    memory_type="AGENT",
                    content=critical_review.summary,
                    importance_score=0.85,
                    confidence_score=0.95,
                    is_shared=True,
                    metadata={
                        "kind": "critical-review",
                        "initial_status": initial_critical_review.status,
                        "status": critical_review.status,
                        "requires_human_review": (
                            critical_review.requires_human_review
                        ),
                        "contradiction_count": (
                            critical_review.contradiction_count
                        ),
                        "unsupported_count": critical_review.unsupported_count,
                        "insufficient_evidence_count": (
                            critical_review.insufficient_evidence_count
                        ),
                        "findings": [
                            item.model_dump(mode="json")
                            for item in critical_review.findings
                        ],
                        "assessments": [
                            item.model_dump(mode="json")
                            for item in critical_review.assessments
                        ],
                    },
                )
            )
            persisted.append(critical_memory.memory_id)

        if request.adaptive_replanning_enabled:
            replanning_memory = self.memory_service.add_event(
                MemoryEventCreate(
                    **common,
                    agent_id="agent-supervisor",
                    memory_type="AGENT",
                    content=adaptive_replanning.summary,
                    importance_score=0.8,
                    confidence_score=0.95,
                    is_shared=True,
                    metadata={
                        "kind": "adaptive-replan",
                        "trace": adaptive_replanning.model_dump(mode="json"),
                    },
                )
            )
            persisted.append(replanning_memory.memory_id)

        episode = self.memory_service.add_event(
            MemoryEventCreate(
                **common,
                agent_id="agent-supervisor",
                memory_type="EPISODIC",
                content=consolidated_summary,
                importance_score=0.8,
                confidence_score=0.9,
                is_shared=True,
                metadata={
                    "kind": "orchestration-result",
                    "plan_strategy": plan_strategy,
                    "selected_agents": selected_agents,
                    "requires_human_review": requires_human_review,
                    "memory_context_mode": request.memory_context_mode,
                    "injected_memory_count": injected_memory_count,
                    "injected_memory_ids_by_agent": injected_memory_ids_by_agent,
                    "grounded_memory_count": grounded_memory_count,
                    "grounded_memory_ids_by_agent": grounded_memory_ids_by_agent,
                    "evidence_precedence": "CURRENT_EVIDENCE_WINS",
                    "initial_critical_validation": (
                        initial_critical_review.model_dump(mode="json")
                    ),
                    "critical_validation": critical_review.model_dump(mode="json"),
                    "conclusion_status": critical_review.status,
                    "adaptive_replanning": (
                        adaptive_replanning.model_dump(mode="json")
                    ),
                },
            )
        )
        persisted.append(episode.memory_id)
        return persisted
