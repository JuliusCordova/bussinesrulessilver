from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .promotion_models import (
    ArtifactPromotionHistoryResponse,
    ArtifactPromotionResponse,
)
from .promotion_repository import GovernancePromotionRepository


class GovernancePromotionNotFoundError(ValueError):
    pass


class GovernancePromotionConflictError(ValueError):
    pass


class GovernancePromotionService:
    def __init__(self, repository: GovernancePromotionRepository) -> None:
        self.repository = repository

    def get_history(self, artifact_id: str) -> ArtifactPromotionHistoryResponse:
        artifact = self.repository.fetch_approved_artifact(artifact_id)
        if artifact is None:
            raise GovernancePromotionNotFoundError(
                f"Artefacto no encontrado: {artifact_id}"
            )
        rows = self.repository.fetch_history(artifact_id)
        current_environment = rows[-1]["target_environment"] if rows else "DEV"
        return ArtifactPromotionHistoryResponse(
            artifact_id=artifact_id,
            current_environment=current_environment,
            total=len(rows),
            promotions=[ArtifactPromotionResponse.model_validate(row) for row in rows],
        )

    def promote(
        self,
        *,
        artifact_id: str,
        target_environment: str,
        promoted_by: str,
        comment: str | None,
    ) -> ArtifactPromotionResponse:
        artifact = self.repository.fetch_approved_artifact(artifact_id)
        if artifact is None:
            raise GovernancePromotionNotFoundError(
                f"Artefacto no encontrado: {artifact_id}"
            )
        if artifact["artifact_type"] != "ARTIFACT_PACKAGE":
            raise GovernancePromotionConflictError(
                "Solo se pueden promover artefactos ARTIFACT_PACKAGE"
            )
        if artifact["generation_status"] != "GENERATED":
            raise GovernancePromotionConflictError(
                "El paquete debe estar en estado GENERATED"
            )
        if artifact.get("decision") != "APPROVED":
            raise GovernancePromotionConflictError(
                "El paquete debe estar APPROVED antes de promoverse"
            )

        history = self.repository.fetch_history(artifact_id)
        current_environment = history[-1]["target_environment"] if history else "DEV"
        expected_target = {"DEV": "QA", "QA": "PROD"}.get(current_environment)
        if expected_target is None:
            raise GovernancePromotionConflictError(
                "El paquete ya se encuentra en PROD"
            )
        if target_environment != expected_target:
            raise GovernancePromotionConflictError(
                f"Promoción inválida: desde {current_environment} solo se permite {expected_target}"
            )

        promoted_at = datetime.now(timezone.utc)
        promotion_id = f"promotion_{uuid4().hex}"
        inserted = self.repository.create_promotion(
            promotion_id=promotion_id,
            artifact_id=artifact_id,
            spec_id=artifact["spec_id"],
            artifact_version=int(artifact["artifact_version"]),
            source_environment=current_environment,
            target_environment=target_environment,
            promoted_by=promoted_by,
            promoted_at=promoted_at,
            comment=comment,
        )
        if not inserted:
            raise GovernancePromotionConflictError(
                f"La promoción hacia {target_environment} ya existe"
            )

        return ArtifactPromotionResponse(
            promotion_id=promotion_id,
            artifact_id=artifact_id,
            spec_id=artifact["spec_id"],
            artifact_version=int(artifact["artifact_version"]),
            source_environment=current_environment,
            target_environment=target_environment,
            promoted_by=promoted_by,
            promoted_at=promoted_at,
            comment=comment,
            immutable=True,
        )
