from datetime import datetime, timezone

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
