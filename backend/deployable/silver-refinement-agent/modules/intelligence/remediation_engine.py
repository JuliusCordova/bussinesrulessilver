from __future__ import annotations

from datetime import datetime, timezone

from .diagnosis_models import IntelligenceExecutionDiagnosis
from .remediation_models import RemediationAction, RemediationPlan


class IntelligentRemediationEngine:
    """Builds an approval-first remediation plan from deterministic diagnosis evidence."""

    def build(self, diagnosis: IntelligenceExecutionDiagnosis) -> RemediationPlan:
        category = diagnosis.diagnosis.category
        actions = self._actions(category, diagnosis)
        safe_to_automate = (
            category == "SUCCESS"
            or (
                diagnosis.diagnosis.severity in {"LOW", "MEDIUM"}
                and diagnosis.diagnosis.confidence >= 0.85
                and not diagnosis.missing_sources
                and all(not action.requires_approval for action in actions)
            )
        )
        return RemediationPlan(
            execution_id=diagnosis.execution_id,
            generated_at=datetime.now(timezone.utc),
            category=category,
            severity=diagnosis.diagnosis.severity,
            confidence=diagnosis.diagnosis.confidence,
            strategy=self._strategy(category),
            safe_to_automate=safe_to_automate,
            actions=actions,
            validation_steps=self._validation(category),
            rollback_plan=self._rollback(category),
            missing_sources=diagnosis.missing_sources,
        )

    @staticmethod
    def _action(action_id: str, title: str, description: str, owner: str, priority: str,
                action_type: str, automation: str, approval: bool, command: str | None = None,
                depends_on: list[str] | None = None, evidence: list[str] | None = None) -> RemediationAction:
        return RemediationAction(
            action_id=action_id,
            title=title,
            description=description,
            owner_role=owner,
            priority=priority,
            action_type=action_type,
            automation_level=automation,
            requires_approval=approval,
            command_hint=command,
            depends_on=depends_on or [],
            evidence_codes=evidence or [],
        )

    def _actions(self, category: str, diagnosis: IntelligenceExecutionDiagnosis) -> list[RemediationAction]:
        codes = [item.code for item in diagnosis.evidence]
        catalog = {
            "SUCCESS": [
                self._action("REM-001", "Cerrar ejecución", "Registrar la ejecución como referencia exitosa.", "DataOps Operator", "LOW", "OBSERVE", "AUTOMATIC", False, evidence=codes),
            ],
            "DATA_QUALITY_FAILURE": [
                self._action("REM-101", "Aislar registros inválidos", "Identificar reglas, columnas y registros fallidos antes de reprocesar.", "Data Quality Owner", "CRITICAL", "QUARANTINE", "ASSISTED", True, evidence=codes),
                self._action("REM-102", "Corregir datos o reglas", "Aplicar la corrección aprobada en origen, transformación o regla de calidad.", "Data Steward", "HIGH", "CORRECT", "MANUAL", True, depends_on=["REM-101"], evidence=codes),
                self._action("REM-103", "Reintentar ejecución", "Relanzar el paquete validado después de la corrección.", "DataOps Operator", "HIGH", "RETRY", "ASSISTED", True, "POST /executions/{execution_id}/retry", ["REM-102"], codes),
            ],
            "RECONCILIATION_FAILURE": [
                self._action("REM-201", "Calcular diferencial", "Comparar conteos, llaves y sumatorias entre origen y destino.", "Data Reconciliation Owner", "HIGH", "ANALYZE", "ASSISTED", True, evidence=codes),
                self._action("REM-202", "Reprocesar diferencial", "Reprocesar únicamente los registros afectados después de aprobación.", "DataOps Operator", "HIGH", "REPROCESS", "ASSISTED", True, depends_on=["REM-201"], evidence=codes),
            ],
            "PROFILING_ALERT": [
                self._action("REM-301", "Validar cambio de perfil", "Revisar distribución, cardinalidad, tipos y porcentaje de nulos.", "Data Steward", "MEDIUM", "ANALYZE", "ASSISTED", True, evidence=codes),
            ],
            "GOVERNANCE_BLOCKED": [
                self._action("REM-401", "Atender observaciones", "Corregir el artefacto conforme a la decisión de gobierno.", "Artifact Owner", "HIGH", "CORRECT", "MANUAL", True, evidence=codes),
                self._action("REM-402", "Generar nueva versión", "Crear una nueva versión y remitirla nuevamente a aprobación.", "Artifact Owner", "HIGH", "VERSION", "ASSISTED", True, depends_on=["REM-401"], evidence=codes),
            ],
            "INFRASTRUCTURE_FAILURE": [
                self._action("REM-501", "Validar plataforma", "Revisar disponibilidad, permisos, cuota y conectividad de GCP.", "Platform Engineer", "CRITICAL", "PLATFORM_CHECK", "ASSISTED", True, evidence=codes),
                self._action("REM-502", "Reintentar de forma controlada", "Relanzar solo cuando la plataforma esté saludable.", "DataOps Operator", "HIGH", "RETRY", "ASSISTED", True, depends_on=["REM-501"], evidence=codes),
            ],
            "EXECUTION_FAILURE": [
                self._action("REM-601", "Analizar logs del driver", "Identificar el error técnico exacto en logs y métricas.", "Data Engineer", "HIGH", "ANALYZE", "ASSISTED", True, evidence=codes),
                self._action("REM-602", "Corregir y reintentar", "Aplicar la corrección técnica y relanzar el paquete validado.", "DataOps Operator", "HIGH", "RETRY", "ASSISTED", True, depends_on=["REM-601"], evidence=codes),
            ],
        }
        return catalog.get(category, [
            self._action("REM-900", "Completar diagnóstico", "Recopilar la evidencia faltante antes de ejecutar acciones correctivas.", "DataOps Operator", "MEDIUM", "INVESTIGATE", "MANUAL", True, evidence=codes),
        ])

    @staticmethod
    def _strategy(category: str) -> str:
        return {
            "SUCCESS": "OBSERVE_AND_CLOSE",
            "DATA_QUALITY_FAILURE": "QUARANTINE_CORRECT_VALIDATE_RETRY",
            "RECONCILIATION_FAILURE": "COMPARE_ISOLATE_REPROCESS",
            "PROFILING_ALERT": "ANALYZE_CONFIRM_OR_ESCALATE",
            "GOVERNANCE_BLOCKED": "CORRECT_VERSION_REAPPROVE",
            "INFRASTRUCTURE_FAILURE": "RESTORE_PLATFORM_THEN_RETRY",
            "EXECUTION_FAILURE": "DIAGNOSE_FIX_RETRY",
        }.get(category, "INVESTIGATE_BEFORE_ACTION")

    @staticmethod
    def _validation(category: str) -> list[str]:
        if category == "SUCCESS":
            return ["Confirmar métricas finales y trazabilidad completa."]
        return [
            "Confirmar que la causa diagnosticada fue corregida.",
            "Ejecutar validaciones de calidad y reconciliación.",
            "Verificar que el reproceso termine en SUCCEEDED.",
            "Registrar evidencia y aprobación en Governance.",
        ]

    @staticmethod
    def _rollback(category: str) -> list[str]:
        if category == "SUCCESS":
            return []
        return [
            "Detener el reproceso si reaparece la señal de falla.",
            "Restaurar la última versión aprobada del artefacto.",
            "Revertir promociones asociadas cuando corresponda.",
            "Escalar a revisión humana con la evidencia consolidada.",
        ]
