from __future__ import annotations

import os
from typing import Any

from google.cloud import bigquery


class GovernanceSummaryRepository:
    def __init__(
        self,
        client: bigquery.Client | None = None,
        project_id: str | None = None,
        dataset: str | None = None,
    ) -> None:
        self.project_id = project_id or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("PROJECT_ID es obligatorio")
        self.dataset = dataset or os.getenv("DATAOPS_DATASET", "dataops_control")
        self.client = client or bigquery.Client(project=self.project_id)
        prefix = f"{self.project_id}.{self.dataset}"
        self.artifacts_table = f"{prefix}.silver_artifacts"
        self.reviews_table = f"{prefix}.governance_artifact_reviews"
        self.promotions_table = f"{prefix}.governance_artifact_promotions"
        self.rollbacks_table = f"{prefix}.governance_artifact_rollbacks"

    def fetch_summary(self) -> dict[str, Any]:
        sql = f"""
        WITH current_packages AS (
          SELECT artifact_id
          FROM `{self.artifacts_table}`
          WHERE artifact_type = 'ARTIFACT_PACKAGE'
            AND is_current = TRUE
            AND generation_status = 'GENERATED'
        ),
        decisions AS (
          SELECT
            COUNTIF(r.decision IS NULL) AS pending,
            COUNTIF(r.decision = 'APPROVED') AS approved,
            COUNTIF(r.decision = 'REJECTED') AS rejected
          FROM current_packages p
          LEFT JOIN `{self.reviews_table}` r USING (artifact_id)
        ),
        governance_events AS (
          SELECT artifact_id, promoted_at AS event_at, target_environment
          FROM `{self.promotions_table}`
          UNION ALL
          SELECT artifact_id, rolled_back_at AS event_at, target_environment
          FROM `{self.rollbacks_table}`
        ),
        latest_environment AS (
          SELECT
            p.artifact_id,
            COALESCE(
              ARRAY_AGG(e.target_environment IGNORE NULLS ORDER BY e.event_at DESC LIMIT 1)[SAFE_OFFSET(0)],
              'DEV'
            ) AS current_environment
          FROM current_packages p
          LEFT JOIN governance_events e USING (artifact_id)
          GROUP BY p.artifact_id
        ),
        environments AS (
          SELECT
            COUNTIF(current_environment = 'DEV') AS dev,
            COUNTIF(current_environment = 'QA') AS qa,
            COUNTIF(current_environment = 'PROD') AS prod
          FROM latest_environment
        ),
        activity AS (
          SELECT
            (SELECT COUNT(*) FROM `{self.promotions_table}`) AS promotions,
            (SELECT COUNT(*) FROM `{self.rollbacks_table}`) AS rollbacks,
            (SELECT COUNT(*) FROM `{self.reviews_table}`)
              + (SELECT COUNT(*) FROM `{self.promotions_table}`)
              + (SELECT COUNT(*) FROM `{self.rollbacks_table}`) AS audit_events
        )
        SELECT
          (SELECT COUNT(*) FROM current_packages) AS total_current_packages,
          d.pending,
          d.approved,
          d.rejected,
          e.dev,
          e.qa,
          e.prod,
          a.promotions,
          a.rollbacks,
          a.audit_events
        FROM decisions d
        CROSS JOIN environments e
        CROSS JOIN activity a
        """
        rows = list(self.client.query(sql).result())
        if not rows:
            return {
                "total_current_packages": 0,
                "pending": 0,
                "approved": 0,
                "rejected": 0,
                "dev": 0,
                "qa": 0,
                "prod": 0,
                "promotions": 0,
                "rollbacks": 0,
                "audit_events": 0,
            }
        return dict(rows[0].items())
