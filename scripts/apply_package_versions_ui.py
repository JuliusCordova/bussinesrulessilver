from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text()
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1))


# 1) Rename the governed artifact step.
replace(
    "src/App.tsx",
    "{ id: 'artifacts', label: 'Artefactos', description: 'DDL, notebook y paquete' },",
    "{ id: 'artifacts', label: 'Package & Versiones', description: 'Versiones, Storage, hashes y paquete gobernado' },",
)

# 2) Enrich ArtifactsStep with visible governed versions.
replace(
    "src/App.tsx",
    """      <div className=\"qualityGateSummary\">\n        <strong>Gate de calidad: {workflow.qualityReviewDecision ?? 'PENDIENTE'}</strong>\n        <span>\n          {workflow.qualityReviewed\n            ? 'Revisión persistida en backend. La generación está habilitada.'\n            : 'Revisa y aprueba las reglas antes de crear artefactos.'}\n        </span>\n      </div>\n      <div className=\"artifactGrid\">""",
    """      <div className=\"qualityGateSummary\">\n        <strong>Gate de calidad: {workflow.qualityReviewDecision ?? 'PENDIENTE'}</strong>\n        <span>\n          {workflow.qualityReviewed\n            ? 'Revisión persistida en backend. La generación está habilitada.'\n            : 'Revisa y aprueba las reglas antes de crear artefactos.'}\n        </span>\n      </div>\n      <div className=\"resultMetrics\">\n        <article><span>Workflow</span><strong>v{workflow.version ?? 1}</strong></article>\n        <article><span>Mapping</span><strong>v{workflow.mappingVersion ?? 1}</strong></article>\n        <article><span>Spec</span><strong>{workflow.specId ?? 'Pendiente'}</strong></article>\n        <article><span>Package</span><strong>{workflow.packageVersion ? `v${workflow.packageVersion}` : 'Pendiente'}</strong></article>\n      </div>\n      <div className=\"artifactGrid\">""",
)

replace(
    "src/App.tsx",
    """            <em>{artifact.generation_status ?? 'GENERATED'}</em>\n            {generated.length > 0 && (\n              <button onClick={() => onDownload(artifact)}>Descargar</button>\n            )}""",
    """            <em>{artifact.generation_status ?? 'GENERATED'}</em>\n            <small>Versión: {artifact.artifact_version ? `v${artifact.artifact_version}` : 'N/A'}</small>\n            <small>Validación: {artifact.validation_status ?? 'PENDIENTE'}</small>\n            <small title={artifact.storage_uri ?? undefined}>Storage: {artifact.storage_uri ?? 'Pendiente'}</small>\n            <small title={artifact.content_hash ?? undefined}>Hash: {artifact.content_hash ?? 'Pendiente'}</small>\n            {generated.length > 0 && (\n              <button onClick={() => onDownload(artifact)}>Descargar</button>\n            )}""",
)

# 3) Load real artifact metadata when reopening an existing process.
replace(
    "src/ProductRoot.tsx",
    """      const latest = await silverApi.getWorkflow(workflowId);\n      setSelected(latest);\n      setResumeWorkflow(hydrateWorkflowForResume(latest));\n      setMode('wizard');""",
    """      const latest = await silverApi.getWorkflow(workflowId);\n      const hydrated = hydrateWorkflowForResume(latest);\n      if (latest.spec_id) {\n        try {\n          const artifacts = await silverApi.listArtifacts(latest.spec_id);\n          hydrated.generatedArtifacts = artifacts;\n        } catch {\n          // The workflow remains reopenable even if historical artifact listing is unavailable.\n        }\n      }\n      const execution = latest.execution && typeof latest.execution === 'object'\n        ? latest.execution as Record<string, unknown>\n        : undefined;\n      const packageData = latest.artifact_package && typeof latest.artifact_package === 'object'\n        ? latest.artifact_package as Record<string, unknown>\n        : undefined;\n      const rawPackageVersion = packageData?.package_version ?? execution?.package_version;\n      if (typeof rawPackageVersion === 'number') hydrated.packageVersion = rawPackageVersion;\n      setSelected(latest);\n      setResumeWorkflow(hydrated);\n      setMode('wizard');""",
)

# 4) Add packageVersion to state contract.
replace(
    "src/types.ts",
    "  mappingVersion?: number;\n  executionId?: string;",
    "  mappingVersion?: number;\n  packageVersion?: number;\n  executionId?: string;",
)

# 5) Hydrate package version from workflow evidence when available.
replace(
    "src/workflowResume.ts",
    """    mappingVersion: workflow.mapping_version ?? undefined,\n    executionId: workflow.execution_id ?? undefined,""",
    """    mappingVersion: workflow.mapping_version ?? undefined,\n    packageVersion: (() => {\n      const pkg = asRecord(workflow.artifact_package);\n      const execution = asRecord(workflow.execution);\n      const value = pkg?.package_version ?? execution?.package_version;\n      return typeof value === 'number' ? value : undefined;\n    })(),\n    executionId: workflow.execution_id ?? undefined,""",
)

# 6) Improve the process detail with real package/storage evidence when present.
replace(
    "src/ProductRoot.tsx",
    """function packageVersion(workflow: SilverWorkflowRecord) {\n  const value = workflow.artifact_package?.package_version;\n  return typeof value === 'number' ? `v${value}` : 'Pendiente';\n}""",
    """function packageVersion(workflow: SilverWorkflowRecord) {\n  const execution = workflow.execution && typeof workflow.execution === 'object'\n    ? workflow.execution as Record<string, unknown>\n    : undefined;\n  const value = workflow.artifact_package?.package_version ?? execution?.package_version;\n  return typeof value === 'number' ? `v${value}` : 'Pendiente';\n}\n\nfunction packageStorage(workflow: SilverWorkflowRecord) {\n  const execution = workflow.execution && typeof workflow.execution === 'object'\n    ? workflow.execution as Record<string, unknown>\n    : undefined;\n  const artifactPackage = workflow.artifact_package && typeof workflow.artifact_package === 'object'\n    ? workflow.artifact_package as Record<string, unknown>\n    : undefined;\n  const value = artifactPackage?.storage_uri ?? artifactPackage?.current_uri ?? execution?.artifact_package_uri;\n  return typeof value === 'string' && value ? value : 'Pendiente';\n}""",
)

replace(
    "src/ProductRoot.tsx",
    """                <div><dt>Package</dt><dd>{packageVersion(selected)}</dd></div>\n                <div><dt>Origen</dt><dd>{selected.source?.fully_qualified_name ?? 'Pendiente'}</dd></div>""",
    """                <div><dt>Package</dt><dd>{packageVersion(selected)}</dd></div>\n                <div><dt>Storage package</dt><dd title={packageStorage(selected)}>{packageStorage(selected)}</dd></div>\n                <div><dt>Origen</dt><dd>{selected.source?.fully_qualified_name ?? 'Pendiente'}</dd></div>""",
)

print("PASS: visibilidad gobernada de Package & Versiones aplicada.")
print("Incluye Workflow/Mapping/Spec/Package + artifact version/status/Storage/hash reales cuando existen.")
