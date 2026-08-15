from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from google.cloud import bigquery

from modules.silver_refinement.artifact_models import ArtifactType

from .execution_models import (
    BigQueryValidationCheck,
    BigQueryValidationResponse,
    ExecutionRecord,
)
from .package_resolver import PackageResolver

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_\-]+$")
_NUMERIC_TYPES = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC"}
_TRACE_COLUMNS = {
    "bronze_registro_id",
    "bronze_carga_id",
    "bronze_fecha_ingesta",
    "bronze_archivo_origen",
    "bronze_hash_origen",
    "bronze_estado_registro",
}


class BigQueryResultValidator:
    def __init__(
        self,
        package_resolver: PackageResolver,
        client: bigquery.Client | None = None,
    ) -> None:
        self.package_resolver = package_resolver
        self.client = client or bigquery.Client()

    def validate(self, execution: ExecutionRecord) -> BigQueryValidationResponse:
        payload = self._load_specification(execution)
        target_table = self._table_fqn(self._target_table(payload), "target")
        source_parts = self._source_table(payload)
        source_table = self._table_fqn(source_parts, "source") if source_parts else None
        business_keys = self._business_keys(payload)
        metric_column = self._metric_column(payload, business_keys)

        target_profile = self._target_profile(target_table, business_keys, metric_column)
        duplicate_count = self._duplicate_count(target_table, business_keys)
        diff_count = (
            self._source_target_diff(source_table, target_table, business_keys, metric_column)
            if source_table
            else None
        )

        checks = self._checks(
            row_count=int(target_profile["row_count"]),
            distinct_business_key_count=self._optional_int(
                target_profile.get("distinct_business_key_count")
            ),
            duplicate_count=duplicate_count,
            diff_count=diff_count,
            business_keys=business_keys,
            source_table=source_table,
        )
        conformant = all(check.status in {"PASS", "SKIPPED"} for check in checks)

        return BigQueryValidationResponse(
            execution=execution,
            status="CONFORME" if conformant else "NO_CONFORME",
            conformant=conformant,
            source_table=source_table,
            target_table=target_table,
            business_keys=business_keys,
            metric_column=metric_column,
            row_count=int(target_profile["row_count"]),
            distinct_business_key_count=self._optional_int(
                target_profile.get("distinct_business_key_count")
            ),
            duplicate_count=duplicate_count,
            diff_count=diff_count,
            metric_sum=self._optional_float(target_profile.get("metric_sum")),
            checks=checks,
        )

    def _load_specification(self, execution: ExecutionRecord) -> dict[str, Any]:
        text = self.package_resolver.resolve_artifact_text(
            spec_id=execution.spec_id,
            expected_package_uri=execution.artifact_package_uri,
            artifact_type=ArtifactType.SPECIFICATION_JSON.value,
        )
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("SPECIFICATION_JSON debe ser un objeto JSON")
        return payload

    def _target_table(self, payload: dict[str, Any]) -> tuple[str, str, str]:
        target = payload.get("target") or {}
        return (
            self._required(
                target.get("project") or target.get("project_id") or payload.get("target_project"),
                "target.project",
            ),
            self._required(
                target.get("dataset") or target.get("dataset_id") or payload.get("target_dataset"),
                "target.dataset",
            ),
            self._required(
                target.get("table") or target.get("table_id") or payload.get("target_table"),
                "target.table",
            ),
        )

    def _source_table(self, payload: dict[str, Any]) -> tuple[str, str, str] | None:
        source = payload.get("source") or {}
        project = source.get("project") or source.get("project_id") or payload.get("source_project")
        dataset = source.get("dataset") or source.get("dataset_id") or payload.get("source_dataset")
        table = source.get("table") or source.get("table_id") or payload.get("source_table")
        if not any([project, dataset, table]):
            return None
        if not all([project, dataset, table]):
            raise ValueError("SPECIFICATION_JSON contiene source incompleto")
        return str(project), str(dataset), str(table)

    def _business_keys(self, payload: dict[str, Any]) -> list[str]:
        strategy = payload.get("load_strategy") or (payload.get("specification") or {}).get("load_strategy") or {}
        keys = strategy.get("business_keys") or payload.get("business_keys") or []
        if isinstance(keys, str):
            keys = [keys]
        if not isinstance(keys, list):
            raise ValueError("business_keys debe ser una lista")
        normalized = [str(key) for key in keys if str(key).strip()]
        for key in normalized:
            self._identifier(key, "business_key")
        return normalized

    def _metric_column(self, payload: dict[str, Any], business_keys: list[str]) -> str | None:
        explicit = payload.get("metric_column") or payload.get("metric")
        if explicit:
            return self._identifier(str(explicit), "metric_column")

        for column in payload.get("columns") or []:
            name = str(column.get("name") or column.get("target_column") or "")
            data_type = str(column.get("data_type") or column.get("type") or column.get("target_type") or "").upper()
            if (
                name
                and name not in business_keys
                and name not in _TRACE_COLUMNS
                and data_type in _NUMERIC_TYPES
            ):
                return self._identifier(name, "metric_column")
        return None

    def _target_profile(
        self,
        target_table: str,
        business_keys: list[str],
        metric_column: str | None,
    ) -> dict[str, Any]:
        distinct_expr = (
            f"COUNT(DISTINCT {self._key_expression(business_keys)})"
            if business_keys
            else "NULL"
        )
        metric_expr = (
            f"SUM(SAFE_CAST(`{metric_column}` AS NUMERIC))"
            if metric_column
            else "NULL"
        )
        query = f"""
        SELECT
          COUNT(1) AS row_count,
          {distinct_expr} AS distinct_business_key_count,
          {metric_expr} AS metric_sum
        FROM `{target_table}`
        """
        return dict(next(iter(self.client.query(query).result())))

    def _duplicate_count(self, target_table: str, business_keys: list[str]) -> int:
        if not business_keys:
            return 0
        group_by = ", ".join(f"`{key}`" for key in business_keys)
        query = f"""
        SELECT COUNT(1) AS duplicate_count
        FROM (
          SELECT {group_by}
          FROM `{target_table}`
          GROUP BY {group_by}
          HAVING COUNT(1) > 1
        )
        """
        row = next(iter(self.client.query(query).result()))
        return int(row["duplicate_count"])

    def _source_target_diff(
        self,
        source_table: str,
        target_table: str,
        business_keys: list[str],
        metric_column: str | None,
    ) -> int:
        if not business_keys:
            return 0
        keys = ", ".join(f"`{key}`" for key in business_keys)
        using_keys = ", ".join(f"`{key}`" for key in business_keys)
        source_metric = (
            f"SUM(SAFE_CAST(`{metric_column}` AS NUMERIC)) AS source_metric"
            if metric_column
            else "CAST(NULL AS NUMERIC) AS source_metric"
        )
        target_metric = (
            f"SUM(SAFE_CAST(`{metric_column}` AS NUMERIC)) AS target_metric"
            if metric_column
            else "CAST(NULL AS NUMERIC) AS target_metric"
        )
        metric_predicate = (
            "OR ABS(IFNULL(source_metric, 0) - IFNULL(target_metric, 0)) > 0.000001"
            if metric_column
            else ""
        )
        query = f"""
        WITH source_profile AS (
          SELECT {keys}, COUNT(1) AS source_rows, {source_metric}
          FROM `{source_table}`
          GROUP BY {keys}
        ),
        target_profile AS (
          SELECT {keys}, COUNT(1) AS target_rows, {target_metric}
          FROM `{target_table}`
          GROUP BY {keys}
        )
        SELECT COUNT(1) AS diff_count
        FROM source_profile
        FULL OUTER JOIN target_profile USING ({using_keys})
        WHERE IFNULL(source_rows, 0) != IFNULL(target_rows, 0)
          {metric_predicate}
        """
        row = next(iter(self.client.query(query).result()))
        return int(row["diff_count"])

    def _checks(
        self,
        *,
        row_count: int,
        distinct_business_key_count: int | None,
        duplicate_count: int,
        diff_count: int | None,
        business_keys: list[str],
        source_table: str | None,
    ) -> list[BigQueryValidationCheck]:
        checks = [
            BigQueryValidationCheck(
                name="target_has_rows",
                status="PASS" if row_count > 0 else "FAIL",
                expected="> 0",
                actual=row_count,
            )
        ]
        if business_keys:
            checks.extend(
                [
                    BigQueryValidationCheck(
                        name="no_duplicate_business_keys",
                        status="PASS" if duplicate_count == 0 else "FAIL",
                        expected=0,
                        actual=duplicate_count,
                    ),
                    BigQueryValidationCheck(
                        name="row_count_equals_distinct_business_keys",
                        status=(
                            "PASS"
                            if distinct_business_key_count == row_count
                            else "FAIL"
                        ),
                        expected=row_count,
                        actual=distinct_business_key_count,
                    ),
                ]
            )
        else:
            checks.append(
                BigQueryValidationCheck(
                    name="business_keys_available",
                    status="SKIPPED",
                    details="La especificación no define business_keys.",
                )
            )

        if source_table and business_keys:
            checks.append(
                BigQueryValidationCheck(
                    name="source_target_business_key_diff_empty",
                    status="PASS" if diff_count == 0 else "FAIL",
                    expected=0,
                    actual=diff_count,
                )
            )
        else:
            checks.append(
                BigQueryValidationCheck(
                    name="source_target_business_key_diff_empty",
                    status="SKIPPED",
                    details="No hay source completo o business_keys para reconciliar.",
                )
            )
        return checks

    @staticmethod
    def _required(value: Any, name: str) -> str:
        if value is None or str(value).strip() == "":
            raise ValueError(f"SPECIFICATION_JSON no contiene {name}")
        return str(value)

    def _table_fqn(self, parts: tuple[str, str, str], label: str) -> str:
        return ".".join(self._identifier(part, f"{label}_table") for part in parts)

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        if not _IDENTIFIER.match(value):
            raise ValueError(f"Identificador inválido para {name}: {value}")
        return value

    @staticmethod
    def _key_expression(keys: list[str]) -> str:
        if len(keys) == 1:
            return f"`{keys[0]}`"
        fields = ", ".join(f"`{key}`" for key in keys)
        return f"TO_JSON_STRING(STRUCT({fields}))"

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
