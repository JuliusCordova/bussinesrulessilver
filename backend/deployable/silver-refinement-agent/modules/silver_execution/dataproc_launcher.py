from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from google.api_core.client_options import ClientOptions
from google.cloud import dataproc_v1


@dataclass(frozen=True)
class DataprocSubmission:
    batch_id: str
    batch_name: str
    pyspark_uri: str
    operation_name: str | None


@dataclass(frozen=True)
class DataprocBatchSnapshot:
    batch_id: str
    batch_name: str
    state: str
    state_message: str | None
    state_time: datetime | None
    output_uri: str | None
    diagnostic_output_uri: str | None


class DataprocLauncher:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        region: str | None = None,
        service_account: str | None = None,
        client: dataproc_v1.BatchControllerClient | None = None,
    ) -> None:
        self.project_id = project_id or os.getenv("PROJECT_ID")
        if not self.project_id:
            raise ValueError("PROJECT_ID es obligatorio")

        self.region = region or os.getenv("DATAPROC_REGION", "us-central1")
        self.service_account = service_account or os.getenv("DATAPROC_SERVICE_ACCOUNT")
        self.client = client or dataproc_v1.BatchControllerClient(
            client_options=ClientOptions(
                api_endpoint=f"{self.region}-dataproc.googleapis.com:443"
            )
        )

    @staticmethod
    def build_batch_id(execution_id: str) -> str:
        normalized = re.sub(r"[^a-z0-9-]", "-", execution_id.lower())
        normalized = re.sub(r"-+", "-", normalized).strip("-")
        batch_id = f"silver-{normalized}"
        if len(batch_id) < 4:
            batch_id = f"silver-exec-{batch_id}"
        return batch_id[:63].rstrip("-")

    @staticmethod
    def _normalize_datetime(value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        to_datetime = getattr(value, "ToDatetime", None)
        if callable(to_datetime):
            return to_datetime()
        return None

    def submit(
        self,
        *,
        execution_id: str,
        pyspark_uri: str,
        runtime_watermark: datetime | None = None,
    ) -> DataprocSubmission:
        if not pyspark_uri.startswith("gs://"):
            raise ValueError("El script PySpark debe estar almacenado en Cloud Storage")

        batch_id = self.build_batch_id(execution_id)
        parent = f"projects/{self.project_id}/locations/{self.region}"

        dataops_dataset = os.getenv("DATAOPS_DATASET", "dataops_control")
        quality_evidence_table = os.getenv(
            "SILVER_QUALITY_EVIDENCE_TABLE",
            f"{self.project_id}.{dataops_dataset}.silver_execution_quality",
        )
        properties = {
            "spark.dataproc.driverEnv.EXECUTION_ID": execution_id,
            "spark.dataproc.driverEnv.QUALITY_EVIDENCE_TABLE": quality_evidence_table,
        }
        if runtime_watermark is not None:
            if runtime_watermark.tzinfo is None or runtime_watermark.utcoffset() is None:
                raise ValueError("runtime_watermark debe incluir zona horaria")
            normalized_watermark = runtime_watermark.astimezone(timezone.utc)
            properties[
                "spark.dataproc.driverEnv.RUNTIME_WATERMARK"
            ] = normalized_watermark.isoformat().replace("+00:00", "Z")

        runtime_config = dataproc_v1.RuntimeConfig(properties=properties)
        environment_config = None
        if self.service_account:
            environment_config = dataproc_v1.EnvironmentConfig(
                execution_config=dataproc_v1.ExecutionConfig(
                    service_account=self.service_account,
                )
            )

        batch = dataproc_v1.Batch(
            pyspark_batch=dataproc_v1.PySparkBatch(
                main_python_file_uri=pyspark_uri,
            ),
            runtime_config=runtime_config,
            environment_config=environment_config,
            labels={
                "component": "silver-execution",
                "execution-id": execution_id.lower().replace("_", "-")[:63],
            },
        )

        request = dataproc_v1.CreateBatchRequest(
            parent=parent,
            batch=batch,
            batch_id=batch_id,
            request_id=execution_id.replace("exec_", "")[:40],
        )
        operation = self.client.create_batch(request=request)

        return DataprocSubmission(
            batch_id=batch_id,
            batch_name=f"{parent}/batches/{batch_id}",
            pyspark_uri=pyspark_uri,
            operation_name=getattr(operation.operation, "name", None),
        )

    def get_batch(self, batch_id: str) -> DataprocBatchSnapshot:
        if not batch_id:
            raise ValueError("dataproc_batch_id es obligatorio")

        batch_name = (
            f"projects/{self.project_id}/locations/{self.region}/batches/{batch_id}"
        )
        batch = self.client.get_batch(name=batch_name)
        state = dataproc_v1.Batch.State(batch.state).name
        state_time = self._normalize_datetime(batch.state_time)
        runtime_info = batch.runtime_info

        return DataprocBatchSnapshot(
            batch_id=batch_id,
            batch_name=batch.name or batch_name,
            state=state,
            state_message=batch.state_message or None,
            state_time=state_time,
            output_uri=runtime_info.output_uri or None,
            diagnostic_output_uri=runtime_info.diagnostic_output_uri or None,
        )
