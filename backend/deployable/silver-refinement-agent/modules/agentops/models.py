from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentOpsSummary(BaseModel):
    total_specs: int = Field(ge=0)
    total_executions: int = Field(ge=0)
    pending: int = Field(ge=0)
    validated: int = Field(ge=0)
    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    success_rate: float = Field(ge=0, le=100)


class AgentOpsToday(BaseModel):
    executions: int = Field(ge=0)
    rows_read: int = Field(ge=0)
    rows_written: int = Field(ge=0)
    avg_runtime_seconds: float = Field(ge=0)


class AgentOpsArtifacts(BaseModel):
    total_artifacts: int = Field(ge=0)
    current_packages: int = Field(ge=0)
    latest_package_version: int = Field(ge=0)


class AgentHealth(BaseModel):
    name: str
    status: str
    last_execution_at: datetime | None = None


class AgentOpsDashboardResponse(BaseModel):
    generated_at: datetime
    summary: AgentOpsSummary
    today: AgentOpsToday
    artifacts: AgentOpsArtifacts
    agents: list[AgentHealth]


class ExecutionTimelineItem(BaseModel):
    execution_id: str
    spec_id: str
    package_version: int
    status: str
    requested_by: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    next_watermark: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    dataproc_batch_id: str | None = None
    rows_read: int | None = Field(default=None, ge=0)
    rows_written: int | None = Field(default=None, ge=0)
    logs_uri: str | None = None
    error_message: str | None = None


class ExecutionTimelineResponse(BaseModel):
    executions: list[ExecutionTimelineItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class ExecutionLogFile(BaseModel):
    uri: str
    size_bytes: int = Field(ge=0)


class ExecutionLogsResponse(BaseModel):
    execution_id: str
    spec_id: str
    status: str
    dataproc_batch_id: str | None = None
    logs_uri: str
    files: list[ExecutionLogFile]
    content: str
    tail_lines: int = Field(ge=1)
    returned_lines: int = Field(ge=0)
    truncated: bool


class ExecutionMetricsResponse(BaseModel):
    execution_id: str
    spec_id: str
    status: str
    rows_read: int = Field(ge=0)
    rows_written: int = Field(ge=0)
    failed_rows: int = Field(ge=0)
    quality_status: str | None = None
    quality_outcome: str | None = None
    quality_score: float | None = Field(default=None, ge=0, le=100)
    quarantined_rows: int = Field(default=0, ge=0)
    quarantine_table: str | None = None
    quality_rule_results: list[dict[str, Any]] = Field(default_factory=list)
    pipeline_status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    next_watermark: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    metrics_persisted: bool
    checkpoint_updated: bool = False
    checkpoint_version: int | None = Field(default=None, ge=1)
    raw_result: dict[str, Any]


class ComponentHealth(BaseModel):
    component: str
    status: str
    latency_ms: float = Field(ge=0)
    detail: str


class AgentOpsHealthResponse(BaseModel):
    checked_at: datetime
    overall_status: str
    healthy_components: int = Field(ge=0)
    total_components: int = Field(ge=0)
    components: list[ComponentHealth]


class AgentOpsAlert(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    title: str
    message: str
    source: str
    execution_id: str | None = None
    spec_id: str | None = None
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None


class AgentOpsAlertsResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    unread: int = Field(ge=0)
    alerts: list[AgentOpsAlert]


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(min_length=1, max_length=200)


class AlertAcknowledgeResponse(BaseModel):
    alert_id: str
    acknowledged: bool
    acknowledged_by: str
    acknowledged_at: datetime
