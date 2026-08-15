from __future__ import annotations

from datetime import datetime, timezone

from .summary_models import (
    GovernanceActivitySummary,
    GovernanceDecisionSummary,
    GovernanceEnvironmentSummary,
    GovernanceSummaryResponse,
)
from .summary_repository import GovernanceSummaryRepository


class GovernanceSummaryService:
    def __init__(self, repository: GovernanceSummaryRepository) -> None:
        self.repository = repository

    def get_summary(self) -> GovernanceSummaryResponse:
        row = self.repository.fetch_summary()
        pending = int(row.get("pending") or 0)
        rejected = int(row.get("rejected") or 0)
        compliance_status = "COMPLIANT"
        if pending > 0:
            compliance_status = "PENDING_REVIEW"
        if rejected > 0:
            compliance_status = "ATTENTION_REQUIRED"

        return GovernanceSummaryResponse(
            generated_at=datetime.now(timezone.utc),
            total_current_packages=int(row.get("total_current_packages") or 0),
            decisions=GovernanceDecisionSummary(
                pending=pending,
                approved=int(row.get("approved") or 0),
                rejected=rejected,
            ),
            environments=GovernanceEnvironmentSummary(
                dev=int(row.get("dev") or 0),
                qa=int(row.get("qa") or 0),
                prod=int(row.get("prod") or 0),
            ),
            activity=GovernanceActivitySummary(
                promotions=int(row.get("promotions") or 0),
                rollbacks=int(row.get("rollbacks") or 0),
                audit_events=int(row.get("audit_events") or 0),
            ),
            compliance_status=compliance_status,
        )
