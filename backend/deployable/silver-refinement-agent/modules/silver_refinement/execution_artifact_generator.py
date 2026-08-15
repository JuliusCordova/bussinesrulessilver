from __future__ import annotations

import json
import re

from modules.silver_intelligent_mapping.compiler import (
    compile_incremental_filter,
    compile_pyspark_expression,
    compile_write_mode,
)
from modules.silver_intelligent_mapping.models import (
    IntelligentMappingColumn,
    LoadStrategyType,
)

from .artifact_models import GenerateArtifactPackageRequest


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")
_SUPPORTED_QUALITY_RULE_TYPES = {
    "NOT_NULL",
    "UNIQUE",
    "ALLOWED_VALUES",
    "VALUE_RANGE",
    "REGEX_MATCH",
    "COLUMN_COMPARISON",
    "FRESHNESS_MAX_HOURS",
    "ROW_COUNT_MIN",
}
_SUPPORTED_COMPARISON_OPERATORS = {
    "EQUAL",
    "NOT_EQUAL",
    "GREATER_THAN",
    "GREATER_THAN_OR_EQUAL",
    "LESS_THAN",
    "LESS_THAN_OR_EQUAL",
}


class ExecutionArtifactGeneratorService:
    """Generates deterministic executable artifacts for Bronze-to-Silver refinement."""

    template_version = "1.4.0"

    @staticmethod
    def _identifier(value: str, label: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError(f"{label} contiene caracteres no permitidos: {value}")
        return value

    def _intelligent_columns(
        self,
        request: GenerateArtifactPackageRequest,
    ) -> list[IntelligentMappingColumn]:
        columns: list[IntelligentMappingColumn] = []
        for column in request.columns:
            columns.append(
                IntelligentMappingColumn(
                    source_column=column.source_column,
                    target_column=column.name,
                    target_type=column.data_type,
                    nullable=column.nullable,
                    include=column.include,
                    transformation=column.normalized_transformation(),
                    confidence=column.confidence,
                    reason=column.recommendation_reason,
                    risk=column.recommendation_risk,
                    requires_approval=column.requires_approval,
                )
            )
        return columns

    @classmethod
    def _normalize_quality_rule(
        cls,
        rule: dict,
        index: int,
    ) -> dict:
        if hasattr(rule, "model_dump"):
            rule = rule.model_dump(mode="json")
        if not isinstance(rule, dict):
            raise ValueError(f"Quality rule {index} debe ser un objeto")

        data = dict(rule)
        parameters = dict(data.get("rule_parameters") or {})
        rule_type = str(data.get("rule_type") or "").strip().upper()

        # Backward compatibility with the first generated-script contract.
        if not rule_type:
            legacy_check = str(data.get("check") or "").strip().upper()
            legacy_column = data.get("column")
            legacy_value = data.get("value")
            if legacy_check == "NOT_NULL":
                rule_type = "NOT_NULL"
            elif legacy_check == "GREATER_THAN_OR_EQUAL":
                rule_type = "VALUE_RANGE"
                parameters["min_value"] = legacy_value
                parameters["min_inclusive"] = True
            elif legacy_check == "GREATER_THAN":
                rule_type = "VALUE_RANGE"
                parameters["min_value"] = legacy_value
                parameters["min_inclusive"] = False
            elif legacy_check == "EQUAL":
                rule_type = "ALLOWED_VALUES"
                parameters["allowed_values"] = [legacy_value]

            if legacy_column and not data.get("column_name"):
                data["column_name"] = legacy_column

        # Very early packages used only {"rule": "column_not_null"}.
        if not rule_type:
            legacy_name = str(data.get("rule") or "").strip()
            if legacy_name.lower().endswith("_not_null"):
                rule_type = "NOT_NULL"
                data.setdefault("column_name", legacy_name[:-9])

        if rule_type not in _SUPPORTED_QUALITY_RULE_TYPES:
            raise ValueError(
                f"Quality rule {index} usa tipo no soportado: {rule_type or '<empty>'}"
            )

        column_name = data.get("column_name")
        comparison_column = data.get("comparison_column")
        if rule_type != "ROW_COUNT_MIN" and not column_name:
            raise ValueError(
                f"Quality rule {index} ({rule_type}) requiere column_name"
            )

        if rule_type == "ALLOWED_VALUES" and not parameters.get("allowed_values"):
            raise ValueError("ALLOWED_VALUES requiere allowed_values")
        if rule_type == "VALUE_RANGE" and not any(
            key in parameters for key in ("min_value", "max_value")
        ):
            raise ValueError("VALUE_RANGE requiere min_value o max_value")
        if rule_type == "REGEX_MATCH" and not parameters.get("regex"):
            raise ValueError("REGEX_MATCH requiere regex")
        if rule_type == "COLUMN_COMPARISON":
            if not comparison_column:
                raise ValueError("COLUMN_COMPARISON requiere comparison_column")
            operator = str(parameters.get("operator") or "EQUAL").upper()
            if operator not in _SUPPORTED_COMPARISON_OPERATORS:
                raise ValueError(
                    f"COLUMN_COMPARISON usa operador no soportado: {operator}"
                )
            parameters["operator"] = operator
        if rule_type == "FRESHNESS_MAX_HOURS" and parameters.get("max_hours") is None:
            raise ValueError("FRESHNESS_MAX_HOURS requiere max_hours")
        if rule_type == "ROW_COUNT_MIN" and parameters.get("min_rows") is None:
            raise ValueError("ROW_COUNT_MIN requiere min_rows")

        warning_threshold = float(data.get("warning_threshold", 1.0))
        critical_threshold = float(data.get("critical_threshold", 5.0))
        if warning_threshold < 0:
            raise ValueError("warning_threshold no puede ser negativo")
        if critical_threshold < warning_threshold:
            raise ValueError(
                "critical_threshold debe ser mayor o igual a warning_threshold"
            )

        default_name = f"{rule_type.lower()}_{column_name or 'table'}"
        return {
            "rule_name": str(
                data.get("rule_name")
                or data.get("name")
                or data.get("rule")
                or default_name
            ),
            "rule_dimension": str(
                data.get("rule_dimension") or "VALIDITY"
            ).upper(),
            "rule_type": rule_type,
            "column_name": column_name,
            "comparison_column": comparison_column,
            "rule_parameters": parameters,
            "warning_threshold": warning_threshold,
            "critical_threshold": critical_threshold,
            "severity_level": str(
                data.get("severity_level")
                or data.get("severity")
                or "MEDIUM"
            ).upper(),
            "active_flag": bool(data.get("active_flag", True)),
        }

    @classmethod
    def normalize_quality_rules(cls, rules: list[dict]) -> list[dict]:
        return [
            cls._normalize_quality_rule(rule, index)
            for index, rule in enumerate(rules or [], start=1)
        ]

    def build_pyspark_script(
        self,
        spec_id: str,
        request: GenerateArtifactPackageRequest,
    ) -> str:
        source_table = ".".join(
            [
                self._identifier(request.source_project, "source_project"),
                self._identifier(request.source_dataset, "source_dataset"),
                self._identifier(request.source_table, "source_table"),
            ]
        )
        target_table = ".".join(
            [
                self._identifier(request.target_project, "target_project"),
                self._identifier(request.target_dataset, "target_dataset"),
                self._identifier(request.target_table, "target_table"),
            ]
        )

        intelligent_columns = self._intelligent_columns(request)
        included_columns = [column for column in intelligent_columns if column.include]
        expressions = ",\n        ".join(
            compile_pyspark_expression(column) for column in included_columns
        )
        if not expressions:
            raise ValueError("El mapping no contiene columnas ejecutables")

        required_columns = [
            column.target_column for column in included_columns if not column.nullable
        ]
        strategy = request.load_strategy
        write_mode = (
            "overwrite"
            if strategy.type in {LoadStrategyType.MERGE, LoadStrategyType.CDC}
            else compile_write_mode(strategy)
        )
        incremental_filter = compile_incremental_filter(strategy)
        quality_rules = self.normalize_quality_rules(request.quality_rules)

        incremental_block = ""
        if incremental_filter:
            incremental_block = f'''\n    runtime_watermark = os.getenv("RUNTIME_WATERMARK")\n    if not runtime_watermark:\n        raise ValueError("INCREMENTAL_WATERMARK requiere RUNTIME_WATERMARK")\n    frame = frame.filter({incremental_filter})\n'''

        template = '''"""Generated Bronze-to-Silver pipeline."""

import json
import logging
import os
from datetime import datetime, timezone

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

SPEC_ID = __SPEC_ID__
MAPPING_VERSION = __MAPPING_VERSION__
SOURCE_TABLE = __SOURCE_TABLE__
TARGET_TABLE = __TARGET_TABLE__
QUARANTINE_TABLE = TARGET_TABLE + "__quarantine"
MATERIALIZATION_PROJECT = __MATERIALIZATION_PROJECT__
MATERIALIZATION_DATASET = __MATERIALIZATION_DATASET__
LOAD_STRATEGY = json.loads(__LOAD_STRATEGY_JSON__)
PHYSICAL_DESIGN = json.loads(__PHYSICAL_DESIGN_JSON__)
REQUIRED_COLUMNS = __REQUIRED_COLUMNS__
QUALITY_RULES = json.loads(__QUALITY_RULES_JSON__)
EXECUTION_ID = os.getenv("EXECUTION_ID", "unknown")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("silver-refinement")


def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName(f"silver-refinement-{SPEC_ID}")
        .getOrCreate()
    )


def read_bronze(spark: SparkSession):
    source_query = f"SELECT * FROM `{SOURCE_TABLE}`"
    frame = (
        spark.read.format("bigquery")
        .option("query", source_query)
        .option("viewsEnabled", "true")
        .option("materializationProject", MATERIALIZATION_PROJECT)
        .option("materializationDataset", MATERIALIZATION_DATASET)
        .option("optimizedEmptyProjection", "false")
        .load()
    )
__INCREMENTAL_BLOCK__    return frame


def transform(df):
    return df.select(
        __EXPRESSIONS__
    )


def _ensure_column(df, column_name: str, rule_name: str):
    if column_name not in df.columns:
        raise ValueError(
            f"Quality rule {rule_name} referencia columna inexistente: {column_name}"
        )


def _classify_rule(
    failed_rows: int,
    failed_percentage: float,
    warning_threshold: float,
    critical_threshold: float,
) -> str:
    if failed_rows <= 0:
        return "PASS"
    if failed_percentage >= critical_threshold:
        return "FAIL"
    if failed_percentage >= warning_threshold:
        return "WARN"
    return "PASS"


def _decorate_failure_frame(df, source_columns: list[str], rule: dict, status: str):
    row_hash = F.sha2(
        F.concat_ws(
            "||",
            *[
                F.coalesce(F.col(column).cast("string"), F.lit("<NULL>"))
                for column in source_columns
            ],
        ),
        256,
    )
    return (
        df.withColumn("_dq_row_hash", row_hash)
        .withColumn("_dq_execution_id", F.lit(EXECUTION_ID))
        .withColumn("_dq_spec_id", F.lit(SPEC_ID))
        .withColumn("_dq_rule_name", F.lit(rule["rule_name"]))
        .withColumn("_dq_rule_type", F.lit(rule["rule_type"]))
        .withColumn("_dq_rule_status", F.lit(status))
        .withColumn("_dq_severity", F.lit(rule.get("severity_level") or "MEDIUM"))
        .withColumn(
            "_dq_rule_parameters",
            F.lit(json.dumps(rule.get("rule_parameters") or {}, ensure_ascii=False)),
        )
        .withColumn("_dq_quarantined_at", F.current_timestamp())
    )


def _row_failure_frame(df, rule: dict):
    rule_type = rule["rule_type"]
    column_name = rule.get("column_name")
    parameters = rule.get("rule_parameters") or {}

    if rule_type in {"ROW_COUNT_MIN", "FRESHNESS_MAX_HOURS"}:
        return None

    _ensure_column(df, column_name, rule["rule_name"])
    column = F.col(column_name)

    if rule_type == "NOT_NULL":
        return df.filter(column.isNull())

    if rule_type == "UNIQUE":
        duplicate_window = Window.partitionBy(column)
        return (
            df.withColumn(
                "__dq_duplicate_count",
                F.count(F.lit(1)).over(duplicate_window),
            )
            .filter(column.isNotNull() & (F.col("__dq_duplicate_count") > 1))
            .drop("__dq_duplicate_count")
        )

    if rule_type == "ALLOWED_VALUES":
        allowed_values = parameters.get("allowed_values") or []
        return df.filter(column.isNotNull() & (~column.isin(allowed_values)))

    if rule_type == "VALUE_RANGE":
        failure = F.lit(False)
        if "min_value" in parameters:
            if parameters.get("min_inclusive", True):
                failure = failure | (column < F.lit(parameters["min_value"]))
            else:
                failure = failure | (column <= F.lit(parameters["min_value"]))
        if "max_value" in parameters:
            if parameters.get("max_inclusive", True):
                failure = failure | (column > F.lit(parameters["max_value"]))
            else:
                failure = failure | (column >= F.lit(parameters["max_value"]))
        return df.filter(column.isNotNull() & failure)

    if rule_type == "REGEX_MATCH":
        return df.filter(
            column.isNotNull() & (~column.cast("string").rlike(parameters["regex"]))
        )

    if rule_type == "COLUMN_COMPARISON":
        comparison_column = rule.get("comparison_column")
        _ensure_column(df, comparison_column, rule["rule_name"])
        other = F.col(comparison_column)
        operator = str(parameters.get("operator") or "EQUAL").upper()
        comparable = column.isNotNull() & other.isNotNull()
        if operator == "EQUAL":
            failure = column != other
        elif operator == "NOT_EQUAL":
            failure = column == other
        elif operator == "GREATER_THAN":
            failure = column <= other
        elif operator == "GREATER_THAN_OR_EQUAL":
            failure = column < other
        elif operator == "LESS_THAN":
            failure = column >= other
        elif operator == "LESS_THAN_OR_EQUAL":
            failure = column > other
        else:
            raise ValueError(f"Operador no soportado: {operator}")
        return df.filter(comparable & failure)

    raise ValueError(f"Quality rule runtime no soportada: {rule_type}")


def _table_rule_result(df, rule: dict, total_rows: int):
    rule_type = rule["rule_type"]
    parameters = rule.get("rule_parameters") or {}

    if rule_type == "ROW_COUNT_MIN":
        min_rows = int(parameters["min_rows"])
        passed = total_rows >= min_rows
        return {
            "failed_rows": 0 if passed else max(min_rows - total_rows, 1),
            "failed_percentage": 0.0 if passed else 100.0,
            "score": 100.0 if passed else 0.0,
            "status": "PASS" if passed else "FAIL",
            "detail": {"min_rows": min_rows, "actual_rows": total_rows},
        }

    if rule_type == "FRESHNESS_MAX_HOURS":
        column_name = rule["column_name"]
        _ensure_column(df, column_name, rule["rule_name"])
        freshest_row = df.agg(F.max(F.col(column_name)).alias("freshest")).first()
        freshest = freshest_row["freshest"] if freshest_row else None
        max_hours = float(parameters["max_hours"])
        age_hours = None
        if freshest is not None:
            if freshest.tzinfo is None or freshest.utcoffset() is None:
                freshest = freshest.replace(tzinfo=timezone.utc)
            else:
                freshest = freshest.astimezone(timezone.utc)
            age_hours = max(
                (datetime.now(timezone.utc) - freshest).total_seconds() / 3600.0,
                0.0,
            )
        passed = age_hours is not None and age_hours <= max_hours
        return {
            "failed_rows": 0 if passed else total_rows,
            "failed_percentage": 0.0 if passed else 100.0,
            "score": 100.0 if passed else 0.0,
            "status": "PASS" if passed else "FAIL",
            "detail": {
                "max_hours": max_hours,
                "age_hours": round(age_hours, 4) if age_hours is not None else None,
            },
        }

    return None


def _combine_failure_frames(frames):
    if not frames:
        return None
    combined = frames[0]
    for frame in frames[1:]:
        combined = combined.unionByName(frame, allowMissingColumns=True)
    return combined


def validate_quality(df):
    total_rows = df.count()
    source_columns = list(df.columns)
    rule_results = []
    blocking_failure_frames = []
    warning_failures = 0
    table_level_failures = 0
    scores = []

    for column_name in REQUIRED_COLUMNS:
        _ensure_column(df, column_name, f"required_{column_name}")
        failed_df = df.filter(F.col(column_name).isNull())
        failed_rows = failed_df.count()
        failed_percentage = (
            round((failed_rows / total_rows) * 100.0, 4)
            if total_rows
            else 0.0
        )
        status = "FAIL" if failed_rows else "PASS"
        score = round(max(100.0 - failed_percentage, 0.0), 4)
        scores.append(score)
        rule = {
            "rule_name": f"required_{column_name}",
            "rule_type": "NOT_NULL",
            "column_name": column_name,
            "severity_level": "CRITICAL",
            "rule_parameters": {},
        }
        rule_results.append(
            {
                **rule,
                "failed_rows": failed_rows,
                "failed_percentage": failed_percentage,
                "score": score,
                "status": status,
                "implicit": True,
            }
        )
        if failed_rows:
            blocking_failure_frames.append(
                _decorate_failure_frame(failed_df, source_columns, rule, status)
            )

    for rule in QUALITY_RULES:
        if not rule.get("active_flag", True):
            continue

        table_result = _table_rule_result(df, rule, total_rows)
        if table_result is not None:
            result = {**rule, **table_result, "implicit": False}
            rule_results.append(result)
            scores.append(float(table_result["score"]))
            if table_result["status"] == "FAIL":
                table_level_failures += 1
            continue

        failed_df = _row_failure_frame(df, rule)
        failed_rows = failed_df.count()
        failed_percentage = (
            round((failed_rows / total_rows) * 100.0, 4)
            if total_rows
            else 0.0
        )
        status = _classify_rule(
            failed_rows,
            failed_percentage,
            float(rule.get("warning_threshold") or 0.0),
            float(rule.get("critical_threshold") or 0.0),
        )
        score = round(max(100.0 - failed_percentage, 0.0), 4)
        scores.append(score)
        rule_results.append(
            {
                **rule,
                "failed_rows": failed_rows,
                "failed_percentage": failed_percentage,
                "score": score,
                "status": status,
                "implicit": False,
            }
        )
        if status == "FAIL" and failed_rows:
            blocking_failure_frames.append(
                _decorate_failure_frame(failed_df, source_columns, rule, status)
            )
        elif status == "WARN":
            warning_failures += failed_rows

    quarantine_df = _combine_failure_frames(blocking_failure_frames)
    quarantined_rows = 0
    quarantine_events = 0
    if quarantine_df is not None:
        quarantine_events = quarantine_df.count()
        quarantined_rows = quarantine_df.select("_dq_row_hash").distinct().count()

    has_blocking_failure = bool(blocking_failure_frames) or table_level_failures > 0
    has_warning = any(item.get("status") == "WARN" for item in rule_results)
    outcome = "FAIL" if has_blocking_failure else ("WARN" if has_warning else "PASS")
    gate_status = "FAILED" if has_blocking_failure else "PASSED"
    quality_score = round(sum(scores) / len(scores), 4) if scores else 100.0

    return (
        {
            "status": gate_status,
            "outcome": outcome,
            "quality_score": quality_score,
            "total_rows": total_rows,
            "failed_rows": quarantined_rows,
            "warning_rows": warning_failures,
            "table_level_failures": table_level_failures,
            "quarantined_rows": quarantined_rows,
            "quarantine_events": quarantine_events,
            "quarantine_table": QUARANTINE_TABLE,
            "rule_results": rule_results,
            "configured_rules": QUALITY_RULES,
        },
        quarantine_df,
    )


def calculate_next_watermark(df):
    watermark_column = LOAD_STRATEGY.get("watermark_column")
    if not watermark_column:
        return None

    row = df.agg(
        F.max(F.col(watermark_column)).alias("next_watermark")
    ).first()
    value = row["next_watermark"] if row else None

    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def read_existing_target(spark: SparkSession, expected_columns: list[str]):
    try:
        existing = (
            spark.read.format("bigquery")
            .option("table", TARGET_TABLE)
            .option("viewsEnabled", "true")
            .option("materializationProject", MATERIALIZATION_PROJECT)
            .option("materializationDataset", MATERIALIZATION_DATASET)
            .option("optimizedEmptyProjection", "false")
            .load()
        )
        missing_columns = [column for column in expected_columns if column not in existing.columns]
        if missing_columns:
            raise ValueError(
                "Target existente no contiene columnas requeridas: "
                + ", ".join(missing_columns)
            )
        return existing.select(*expected_columns)
    except Exception as exc:
        message = str(exc)
        if "Not found" in message or "notFound" in message or "404" in message:
            logger.warning("Target no existe; se creara con la primera carga MERGE")
            return None
        raise


def deduplicate_for_merge(df):
    business_keys = LOAD_STRATEGY.get("business_keys") or []
    if not business_keys:
        raise ValueError("MERGE requiere business_keys")

    for column in business_keys:
        if column not in df.columns:
            raise ValueError(f"MERGE business_key inexistente en dataframe: {column}")

    order_columns = []
    watermark_column = LOAD_STRATEGY.get("watermark_column")
    if watermark_column:
        if watermark_column not in df.columns:
            raise ValueError(f"MERGE watermark_column inexistente en dataframe: {watermark_column}")
        order_columns.append(F.col(watermark_column).desc_nulls_last())

    tie_breaker_column = LOAD_STRATEGY.get("tie_breaker_column")
    if tie_breaker_column:
        if tie_breaker_column not in df.columns:
            raise ValueError(f"MERGE tie_breaker_column inexistente en dataframe: {tie_breaker_column}")
        order_columns.append(F.col(tie_breaker_column).desc_nulls_last())

    if not order_columns:
        order_columns = [F.monotonically_increasing_id().desc()]

    window = Window.partitionBy(*[F.col(column) for column in business_keys]).orderBy(*order_columns)
    return (
        df.withColumn("__silver_merge_rank", F.row_number().over(window))
        .filter(F.col("__silver_merge_rank") == 1)
        .drop("__silver_merge_rank")
    )


def write_silver(spark: SparkSession, df):
    if LOAD_STRATEGY.get("type") in {"MERGE", "CDC"}:
        expected_columns = list(df.columns)
        existing_df = read_existing_target(spark, expected_columns)
        merged_df = df if existing_df is None else existing_df.unionByName(df, allowMissingColumns=True)
        output_df = deduplicate_for_merge(merged_df)
    else:
        output_df = df

    (
        output_df.write.format("bigquery")
        .option("table", TARGET_TABLE)
        .option("writeMethod", "direct")
        .mode(__WRITE_MODE__)
        .save()
    )


def write_quarantine(df):
    (
        df.write.format("bigquery")
        .option("table", QUARANTINE_TABLE)
        .option("writeMethod", "direct")
        .mode("append")
        .save()
    )


def main() -> dict:
    started_at = datetime.now(timezone.utc)
    spark = build_spark()
    try:
        bronze_df = read_bronze(spark)
        rows_read = bronze_df.count()
        silver_df = transform(bronze_df)
        quality, quarantine_df = validate_quality(silver_df)
        next_watermark = calculate_next_watermark(bronze_df)

        if quality["status"] != "PASSED":
            if quarantine_df is not None and quality["quarantine_events"] > 0:
                write_quarantine(quarantine_df)
            result = {
                "spec_id": SPEC_ID,
                "execution_id": EXECUTION_ID,
                "mapping_version": MAPPING_VERSION,
                "source_table": SOURCE_TABLE,
                "target_table": TARGET_TABLE,
                "load_strategy": LOAD_STRATEGY,
                "physical_design": PHYSICAL_DESIGN,
                "rows_read": rows_read,
                "rows_written": 0,
                "next_watermark": next_watermark,
                "quality": quality,
                "status": "FAILED",
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(json.dumps(result, ensure_ascii=False))
            raise ValueError(
                "Quality gate failed; Silver write blocked and failing rows quarantined"
            )

        write_silver(spark, silver_df)
        rows_written = silver_df.count()
        result = {
            "spec_id": SPEC_ID,
            "execution_id": EXECUTION_ID,
            "mapping_version": MAPPING_VERSION,
            "source_table": SOURCE_TABLE,
            "target_table": TARGET_TABLE,
            "load_strategy": LOAD_STRATEGY,
            "physical_design": PHYSICAL_DESIGN,
            "rows_read": rows_read,
            "rows_written": rows_written,
            "next_watermark": next_watermark,
            "quality": quality,
            "status": "SUCCESS",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(json.dumps(result, ensure_ascii=False))
        return result
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
'''

        replacements = {
            "__SPEC_ID__": repr(spec_id),
            "__MAPPING_VERSION__": str(request.mapping_version),
            "__SOURCE_TABLE__": repr(source_table),
            "__TARGET_TABLE__": repr(target_table),
            "__MATERIALIZATION_PROJECT__": repr(request.target_project),
            "__MATERIALIZATION_DATASET__": repr(request.target_dataset),
            "__LOAD_STRATEGY_JSON__": repr(
                json.dumps(strategy.model_dump(mode="json"), ensure_ascii=False)
            ),
            "__PHYSICAL_DESIGN_JSON__": repr(
                json.dumps(
                    request.physical_design.model_dump(mode="json"),
                    ensure_ascii=False,
                )
            ),
            "__REQUIRED_COLUMNS__": repr(required_columns),
            "__QUALITY_RULES_JSON__": repr(
                json.dumps(quality_rules, ensure_ascii=False)
            ),
            "__INCREMENTAL_BLOCK__": incremental_block,
            "__EXPRESSIONS__": expressions,
            "__WRITE_MODE__": repr(write_mode),
        }
        for token, value in replacements.items():
            template = template.replace(token, value)
        return template

    def build_notebook(
        self,
        spec_id: str,
        request: GenerateArtifactPackageRequest,
        pyspark_script: str,
    ) -> str:
        notebook = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        f"# Silver Refinement Pipeline: {spec_id}\n",
                        "Notebook generado automáticamente desde el mapping aprobado.\n",
                        f"- Mapping version: {request.mapping_version}\n",
                        f"- Source: `{request.source_project}.{request.source_dataset}.{request.source_table}`\n",
                        f"- Target: `{request.target_project}.{request.target_dataset}.{request.target_table}`\n",
                        f"- Load strategy: `{request.load_strategy.type.value}`\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "## Flujo\n",
                        "1. Crear sesión Spark.\n",
                        "2. Leer Bronze desde BigQuery.\n",
                        "3. Aplicar filtro incremental cuando corresponda.\n",
                        "4. Aplicar mapping y transformaciones tipadas.\n",
                        "5. Ejecutar reglas gobernadas de calidad.\n",
                        "6. Si falla el gate, escribir evidencia en quarantine y bloquear Silver.\n",
                        "7. Si pasa el gate, escribir Silver.\n",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [line + "\n" for line in pyspark_script.splitlines()],
                },
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "PySpark",
                    "language": "python",
                    "name": "pyspark",
                },
                "language_info": {"name": "python", "version": "3.11"},
                "silver_refinement": {
                    "spec_id": spec_id,
                    "mapping_version": request.mapping_version,
                    "template_version": self.template_version,
                },
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        return json.dumps(notebook, ensure_ascii=False, indent=2)
