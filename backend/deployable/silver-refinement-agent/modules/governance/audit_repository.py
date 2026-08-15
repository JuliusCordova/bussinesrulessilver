from __future__ import annotations

import os
from typing import Any

from google.cloud import bigquery


class GovernanceAuditRepository:
    def __init__(self, client: bigquery.Client | None = None, project_id: str | None = None, dataset: str | None = None) -> None:
        self.project_id = project_id or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("PROJECT_ID es obligatorio")
        self.dataset = dataset or os.getenv("DATAOPS_DATASET", "dataops_control")
        self.client = client or bigquery.Client(project=self.project_id)
        prefix = f"{self.project_id}.{self.dataset}"
        self.reviews_table = f"{prefix}.governance_artifact_reviews"
        self.promotions_table = f"{prefix}.governance_artifact_promotions"
        self.rollbacks_table = f"{prefix}.governance_artifact_rollbacks"

    def fetch_events(self, artifact_id: str) -> list[dict[str, Any]]:
        sql = f"""
        SELECT
          CONCAT('review_', artifact_id) AS event_id,
          artifact_id,
          CONCAT('ARTIFACT_', decision) AS event_type,
          reviewed_by AS actor,
          reviewed_at AS event_at,
          CAST(NULL AS STRING) AS source_environment,
          CAST(NULL AS STRING) AS target_environment,
          decision,
          comment
        FROM `{self.reviews_table}`
        WHERE artifact_id = @artifact_id

        UNION ALL

        SELECT
          promotion_id AS event_id,
          artifact_id,
          'ARTIFACT_PROMOTED' AS event_type,
          promoted_by AS actor,
          promoted_at AS event_at,
          source_environment,
          target_environment,
          CAST(NULL AS STRING) AS decision,
          comment
        FROM `{self.promotions_table}`
        WHERE artifact_id = @artifact_id

        UNION ALL

        SELECT
          rollback_id AS event_id,
          artifact_id,
          'ARTIFACT_ROLLED_BACK' AS event_type,
          rolled_back_by AS actor,
          rolled_back_at AS event_at,
          source_environment,
          target_environment,
          CAST(NULL AS STRING) AS decision,
          comment
        FROM `{self.rollbacks_table}`
        WHERE artifact_id = @artifact_id

        ORDER BY event_at ASC
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("artifact_id", "STRING", artifact_id)]
        )
        return [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]
