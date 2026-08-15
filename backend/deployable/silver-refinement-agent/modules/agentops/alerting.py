from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from google.cloud import bigquery

from .models import (
    AgentOpsAlert,
    AgentOpsAlertsResponse,
    AlertAcknowledgeResponse,
)


class AlertNotFoundError(ValueError):
    pass


class AgentOpsAlertService:
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
        self.executions_table = f"{self.project_id}.{self.dataset}.silver_executions"
        self.acks_table = f"{self.project_id}.{self.dataset}.agentops_alert_acknowledgements"

    @staticmethod
    def _alert_id(alert_type: str, source_id: str) -> str:
        digest = hashlib.sha256(f"{alert_type}:{source_id}".encode("utf-8")).hexdigest()[:24]
        return f"alert_{digest}"

    def _ensure_ack_table(self) -> None:
        sql = f"""
        CREATE TABLE IF NOT EXISTS `{self.acks_table}` (
          alert_id STRING NOT NULL,
          acknowledged_by STRING NOT NULL,
          acknowledged_at TIMESTAMP NOT NULL
        )
        """
        self.client.query(sql).result()

    def _fetch_execution_alerts(self, limit: int) -> list[dict[str, Any]]:
        sql = f"""
        SELECT
          execution_id,
          spec_id,
          status,
          created_at,
          started_at,
          finished_at,
          error_message,
          TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, MINUTE) AS age_minutes
        FROM `{self.executions_table}`
        WHERE
          status IN ('FAILED', 'CANCELLED')
          OR (
            status IN ('PENDING', 'VALIDATED', 'QUEUED', 'RUNNING')
            AND created_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE)
          )
        ORDER BY created_at DESC
        LIMIT @limit
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        )
        return [dict(row.items()) for row in self.client.query(sql, job_config=config).result()]

    def _fetch_acknowledgements(self, alert_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not alert_ids:
            return {}
        self._ensure_ack_table()
        sql = f"""
        SELECT alert_id, acknowledged_by, acknowledged_at
        FROM `{self.acks_table}`
        WHERE alert_id IN UNNEST(@alert_ids)
        QUALIFY ROW_NUMBER() OVER (PARTITION BY alert_id ORDER BY acknowledged_at DESC) = 1
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("alert_ids", "STRING", alert_ids)
            ]
        )
        rows = self.client.query(sql, job_config=config).result()
        return {row["alert_id"]: dict(row.items()) for row in rows}

    def list_alerts(
        self,
        *,
        limit: int = 100,
        unread_only: bool = False,
    ) -> AgentOpsAlertsResponse:
        rows = self._fetch_execution_alerts(limit)
        raw_alerts: list[dict[str, Any]] = []
        for row in rows:
            execution_id = row["execution_id"]
            execution_status = row["status"]
            if execution_status == "FAILED":
                alert_type = "EXECUTION_FAILED"
                severity = "CRITICAL"
                title = "Ejecución fallida"
                message = row.get("error_message") or "La ejecución terminó con error."
            elif execution_status == "CANCELLED":
                alert_type = "EXECUTION_CANCELLED"
                severity = "WARNING"
                title = "Ejecución cancelada"
                message = "La ejecución fue cancelada antes de finalizar."
            else:
                alert_type = "EXECUTION_STALLED"
                severity = "WARNING"
                title = "Ejecución detenida"
                message = (
                    f"La ejecución permanece en {execution_status} por "
                    f"{int(row.get('age_minutes') or 0)} minutos."
                )
            raw_alerts.append(
                {
                    "alert_id": self._alert_id(alert_type, execution_id),
                    "alert_type": alert_type,
                    "severity": severity,
                    "title": title,
                    "message": message,
                    "source": "silver_execution",
                    "execution_id": execution_id,
                    "spec_id": row.get("spec_id"),
                    "created_at": row["created_at"],
                }
            )

        ack_map = self._fetch_acknowledgements([item["alert_id"] for item in raw_alerts])
        alerts: list[AgentOpsAlert] = []
        for item in raw_alerts:
            ack = ack_map.get(item["alert_id"])
            item["acknowledged"] = ack is not None
            item["acknowledged_by"] = ack.get("acknowledged_by") if ack else None
            item["acknowledged_at"] = ack.get("acknowledged_at") if ack else None
            alert = AgentOpsAlert.model_validate(item)
            if unread_only and alert.acknowledged:
                continue
            alerts.append(alert)

        return AgentOpsAlertsResponse(
            generated_at=datetime.now(timezone.utc),
            total=len(alerts),
            unread=sum(1 for alert in alerts if not alert.acknowledged),
            alerts=alerts,
        )

    def acknowledge(self, alert_id: str, acknowledged_by: str) -> AlertAcknowledgeResponse:
        current = self.list_alerts(limit=500, unread_only=False)
        if not any(alert.alert_id == alert_id for alert in current.alerts):
            raise AlertNotFoundError(f"Alerta no encontrada: {alert_id}")
        self._ensure_ack_table()
        acknowledged_at = datetime.now(timezone.utc)
        sql = f"""
        INSERT INTO `{self.acks_table}` (alert_id, acknowledged_by, acknowledged_at)
        VALUES (@alert_id, @acknowledged_by, @acknowledged_at)
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("alert_id", "STRING", alert_id),
                bigquery.ScalarQueryParameter("acknowledged_by", "STRING", acknowledged_by),
                bigquery.ScalarQueryParameter("acknowledged_at", "TIMESTAMP", acknowledged_at),
            ]
        )
        self.client.query(sql, job_config=config).result()
        return AlertAcknowledgeResponse(
            alert_id=alert_id,
            acknowledged=True,
            acknowledged_by=acknowledged_by,
            acknowledged_at=acknowledged_at,
        )
