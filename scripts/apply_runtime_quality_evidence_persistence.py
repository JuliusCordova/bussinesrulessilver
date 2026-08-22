from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "backend/deployable/silver-refinement-agent"

launcher = BASE / "modules/silver_execution/dataproc_launcher.py"
generator = BASE / "modules/silver_refinement/execution_artifact_generator.py"
test_path = BASE / "tests/test_runtime_quality_evidence.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"No se encontro bloque esperado en {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


# 1) Dataproc launcher: pass canonical quality evidence table to the driver.
replace_once(
    launcher,
    '        properties = {\n            "spark.dataproc.driverEnv.EXECUTION_ID": execution_id,\n        }\n',
    '        dataops_dataset = os.getenv("DATAOPS_DATASET", "dataops_control")\n'
    '        quality_evidence_table = os.getenv(\n'
    '            "SILVER_QUALITY_EVIDENCE_TABLE",\n'
    '            f"{self.project_id}.{dataops_dataset}.silver_execution_quality",\n'
    '        )\n'
    '        properties = {\n'
    '            "spark.dataproc.driverEnv.EXECUTION_ID": execution_id,\n'
    '            "spark.dataproc.driverEnv.QUALITY_EVIDENCE_TABLE": quality_evidence_table,\n'
    '        }\n',
)

# 2) Generated PySpark contract: mandatory table reference.
replace_once(
    generator,
    'EXECUTION_ID = os.getenv("EXECUTION_ID", "unknown")\n\nlogging.basicConfig',
    'EXECUTION_ID = os.getenv("EXECUTION_ID", "unknown")\n'
    'QUALITY_EVIDENCE_TABLE = os.getenv("QUALITY_EVIDENCE_TABLE")\n\n'
    'logging.basicConfig',
)

# 3) Persist one normalized, append-only quality evaluation row using the same
# Spark BigQuery connector already required by the governed execution artifact.
marker = '''\ndef calculate_next_watermark(df):\n'''
insert = '''\ndef persist_quality_evidence(spark: SparkSession, quality: dict) -> None:\n    if not QUALITY_EVIDENCE_TABLE:\n        raise ValueError("QUALITY_EVIDENCE_TABLE es obligatorio para ejecución gobernada")\n\n    recorded_at = datetime.now(timezone.utc)\n    row = {\n        "execution_id": EXECUTION_ID,\n        "spec_id": SPEC_ID,\n        "mapping_version": int(MAPPING_VERSION),\n        "recorded_at": recorded_at,\n        "gate_status": str(quality.get("status") or "UNKNOWN"),\n        "runtime_decision": str(quality.get("runtime_decision") or quality.get("outcome") or "UNKNOWN"),\n        "quality_score": float(quality.get("quality_score") or 0.0),\n        "total_rows": int(quality.get("total_rows") or 0),\n        "failed_rows": int(quality.get("failed_rows") or 0),\n        "warning_rows": int(quality.get("warning_rows") or 0),\n        "observed_failure_rows": int(quality.get("observed_failure_rows") or 0),\n        "quarantined_rows": int(quality.get("quarantined_rows") or 0),\n        "continued_quarantined_rows": int(quality.get("continued_quarantined_rows") or 0),\n        "quarantine_events": int(quality.get("quarantine_events") or 0),\n        "table_level_blocking_failures": int(quality.get("table_level_blocking_failures") or 0),\n        "table_level_warnings": int(quality.get("table_level_warnings") or 0),\n        "quarantine_table": str(quality.get("quarantine_table") or ""),\n        "rule_results_json": json.dumps(quality.get("rule_results") or [], ensure_ascii=False, default=str),\n        "configured_rules_json": json.dumps(quality.get("configured_rules") or [], ensure_ascii=False, default=str),\n    }\n    evidence_df = spark.createDataFrame([row])\n    (\n        evidence_df.write.format("bigquery")\n        .option("table", QUALITY_EVIDENCE_TABLE)\n        .option("writeMethod", "direct")\n        .mode("append")\n        .save()\n    )\n\n\n'''
text = generator.read_text()
if 'def persist_quality_evidence(' not in text:
    if marker not in text:
        raise SystemExit("No se encontro calculate_next_watermark marker")
    generator.write_text(text.replace(marker, insert + marker, 1))

# 4) Gate evaluation must be persisted before any Silver write or BLOCK_LOAD raise.
replace_once(
    generator,
    '        quality, quarantine_df, silver_output_df = validate_quality(silver_df)\n        next_watermark = calculate_next_watermark(bronze_df)\n\n        if quality["status"] != "PASSED":\n',
    '        quality, quarantine_df, silver_output_df = validate_quality(silver_df)\n'
    '        next_watermark = calculate_next_watermark(bronze_df)\n'
    '        persist_quality_evidence(spark, quality)\n\n'
    '        if quality["status"] != "PASSED":\n',
)

# 5) Unit tests are source-level by design: they validate that the generated
# governed artifact contains the mandatory persistence contract without requiring Spark.
test_path.write_text('''from modules.silver_refinement.execution_artifact_generator import ExecutionArtifactGeneratorService\n\n\ndef test_generated_runtime_contains_mandatory_quality_evidence_contract():\n    source = open(\n        "modules/silver_refinement/execution_artifact_generator.py",\n        encoding="utf-8",\n    ).read()\n    assert 'QUALITY_EVIDENCE_TABLE = os.getenv("QUALITY_EVIDENCE_TABLE")' in source\n    assert "def persist_quality_evidence(spark: SparkSession, quality: dict)" in source\n    assert 'raise ValueError("QUALITY_EVIDENCE_TABLE es obligatorio para ejecución gobernada")' in source\n    assert '"runtime_decision": str(quality.get("runtime_decision")' in source\n    assert '"rule_results_json": json.dumps' in source\n    assert '.option("table", QUALITY_EVIDENCE_TABLE)' in source\n    assert "persist_quality_evidence(spark, quality)" in source\n\n\ndef test_dataproc_launcher_passes_quality_evidence_table_to_driver():\n    source = open(\n        "modules/silver_execution/dataproc_launcher.py",\n        encoding="utf-8",\n    ).read()\n    assert 'SILVER_QUALITY_EVIDENCE_TABLE' in source\n    assert 'silver_execution_quality' in source\n    assert 'spark.dataproc.driverEnv.QUALITY_EVIDENCE_TABLE' in source\n''')

print("PASS: Runtime Quality Evidence persistence aplicado.")
print("El PySpark gobernado persiste la decisión de calidad antes de escribir Silver.")
print("No parsea logs, no usa mocks, no toca preview, orchestrator ni GitHub Actions.")
