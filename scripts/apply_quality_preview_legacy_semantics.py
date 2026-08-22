from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUALITY_JS = ROOT / "preview/governance-dashboard/quality.js"
INDEX_HTML = ROOT / "preview/governance-dashboard/index.html"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"ERROR: no se encontró patrón para {label}")
    return text.replace(old, new, 1)


quality = QUALITY_JS.read_text(encoding="utf-8")
quality = replace_once(
    quality,
    "const versions = governed.map((workflow) => Number(workflow?.quality_rules_version)).filter(Number.isFinite);",
    "const versions = governed\n      .map((workflow) => workflow?.quality_rules_version)\n      .filter((value) => value !== null && value !== undefined && value !== '')\n      .map(Number)\n      .filter(Number.isFinite);",
    "quality rules version null-safe",
)
quality = replace_once(
    quality,
    "setText('qualityRuleCountBadge', `${rows.length} reglas`, '0 reglas');",
    "setText('qualityRuleCountBadge', `${rows.length} reglas observables`, '0 reglas observables');",
    "rule badge semantics",
)
quality = replace_once(
    quality,
    ": '<div class=\"quality-empty\">No hay procesos con contrato de calidad observable.</div>';",
    ": '<div class=\"quality-empty\">No hay procesos con reglas de calidad observables.</div>';",
    "coverage empty semantics",
)
quality = replace_once(
    quality,
    "const message = governed.length ? `${governed.length} procesos con contrato observable` : 'Sin contrato de calidad observable';",
    "const message = governed.length ? `${governed.length} procesos con reglas observables` : 'Sin reglas de calidad observables';",
    "source status semantics",
)
QUALITY_JS.write_text(quality, encoding="utf-8")

html = INDEX_HTML.read_text(encoding="utf-8")
html = replace_once(
    html,
    "<h2>Calidad gobernada · del diseño al runtime</h2>",
    "<h2>Calidad de datos · configuración y runtime</h2>",
    "quality heading",
)
html = replace_once(
    html,
    "<p>Reglas aprobadas, decisiones de ejecución y evidencia por proceso Silver. Solo se muestran datos trazables disponibles en backend.</p>",
    "<p>Reglas observables, aprobaciones gobernadas y evidencia runtime por proceso Silver. Solo se muestran datos trazables disponibles en backend.</p>",
    "quality intro",
)
html = replace_once(
    html,
    "<div class=\"quality-panel-head\"><div><h3>Cobertura por proceso</h3><p>Procesos Silver con contrato de calidad versionado.</p></div></div>",
    "<div class=\"quality-panel-head\"><div><h3>Cobertura por proceso</h3><p>Procesos Silver con reglas de calidad observables; la versión se muestra solo cuando el backend la expone.</p></div></div>",
    "coverage copy",
)
html = replace_once(
    html,
    "<div class=\"quality-panel-head\"><div><h3>Reglas gobernadas</h3><p>Dimensión, severidad, runtime action, versión y estado. Selecciona una fila para inspeccionar su evidencia.</p></div><span id=\"qualityRuleCountBadge\" class=\"quality-soft-badge\">— reglas</span></div>",
    "<div class=\"quality-panel-head\"><div><h3>Reglas observables</h3><p>Incluye reglas legacy y gobernadas. Versión, runtime action y estado se muestran únicamente cuando existen en backend.</p></div><span id=\"qualityRuleCountBadge\" class=\"quality-soft-badge\">— reglas observables</span></div>",
    "rules panel copy",
)
INDEX_HTML.write_text(html, encoding="utf-8")

print("PASS: Semántica Quality preview corregida para reglas legacy y gobernadas.")
print("quality_rules_version null ya no se representa como v0.")
print("La UI distingue reglas observables, aprobaciones gobernadas y evidencia runtime.")
