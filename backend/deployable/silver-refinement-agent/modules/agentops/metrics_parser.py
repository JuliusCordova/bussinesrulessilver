from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ExecutionMetricsSnapshot:
    rows_read: int
    rows_written: int
    failed_rows: int
    quality_status: str | None
    quality_outcome: str | None
    quality_score: float | None
    quarantined_rows: int
    quarantine_table: str | None
    quality_rule_results: list[dict[str, Any]]
    pipeline_status: str | None
    started_at: datetime | None
    finished_at: datetime | None
    next_watermark: datetime | None
    raw_result: dict[str, Any]


class StructuredPipelineMetricsParser:
    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    @classmethod
    def _parse_next_watermark(cls, value: Any) -> datetime | None:
        parsed = cls._parse_datetime(value)
        if parsed is None:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _candidate_json(line: str) -> dict[str, Any] | None:
        start = line.find("{")
        if start < 0:
            return None
        try:
            candidate = json.loads(line[start:])
        except json.JSONDecodeError:
            return None
        if not isinstance(candidate, dict):
            return None
        if "spec_id" not in candidate or "status" not in candidate:
            return None
        return candidate

    def parse(self, contents: list[str]) -> ExecutionMetricsSnapshot:
        result: dict[str, Any] | None = None
        for content in contents:
            for line in content.splitlines():
                candidate = self._candidate_json(line)
                if candidate is not None:
                    result = candidate

        if result is None:
            raise ValueError("No se encontró un resultado estructurado del pipeline en los logs")

        quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
        total_rows = int(quality.get("total_rows") or result.get("rows_read") or 0)
        failed_rows = int(quality.get("failed_rows") or 0)
        rows_read = int(result.get("rows_read") or total_rows)
        rows_written = int(
            result.get("rows_written")
            if result.get("rows_written") is not None
            else max(total_rows - failed_rows, 0)
        )
        raw_score = quality.get("quality_score")
        quality_score = float(raw_score) if raw_score is not None else None
        rule_results = quality.get("rule_results")
        if not isinstance(rule_results, list):
            rule_results = []

        return ExecutionMetricsSnapshot(
            rows_read=rows_read,
            rows_written=rows_written,
            failed_rows=failed_rows,
            quality_status=quality.get("status"),
            quality_outcome=quality.get("outcome"),
            quality_score=quality_score,
            quarantined_rows=int(quality.get("quarantined_rows") or 0),
            quarantine_table=quality.get("quarantine_table"),
            quality_rule_results=[
                item for item in rule_results if isinstance(item, dict)
            ],
            pipeline_status=result.get("status"),
            started_at=self._parse_datetime(result.get("started_at")),
            finished_at=self._parse_datetime(result.get("finished_at")),
            next_watermark=self._parse_next_watermark(
                result.get("next_watermark")
            ),
            raw_result=result,
        )
