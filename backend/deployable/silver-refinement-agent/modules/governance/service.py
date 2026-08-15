from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    ArtifactDecisionResponse,
    GovernanceArtifactItem,
    PendingArtifactReviewsResponse,
)
from .repository import GovernanceRepository


class GovernanceArtifactNotFoundError(ValueError):
    pass


class GovernanceDecisionConflictError(ValueError):
    pass


class GovernanceService:
    def __init__(self, repository: GovernanceRepository) -> None:
        self.repository = repository

    def list_pending(self, *, limit: int) -> PendingArtifactReviewsResponse:
        rows, total = self.repository.fetch_pending(limit=limit)
        return PendingArtifactReviewsResponse(
            total=total,
            artifacts=[GovernanceArtifactItem.model_validate(row) for row in rows],
        )

    def get_decision(self, artifact_id: str) -> ArtifactDecisionResponse:
        artifact = self.repository.fetch_artifact(artifact_id)
        if artifact is None:
            raise GovernanceArtifactNotFoundError(
                f"Artefacto no encontrado: {artifact_id}"
            )
        decision = self.repository.fetch_decision(artifact_id)
        if decision is None:
            raise GovernanceArtifactNotFoundError(
                f"El artefacto todavía no tiene decisión: {artifact_id}"
            )
        return ArtifactDecisionResponse.model_validate(decision)

    def decide(
        self,
        *,
        artifact_id: str,
        decision: str,
        reviewed_by: str,
        comment: str | None,
    ) -> ArtifactDecisionResponse:
        artifact = self.repository.fetch_artifact(artifact_id)
        if artifact is None:
            raise GovernanceArtifactNotFoundError(
                f"Artefacto no encontrado: {artifact_id}"
            )
        if artifact["artifact_type"] != "ARTIFACT_PACKAGE":
            raise GovernanceDecisionConflictError(
                "Solo se pueden revisar artefactos ARTIFACT_PACKAGE"
            )
        if artifact["generation_status"] != "GENERATED":
            raise GovernanceDecisionConflictError(
                "El paquete debe estar en estado GENERATED"
            )
        existing = self.repository.fetch_decision(artifact_id)
        if existing is not None:
            raise GovernanceDecisionConflictError(
                f"La decisión es inmutable y ya existe: {existing['decision']}"
            )

        reviewed_at = datetime.now(timezone.utc)
        inserted = self.repository.create_decision(
            artifact_id=artifact_id,
            decision=decision,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            comment=comment,
        )
        if not inserted:
            raise GovernanceDecisionConflictError(
                "No fue posible registrar la decisión; probablemente ya fue revisado"
            )
        return ArtifactDecisionResponse(
            artifact_id=artifact_id,
            decision=decision,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            comment=comment,
            immutable=True,
        )
