from __future__ import annotations

import json
from datetime import datetime, timezone

from modules.silver_execution.execution_models import ExecutionRecord, ExecutionStatus
from modules.silver_execution.result_validator import BigQueryResultValidator


class FakeRow(dict):
    pass


class FakeResult:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = FakeRow(row)

    def result(self):
        return iter([self.row])


class FakeBigQueryClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def query(self, query: str) -> FakeResult:
        self.queries.append(query)
        normalized = " ".join(query.split())
        if "duplicate_count" in normalized:
            return FakeResult({"duplicate_count": 0})
        if "diff_count" in normalized:
            return FakeResult({"diff_count": 0})
        return FakeResult(
            {
                "row_count": 13,
                "distinct_business_key_count": 13,
                "metric_sum": 21390,
            }
        )


class FakePackageResolver:
    def resolve_artifact_text(self, **_: object) -> str:
        return json.dumps(
            {
                "source_project": "proyectopersonal-480420",
                "source_dataset": "seguros_bronce",
                "source_table": "cat_producto",
                "target_project": "proyectopersonal-480420",
                "target_dataset": "seguros_silver",
                "target_table": "cat_producto",
                "load_strategy": {
                    "type": "MERGE",
                    "business_keys": ["producto_id"],
                    "watermark_column": "bronze_fecha_ingesta",
                },
                "columns": [
                    {"name": "producto_id", "data_type": "STRING"},
                    {"name": "prima_base", "data_type": "NUMERIC"},
                    {"name": "bronze_fecha_ingesta", "data_type": "TIMESTAMP"},
                ],
            }
        )


def test_bigquery_result_validator_returns_conformant_response() -> None:
    client = FakeBigQueryClient()
    validator = BigQueryResultValidator(
        package_resolver=FakePackageResolver(),
        client=client,
    )
    execution = ExecutionRecord(
        execution_id="exec_test",
        spec_id="spec_test",
        mapping_version=1,
        package_version=1,
        artifact_package_uri="gs://bucket/package.zip",
        status=ExecutionStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
        dataproc_batch_id="silver-exec-test",
    )

    result = validator.validate(execution)

    assert result.conformant is True
    assert result.status == "CONFORME"
    assert result.source_table == "proyectopersonal-480420.seguros_bronce.cat_producto"
    assert result.target_table == "proyectopersonal-480420.seguros_silver.cat_producto"
    assert result.business_keys == ["producto_id"]
    assert result.metric_column == "prima_base"
    assert result.row_count == 13
    assert result.distinct_business_key_count == 13
    assert result.duplicate_count == 0
    assert result.diff_count == 0
    assert result.metric_sum == 21390
    assert all(check.status == "PASS" for check in result.checks)
    assert len(client.queries) == 3
