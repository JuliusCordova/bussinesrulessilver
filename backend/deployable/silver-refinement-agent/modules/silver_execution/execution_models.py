from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CreateExecutionRequest(BaseModel):
    spec_id: str = Field(min_length=1)
    requested_by: str = Field(default="system", min_length=1)


class ExecutionRecord(BaseModel):
    execution_id: str
    spec_id: str
    mapping_version: int = Field(ge=1)
    package_version: int = Field(ge=1)
    artifact_package_uri: str
    load_strategy: str = "FULL"
    watermark_column: str | None = None
    runtime_watermark: datetime | None = None
    next_watermark: datetime | None = None
    lookback_value: int | None = Field(default=None, ge=0)
    lookback_unit: str | None = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    dataproc_batch_id: str | None = None
    rows_read: int | None = Field(default=None, ge=0)
    rows_written: int | None = Field(default=None, ge=0)
    error_message: str | None = None
    logs_uri: str | None = None
    requested_by: str = "system"


class ExecutionListResponse(BaseModel):
    executions: list[ExecutionRecord]


class PackageValidationResponse(BaseModel):
    execution: ExecutionRecord
    current_uri: str
    manifest_uri: str
    package_hash: str
    files_validated: int = Field(ge=1)


class DataprocSubmissionResponse(BaseModel):
    execution: ExecutionRecord
    batch_id: str
    batch_name: str
    pyspark_uri: str
    operation_name: str | None = None


class ExecutionMonitoringResponse(BaseModel):
    execution: ExecutionRecord
    dataproc_state: str
    state_message: str | None = None
    state_time: datetime | None = None
    output_uri: str | None = None
    diagnostic_output_uri: str | None = None
