from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable

from .models import (
    AgentTaskResult,
    CriticalConclusionAssessment,
    CriticalFinding,
    CriticalReview,
)


class CriticalConclusionAgent:
    """Second-line validator for conclusions produced by specialized agents.

    The critic never replaces live evidence. It validates whether conclusions are
    supported, identifies partial evidence, and detects contradictory live claims
    before the Supervisor publishes a consolidated conclusion.
    """

    EXCLUDED_EVIDENCE_SOURCES = {
        "controlled_memory_context",
        "memory_grounding_trace",
    }

    CLAIM_KEYS = {
        "status",
        "state",
        "overall_status",
        "health_status",
        "quality_status",
        "approval_status",
        "promotion_status",
        "requires_human_review",
        "safe_to_automate",
    }

    POSITIVE_VALUES = {
        "SUCCEEDED",
        "SUCCESS",
        "COMPLETED",
        "HEALTHY",
        "APPROVED",
        "PASSED",
        "READY",
        "SAFE",
        "TRUE",
    }
    NEGATIVE_VALUES = {
        "FAILED",
        "FAILURE",
        "ERROR",
        "UNHEALTHY",
        "REJECTED",
        "BLOCKED",
        "CRITICAL",
        "UNSAFE",
        "FALSE",
    }

    SOURCE_DIMENSIONS = {
        "silver_execution": "execution",
        "current_execution_status": "execution",
        "execution_metrics": "quality",
        "data_quality": "quality",
        "profiling": "quality",
        "reconciliation": "quality",
        "governance": "governance",
        "platform_health": "platform",
        "diagnosis": "diagnosis",
    }

    MEMORY_WARNING_MARKERS = {
        "memorias por conflicto",
        "memoria por conflicto",
        "current_evidence_wins",
        "evidencia actual",
    }

    def review(
        self,
        *,
        results: list[AgentTaskResult],
        enabled: bool = True,
        mode: str = "STANDARD",
        min_live_evidence_sources: int = 1,
        reject_on_contradiction: bool = True,
    ) -> CriticalReview:
        normalized_mode = "STRICT" if str(mode).upper() == "STRICT" else "STANDARD"
        review = CriticalReview(
            enabled=enabled,
            mode=normalized_mode,
            reviewed_agent_count=len(results),
        )

        if not enabled:
            review.summary = "La validación crítica fue deshabilitada para esta consulta."
            return review

        assessments: dict[str, CriticalConclusionAssessment] = {}
        findings: list[CriticalFinding] = []

        for result in results:
            live_sources = self._live_evidence_sources(result)
            operational_warnings = self._operational_warnings(result)
            assessment_status = "VALIDATED"
            reasons: list[str] = []

            if len(live_sources) < min_live_evidence_sources:
                assessment_status = (
                    "REJECTED" if normalized_mode == "STRICT" else "CONDITIONED"
                )
                reasons.append(
                    "La conclusión no alcanzó el mínimo de fuentes de evidencia viva."
                )
                findings.append(
                    self._finding(
                        category="UNSUPPORTED_CONCLUSION",
                        severity=(
                            "CRITICAL" if normalized_mode == "STRICT" else "WARNING"
                        ),
                        agent_ids=[result.agent_id],
                        subject=f"conclusion.{result.agent_id}",
                        description=(
                            f"La conclusión del agente {result.agent_id} tiene "
                            f"{len(live_sources)} fuentes vivas; se requieren "
                            f"{min_live_evidence_sources}."
                        ),
                        evidence_sources=live_sources,
                        resolution=(
                            "Solicitar evidencia operativa adicional antes de aceptar "
                            "la conclusión."
                        ),
                    )
                )

            if result.status.upper() == "PARTIAL" or operational_warnings:
                if assessment_status != "REJECTED":
                    assessment_status = "CONDITIONED"
                reasons.append(
                    "El agente reportó resultado parcial o advertencias operativas."
                )
                findings.append(
                    self._finding(
                        category="INSUFFICIENT_EVIDENCE",
                        severity="WARNING",
                        agent_ids=[result.agent_id],
                        subject=f"evidence.{result.agent_id}",
                        description=(
                            f"El resultado de {result.agent_id} requiere contexto adicional: "
                            + "; ".join(
                                operational_warnings or ["resultado parcial"]
                            )
                        ),
                        evidence_sources=live_sources,
                        resolution=(
                            "Mantener la conclusión condicionada hasta completar las "
                            "fuentes faltantes."
                        ),
                    )
                )

            if (
                result.memory_grounding is not None
                and result.memory_grounding.conflict_count
            ):
                findings.append(
                    self._finding(
                        category="MEMORY_CONFLICT_BLOCKED",
                        severity="INFO",
                        agent_ids=[result.agent_id],
                        subject=f"memory_grounding.{result.agent_id}",
                        description=(
                            f"Se bloquearon {result.memory_grounding.conflict_count} "
                            "memorias por contradicción con la evidencia actual."
                        ),
                        evidence_sources=["memory_grounding_trace"],
                        resolution=(
                            "Conservar la memoria para auditoría y mantener "
                            "CURRENT_EVIDENCE_WINS."
                        ),
                    )
                )

            assessments[result.agent_id] = CriticalConclusionAssessment(
                agent_id=result.agent_id,
                status=assessment_status,
                conclusion=result.summary,
                live_evidence_sources=live_sources,
                reasons=reasons,
            )

        contradiction_findings = self._detect_contradictions(results)
        findings.extend(contradiction_findings)

        for finding in contradiction_findings:
            for agent_id in finding.agent_ids:
                assessment = assessments.get(agent_id)
                if assessment is None:
                    continue
                if reject_on_contradiction:
                    assessment.status = "REJECTED"
                    assessment.reasons.append(
                        "La conclusión participa en una contradicción crítica no resuelta."
                    )
                elif assessment.status != "REJECTED":
                    assessment.status = "CONDITIONED"
                    assessment.reasons.append(
                        "La conclusión participa en una contradicción que requiere revisión."
                    )

        review.assessments = [assessments[key] for key in sorted(assessments)]
        review.findings = findings
        review.validated_count = sum(
            1 for item in review.assessments if item.status == "VALIDATED"
        )
        review.conditioned_count = sum(
            1 for item in review.assessments if item.status == "CONDITIONED"
        )
        review.rejected_count = sum(
            1 for item in review.assessments if item.status == "REJECTED"
        )
        review.contradiction_count = len(contradiction_findings)
        review.unsupported_count = sum(
            1 for item in findings if item.category == "UNSUPPORTED_CONCLUSION"
        )
        review.insufficient_evidence_count = sum(
            1 for item in findings if item.category == "INSUFFICIENT_EVIDENCE"
        )

        if review.rejected_count:
            review.status = "REJECTED"
        elif review.conditioned_count:
            review.status = "CONDITIONED"
        else:
            review.status = "VALIDATED"

        review.requires_human_review = review.status != "VALIDATED"
        review.summary = (
            f"El agente crítico revisó {review.reviewed_agent_count} conclusiones: "
            f"{review.validated_count} validadas, "
            f"{review.conditioned_count} condicionadas y "
            f"{review.rejected_count} rechazadas. "
            f"Contradicciones detectadas: {review.contradiction_count}."
        )
        return review

    def _detect_contradictions(
        self,
        results: list[AgentTaskResult],
    ) -> list[CriticalFinding]:
        claims_by_subject: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

        for result in results:
            for item in result.evidence:
                source = str(item.get("source", "unknown"))
                if source in self.EXCLUDED_EVIDENCE_SOURCES:
                    continue
                dimension = self.SOURCE_DIMENSIONS.get(source, source)
                payload = item.get("payload")
                for key, value in self._extract_claims(payload):
                    normalized = self._normalize_value(value)
                    if normalized is None:
                        continue
                    subject = f"{dimension}.{key}"
                    claims_by_subject[subject].append(
                        (result.agent_id, normalized, source)
                    )

        findings: list[CriticalFinding] = []
        for subject, claims in sorted(claims_by_subject.items()):
            polarities = {
                polarity
                for _, value, _ in claims
                if (polarity := self._polarity(value)) is not None
            }
            boolean_values = {
                value for _, value, _ in claims if value in {"TRUE", "FALSE"}
            }
            contradiction = polarities == {
                "POSITIVE",
                "NEGATIVE",
            } or boolean_values == {"TRUE", "FALSE"}
            if not contradiction:
                continue

            agent_ids = sorted({agent_id for agent_id, _, _ in claims})
            sources = sorted({source for _, _, source in claims})
            rendered = ", ".join(
                f"{agent_id}={value}" for agent_id, value, _ in claims
            )
            findings.append(
                self._finding(
                    category="CONTRADICTION",
                    severity="CRITICAL",
                    agent_ids=agent_ids,
                    subject=subject,
                    description=(
                        f"Se detectaron afirmaciones contradictorias: {rendered}."
                    ),
                    evidence_sources=sources,
                    resolution=(
                        "No publicar una conclusión definitiva hasta resolver la "
                        "fuente operativa autoritativa."
                    ),
                )
            )

        return findings

    def _live_evidence_sources(self, result: AgentTaskResult) -> list[str]:
        return sorted(
            {
                str(item.get("source", "unknown"))
                for item in result.evidence
                if str(item.get("source", "unknown"))
                not in self.EXCLUDED_EVIDENCE_SOURCES
            }
        )

    def _operational_warnings(self, result: AgentTaskResult) -> list[str]:
        operational: list[str] = []
        for warning in result.warnings:
            normalized = warning.lower()
            if any(marker in normalized for marker in self.MEMORY_WARNING_MARKERS):
                continue
            operational.append(warning)
        return operational

    def _extract_claims(self, payload: Any) -> Iterable[tuple[str, Any]]:
        if isinstance(payload, dict):
            for key, value in payload.items():
                normalized_key = str(key).lower()
                if normalized_key in self.CLAIM_KEYS and not isinstance(
                    value,
                    (dict, list, tuple, set),
                ):
                    yield normalized_key, value
                yield from self._extract_claims(value)
        elif isinstance(payload, (list, tuple, set)):
            for item in payload:
                yield from self._extract_claims(item)

    @staticmethod
    def _normalize_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        rendered = str(value).strip().upper()
        return rendered or None

    def _polarity(self, value: str) -> str | None:
        if value in self.POSITIVE_VALUES:
            return "POSITIVE"
        if value in self.NEGATIVE_VALUES:
            return "NEGATIVE"
        return None

    @staticmethod
    def _finding(
        *,
        category: str,
        severity: str,
        agent_ids: list[str],
        subject: str,
        description: str,
        evidence_sources: list[str],
        resolution: str,
    ) -> CriticalFinding:
        digest = hashlib.sha1(
            f"{category}|{subject}|{'|'.join(agent_ids)}|{description}".encode(
                "utf-8"
            )
        ).hexdigest()[:12]
        return CriticalFinding(
            finding_id=f"critical_{digest}",
            category=category,
            severity=severity,
            agent_ids=agent_ids,
            subject=subject,
            description=description,
            evidence_sources=evidence_sources,
            resolution=resolution,
        )
