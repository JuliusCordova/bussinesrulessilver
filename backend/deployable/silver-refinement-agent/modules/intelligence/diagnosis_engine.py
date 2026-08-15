from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .context_models import IntelligenceExecutionContext
from .diagnosis_models import (
    DiagnosisEvidence,
    DiagnosisSummary,
    DiagnosisTimelineItem,
    IntelligenceExecutionDiagnosis,
    RootCauseCandidate,
)


class IntelligentDiagnosisEngine:
    """Deterministic, evidence-first diagnosis engine for Sprint 6.2."""

    TERMINAL_FAILURES = {"FAILED", "CANCELLED"}
    ACTIVE_STATES = {"PENDING", "VALIDATED", "QUEUED", "RUNNING"}

    def diagnose(self, context: IntelligenceExecutionContext) -> IntelligenceExecutionDiagnosis:
        execution = context.execution
        evidence: list[DiagnosisEvidence] = []
        status = str(execution.get("status") or "UNKNOWN").upper()
        error_message = str(execution.get("error_message") or "").strip()

        if status == "SUCCEEDED":
            evidence.append(self._evidence("silver_execution", "EXECUTION_SUCCEEDED", "La ejecución terminó en estado SUCCEEDED.", 35, {"status": status}))
        elif status in self.TERMINAL_FAILURES:
            detail = f"La ejecución terminó en estado {status}."
            if error_message:
                detail += f" Error reportado: {error_message}"
            evidence.append(self._evidence("silver_execution", "EXECUTION_TERMINAL_FAILURE", detail, 30, {"status": status, "error_message": error_message or None}))
        elif status in self.ACTIVE_STATES:
            evidence.append(self._evidence("silver_execution", "EXECUTION_ACTIVE", f"La ejecución continúa en estado {status}.", 15, {"status": status}))
        else:
            evidence.append(self._evidence("silver_execution", "EXECUTION_UNKNOWN", f"Estado de ejecución no reconocido: {status}.", 10, {"status": status}))

        metrics = context.metrics or {}
        failed_rows = int(metrics.get("failed_rows") or 0)
        rows_read = int(metrics.get("rows_read") or execution.get("rows_read") or 0)
        rows_written = int(metrics.get("rows_written") or execution.get("rows_written") or 0)
        quality_status = str(metrics.get("quality_status") or "").upper()
        if failed_rows > 0 or quality_status == "FAILED":
            evidence.append(self._evidence("execution_metrics", "QUALITY_FAILURE", f"Las métricas registran {failed_rows} filas fallidas y quality_status={quality_status or 'UNKNOWN'}.", 35, {"failed_rows": failed_rows, "quality_status": quality_status or None}))
        if rows_read > 0 and rows_written == 0 and status != "SUCCEEDED":
            evidence.append(self._evidence("execution_metrics", "NO_ROWS_WRITTEN", f"Se leyeron {rows_read} filas, pero no se escribió ninguna fila.", 20, {"rows_read": rows_read, "rows_written": rows_written}))

        dq_status = self._status(context.data_quality)
        if dq_status in {"FAILED", "FAIL", "ERROR", "CRITICAL"}:
            evidence.append(self._evidence("data_quality", "DATA_QUALITY_FAILED", f"Data Quality reportó estado {dq_status}.", 35, context.data_quality or {}))

        reconciliation_status = self._status(context.reconciliation)
        if reconciliation_status in {"FAILED", "FAIL", "MISMATCH", "ERROR"}:
            evidence.append(self._evidence("reconciliation", "RECONCILIATION_FAILED", f"Reconciliation reportó estado {reconciliation_status}.", 30, context.reconciliation or {}))

        profiling_status = self._status(context.profiling)
        if profiling_status in {"ANOMALY", "WARNING", "FAILED", "ERROR"}:
            evidence.append(self._evidence("profiling", "PROFILING_ANOMALY", f"Profiling reportó estado {profiling_status}.", 15, context.profiling or {}))

        governance = context.governance or {}
        reviews = governance.get("reviews") or []
        if any(str(item.get("decision") or "").upper() == "REJECTED" for item in reviews if isinstance(item, dict)):
            evidence.append(self._evidence("governance", "GOVERNANCE_REJECTED", "Existe una decisión de gobierno REJECTED asociada al paquete.", 30, {"reviews": reviews}))

        platform_status = self._status(context.platform_health)
        if platform_status in {"DEGRADED", "UNAVAILABLE", "FAILED"}:
            evidence.append(self._evidence("platform_health", "PLATFORM_DEGRADED", f"La plataforma reportó estado {platform_status}.", 25, context.platform_health or {}))

        category = self._category(evidence, status)
        severity = self._severity(category, evidence, status)
        confidence = self._confidence(evidence, context.completeness)
        missing_sources = [item.source for item in context.sources if item.status != "AVAILABLE"]
        requires_review = category not in {"SUCCESS"} or confidence < 0.85 or bool(missing_sources)

        root_causes = self._root_causes(category, evidence, confidence)
        recommendations = self._recommendations(category, missing_sources)
        timeline = self._timeline(context)

        return IntelligenceExecutionDiagnosis(
            execution_id=context.execution_id,
            generated_at=datetime.now(timezone.utc),
            diagnosis=DiagnosisSummary(
                category=category,
                severity=severity,
                confidence=confidence,
                requires_human_review=requires_review,
            ),
            summary=self._summary(category, status, evidence),
            root_causes=root_causes,
            evidence=evidence,
            recommendations=recommendations,
            timeline=timeline,
            missing_sources=missing_sources,
            context_completeness=context.completeness,
        )

    @staticmethod
    def _status(payload: dict[str, Any] | None) -> str:
        if not payload:
            return ""
        for key in ("status", "overall_status", "result", "state"):
            value = payload.get(key)
            if value is not None:
                return str(value).upper()
        return ""

    @staticmethod
    def _evidence(source: str, code: str, detail: str, weight: int, payload: dict[str, Any]) -> DiagnosisEvidence:
        return DiagnosisEvidence(source=source, code=code, detail=detail, weight=weight, payload=payload)

    @staticmethod
    def _category(evidence: list[DiagnosisEvidence], status: str) -> str:
        codes = {item.code for item in evidence}
        if "GOVERNANCE_REJECTED" in codes:
            return "GOVERNANCE_BLOCKED"
        if "PLATFORM_DEGRADED" in codes and status in {"FAILED", "CANCELLED"}:
            return "INFRASTRUCTURE_FAILURE"
        if "DATA_QUALITY_FAILED" in codes or "QUALITY_FAILURE" in codes:
            return "DATA_QUALITY_FAILURE"
        if "RECONCILIATION_FAILED" in codes:
            return "RECONCILIATION_FAILURE"
        if "PROFILING_ANOMALY" in codes:
            return "PROFILING_ALERT"
        if status == "SUCCEEDED":
            return "SUCCESS"
        if status in {"FAILED", "CANCELLED"}:
            return "EXECUTION_FAILURE"
        if status in {"PENDING", "VALIDATED", "QUEUED", "RUNNING"}:
            return "UNKNOWN"
        return "CONFIGURATION_ERROR"

    @staticmethod
    def _severity(category: str, evidence: list[DiagnosisEvidence], status: str) -> str:
        if category == "SUCCESS":
            return "LOW"
        score = sum(item.weight for item in evidence)
        if category in {"INFRASTRUCTURE_FAILURE", "GOVERNANCE_BLOCKED"} or score >= 70:
            return "CRITICAL"
        if status in {"FAILED", "CANCELLED"} or score >= 45:
            return "HIGH"
        if score >= 25:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _confidence(evidence: list[DiagnosisEvidence], completeness: str) -> float:
        score = min(sum(item.weight for item in evidence), 100)
        multiplier = {"COMPLETE": 1.0, "PARTIAL": 0.9, "MINIMAL": 0.75}.get(completeness, 0.8)
        return round(min((score / 100) * multiplier, 0.99), 2)

    @staticmethod
    def _root_causes(category: str, evidence: list[DiagnosisEvidence], confidence: float) -> list[RootCauseCandidate]:
        relevant = sorted(evidence, key=lambda item: item.weight, reverse=True)[:3]
        return [
            RootCauseCandidate(
                rank=index,
                reason=item.detail,
                confidence=round(max(confidence - ((index - 1) * 0.12), 0.1), 2),
                evidence_codes=[item.code],
            )
            for index, item in enumerate(relevant, start=1)
        ]

    @staticmethod
    def _recommendations(category: str, missing_sources: list[str]) -> list[str]:
        catalog = {
            "SUCCESS": ["Mantener el monitoreo y registrar la ejecución como referencia exitosa."],
            "DATA_QUALITY_FAILURE": ["Identificar las reglas y columnas fallidas.", "Corregir o poner en cuarentena los registros inválidos.", "Ejecutar nuevamente el pipeline y validar reconciliación."],
            "RECONCILIATION_FAILURE": ["Comparar conteos, llaves y sumatorias entre origen y destino.", "Aislar el diferencial y reprocesar solo los registros afectados."],
            "PROFILING_ALERT": ["Revisar cambios de distribución, cardinalidad y porcentaje de nulos.", "Validar si el cambio corresponde a una alteración legítima del origen."],
            "GOVERNANCE_BLOCKED": ["Revisar la decisión y comentario de gobierno.", "Corregir el artefacto y generar una nueva versión para aprobación."],
            "INFRASTRUCTURE_FAILURE": ["Revisar salud de BigQuery, Cloud Storage y Dataproc Serverless.", "Validar permisos, cuota y conectividad antes de reintentar."],
            "EXECUTION_FAILURE": ["Revisar el mensaje de error y los logs del driver.", "Corregir la causa técnica y reintentar desde un paquete validado."],
            "UNKNOWN": ["Esperar la finalización de la ejecución o sincronizar nuevamente su estado."],
            "CONFIGURATION_ERROR": ["Validar estado, configuración y referencias de la ejecución."],
        }
        recommendations = list(catalog.get(category, catalog["UNKNOWN"]))
        if missing_sources:
            recommendations.append("Habilitar o alinear los contratos de las fuentes faltantes: " + ", ".join(missing_sources) + ".")
        return recommendations

    @staticmethod
    def _summary(category: str, status: str, evidence: list[DiagnosisEvidence]) -> str:
        if category == "SUCCESS":
            return "La ejecución terminó correctamente y no se identificaron señales determinísticas de falla."
        top = max(evidence, key=lambda item: item.weight)
        return f"Diagnóstico {category} para una ejecución en estado {status}. Evidencia principal: {top.detail}"

    @staticmethod
    def _timeline(context: IntelligenceExecutionContext) -> list[DiagnosisTimelineItem]:
        execution = context.execution
        items = [
            DiagnosisTimelineItem(event_at=execution.get("created_at"), event_type="EXECUTION_CREATED", source="silver_execution", detail="La ejecución fue registrada."),
        ]
        if execution.get("started_at"):
            items.append(DiagnosisTimelineItem(event_at=execution.get("started_at"), event_type="EXECUTION_STARTED", source="silver_execution", detail="La ejecución inició procesamiento."))
        if execution.get("finished_at"):
            items.append(DiagnosisTimelineItem(event_at=execution.get("finished_at"), event_type="EXECUTION_FINISHED", source="silver_execution", detail=f"La ejecución terminó en estado {execution.get('status')}."))
        governance = context.governance or {}
        for event_type, key, date_key, actor_key in (
            ("GOVERNANCE_REVIEW", "reviews", "reviewed_at", "reviewed_by"),
            ("ARTIFACT_PROMOTION", "promotions", "promoted_at", "promoted_by"),
            ("ARTIFACT_ROLLBACK", "rollbacks", "rolled_back_at", "rolled_back_by"),
        ):
            for event in governance.get(key) or []:
                if isinstance(event, dict):
                    items.append(DiagnosisTimelineItem(event_at=event.get(date_key), event_type=event_type, source="governance", detail=f"Evento ejecutado por {event.get(actor_key) or 'unknown'}."))
        return sorted(items, key=lambda item: item.event_at or datetime.min.replace(tzinfo=timezone.utc))
