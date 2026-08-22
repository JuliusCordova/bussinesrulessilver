from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:180]!r}")
    file.write_text(text.replace(old, new, 1))


EXEC = "backend/deployable/silver-refinement-agent/modules/silver_refinement/execution_artifact_generator.py"
PACKAGE = "backend/deployable/silver-refinement-agent/modules/silver_refinement/artifact_package_generator.py"
APP = "src/App.tsx"
TEST = ROOT / "backend/deployable/silver-refinement-agent/tests/test_runtime_quality_gates.py"

replace(
    EXEC,
    '''_SUPPORTED_COMPARISON_OPERATORS = {\n    "EQUAL",\n    "NOT_EQUAL",\n    "GREATER_THAN",\n    "GREATER_THAN_OR_EQUAL",\n    "LESS_THAN",\n    "LESS_THAN_OR_EQUAL",\n}\n''',
    '''_SUPPORTED_COMPARISON_OPERATORS = {\n    "EQUAL",\n    "NOT_EQUAL",\n    "GREATER_THAN",\n    "GREATER_THAN_OR_EQUAL",\n    "LESS_THAN",\n    "LESS_THAN_OR_EQUAL",\n}\n_SUPPORTED_RUNTIME_ACTIONS = {\n    "OBSERVE_ONLY",\n    "WARN",\n    "QUARANTINE",\n    "BLOCK_LOAD",\n}\n''',
)

replace(
    EXEC,
    '''        data = dict(rule)\n        parameters = dict(data.get("rule_parameters") or {})\n        rule_type = str(data.get("rule_type") or "").strip().upper()\n''',
    '''        data = dict(rule)\n        parameters = dict(data.get("parameters") or data.get("rule_parameters") or {})\n        rule_type = str(data.get("rule_type") or "").strip().upper()\n        if rule_type == "REGEX":\n            rule_type = "REGEX_MATCH"\n            if parameters.get("pattern") is not None and parameters.get("regex") is None:\n                parameters["regex"] = parameters["pattern"]\n        if rule_type == "VALUE_RANGE":\n            if parameters.get("min") is not None and parameters.get("min_value") is None:\n                parameters["min_value"] = parameters["min"]\n            if parameters.get("max") is not None and parameters.get("max_value") is None:\n                parameters["max_value"] = parameters["max"]\n\n        governed_columns = data.get("columns")\n        if isinstance(governed_columns, list) and governed_columns:\n            data.setdefault("column_name", governed_columns[0])\n            if len(governed_columns) > 1:\n                data.setdefault("comparison_column", governed_columns[1])\n''',
)

replace(
    EXEC,
    '''        warning_threshold = float(data.get("warning_threshold", 1.0))\n        critical_threshold = float(data.get("critical_threshold", 5.0))\n        if warning_threshold < 0:\n            raise ValueError("warning_threshold no puede ser negativo")\n        if critical_threshold < warning_threshold:\n            raise ValueError(\n                "critical_threshold debe ser mayor o igual a warning_threshold"\n            )\n\n        default_name = f"{rule_type.lower()}_{column_name or 'table'}"\n        return {\n''',
    '''        warning_threshold = float(data.get("warning_threshold", 1.0))\n        critical_threshold = float(data.get("critical_threshold", 5.0))\n        if warning_threshold < 0:\n            raise ValueError("warning_threshold no puede ser negativo")\n        if critical_threshold < warning_threshold:\n            raise ValueError(\n                "critical_threshold debe ser mayor o igual a warning_threshold"\n            )\n\n        status = str(data.get("status") or "").strip().upper()\n        if status and status != "APPROVED":\n            raise ValueError(\n                f"Quality rule {index} no está aprobada para ejecución: {status}"\n            )\n\n        runtime_action = str(data.get("runtime_action") or "BLOCK_LOAD").strip().upper()\n        if runtime_action not in _SUPPORTED_RUNTIME_ACTIONS:\n            raise ValueError(\n                f"Quality rule {index} usa runtime_action no soportado: {runtime_action}"\n            )\n        if rule_type in {"ROW_COUNT_MIN", "FRESHNESS_MAX_HOURS"} and runtime_action == "QUARANTINE":\n            raise ValueError(\n                f"Quality rule {index} usa QUARANTINE en una regla de nivel tabla"\n            )\n\n        default_name = f"{rule_type.lower()}_{column_name or 'table'}"\n        return {\n''',
)

replace(
    EXEC,
    '''            "severity_level": str(\n                data.get("severity_level")\n                or data.get("severity")\n                or "MEDIUM"\n            ).upper(),\n            "active_flag": bool(data.get("active_flag", True)),\n        }\n''',
    '''            "severity_level": str(\n                data.get("severity_level")\n                or data.get("severity")\n                or "MEDIUM"\n            ).upper(),\n            "runtime_action": runtime_action,\n            "rule_id": data.get("rule_id"),\n            "rule_version": data.get("version", 1),\n            "source": data.get("source"),\n            "status": status or None,\n            "evidence": data.get("evidence") or data.get("agent_evidence"),\n            "confidence": data.get("confidence") if data.get("confidence") is not None else data.get("agent_confidence"),\n            "metadata": data.get("metadata") or {},\n            "active_flag": bool(data.get("active_flag", data.get("active", True))),\n        }\n''',
)

replace(
    EXEC,
    '''def _decorate_failure_frame(df, source_columns: list[str], rule: dict, status: str):\n    row_hash = F.sha2(\n        F.concat_ws(\n            "||",\n            *[\n                F.coalesce(F.col(column).cast("string"), F.lit("<NULL>"))\n                for column in source_columns\n            ],\n        ),\n        256,\n    )\n    return (\n        df.withColumn("_dq_row_hash", row_hash)\n''',
    '''def _row_hash_expression(source_columns: list[str]):\n    return F.sha2(\n        F.concat_ws(\n            "||",\n            *[\n                F.coalesce(F.col(column).cast("string"), F.lit("<NULL>"))\n                for column in source_columns\n            ],\n        ),\n        256,\n    )\n\n\ndef _decorate_failure_frame(df, source_columns: list[str], rule: dict, status: str):\n    return (\n        df.withColumn("_dq_row_hash", _row_hash_expression(source_columns))\n''',
)

replace(
    EXEC,
    '''        .withColumn("_dq_rule_status", F.lit(status))\n        .withColumn("_dq_severity", F.lit(rule.get("severity_level") or "MEDIUM"))\n''',
    '''        .withColumn("_dq_rule_status", F.lit(status))\n        .withColumn("_dq_runtime_action", F.lit(rule.get("runtime_action") or "BLOCK_LOAD"))\n        .withColumn("_dq_severity", F.lit(rule.get("severity_level") or "MEDIUM"))\n''',
)

replace(
    EXEC,
    '''def _combine_failure_frames(frames):\n    if not frames:\n        return None\n    combined = frames[0]\n    for frame in frames[1:]:\n        combined = combined.unionByName(frame, allowMissingColumns=True)\n    return combined\n\n\ndef validate_quality(df):\n''',
    '''def _combine_failure_frames(frames):\n    if not frames:\n        return None\n    combined = frames[0]\n    for frame in frames[1:]:\n        combined = combined.unionByName(frame, allowMissingColumns=True)\n    return combined\n\n\ndef _exclude_quarantined_rows(df, quarantine_df, source_columns: list[str]):\n    if quarantine_df is None:\n        return df\n    quarantine_hashes = quarantine_df.select(\n        F.col("_dq_row_hash").alias("__dq_excluded_hash")\n    ).distinct()\n    return (\n        df.withColumn("__dq_candidate_hash", _row_hash_expression(source_columns))\n        .join(\n            quarantine_hashes,\n            F.col("__dq_candidate_hash") == F.col("__dq_excluded_hash"),\n            "left_anti",\n        )\n        .drop("__dq_candidate_hash")\n    )\n\n\ndef validate_quality(df):\n''',
)

start = '''def validate_quality(df):\n    total_rows = df.count()\n    source_columns = list(df.columns)\n    rule_results = []\n    blocking_failure_frames = []\n    warning_failures = 0\n    table_level_failures = 0\n    scores = []\n'''
new_start = '''def validate_quality(df):\n    total_rows = df.count()\n    source_columns = list(df.columns)\n    rule_results = []\n    blocking_failure_frames = []\n    quarantine_failure_frames = []\n    warning_failures = 0\n    observed_failures = 0\n    table_level_blocking_failures = 0\n    table_level_warnings = 0\n    scores = []\n'''
replace(EXEC, start, new_start)

replace(
    EXEC,
    '''        rule = {\n            "rule_name": f"required_{column_name}",\n            "rule_type": "NOT_NULL",\n            "column_name": column_name,\n            "severity_level": "CRITICAL",\n            "rule_parameters": {},\n        }\n''',
    '''        rule = {\n            "rule_name": f"required_{column_name}",\n            "rule_type": "NOT_NULL",\n            "column_name": column_name,\n            "severity_level": "CRITICAL",\n            "runtime_action": "BLOCK_LOAD",\n            "rule_parameters": {},\n        }\n''',
)

replace(
    EXEC,
    '''        table_result = _table_rule_result(df, rule, total_rows)\n        if table_result is not None:\n            result = {**rule, **table_result, "implicit": False}\n            rule_results.append(result)\n            scores.append(float(table_result["score"]))\n            if table_result["status"] == "FAIL":\n                table_level_failures += 1\n            continue\n''',
    '''        table_result = _table_rule_result(df, rule, total_rows)\n        if table_result is not None:\n            action = str(rule.get("runtime_action") or "BLOCK_LOAD").upper()\n            result = {**rule, **table_result, "implicit": False, "enforcement": action}\n            rule_results.append(result)\n            scores.append(float(table_result["score"]))\n            if table_result["status"] == "FAIL":\n                if action == "BLOCK_LOAD":\n                    table_level_blocking_failures += 1\n                elif action == "WARN":\n                    table_level_warnings += 1\n                elif action == "OBSERVE_ONLY":\n                    observed_failures += int(table_result.get("failed_rows") or 0)\n            continue\n''',
)

replace(
    EXEC,
    '''        rule_results.append(\n            {\n                **rule,\n                "failed_rows": failed_rows,\n                "failed_percentage": failed_percentage,\n                "score": score,\n                "status": status,\n                "implicit": False,\n            }\n        )\n        if status == "FAIL" and failed_rows:\n            blocking_failure_frames.append(\n                _decorate_failure_frame(failed_df, source_columns, rule, status)\n            )\n        elif status == "WARN":\n            warning_failures += failed_rows\n\n    quarantine_df = _combine_failure_frames(blocking_failure_frames)\n    quarantined_rows = 0\n    quarantine_events = 0\n    if quarantine_df is not None:\n        quarantine_events = quarantine_df.count()\n        quarantined_rows = quarantine_df.select("_dq_row_hash").distinct().count()\n\n    has_blocking_failure = bool(blocking_failure_frames) or table_level_failures > 0\n    has_warning = any(item.get("status") == "WARN" for item in rule_results)\n    outcome = "FAIL" if has_blocking_failure else ("WARN" if has_warning else "PASS")\n    gate_status = "FAILED" if has_blocking_failure else "PASSED"\n    quality_score = round(sum(scores) / len(scores), 4) if scores else 100.0\n\n    return (\n        {\n            "status": gate_status,\n            "outcome": outcome,\n            "quality_score": quality_score,\n            "total_rows": total_rows,\n            "failed_rows": quarantined_rows,\n            "warning_rows": warning_failures,\n            "table_level_failures": table_level_failures,\n            "quarantined_rows": quarantined_rows,\n            "quarantine_events": quarantine_events,\n            "quarantine_table": QUARANTINE_TABLE,\n            "rule_results": rule_results,\n            "configured_rules": QUALITY_RULES,\n        },\n        quarantine_df,\n    )\n''',
    '''        action = str(rule.get("runtime_action") or "BLOCK_LOAD").upper()\n        rule_results.append(\n            {\n                **rule,\n                "failed_rows": failed_rows,\n                "failed_percentage": failed_percentage,\n                "score": score,\n                "status": status,\n                "implicit": False,\n                "enforcement": action,\n            }\n        )\n        if status == "FAIL" and failed_rows:\n            decorated = _decorate_failure_frame(failed_df, source_columns, rule, status)\n            if action == "BLOCK_LOAD":\n                blocking_failure_frames.append(decorated)\n            elif action == "QUARANTINE":\n                quarantine_failure_frames.append(decorated)\n            elif action == "WARN":\n                warning_failures += failed_rows\n            elif action == "OBSERVE_ONLY":\n                observed_failures += failed_rows\n        elif status == "WARN":\n            warning_failures += failed_rows\n\n    quarantine_only_df = _combine_failure_frames(quarantine_failure_frames)\n    evidence_df = _combine_failure_frames(blocking_failure_frames + quarantine_failure_frames)\n    quarantine_events = evidence_df.count() if evidence_df is not None else 0\n    quarantined_rows = (\n        evidence_df.select("_dq_row_hash").distinct().count()\n        if evidence_df is not None\n        else 0\n    )\n    continued_quarantined_rows = (\n        quarantine_only_df.select("_dq_row_hash").distinct().count()\n        if quarantine_only_df is not None\n        else 0\n    )\n\n    has_blocking_failure = bool(blocking_failure_frames) or table_level_blocking_failures > 0\n    has_quarantine = bool(quarantine_failure_frames)\n    has_warning = warning_failures > 0 or table_level_warnings > 0 or any(\n        item.get("status") == "WARN" for item in rule_results\n    )\n    if has_blocking_failure:\n        outcome = "BLOCK_LOAD"\n    elif has_quarantine:\n        outcome = "QUARANTINE"\n    elif has_warning:\n        outcome = "WARN"\n    elif observed_failures > 0:\n        outcome = "OBSERVE_ONLY"\n    else:\n        outcome = "PASS"\n    gate_status = "FAILED" if has_blocking_failure else "PASSED"\n    quality_score = round(sum(scores) / len(scores), 4) if scores else 100.0\n    silver_output_df = _exclude_quarantined_rows(df, quarantine_only_df, source_columns)\n\n    return (\n        {\n            "status": gate_status,\n            "outcome": outcome,\n            "runtime_decision": outcome,\n            "quality_score": quality_score,\n            "total_rows": total_rows,\n            "failed_rows": quarantined_rows,\n            "warning_rows": warning_failures,\n            "observed_failure_rows": observed_failures,\n            "table_level_blocking_failures": table_level_blocking_failures,\n            "table_level_warnings": table_level_warnings,\n            "quarantined_rows": quarantined_rows,\n            "continued_quarantined_rows": continued_quarantined_rows,\n            "quarantine_events": quarantine_events,\n            "quarantine_table": QUARANTINE_TABLE,\n            "rule_results": rule_results,\n            "configured_rules": QUALITY_RULES,\n        },\n        evidence_df,\n        silver_output_df,\n    )\n''',
)

replace(
    EXEC,
    '''        quality, quarantine_df = validate_quality(silver_df)\n        next_watermark = calculate_next_watermark(bronze_df)\n\n        if quality["status"] != "PASSED":\n''',
    '''        quality, quarantine_df, silver_output_df = validate_quality(silver_df)\n        next_watermark = calculate_next_watermark(bronze_df)\n\n        if quality["status"] != "PASSED":\n''',
)

replace(
    EXEC,
    '''        write_silver(spark, silver_df)\n        rows_written = silver_df.count()\n''',
    '''        if quarantine_df is not None and quality["quarantine_events"] > 0:\n            write_quarantine(quarantine_df)\n\n        write_silver(spark, silver_output_df)\n        rows_written = silver_output_df.count()\n''',
)

replace(
    EXEC,
    '''                "Quality gate failed; Silver write blocked and failing rows quarantined"\n''',
    '''                "Quality gate BLOCK_LOAD; Silver write blocked and failing rows persisted as evidence"\n''',
)

replace(
    EXEC,
    '''    template_version = "1.4.0"\n''',
    '''    template_version = "1.5.0"\n''',
)

replace(
    PACKAGE,
    '''class ArtifactPackageGeneratorService:\n    template_version = "1.2.0"\n''',
    '''class ArtifactPackageGeneratorService:\n    template_version = "1.3.0"\n''',
)

replace(
    PACKAGE,
    '''            "with the Spark BigQuery connector. Governed quality validation runs "\n            "before the target table is written. Blocking failures prevent the "\n            "Silver write and persist failing row evidence in `<target>__quarantine`; "\n            "warnings remain non-blocking and are exposed in the structured result.\\n"\n''',
    '''            "with the Spark BigQuery connector. Governed quality validation runs "\n            "before the target table is written. Runtime actions are enforced exactly: "\n            "OBSERVE_ONLY records evidence, WARN continues, QUARANTINE excludes failing "\n            "rows from Silver and persists them in `<target>__quarantine`, and BLOCK_LOAD "\n            "prevents the Silver write.\\n"\n''',
)

replace(
    APP,
    '''                  qualityReviewed: true,\n                  qualityReviewDecision: 'APPROVED',\n                  activeStep: 'artifacts',\n''',
    '''                  approvedQualityRules: reviewed.quality_rules as GovernedQualityRule[],\n                  qualityRulesVersion: reviewed.quality_rules_version ?? current.qualityRulesVersion,\n                  qualityReviewed: true,\n                  qualityReviewDecision: 'APPROVED',\n                  activeStep: 'artifacts',\n''',
)

replace(
    APP,
    '''                const contract = buildArtifactContract(workflow);\n                const pkg = await silverApi.generateArtifacts(workflow.specId, {\n''',
    '''                const contract = buildArtifactContract(workflow);\n                const governedRules = workflow.approvedQualityRules ?? [];\n                const notApproved = governedRules.filter((rule) => rule.status !== 'APPROVED');\n                if (notApproved.length) {\n                  throw new Error('El package solo puede ejecutarse con reglas de calidad APPROVED.');\n                }\n                const pkg = await silverApi.generateArtifacts(workflow.specId, {\n''',
)

replace(
    APP,
    '''                  quality_rules: contract.qualityRules,\n                });\n                const execution = await silverApi.createExecution({\n''',
    '''                  quality_rules: governedRules.length ? governedRules : contract.qualityRules,\n                });\n                const execution = await silverApi.createExecution({\n''',
)

if not TEST.exists():
    TEST.write_text('''import pytest\n\nfrom modules.silver_refinement.execution_artifact_generator import ExecutionArtifactGeneratorService\n\n\ndef test_governed_rule_normalization_preserves_runtime_action_and_contract():\n    normalized = ExecutionArtifactGeneratorService.normalize_quality_rules([{\n        "rule_id": "qr_amount_range",\n        "name": "amount_range",\n        "version": 2,\n        "dimension": "VALIDITY",\n        "rule_type": "VALUE_RANGE",\n        "columns": ["amount"],\n        "parameters": {"min": 0, "max": 100},\n        "warning_threshold": 1,\n        "critical_threshold": 5,\n        "severity": "HIGH",\n        "runtime_action": "QUARANTINE",\n        "source": "DERIVED_NL",\n        "status": "APPROVED",\n        "active": True,\n        "metadata": {"natural_rule": "amount entre 0 y 100"},\n    }])[0]\n\n    assert normalized["rule_id"] == "qr_amount_range"\n    assert normalized["rule_version"] == 2\n    assert normalized["column_name"] == "amount"\n    assert normalized["rule_parameters"]["min_value"] == 0\n    assert normalized["rule_parameters"]["max_value"] == 100\n    assert normalized["runtime_action"] == "QUARANTINE"\n    assert normalized["status"] == "APPROVED"\n\n\ndef test_governed_regex_alias_is_executable_contract():\n    normalized = ExecutionArtifactGeneratorService.normalize_quality_rules([{\n        "rule_id": "qr_code_regex",\n        "name": "code_regex",\n        "dimension": "VALIDITY",\n        "rule_type": "REGEX",\n        "columns": ["code"],\n        "parameters": {"pattern": "^[A-Z]+$"},\n        "runtime_action": "WARN",\n        "status": "APPROVED",\n    }])[0]\n    assert normalized["rule_type"] == "REGEX_MATCH"\n    assert normalized["rule_parameters"]["regex"] == "^[A-Z]+$"\n    assert normalized["runtime_action"] == "WARN"\n\n\ndef test_pending_governed_rule_cannot_enter_executable_package():\n    with pytest.raises(ValueError, match="no está aprobada"):\n        ExecutionArtifactGeneratorService.normalize_quality_rules([{\n            "rule_id": "qr_pending",\n            "name": "pending",\n            "dimension": "COMPLETENESS",\n            "rule_type": "NOT_NULL",\n            "columns": ["id"],\n            "parameters": {},\n            "runtime_action": "BLOCK_LOAD",\n            "status": "PENDING_APPROVAL",\n        }])\n\n\ndef test_table_level_quarantine_is_rejected():\n    with pytest.raises(ValueError, match="nivel tabla"):\n        ExecutionArtifactGeneratorService.normalize_quality_rules([{\n            "rule_name": "row_count",\n            "rule_type": "ROW_COUNT_MIN",\n            "rule_parameters": {"min_rows": 10},\n            "runtime_action": "QUARANTINE",\n        }])\n\n\ndef test_generated_script_contains_all_runtime_gate_paths():\n    source = (\n        __import__("pathlib").Path(__file__).parents[1]\n        / "modules/silver_refinement/execution_artifact_generator.py"\n    ).read_text()\n    assert 'action == "BLOCK_LOAD"' in source\n    assert 'action == "QUARANTINE"' in source\n    assert 'action == "WARN"' in source\n    assert 'action == "OBSERVE_ONLY"' in source\n    assert "silver_output_df" in source\n    assert "_exclude_quarantined_rows" in source\n''')

print("PASS: Runtime Quality Gates aplicado.")
print("OBSERVE_ONLY/WARN continúan; QUARANTINE excluye filas; BLOCK_LOAD bloquea; package exige aprobación.")
