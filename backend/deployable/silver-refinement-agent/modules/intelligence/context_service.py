from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules.agentops.service import AgentOpsService, ExecutionLogsUnavailableError

from .context_models import ContextSourceStatus, IntelligenceExecutionContext
from .context_repository import IntelligenceContextRepository
from .quality_client import QualityDomainClient


class IntelligenceExecutionNotFoundError(ValueError):
    pass


class IntelligenceContextService:
    def __init__(
        self,
        repository: IntelligenceContextRepository,
        quality_client: QualityDomainClient | None = None,
        agentops_service: AgentOpsService | None = None,
    ) -> None:
        self.repository = repository
        self.quality_client = quality_client or QualityDomainClient()
        self.agentops_service = agentops_service

    @staticmethod
    def _record(sources: list[ContextSourceStatus], source: str, payload: Any, error: str | None = None) -> None:
        status = "AVAILABLE" if payload is not None else "UNAVAILABLE"
        sources.append(ContextSourceStatus(source=source, status=status, detail=error))

    def build(self, execution_id: str, include_logs: bool = True) -> IntelligenceExecutionContext:
        execution = self.repository.fetch_execution(execution_id)
        if execution is None:
            raise IntelligenceExecutionNotFoundError(f"Ejecución no encontrada: {execution_id}")

        sources: list[ContextSourceStatus] = []
        self._record(sources, "silver_execution", execution)
        spec_id = str(execution["spec_id"])
        package_version = int(execution.get("package_version") or 0)

        artifacts = self.repository.fetch_artifacts(spec_id, package_version)
        self._record(sources, "silver_artifacts", artifacts)
        artifact_ids = [str(item["artifact_id"]) for item in artifacts if item.get("artifact_id")]
        governance = self.repository.fetch_governance(artifact_ids)
        self._record(sources, "governance", governance)

        logs = metrics = platform_health = None
        if self.agentops_service is not None:
            if include_logs:
                try:
                    logs = self.agentops_service.get_execution_logs(execution_id, tail_lines=300).model_dump(mode="json")
                    self._record(sources, "execution_logs", logs)
                except Exception as exc:
                    self._record(sources, "execution_logs", None, str(exc))
            try:
                metrics = self.agentops_service.sync_execution_metrics(execution_id).model_dump(mode="json")
                self._record(sources, "execution_metrics", metrics)
            except ExecutionLogsUnavailableError as exc:
                self._record(sources, "execution_metrics", None, str(exc))
            except Exception as exc:
                self._record(sources, "execution_metrics", None, str(exc))
            try:
                platform_health = self.agentops_service.get_health().model_dump(mode="json")
                self._record(sources, "platform_health", platform_health)
            except Exception as exc:
                self._record(sources, "platform_health", None, str(exc))

        data_quality, dq_error = self.quality_client.data_quality(execution_id, spec_id)
        profiling, profiling_error = self.quality_client.profiling(execution_id, spec_id)
        reconciliation, reconciliation_error = self.quality_client.reconciliation(execution_id, spec_id)
        self._record(sources, "data_quality", data_quality, dq_error)
        self._record(sources, "profiling", profiling, profiling_error)
        self._record(sources, "reconciliation", reconciliation, reconciliation_error)

        available = sum(1 for item in sources if item.status == "AVAILABLE")
        completeness = "COMPLETE" if available == len(sources) else "PARTIAL"
        if available <= 3:
            completeness = "MINIMAL"

        return IntelligenceExecutionContext(
            execution_id=execution_id,
            generated_at=datetime.now(timezone.utc),
            completeness=completeness,
            execution=execution,
            artifacts=artifacts,
            governance=governance,
            logs=logs,
            metrics=metrics,
            data_quality=data_quality,
            profiling=profiling,
            reconciliation=reconciliation,
            platform_health=platform_health,
            sources=sources,
        )
