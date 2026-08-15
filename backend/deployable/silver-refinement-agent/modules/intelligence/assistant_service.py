from __future__ import annotations

import json
from datetime import datetime, timezone

from .assistant_models import (
    AssistantGroundingReference,
    IntelligentAssistantRequest,
    IntelligentAssistantResponse,
)
from .context_service import IntelligenceContextService
from .diagnosis_engine import IntelligentDiagnosisEngine
from .gemini_provider import GeminiProvider
from .remediation_engine import IntelligentRemediationEngine


class IntelligentAssistantService:
    def __init__(
        self,
        context_service: IntelligenceContextService,
        diagnosis_engine: IntelligentDiagnosisEngine | None = None,
        remediation_engine: IntelligentRemediationEngine | None = None,
        gemini_provider: GeminiProvider | None = None,
    ) -> None:
        self.context_service = context_service
        self.diagnosis_engine = diagnosis_engine or IntelligentDiagnosisEngine()
        self.remediation_engine = remediation_engine or IntelligentRemediationEngine()
        self.gemini_provider = gemini_provider or GeminiProvider()

    def ask(self, request: IntelligentAssistantRequest) -> IntelligentAssistantResponse:
        context = self.context_service.build(
            request.execution_id,
            include_logs=request.include_logs,
        )
        diagnosis = self.diagnosis_engine.diagnose(context)
        remediation = self.remediation_engine.build(diagnosis)
        grounding = self._grounding(diagnosis, remediation)
        warnings: list[str] = []
        provider = "DETERMINISTIC"
        model: str | None = None

        if request.use_gemini:
            try:
                answer = self.gemini_provider.generate(
                    self._prompt(request.question, context.model_dump(mode="json"), diagnosis.model_dump(mode="json"), remediation.model_dump(mode="json"))
                )
                provider = "VERTEX_AI_GEMINI"
                model = self.gemini_provider.model
            except Exception as exc:
                warnings.append(f"Gemini no estuvo disponible; se usó respuesta determinística: {exc}")
                answer = self._deterministic_answer(request.question, diagnosis, remediation)
                provider = "DETERMINISTIC_FALLBACK"
        else:
            answer = self._deterministic_answer(request.question, diagnosis, remediation)

        if diagnosis.missing_sources:
            warnings.append(
                "El análisis es parcial porque faltan las fuentes: "
                + ", ".join(diagnosis.missing_sources)
                + "."
            )

        return IntelligentAssistantResponse(
            execution_id=request.execution_id,
            generated_at=datetime.now(timezone.utc),
            question=request.question,
            answer=answer,
            provider=provider,
            model=model,
            diagnosis_category=diagnosis.diagnosis.category,
            severity=diagnosis.diagnosis.severity,
            confidence=diagnosis.diagnosis.confidence,
            safe_to_automate=remediation.safe_to_automate,
            requires_human_review=diagnosis.diagnosis.requires_human_review,
            grounding=grounding,
            missing_sources=diagnosis.missing_sources,
            warnings=warnings,
        )

    @staticmethod
    def _prompt(question: str, context: dict, diagnosis: dict, remediation: dict) -> str:
        evidence_package = {
            "question": question,
            "context": context,
            "diagnosis": diagnosis,
            "remediation_plan": remediation,
        }
        return (
            "Analiza el siguiente paquete de evidencia de DataOps y responde la pregunta del usuario. "
            "Estructura la respuesta en: conclusión, evidencia, impacto, próximos pasos y limitaciones. "
            "No propongas ejecución automática cuando safe_to_automate sea false.\n\n"
            + json.dumps(evidence_package, ensure_ascii=False, default=str)
        )

    @staticmethod
    def _deterministic_answer(question: str, diagnosis, remediation) -> str:
        actions = "; ".join(
            f"{item.action_id}: {item.title} ({item.owner_role})"
            for item in remediation.actions
        ) or "No hay acciones pendientes."
        missing = ", ".join(diagnosis.missing_sources) or "ninguna"
        return (
            f"Pregunta: {question}\n"
            f"Conclusión: la ejecución está clasificada como {diagnosis.diagnosis.category}, "
            f"con severidad {diagnosis.diagnosis.severity} y confianza {diagnosis.diagnosis.confidence:.2f}.\n"
            f"Evidencia principal: {diagnosis.summary}\n"
            f"Próximos pasos: {actions}.\n"
            f"Automatización segura: {'sí' if remediation.safe_to_automate else 'no'}. "
            f"Revisión humana: {'requerida' if diagnosis.diagnosis.requires_human_review else 'no requerida'}.\n"
            f"Fuentes faltantes: {missing}."
        )

    @staticmethod
    def _grounding(diagnosis, remediation) -> list[AssistantGroundingReference]:
        references = [
            AssistantGroundingReference(
                source=item.source,
                reference=item.code,
                detail=item.detail,
            )
            for item in diagnosis.evidence[:8]
        ]
        references.extend(
            AssistantGroundingReference(
                source="remediation_plan",
                reference=item.action_id,
                detail=f"{item.title}; owner={item.owner_role}; approval={item.requires_approval}",
            )
            for item in remediation.actions[:6]
        )
        return references
