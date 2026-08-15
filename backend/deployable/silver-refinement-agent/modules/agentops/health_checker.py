from __future__ import annotations

import os
from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from google.cloud import bigquery, dataproc_v1, storage


@dataclass(frozen=True)
class HealthProbeResult:
    component: str
    status: str
    latency_ms: float
    detail: str


class AgentOpsHealthChecker:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        dataproc_region: str | None = None,
        artifact_bucket: str | None = None,
        bigquery_client: bigquery.Client | None = None,
        storage_client: storage.Client | None = None,
        dataproc_client: dataproc_v1.BatchControllerClient | None = None,
    ) -> None:
        self.project_id = project_id or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("PROJECT_ID es obligatorio")
        self.dataproc_region = dataproc_region or os.getenv("DATAPROC_REGION", "us-central1")
        self.artifact_bucket = artifact_bucket or os.getenv("ARTIFACT_BUCKET")
        self._bigquery_client = bigquery_client
        self._storage_client = storage_client
        self._dataproc_client = dataproc_client

    @staticmethod
    def _run_probe(component: str, action: Callable[[], str]) -> HealthProbeResult:
        started = perf_counter()
        try:
            detail = action()
            status = "HEALTHY"
        except Exception as exc:  # health checks must report failures instead of raising
            detail = str(exc)
            status = "UNAVAILABLE"
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return HealthProbeResult(
            component=component,
            status=status,
            latency_ms=latency_ms,
            detail=detail,
        )

    def check(self) -> list[HealthProbeResult]:
        return [
            HealthProbeResult(
                component="cloud_run_api",
                status="HEALTHY",
                latency_ms=0.0,
                detail="AgentOps API is responding",
            ),
            self._run_probe("bigquery", self._check_bigquery),
            self._run_probe("cloud_storage", self._check_storage),
            self._run_probe("dataproc_serverless", self._check_dataproc),
        ]

    def _check_bigquery(self) -> str:
        client = self._bigquery_client or bigquery.Client(project=self.project_id)
        rows = list(client.query("SELECT 1 AS ok").result())
        if not rows or int(rows[0]["ok"]) != 1:
            raise RuntimeError("BigQuery health query returned an invalid result")
        return f"BigQuery reachable in project {self.project_id}"

    def _check_storage(self) -> str:
        if not self.artifact_bucket:
            raise RuntimeError("ARTIFACT_BUCKET is not configured")
        client = self._storage_client or storage.Client(project=self.project_id)
        bucket = client.bucket(self.artifact_bucket)
        bucket.reload()
        return f"Artifact bucket reachable: gs://{self.artifact_bucket}"

    def _check_dataproc(self) -> str:
        client = self._dataproc_client
        if client is None:
            endpoint = f"{self.dataproc_region}-dataproc.googleapis.com:443"
            client = dataproc_v1.BatchControllerClient(
                client_options={"api_endpoint": endpoint}
            )
        parent = f"projects/{self.project_id}/locations/{self.dataproc_region}"
        iterator = client.list_batches(request={"parent": parent, "page_size": 1})
        next(iter(iterator), None)
        return f"Dataproc Serverless reachable in {self.dataproc_region}"
