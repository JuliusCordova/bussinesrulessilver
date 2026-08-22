from modules.silver_refinement.execution_artifact_generator import ExecutionArtifactGeneratorService


def test_generated_runtime_contains_mandatory_quality_evidence_contract():
    source = open(
        "modules/silver_refinement/execution_artifact_generator.py",
        encoding="utf-8",
    ).read()
    assert 'QUALITY_EVIDENCE_TABLE = os.getenv("QUALITY_EVIDENCE_TABLE")' in source
    assert "def persist_quality_evidence(spark: SparkSession, quality: dict)" in source
    assert 'raise ValueError("QUALITY_EVIDENCE_TABLE es obligatorio para ejecución gobernada")' in source
    assert '"runtime_decision": str(quality.get("runtime_decision")' in source
    assert '"rule_results_json": json.dumps' in source
    assert '.option("table", QUALITY_EVIDENCE_TABLE)' in source
    assert "persist_quality_evidence(spark, quality)" in source


def test_dataproc_launcher_passes_quality_evidence_table_to_driver():
    source = open(
        "modules/silver_execution/dataproc_launcher.py",
        encoding="utf-8",
    ).read()
    assert 'SILVER_QUALITY_EVIDENCE_TABLE' in source
    assert 'silver_execution_quality' in source
    assert 'spark.dataproc.driverEnv.QUALITY_EVIDENCE_TABLE' in source
