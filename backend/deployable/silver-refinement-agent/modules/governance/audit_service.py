from __future__ import annotations

from .audit_models import GovernanceAuditEvent, GovernanceAuditTrailResponse
from .audit_repository import GovernanceAuditRepository


class GovernanceAuditNotFoundError(ValueError):
    pass


class GovernanceAuditService:
    def __init__(self, repository: GovernanceAuditRepository) -> None:
        self.repository = repository

    def get_trail(self, artifact_id: str) -> GovernanceAuditTrailResponse:
        rows = self.repository.fetch_events(artifact_id)
        if not rows:
            raise GovernanceAuditNotFoundError(
                f"No existen eventos de gobierno para el artefacto: {artifact_id}"
            )
        return GovernanceAuditTrailResponse(
            artifact_id=artifact_id,
            total=len(rows),
            events=[GovernanceAuditEvent.model_validate(row) for row in rows],
        )
