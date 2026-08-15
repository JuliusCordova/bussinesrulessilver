from __future__ import annotations

from datetime import datetime, timezone

from modules.silver_execution.watermark_repository import (
    WatermarkCheckpoint,
    WatermarkRepository,
)

from .health_checker import AgentOpsHealthChecker
from .log_reader import CloudStorageLogReader
from .metrics_parser import StructuredPipelineMetricsParser
from .models import (
    AgentHealth,
    AgentOpsArtifacts,
    AgentOpsDashboardResponse,
    AgentOpsHealthResponse,
    AgentOpsSummary,
    AgentOpsToday,
    ComponentHealth,
    ExecutionLogFile,
    ExecutionLogsResponse,
    ExecutionMetricsResponse,
    ExecutionTimelineItem,
    ExecutionTimelineResponse,
)
from .repository import AgentOpsRepository


class ExecutionNotFoundError(ValueError):
    pass


class ExecutionLogsUnavailableError(ValueError):
    pass


class AgentOpsService:
    def __init__(
        self,
        repository: AgentOpsRepository,
        log_reader: CloudStorageLogReader | None = None,
        metrics_parser: StructuredPipelineMetricsParser | None = None,
        health_checker: AgentOpsHealthChecker | None = None,
        watermark_repository: WatermarkRepository | None = None,
    ) -> None:
        self.repository = repository
        self.log_reader = log_reader or CloudStorageLogReader()
        self.metrics_parser = metrics_parser or StructuredPipelineMetricsParser()
        self.health_checker = health_checker
        self.watermark_repository = watermark_repository

    def get_dashboard(self) -> AgentOpsDashboardResponse:
        metrics = self.repository.fetch_dashboard()
        total_executions = int(metrics["total_executions"] or 0)
        succeeded = int(metrics["succeeded"] or 0)
        failed = int(metrics["failed"] or 0)
        terminal = succeeded + failed + int(metrics["cancelled"] or 0)
        success_rate = round((succeeded / terminal) * 100, 2) if terminal else 0.0

        active = (
            int(metrics["queued"] or 0)
            + int(metrics["running"] or 0)
            + int(metrics["pending"] or 0)
            + int(metrics["validated"] or 0)
        )
        health_status = "DEGRADED" if failed > 0 and succeeded == 0 else "HEALTHY"
        if active > 0:
            health_status = "ACTIVE"

        return AgentOpsDashboardResponse(
            generated_at=datetime.now(timezone.utc),
            summary=AgentOpsSummary(
                total_specs=int(metrics["total_specs"] or 0),
                total_executions=total_executions,
                pending=int(metrics["pending"] or 0),
                validated=int(metrics["validated"] or 0),
                queued=int(metrics["queued"] or 0),
                running=int(metrics["running"] or 0),
                succeeded=succeeded,
                failed=failed,
                cancelled=int(metrics["cancelled"] or 0),
                success_rate=success_rate,
            ),
            today=AgentOpsToday(
                executions=int(metrics["executions_today"] or 0),
                rows_read=int(metrics["rows_read_today"] or 0),
                rows_written=int(metrics["rows_written_today"] or 0),
                avg_runtime_seconds=round(float(metrics["avg_runtime_seconds"] or 0), 2),
            ),
            artifacts=AgentOpsArtifacts(
                total_artifacts=int(metrics["total_artifacts"] or 0),
                current_packages=int(metrics["current_packages"] or 0),
                latest_package_version=int(metrics["latest_package_version"] or 0),
            ),
            agents=[
                AgentHealth(
                    name="Silver Refinement Agent",
                    status=health_status,
                    last_execution_at=metrics.get("last_execution_at"),
                )
            ],
        )

    def get_health(self) -> AgentOpsHealthResponse:
        checker = self.health_checker or AgentOpsHealthChecker()
        probe_results = checker.check()
        components = [
            ComponentHealth(
                component=result.component,
                status=result.status,
                latency_ms=result.latency_ms,
                detail=result.detail,
            )
            for result in probe_results
        ]
        healthy_components = sum(
            1 for component in components if component.status == "HEALTHY"
        )
        if healthy_components == len(components):
            overall_status = "HEALTHY"
        elif healthy_components == 0:
            overall_status = "UNAVAILABLE"
        else:
            overall_status = "DEGRADED"
        return AgentOpsHealthResponse(
            checked_at=datetime.now(timezone.utc),
            overall_status=overall_status,
            healthy_components=healthy_components,
            total_components=len(components),
            components=components,
        )

    def get_execution_timeline(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        spec_id: str | None = None,
    ) -> ExecutionTimelineResponse:
        rows, total = self.repository.fetch_executions(
            limit=limit,
            offset=offset,
            status=status,
            spec_id=spec_id,
        )
        return ExecutionTimelineResponse(
            executions=[ExecutionTimelineItem.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def _load_execution_log_files(self, execution_id: str):
        execution = self.repository.fetch_execution_log_reference(execution_id)
        if execution is None:
            raise ExecutionNotFoundError(f"Ejecución no encontrada: {execution_id}")
        logs_uri = execution.get("logs_uri")
        if not logs_uri:
            raise ExecutionLogsUnavailableError(
                "La ejecución todavía no tiene logs_uri. Sincroniza primero su estado."
            )
        files = self.log_reader.read_prefix(logs_uri)
        if not files:
            raise ExecutionLogsUnavailableError(
                f"No se encontraron archivos de log para {logs_uri}"
            )
        return execution, logs_uri, files

    def get_execution_logs(
        self,
        execution_id: str,
        *,
        tail_lines: int,
    ) -> ExecutionLogsResponse:
        execution, logs_uri, files = self._load_execution_log_files(execution_id)
        combined_sections = []
        for file in files:
            combined_sections.append(f"===== {file.uri} =====\n{file.content.rstrip()}")
        all_lines = "\n\n".join(combined_sections).splitlines()
        truncated = len(all_lines) > tail_lines
        selected_lines = all_lines[-tail_lines:]

        return ExecutionLogsResponse(
            execution_id=execution["execution_id"],
            spec_id=execution["spec_id"],
            status=execution["status"],
            dataproc_batch_id=execution.get("dataproc_batch_id"),
            logs_uri=logs_uri,
            files=[
                ExecutionLogFile(uri=file.uri, size_bytes=file.size_bytes)
                for file in files
            ],
            content="\n".join(selected_lines),
            tail_lines=tail_lines,
            returned_lines=len(selected_lines),
            truncated=truncated,
        )

    def _advance_incremental_checkpoint(
        self,
        execution: dict,
        snapshot,
    ) -> tuple[bool, int | None]:
        strategy = str(execution.get("load_strategy") or "FULL")
        if strategy != "INCREMENTAL_WATERMARK":
            return False, None

        status = execution.get("status")
        status_value = getattr(status, "value", status)
        if status_value != "SUCCEEDED":
            return False, None

        if snapshot.pipeline_status != "SUCCESS":
            raise ValueError(
                "No se puede avanzar el watermark sin resultado SUCCESS"
            )
        if snapshot.quality_status != "PASSED":
            raise ValueError(
                "No se puede avanzar el watermark sin calidad PASSED"
            )
        if self.watermark_repository is None:
            raise ValueError(
                "No existe WatermarkRepository configurado para la ejecución incremental"
            )

        spec_id = str(execution["spec_id"])
        execution_id = str(execution["execution_id"])
        watermark_column = execution.get("watermark_column")
        if not watermark_column:
            raise ValueError(
                "La ejecución incremental no tiene watermark_column"
            )

        current = self.watermark_repository.get(spec_id)
        next_watermark = snapshot.next_watermark
        if next_watermark is None:
            if snapshot.rows_read > 0:
                raise ValueError(
                    "El pipeline procesó filas pero no publicó next_watermark"
                )
            return False, current.version if current else None

        if next_watermark.tzinfo is None or next_watermark.utcoffset() is None:
            raise ValueError("next_watermark debe incluir zona horaria")

        if current is not None:
            if current.watermark_column != watermark_column:
                raise ValueError(
                    "La columna watermark del checkpoint no coincide con la ejecución"
                )
            if current.last_successful_execution_id == execution_id:
                if current.current_watermark != next_watermark:
                    raise ValueError(
                        "La ejecución ya actualizó el checkpoint con otro watermark"
                    )
                return False, current.version
            if next_watermark <= current.current_watermark:
                return False, current.version
            version = current.version + 1
            expected_version = current.version
        else:
            version = 1
            expected_version = None

        checkpoint = WatermarkCheckpoint(
            spec_id=spec_id,
            watermark_column=str(watermark_column),
            current_watermark=next_watermark,
            last_successful_execution_id=execution_id,
            updated_at=snapshot.finished_at or datetime.now(timezone.utc),
            version=version,
        )
        saved = self.watermark_repository.save(
            checkpoint,
            expected_version=expected_version,
        )
        return True, saved.version

    def sync_execution_metrics(self, execution_id: str) -> ExecutionMetricsResponse:
        execution, _, files = self._load_execution_log_files(execution_id)
        snapshot = self.metrics_parser.parse([file.content for file in files])
        persisted = self.repository.update_execution_metrics(
            execution_id,
            rows_read=snapshot.rows_read,
            rows_written=snapshot.rows_written,
            started_at=snapshot.started_at,
            finished_at=snapshot.finished_at,
            next_watermark=snapshot.next_watermark,
        )
        checkpoint_updated = False
        checkpoint_version = None

        strategy = str(execution.get("load_strategy") or "FULL")
        if strategy == "INCREMENTAL_WATERMARK":
            if not persisted:
                raise ValueError(
                    "No se puede avanzar el checkpoint si las métricas "
                    "no fueron persistidas"
                )
            checkpoint_updated, checkpoint_version = (
                self._advance_incremental_checkpoint(execution, snapshot)
            )
        duration_seconds = None
        if snapshot.started_at and snapshot.finished_at:
            duration_seconds = max(
                int((snapshot.finished_at - snapshot.started_at).total_seconds()),
                0,
            )

        return ExecutionMetricsResponse(
            execution_id=execution["execution_id"],
            spec_id=execution["spec_id"],
            status=execution["status"],
            rows_read=snapshot.rows_read,
            rows_written=snapshot.rows_written,
            failed_rows=snapshot.failed_rows,
            quality_status=snapshot.quality_status,
            quality_outcome=snapshot.quality_outcome,
            quality_score=snapshot.quality_score,
            quarantined_rows=snapshot.quarantined_rows,
            quarantine_table=snapshot.quarantine_table,
            quality_rule_results=snapshot.quality_rule_results,
            pipeline_status=snapshot.pipeline_status,
            started_at=snapshot.started_at,
            finished_at=snapshot.finished_at,
            next_watermark=snapshot.next_watermark,
            duration_seconds=duration_seconds,
            metrics_persisted=persisted,
            checkpoint_updated=checkpoint_updated,
            checkpoint_version=checkpoint_version,
            raw_result=snapshot.raw_result,
        )
