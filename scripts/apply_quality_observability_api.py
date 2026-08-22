from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend/deployable/silver-refinement-agent"
AGENTOPS = BACKEND / "modules/agentops"
TESTS = BACKEND / "tests"

quality_module = AGENTOPS / "quality_observability.py"
quality_module.write_text('''from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from pydantic import BaseModel, Field


class QualitySummaryResponse(BaseModel):
    generated_at: datetime
    source_available: bool
    evidence_count: int = Field(ge=0)
    latest_recorded_at: datetime | None = None
    latest_quality_score: float | None = Field(default=None, ge=0, le=100)
    latest_runtime_decision: str | None = None
    warning_executions: int = Field(default=0, ge=0)
    quarantine_executions: int = Field(default=0, ge=0)
    block_load_executions: int = Field(default=0, ge=0)
    total_warning_rows: int = Field(default=0, ge=0)
    total_quarantined_rows: int = Field(default=0, ge=0)


class QualityExecutionEvidence(BaseModel):
    execution_id: str
    spec_id: str
    mapping_version: int = Field(ge=1)
    recorded_at: datetime
    gate_status: str
    runtime_decision: str
    quality_score: float = Field(ge=0, le=100)
    total_rows: int = Field(ge=0)
    failed_rows: int = Field(ge=0)
    warning_rows: int = Field(ge=0)
    observed_failure_rows: int = Field(ge=0)
    quarantined_rows: int = Field(ge=0)
    continued_quarantined_rows: int = Field(ge=0)
    quarantine_events: int = Field(ge=0)
    table_level_blocking_failures: int = Field(ge=0)
    table_level_warnings: int = Field(ge=0)
    quarantine_table: str | None = None
    rule_results: list[dict[str, Any]] = Field(default_factory=list)
    configured_rules: list[dict[str, Any]] = Field(default_factory=list)


class QualityExecutionListResponse(BaseModel):
    source_available: bool
    executions: list[QualityExecutionEvidence]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)


class QualityEvidenceNotFoundError(ValueError):
    pass


class QualityObservabilityRepository:
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
        self.table_id = os.getenv(
            "SILVER_QUALITY_EVIDENCE_TABLE",
            f"{self.project_id}.{self.dataset}.silver_execution_quality",
        )

    def source_available(self) -> bool:
        try:
            self.client.get_table(self.table_id)
            return True
        except NotFound:
            return False

    @staticmethod
    def _parse_json(value: Any) -> list[dict[str, Any]]:
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        return []

    def _to_evidence(self, row: Any) -> QualityExecutionEvidence:
        data = dict(row.items())
        data["rule_results"] = self._parse_json(data.pop("rule_results_json", None))
        data["configured_rules"] = self._parse_json(data.pop("configured_rules_json", None))
        data["quarantine_table"] = data.get("quarantine_table") or None
        return QualityExecutionEvidence.model_validate(data)

    def fetch_summary(self) -> QualitySummaryResponse:
        generated_at = datetime.now(timezone.utc)
        if not self.source_available():
            return QualitySummaryResponse(
                generated_at=generated_at,
                source_available=False,
                evidence_count=0,
            )

        sql = f"""
        WITH latest AS (
          SELECT *
          FROM `{self.table_id}`
          QUALIFY ROW_NUMBER() OVER (
            PARTITION BY execution_id ORDER BY recorded_at DESC
          ) = 1
        ), latest_global AS (
          SELECT quality_score, runtime_decision, recorded_at
          FROM latest
          ORDER BY recorded_at DESC
          LIMIT 1
        )
        SELECT
          COUNT(*) AS evidence_count,
          MAX(recorded_at) AS latest_recorded_at,
          (SELECT quality_score FROM latest_global) AS latest_quality_score,
          (SELECT runtime_decision FROM latest_global) AS latest_runtime_decision,
          COUNTIF(runtime_decision = 'WARN') AS warning_executions,
          COUNTIF(runtime_decision = 'QUARANTINE') AS quarantine_executions,
          COUNTIF(runtime_decision = 'BLOCK_LOAD') AS block_load_executions,
          COALESCE(SUM(warning_rows), 0) AS total_warning_rows,
          COALESCE(SUM(quarantined_rows), 0) AS total_quarantined_rows
        FROM latest
        """
        rows = list(self.client.query(sql).result())
        data = dict(rows[0].items()) if rows else {}
        return QualitySummaryResponse(
            generated_at=generated_at,
            source_available=True,
            evidence_count=int(data.get("evidence_count") or 0),
            latest_recorded_at=data.get("latest_recorded_at"),
            latest_quality_score=(
                float(data["latest_quality_score"])
                if data.get("latest_quality_score") is not None
                else None
            ),
            latest_runtime_decision=data.get("latest_runtime_decision"),
            warning_executions=int(data.get("warning_executions") or 0),
            quarantine_executions=int(data.get("quarantine_executions") or 0),
            block_load_executions=int(data.get("block_load_executions") or 0),
            total_warning_rows=int(data.get("total_warning_rows") or 0),
            total_quarantined_rows=int(data.get("total_quarantined_rows") or 0),
        )

    def list_latest(self, limit: int) -> QualityExecutionListResponse:
        if not self.source_available():
            return QualityExecutionListResponse(
                source_available=False,
                executions=[],
                total=0,
                limit=limit,
            )
        sql = f"""
        SELECT *, COUNT(*) OVER() AS total_count
        FROM `{self.table_id}`
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY execution_id ORDER BY recorded_at DESC
        ) = 1
        ORDER BY recorded_at DESC
        LIMIT @limit
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ])
        rows = list(self.client.query(sql, job_config=config).result())
        total = int(rows[0]["total_count"]) if rows else 0
        evidence = []
        for row in rows:
            data = dict(row.items())
            data.pop("total_count", None)
            class RowAdapter:
                def items(self_nonlocal):
                    return data.items()
            evidence.append(self._to_evidence(RowAdapter()))
        return QualityExecutionListResponse(
            source_available=True,
            executions=evidence,
            total=total,
            limit=limit,
        )

    def get_latest(self, execution_id: str) -> QualityExecutionEvidence:
        if not self.source_available():
            raise QualityEvidenceNotFoundError(
                "No existe fuente persistida de evidencia de calidad runtime"
            )
        sql = f"""
        SELECT *
        FROM `{self.table_id}`
        WHERE execution_id = @execution_id
        ORDER BY recorded_at DESC
        LIMIT 1
        """
        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id),
        ])
        rows = list(self.client.query(sql, job_config=config).result())
        if not rows:
            raise QualityEvidenceNotFoundError(
                f"No existe evidencia de calidad runtime para {execution_id}"
            )
        return self._to_evidence(rows[0])
''', encoding="utf-8")

router_path = AGENTOPS / "router.py"
router = router_path.read_text(encoding="utf-8")
import_anchor = "from .repository import AgentOpsRepository\n"
quality_import = '''from .quality_observability import (
    QualityEvidenceNotFoundError,
    QualityExecutionEvidence,
    QualityExecutionListResponse,
    QualityObservabilityRepository,
    QualitySummaryResponse,
)
'''
if quality_import not in router:
    router = router.replace(import_anchor, import_anchor + quality_import)

provider_anchor = "def get_agent_governance_repository() -> AgentGovernanceRepository:\n    return AgentGovernanceRepository()\n\n\n"
provider = '''def get_quality_observability_repository() -> QualityObservabilityRepository:
    return QualityObservabilityRepository()


'''
if provider not in router:
    router = router.replace(provider_anchor, provider_anchor + provider)

endpoint_anchor = '@router.get("/dashboard", response_model=AgentOpsDashboardResponse)\n'
endpoints = '''@router.get("/quality/summary", response_model=QualitySummaryResponse)
def get_quality_summary(
    repository: QualityObservabilityRepository = Depends(
        get_quality_observability_repository
    ),
) -> QualitySummaryResponse:
    try:
        return repository.fetch_summary()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener el resumen de calidad runtime: {exc}",
        ) from exc


@router.get("/quality/executions", response_model=QualityExecutionListResponse)
def get_quality_executions(
    limit: int = Query(default=50, ge=1, le=200),
    repository: QualityObservabilityRepository = Depends(
        get_quality_observability_repository
    ),
) -> QualityExecutionListResponse:
    try:
        return repository.list_latest(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener evidencia de calidad runtime: {exc}",
        ) from exc


@router.get(
    "/quality/executions/{execution_id}",
    response_model=QualityExecutionEvidence,
)
def get_quality_execution(
    execution_id: str,
    repository: QualityObservabilityRepository = Depends(
        get_quality_observability_repository
    ),
) -> QualityExecutionEvidence:
    try:
        return repository.get_latest(execution_id)
    except QualityEvidenceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible obtener la evidencia de calidad runtime: {exc}",
        ) from exc


'''
if endpoints not in router:
    router = router.replace(endpoint_anchor, endpoints + endpoint_anchor)
router_path.write_text(router, encoding="utf-8")

test_path = TESTS / "test_quality_observability_api.py"
test_path.write_text('''from datetime import datetime, timezone

from google.api_core.exceptions import NotFound

from modules.agentops.quality_observability import QualityObservabilityRepository


class MissingTableClient:
    def get_table(self, table_id):
        raise NotFound("missing")


class FakeRow(dict):
    def items(self):
        return super().items()


class FakeQueryJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeClient:
    def __init__(self, rows):
        self.rows = rows

    def get_table(self, table_id):
        return object()

    def query(self, sql, job_config=None):
        return FakeQueryJob(self.rows)


def test_summary_is_honest_when_quality_table_does_not_exist():
    repo = QualityObservabilityRepository(
        client=MissingTableClient(), project_id="p", dataset="d"
    )
    summary = repo.fetch_summary()
    assert summary.source_available is False
    assert summary.evidence_count == 0
    assert summary.latest_quality_score is None


def test_quality_evidence_detail_parses_governed_rule_json():
    now = datetime.now(timezone.utc)
    row = FakeRow(
        execution_id="exec_1",
        spec_id="spec_1",
        mapping_version=2,
        recorded_at=now,
        gate_status="PASSED",
        runtime_decision="QUARANTINE",
        quality_score=97.5,
        total_rows=100,
        failed_rows=2,
        warning_rows=1,
        observed_failure_rows=0,
        quarantined_rows=2,
        continued_quarantined_rows=2,
        quarantine_events=2,
        table_level_blocking_failures=0,
        table_level_warnings=0,
        quarantine_table="p.silver.t__quarantine",
        rule_results_json='[{"rule_name":"email_regex","status":"FAIL"}]',
        configured_rules_json='[{"rule_name":"email_regex","runtime_action":"QUARANTINE"}]',
    )
    repo = QualityObservabilityRepository(
        client=FakeClient([row]), project_id="p", dataset="d"
    )
    detail = repo.get_latest("exec_1")
    assert detail.runtime_decision == "QUARANTINE"
    assert detail.quality_score == 97.5
    assert detail.rule_results[0]["rule_name"] == "email_regex"
    assert detail.configured_rules[0]["runtime_action"] == "QUARANTINE"


def test_router_exposes_quality_observability_contract():
    source = open("modules/agentops/router.py", encoding="utf-8").read()
    assert '"/quality/summary"' in source
    assert '"/quality/executions"' in source
    assert '"/quality/executions/{execution_id}"' in source
''', encoding="utf-8")

print("PASS: Quality Observability API aplicado.")
print("Fuente runtime: silver_execution_quality; sin parsing de logs para Gobierno.")
print("Endpoints: summary, executions y detail; sin mocks, sin Actions, sin orchestrator.")
