from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src/App.tsx"


def replace_once(old: str, new: str) -> None:
    text = APP.read_text()
    if old not in text:
        raise SystemExit(f"Pattern not found in {APP}:\n{old[:220]}")
    APP.write_text(text.replace(old, new, 1))


replace_once(
    """  const displayArtifacts: GeneratedArtifact[] = generated.length\n    ? generated\n    : artifacts.map((artifactType) => ({\n        artifact_id: undefined,\n        artifact_type: artifactType,\n        artifact_name: artifactType,\n        generation_status: 'PENDING',\n      }));\n\n  return (\n""",
    """  const displayArtifacts: GeneratedArtifact[] = generated.length\n    ? generated\n    : artifacts.map((artifactType) => ({\n        artifact_id: undefined,\n        artifact_type: artifactType,\n        artifact_name: artifactType,\n        generation_status: 'PENDING',\n      }));\n  const packageArtifact = generated.find((artifact) =>\n    /zip|package/i.test(`${artifact.artifact_type ?? ''} ${artifact.artifact_name ?? ''}`),\n  );\n\n  return (\n""",
)

replace_once(
    """      <div className=\"qualityGateSummary\">\n        <strong>Gate de calidad: {workflow.qualityReviewDecision ?? 'PENDIENTE'}</strong>\n        <span>\n          {workflow.qualityReviewed\n            ? 'Revisión persistida en backend. La generación está habilitada.'\n            : 'Revisa y aprueba las reglas antes de crear artefactos.'}\n        </span>\n      </div>\n      <div className=\"resultMetrics\">\n""",
    """      <div className=\"qualityGateSummary\">\n        <strong>Gate de calidad: {workflow.qualityReviewDecision ?? 'PENDIENTE'}</strong>\n        <span>\n          {workflow.qualityReviewed\n            ? 'Revisión persistida en backend. La generación está habilitada.'\n            : 'Revisa y aprueba las reglas antes de crear artefactos.'}\n        </span>\n      </div>\n\n      <section className=\"packageDownloadPanel\">\n        <div>\n          <span className=\"resultEyebrow\">Paquete ejecutable gobernado</span>\n          <h3>{packageArtifact ? 'Package ZIP listo para descargar' : 'Package ZIP pendiente'}</h3>\n          <p>\n            Descarga el paquete exacto que será validado y enviado a Dataproc.\n            Incluye los artefactos versionados de este workflow.\n          </p>\n          <small>\n            Versión: {workflow.packageVersion ? `v${workflow.packageVersion}` : 'Pendiente'} ·{' '}\n            Hash: {packageArtifact?.content_hash ?? 'Pendiente'}\n          </small>\n          <small title={packageArtifact?.storage_uri ?? undefined}>\n            Storage: {packageArtifact?.storage_uri ?? 'Pendiente'}\n          </small>\n        </div>\n        <button\n          className=\"primary\"\n          disabled={!packageArtifact}\n          onClick={() => packageArtifact && onDownload(packageArtifact)}\n        >\n          Descargar paquete ZIP\n        </button>\n      </section>\n\n      <div className=\"resultMetrics\">\n""",
)

print("P0.3 applied: prominent governed ZIP download panel")
