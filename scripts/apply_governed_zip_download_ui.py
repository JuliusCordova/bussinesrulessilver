from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text)


def replace_once(path: str, old: str, new: str, *, already: str | None = None) -> None:
    text = read(path)
    if already and already in text:
        return
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:140]!r}")
    write(path, text.replace(old, new, 1))


# 1) ProductRoot: explicit governed ZIP download from the current ARTIFACT_PACKAGE.
replace_once(
    "src/ProductRoot.tsx",
    """  const [historyLoading, setHistoryLoading] = useState(false);\n  const [resumeWorkflow, setResumeWorkflow] = useState<WorkflowState>();""",
    """  const [historyLoading, setHistoryLoading] = useState(false);\n  const [packageDownloadLoading, setPackageDownloadLoading] = useState(false);\n  const [resumeWorkflow, setResumeWorkflow] = useState<WorkflowState>();""",
    already="const [packageDownloadLoading, setPackageDownloadLoading]",
)

replace_once(
    "src/ProductRoot.tsx",
    """  async function loadVersionHistory(workflowId: string) {\n    setHistoryLoading(true);""",
    """  async function downloadGovernedPackage(workflow: SilverWorkflowRecord) {\n    if (!workflow.spec_id) {\n      setError('El proceso todavía no tiene spec_id; no existe un package gobernado descargable.');\n      return;\n    }\n    setPackageDownloadLoading(true);\n    setError(undefined);\n    try {\n      const artifacts = await silverApi.listArtifacts(workflow.spec_id);\n      const packageArtifact = artifacts.find((artifact) =>\n        artifact.artifact_type === 'ARTIFACT_PACKAGE' && artifact.is_current !== false,\n      );\n      if (!packageArtifact) {\n        throw new Error('No existe un ARTIFACT_PACKAGE vigente para esta especificación.');\n      }\n      const blob = await silverApi.downloadArtifact(workflow.spec_id, 'ARTIFACT_PACKAGE');\n      const url = URL.createObjectURL(blob);\n      const anchor = document.createElement('a');\n      anchor.href = url;\n      anchor.download = packageArtifact.artifact_name || 'artifact-package.zip';\n      document.body.appendChild(anchor);\n      anchor.click();\n      anchor.remove();\n      URL.revokeObjectURL(url);\n    } catch (downloadError) {\n      setError(downloadError instanceof Error ? downloadError.message : String(downloadError));\n    } finally {\n      setPackageDownloadLoading(false);\n    }\n  }\n\n  async function loadVersionHistory(workflowId: string) {\n    setHistoryLoading(true);""",
    already="async function downloadGovernedPackage(workflow: SilverWorkflowRecord)",
)

replace_once(
    "src/ProductRoot.tsx",
    """              <div className=\"processHistoryActions\">\n                <button\n                  disabled={historyLoading}""",
    """              <div className=\"processHistoryActions\">\n                <button\n                  disabled={!selected.spec_id || packageDownloadLoading}\n                  onClick={() => void downloadGovernedPackage(selected)}\n                >\n                  {packageDownloadLoading ? 'Descargando package…' : 'Descargar package ZIP'}\n                </button>\n                <button\n                  disabled={historyLoading}""",
    already="Descargar package ZIP",
)

# 2) App: reflect the governed ARTIFACT_PACKAGE version immediately after generation.
replace_once(
    "src/App.tsx",
    """                setWorkflow((current) => ({\n                  ...current,\n                  ...demoWorkflowPatch('Artefactos descargables y execution creados'),\n                  specId: pkg.spec_id,\n                  mappingVersion: pkg.mapping_version,\n                  generatedArtifacts: pkg.artifacts,""",
    """                const packageArtifact = pkg.artifacts.find((artifact) =>\n                  artifact.artifact_type === 'ARTIFACT_PACKAGE',\n                );\n                setWorkflow((current) => ({\n                  ...current,\n                  ...demoWorkflowPatch('Artefactos descargables y execution creados'),\n                  specId: pkg.spec_id,\n                  mappingVersion: pkg.mapping_version,\n                  packageVersion: packageArtifact?.artifact_version ?? current.packageVersion,\n                  generatedArtifacts: pkg.artifacts,""",
    already="packageVersion: packageArtifact?.artifact_version",
)

print('PASS: descarga gobernada de Package ZIP expuesta en Procesos Silver.')
print('El navegador descarga ARTIFACT_PACKAGE desde backend/GCS; no reconstruye el ZIP localmente.')
