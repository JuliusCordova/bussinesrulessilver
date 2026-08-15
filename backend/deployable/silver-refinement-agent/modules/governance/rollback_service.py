from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .rollback_models import ArtifactRollbackHistoryResponse, ArtifactRollbackResponse
from .rollback_repository import GovernanceRollbackRepository


class GovernanceRollbackNotFoundError(ValueError):
    pass


class GovernanceRollbackConflictError(ValueError):
    pass


class GovernanceRollbackService:
    def __init__(self, repository: GovernanceRollbackRepository) -> None:
        self.repository = repository

    def get_history(self, artifact_id: str) -> ArtifactRollbackHistoryResponse:
        artifact = self.repository.fetch_artifact(artifact_id)
        if artifact is None:
            raise GovernanceRollbackNotFoundError(f"Artefacto no encontrado: {artifact_id}")
        events = self.repository.fetch_environment_events(artifact_id)
        current_environment = events[-1]["target_environment"] if events else "DEV"
        rows = self.repository.fetch_history(artifact_id)
        return ArtifactRollbackHistoryResponse(
            artifact_id=artifact_id,
            current_environment=current_environment,
            total=len(rows),
            rollbacks=[ArtifactRollbackResponse.model_validate(row) for row in rows],
        )

    def rollback(self, *, artifact_id: str, rolled_back_by: str, comment: str) -> ArtifactRollbackResponse:
        artifact = self.repository.fetch_artifact(artifact_id)
        if artifact is None:
            raise GovernanceRollbackNotFoundError(f"Artefacto no encontrado: {artifact_id}")
        if artifact["artifact_type"] != "ARTIFACT_PACKAGE":
            raise GovernanceRollbackConflictError("Solo se pueden revertir artefactos ARTIFACT_PACKAGE")
        if artifact["generation_status"] != "GENERATED" or artifact.get("decision") != "APPROVED":
            raise GovernanceRollbackConflictError("El paquete debe estar GENERATED y APPROVED")

        events = self.repository.fetch_environment_events(artifact_id)
        current_environment = events[-1]["target_environment"] if events else "DEV"
        target_environment = {"PROD": "QA", "QA": "DEV"}.get(current_environment)
        if target_environment is None:
            raise GovernanceRollbackConflictError("El paquete ya se encuentra en DEV y no admite rollback")

        rolled_back_at = datetime.now(timezone.utc)
        rollback_id = f"rollback_{uuid4().hex}"
        inserted = self.repository.create_rollback(
            rollback_id=rollback_id,
            artifact_id=artifact_id,
            spec_id=artifact["spec_id"],
            artifact_version=int(artifact["artifact_version"]),
            source_environment=current_environment,
            target_environment=target_environment,
            rolled_back_by=rolled_back_by,
            rolled_back_at=rolled_back_at,
            comment=comment,
        )
        if not inserted:
            raise GovernanceRollbackConflictError("No fue posible registrar el rollback")
        return ArtifactRollbackResponse(
            rollback_id=rollback_id,
            artifact_id=artifact_id,
            spec_id=artifact["spec_id"],
            artifact_version=int(artifact["artifact_version"]),
            source_environment=current_environment,
            target_environment=target_environment,
            rolled_back_by=rolled_back_by,
            rolled_back_at=rolled_back_at,
            comment=comment,
            immutable=True,
        )
