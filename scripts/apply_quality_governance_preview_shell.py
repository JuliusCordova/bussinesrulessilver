from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "preview" / "governance-dashboard"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Marker not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1))


index = PREVIEW / "index.html"
router = PREVIEW / "router.js"
deploy = ROOT / "scripts" / "deploy_governance_dashboard_preview.sh"

replace_once(
    index,
    '  <link rel="stylesheet" href="./product-polish.css" />',
    '  <link rel="stylesheet" href="./product-polish.css" />\n  <link rel="stylesheet" href="./quality.css" />',
)
replace_once(
    index,
    '        <button class="nav-item" type="button" data-view-target="finops"><span>◉</span>FinOps IA</button>',
    '        <button class="nav-item" type="button" data-view-target="finops"><span>◉</span>FinOps IA</button>\n        <button class="nav-item" type="button" data-view-target="quality"><span>✓</span>Calidad de datos</button>',
)
quality_section = r'''
      <section class="quality-section" id="quality" aria-label="Gobierno de calidad de datos">
        <div class="quality-head">
          <div>
            <span class="quality-kicker">QUALITY GOVERNANCE</span>
            <h2>Calidad gobernada · del diseño al runtime</h2>
            <p>Reglas aprobadas, decisiones de ejecución y evidencia por proceso Silver. Solo se muestran datos trazables disponibles en backend.</p>
          </div>
          <span id="qualitySourceStatus" class="quality-source-badge pending">Consultando…</span>
        </div>

        <div class="quality-kpis" aria-label="Indicadores de calidad">
          <article class="quality-kpi hero"><span>Quality score</span><strong id="qualityScore">No disponible</strong><small>Última evidencia observable</small></article>
          <article class="quality-kpi"><span>Reglas aprobadas</span><strong id="qualityApprovedRules">—</strong><small>Contrato gobernado vigente</small></article>
          <article class="quality-kpi"><span>Quality rules version</span><strong id="qualityRulesVersion">No disponible</strong><small>Máxima versión observable</small></article>
          <article class="quality-kpi warn"><span>Warnings</span><strong id="qualityWarnings">No disponible</strong><small>Eventos runtime trazables</small></article>
          <article class="quality-kpi quarantine"><span>Filas quarantine</span><strong id="qualityQuarantineRows">No disponible</strong><small>Excluidas de Silver por gate</small></article>
          <article class="quality-kpi block"><span>Block load</span><strong id="qualityBlockedLoads">No disponible</strong><small>Cargas bloqueadas por calidad</small></article>
        </div>

        <div class="quality-grid quality-top-grid">
          <article class="quality-panel">
            <div class="quality-panel-head"><div><h3>Decisión de runtime</h3><p>Distribución de la última evidencia disponible.</p></div><span class="quality-soft-badge">Gates gobernados</span></div>
            <div id="qualityRuntimeDecisions" class="quality-decision-grid"><div class="quality-empty">Sin evidencia runtime disponible.</div></div>
          </article>
          <article class="quality-panel">
            <div class="quality-panel-head"><div><h3>Cobertura por proceso</h3><p>Procesos Silver con contrato de calidad versionado.</p></div></div>
            <div id="qualityProcessCoverage" class="quality-process-list"><div class="quality-empty">Consultando procesos…</div></div>
          </article>
        </div>

        <article class="quality-panel quality-rules-panel">
          <div class="quality-panel-head"><div><h3>Reglas gobernadas</h3><p>Dimensión, severidad, runtime action, versión y estado. Selecciona una fila para inspeccionar su evidencia.</p></div><span id="qualityRuleCountBadge" class="quality-soft-badge">— reglas</span></div>
          <div class="quality-table-wrap"><table><thead><tr><th>Regla</th><th>Proceso</th><th>Dimensión</th><th>Severidad</th><th>Runtime action</th><th>Versión</th><th>Estado</th></tr></thead><tbody id="qualityRulesTable"><tr><td colspan="7" class="quality-empty">Sin reglas disponibles.</td></tr></tbody></table></div>
        </article>

        <div class="quality-note"><i>ⓘ</i><div><strong>Semántica:</strong> OBSERVE_ONLY mide sin alterar la carga; WARN registra y continúa; QUARANTINE excluye filas fallidas; BLOCK_LOAD bloquea la escritura Silver. La vista no fabrica métricas cuando la evidencia no está persistida.</div></div>
      </section>
'''
replace_once(
    index,
    '      <section class="dashboard-grid middle-grid">',
    quality_section + '\n      <section class="dashboard-grid middle-grid">',
)
replace_once(
    index,
    '  <script src="./finops-polish.js"></script>',
    '  <script src="./finops-polish.js"></script>\n  <script src="./quality.js"></script>',
)

replace_once(
    router,
    "    finops: ['FinOps IA · Consumo & Costos','Visión financiera y operativa del consumo real de IA en Business Rules Silver.','Cloud Billing + AgentOps · Costo real y atribución gobernada'],",
    "    finops: ['FinOps IA · Consumo & Costos','Visión financiera y operativa del consumo real de IA en Business Rules Silver.','Cloud Billing + AgentOps · Costo real y atribución gobernada'],\n    quality: ['Calidad de datos · Gobierno & runtime','Reglas aprobadas, decisiones de ejecución y evidencia observable por proceso Silver.','Quality Governance · Contratos versionados y runtime gates'],",
)
replace_once(
    router,
    '<article class="overview-rail-card"><header><span>Agentes</span><button type="button" data-view-link="agents">Ver catálogo →</button></header>',
    '<article class="overview-rail-card quality-rail-card"><header><span>Calidad</span><button type="button" data-view-link="quality">Ver detalle →</button></header><div class="rail-metrics two"><div><small>Reglas aprobadas</small><strong id="overviewQualityRules">—</strong></div><div><small>Versión</small><strong id="overviewQualityVersion">—</strong></div></div><div id="overviewQualityState" class="rail-state pending">Consultando evidencia…</div></article>\n      <article class="overview-rail-card"><header><span>Agentes</span><button type="button" data-view-link="agents">Ver catálogo →</button></header>',
)
replace_once(
    router,
    "    shortcuts.innerHTML=quick('finops','↗','FinOps IA','Consumo real, costo y atribución gobernada.')+quick('agents','◇','Agentes','Catálogo ADK, tools y desempeño observable.')+quick('runs','↻','Ejecuciones','Historial, estados y trazabilidad por run.');",
    "    shortcuts.innerHTML=quick('finops','↗','FinOps IA','Consumo real, costo y atribución gobernada.')+quick('quality','✓','Calidad','Reglas gobernadas, runtime gates y evidencia.')+quick('agents','◇','Agentes','Catálogo ADK, tools y desempeño observable.')+quick('runs','↻','Ejecuciones','Historial, estados y trazabilidad por run.');",
)
replace_once(
    router,
    "    const agentPanel=$('.agents-registry-panel'); if(agentPanel) views.agents.appendChild(agentPanel);",
    "    const quality=document.getElementById('quality'); if(quality) views.quality.appendChild(quality);\n    const agentPanel=$('.agents-registry-panel'); if(agentPanel) views.agents.appendChild(agentPanel);",
)

quality_js = r'''(() => {
  'use strict';

  const DEFAULT_API = 'https://silver-refinement-agent-mkqutd4koq-uc.a.run.app';
  const params = new URLSearchParams(window.location.search);
  const API_BASE = (params.get('api') || DEFAULT_API).replace(/\/$/, '');
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const int = (value) => new Intl.NumberFormat('es-PE').format(Number(value || 0));

  async function get(path) {
    const response = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  }

  function list(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.workflows)) return payload.workflows;
    return [];
  }

  function rulesOf(workflow) {
    return Array.isArray(workflow?.quality_rules) ? workflow.quality_rules : [];
  }

  function qualityEvidence(workflow) {
    const candidates = [
      workflow?.validation?.quality,
      workflow?.execution?.quality,
      workflow?.validation?.result?.quality,
      workflow?.execution?.result?.quality,
    ];
    return candidates.find((item) => item && typeof item === 'object') || null;
  }

  function processName(workflow) {
    return workflow?.silver_target?.table_id || workflow?.source?.table_id || workflow?.workflow_id || 'Proceso Silver';
  }

  function runtimeDecision(evidence) {
    return String(evidence?.runtime_decision || evidence?.outcome || '').toUpperCase();
  }

  function setText(id, value, fallback='No disponible') {
    const target = $(id);
    if (target) target.textContent = value == null || value === '' ? fallback : String(value);
  }

  function openRuleDetail(row) {
    const rule = row.rule;
    if (!window.openGovernanceDrawer) return;
    window.openGovernanceDrawer({
      eyebrow: 'Quality rule',
      title: rule.name || rule.rule_name || rule.rule_id || 'Regla de calidad',
      html: `<div class="drawer-section"><h3>Contrato gobernado</h3><pre>${esc(JSON.stringify({
        process: row.process,
        rule_id: rule.rule_id,
        version: rule.version,
        dimension: rule.dimension || rule.rule_dimension,
        rule_type: rule.rule_type,
        columns: rule.columns || (rule.column_name ? [rule.column_name] : []),
        severity: rule.severity || rule.severity_level,
        runtime_action: rule.runtime_action,
        source: rule.source,
        status: rule.status,
        evidence: rule.evidence,
        confidence: rule.confidence,
        metadata: rule.metadata,
      }, null, 2))}</pre></div>`,
    });
  }

  function render(workflows) {
    const governed = workflows.filter((workflow) => rulesOf(workflow).length || workflow?.quality_rules_version != null);
    const rows = governed.flatMap((workflow) => rulesOf(workflow).map((rule) => ({ workflow, rule, process: processName(workflow) })));
    const approved = rows.filter(({rule}) => String(rule?.status || '').toUpperCase() === 'APPROVED');
    const versions = governed.map((workflow) => Number(workflow?.quality_rules_version)).filter(Number.isFinite);
    const evidences = governed.map((workflow) => ({ workflow, evidence: qualityEvidence(workflow) })).filter((item) => item.evidence);

    setText('qualityApprovedRules', int(approved.length), '0');
    setText('qualityRulesVersion', versions.length ? `v${Math.max(...versions)}` : null);
    setText('qualityRuleCountBadge', `${rows.length} reglas`, '0 reglas');
    setText('overviewQualityRules', int(approved.length), '0');
    setText('overviewQualityVersion', versions.length ? `v${Math.max(...versions)}` : '—', '—');

    const scores = evidences.map(({evidence}) => Number(evidence?.quality_score)).filter(Number.isFinite);
    setText('qualityScore', scores.length ? `${scores[scores.length - 1].toFixed(1)}%` : null);

    const warnings = evidences.map(({evidence}) => Number(evidence?.warning_rows)).filter(Number.isFinite);
    setText('qualityWarnings', warnings.length ? int(warnings.reduce((a,b)=>a+b,0)) : null);
    const quarantine = evidences.map(({evidence}) => Number(evidence?.continued_quarantined_rows ?? evidence?.quarantined_rows)).filter(Number.isFinite);
    setText('qualityQuarantineRows', quarantine.length ? int(quarantine.reduce((a,b)=>a+b,0)) : null);
    const blocked = evidences.filter(({evidence}) => runtimeDecision(evidence) === 'BLOCK_LOAD').length;
    setText('qualityBlockedLoads', evidences.length ? int(blocked) : null);

    const decisionCounts = new Map();
    evidences.forEach(({evidence}) => {
      const decision = runtimeDecision(evidence);
      if (decision) decisionCounts.set(decision, (decisionCounts.get(decision) || 0) + 1);
    });
    const order = ['PASS','OBSERVE_ONLY','WARN','QUARANTINE','BLOCK_LOAD'];
    $('qualityRuntimeDecisions').innerHTML = decisionCounts.size
      ? order.map((name) => `<div class="quality-decision ${name.toLowerCase().replace('_','-')}"><span>${name.replace('_',' ')}</span><strong>${int(decisionCounts.get(name) || 0)}</strong><small>ejecuciones observadas</small></div>`).join('')
      : '<div class="quality-empty">El backend aún no expone evidencia runtime de calidad en los workflows observables.</div>';

    $('qualityProcessCoverage').innerHTML = governed.length
      ? governed.slice(0, 12).map((workflow) => {
          const evidence = qualityEvidence(workflow);
          const decision = runtimeDecision(evidence) || 'SIN EVIDENCIA RUNTIME';
          return `<div class="quality-process-row"><div><strong>${esc(processName(workflow))}</strong><small>${esc(workflow.workflow_id || '')}</small></div><span>v${esc(workflow.quality_rules_version ?? '—')}</span><b class="quality-chip ${decision.toLowerCase().replaceAll('_','-')}">${esc(decision.replaceAll('_',' '))}</b></div>`;
        }).join('')
      : '<div class="quality-empty">No hay procesos con contrato de calidad observable.</div>';

    $('qualityRulesTable').innerHTML = rows.length
      ? rows.slice(0, 100).map((row, index) => {
          const rule = row.rule;
          return `<tr class="quality-rule-row" data-quality-rule-index="${index}"><td><strong>${esc(rule.name || rule.rule_name || rule.rule_id || 'Regla')}</strong><small>${esc(rule.rule_type || '')}</small></td><td>${esc(row.process)}</td><td>${esc(rule.dimension || rule.rule_dimension || '—')}</td><td>${esc(rule.severity || rule.severity_level || '—')}</td><td><span class="quality-chip ${esc(String(rule.runtime_action || '').toLowerCase().replaceAll('_','-'))}">${esc(rule.runtime_action || '—')}</span></td><td>v${esc(rule.version ?? rule.rule_version ?? '—')}</td><td>${esc(rule.status || 'LEGACY')}</td></tr>`;
        }).join('')
      : '<tr><td colspan="7" class="quality-empty">No hay reglas de calidad observables en el backend actual.</td></tr>';

    document.querySelectorAll('[data-quality-rule-index]').forEach((element) => {
      element.addEventListener('click', () => openRuleDetail(rows[Number(element.dataset.qualityRuleIndex)]));
    });

    const source = $('qualitySourceStatus');
    const overviewState = $('overviewQualityState');
    const message = governed.length ? `${governed.length} procesos con contrato observable` : 'Sin contrato de calidad observable';
    [source, overviewState].forEach((node) => {
      if (!node) return;
      node.textContent = message;
      node.classList.toggle('live', governed.length > 0);
      node.classList.toggle('pending', governed.length === 0);
    });
  }

  async function load() {
    try {
      const payload = await get('/silver-workflows?limit=50');
      render(list(payload));
    } catch (error) {
      console.warn('Quality governance preview: evidence unavailable', error);
      render([]);
      const source = $('qualitySourceStatus');
      if (source) source.textContent = 'Backend sin evidencia disponible';
      const overview = $('overviewQualityState');
      if (overview) overview.textContent = 'Backend sin evidencia disponible';
    }
  }

  window.addEventListener('DOMContentLoaded', load);
  document.getElementById('refreshButton')?.addEventListener('click', load);
})();
'''
(PREVIEW / "quality.js").write_text(quality_js)

quality_css = r'''/* Quality Governance preview. Extends the existing Business Rules Silver visual language. */
.quality-section{display:grid;gap:14px}
.quality-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}
.quality-head h2{margin:3px 0 4px;font-size:21px;letter-spacing:-.02em;color:var(--br-ink)}
.quality-head p{margin:0;color:var(--br-muted);font-size:11px;max-width:820px;line-height:1.55}
.quality-kicker{display:block;color:var(--br-red);font-size:8.5px;font-weight:850;letter-spacing:.1em}
.quality-source-badge,.quality-soft-badge{border:1px solid var(--br-line);background:#f8fafc;color:#667085;border-radius:999px;padding:7px 10px;font-size:9px;font-weight:800;white-space:nowrap}
.quality-source-badge.live{background:#eefaf4;border-color:#ccebdc;color:#10734f}.quality-source-badge.pending{background:#fff9ed;border-color:#f3dfb8;color:#9a6200}
.quality-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}
.quality-kpi{position:relative;overflow:hidden;min-height:108px;background:#fff;border:1px solid var(--br-line);border-radius:16px;padding:14px 15px;box-shadow:0 7px 22px rgba(24,36,67,.045)}
.quality-kpi span{display:block;color:#697386;font-size:9px;text-transform:uppercase;letter-spacing:.035em;font-weight:800}.quality-kpi strong{display:block;margin:8px 0 5px;font-size:23px;letter-spacing:-.025em;color:var(--br-ink)}.quality-kpi small{color:#98a2b3;font-size:9px;line-height:1.35}
.quality-kpi.hero{background:linear-gradient(145deg,#fff 0%,#f4fbf7 100%);border-color:#d8eee2}.quality-kpi.hero:before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:var(--br-green)}
.quality-kpi.warn{background:linear-gradient(145deg,#fff 0%,#fffaf0 100%)}.quality-kpi.quarantine{background:linear-gradient(145deg,#fff 0%,#fff6ef 100%)}.quality-kpi.block{background:linear-gradient(145deg,#fff 0%,#fff3f2 100%);border-color:#f6d7d3}
.quality-grid{display:grid;gap:14px}.quality-top-grid{grid-template-columns:minmax(0,1.15fr) minmax(340px,.85fr)}
.quality-panel{background:#fff;border:1px solid var(--br-line);border-radius:18px;padding:16px;box-shadow:0 8px 24px rgba(24,36,67,.045)}
.quality-panel-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:13px}.quality-panel h3{margin:0 0 3px;font-size:14px;letter-spacing:-.01em;color:var(--br-ink)}.quality-panel p{margin:0;color:var(--br-muted);font-size:10px}
.quality-decision-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px}.quality-decision{border:1px solid var(--br-line);border-radius:14px;padding:12px;background:#fbfcfe}.quality-decision span{display:block;font-size:8.5px;font-weight:850;color:#667085}.quality-decision strong{display:block;font-size:22px;margin:6px 0 2px;color:var(--br-ink)}.quality-decision small{font-size:8.5px;color:#98a2b3}.quality-decision.warn{background:#fffaf0}.quality-decision.quarantine{background:#fff7ef}.quality-decision.block-load{background:#fff3f2;border-color:#f6d7d3}.quality-decision.pass{background:#f2fbf6}
.quality-process-list{display:grid;gap:8px}.quality-process-row{display:grid;grid-template-columns:minmax(0,1fr) 50px auto;gap:10px;align-items:center;border-bottom:1px solid #f0f2f6;padding:8px 0}.quality-process-row:last-child{border-bottom:0}.quality-process-row strong{display:block;font-size:10.5px;color:var(--br-ink)}.quality-process-row small{display:block;color:#98a2b3;font-size:8.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.quality-process-row>span{font-size:9px;color:#667085;font-weight:800}
.quality-chip{display:inline-flex;align-items:center;border:1px solid var(--br-line);background:#f8fafc;border-radius:999px;padding:4px 7px;font-size:8px;font-weight:850;color:#667085;white-space:nowrap}.quality-chip.pass{background:#eefaf4;border-color:#ccebdc;color:#10734f}.quality-chip.warn{background:#fff9ed;border-color:#f3dfb8;color:#9a6200}.quality-chip.quarantine{background:#fff4e9;border-color:#f7d8b9;color:#a45d16}.quality-chip.block-load{background:#fff1ef;border-color:#f6d2ce;color:#c5372d}.quality-chip.observe-only{background:#f2f5ff;border-color:#dce3ff;color:#4c5fc1}
.quality-table-wrap{overflow:auto}.quality-table-wrap table{width:100%;border-collapse:collapse}.quality-table-wrap th{text-align:left;color:#98a2b3;font-size:8.5px;text-transform:uppercase;letter-spacing:.045em;padding:9px 10px;border-bottom:1px solid var(--br-line)}.quality-table-wrap td{padding:11px 10px;border-bottom:1px solid #f0f2f6;color:#667085;font-size:9.5px}.quality-table-wrap td strong{display:block;color:var(--br-ink);font-size:10.5px}.quality-table-wrap td small{display:block;color:#98a2b3;margin-top:2px}.quality-rule-row{cursor:pointer}.quality-rule-row:hover{background:#fbfcfe}
.quality-empty{padding:18px;color:#98a2b3;font-size:10px;text-align:center}.quality-note{display:flex;gap:10px;align-items:flex-start;border:1px solid #e8eaf2;background:#fbfcfe;border-radius:14px;padding:12px 14px;color:#697386;font-size:9.5px;line-height:1.5}.quality-note i{font-style:normal;color:var(--br-blue);font-size:14px}.quality-rail-card{background:linear-gradient(145deg,#fff 0%,#f4fbf7 100%)}
.view-overview .overview-quick-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
.view-overview .overview-quick-card:nth-child(2) .overview-quick-icon{background:#eafaf2;color:var(--br-green)}.view-overview .overview-quick-card:nth-child(3) .overview-quick-icon{background:#eef5ff;color:var(--br-blue)}.view-overview .overview-quick-card:nth-child(4) .overview-quick-icon{background:#f4f0ff;color:var(--br-violet)}
@media(max-width:1450px){.quality-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.quality-top-grid{grid-template-columns:1fr}.quality-decision-grid{grid-template-columns:repeat(5,minmax(110px,1fr));overflow:auto}}
@media(max-width:900px){.quality-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.view-overview .overview-quick-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.quality-kpis{grid-template-columns:1fr}.quality-head{display:grid}.view-overview .overview-quick-grid{grid-template-columns:1fr}}
'''
(PREVIEW / "quality.css").write_text(quality_css)

replace_once(
    deploy,
    'for file in Dockerfile index.html app.js styles.css finops.js finops.css theme-red.css spa.css product-polish.css router.js finops-polish.js; do',
    'for file in Dockerfile index.html app.js styles.css finops.js finops.css theme-red.css spa.css product-polish.css router.js finops-polish.js quality.js quality.css; do',
)
replace_once(
    deploy,
    '  node --check "$PREVIEW_DIR/finops-polish.js"',
    '  node --check "$PREVIEW_DIR/finops-polish.js"\n  node --check "$PREVIEW_DIR/quality.js"',
)
replace_once(
    deploy,
    "grep -Fq 'data-view-target=\"finops\"' \"$PREVIEW_HTML\"",
    "grep -Fq 'data-view-target=\"finops\"' \"$PREVIEW_HTML\"\ngrep -Fq 'data-view-target=\"quality\"' \"$PREVIEW_HTML\"\ngrep -Fq './quality.css' \"$PREVIEW_HTML\"",
)
replace_once(
    deploy,
    'PREVIEW_PRODUCT_POLISH_CSS=/tmp/governance-preview-product-polish.css',
    'PREVIEW_PRODUCT_POLISH_CSS=/tmp/governance-preview-product-polish.css\nPREVIEW_QUALITY_JS=/tmp/governance-preview-quality.js\nPREVIEW_QUALITY_CSS=/tmp/governance-preview-quality.css',
)
replace_once(
    deploy,
    'curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/product-polish.css" -o "$PREVIEW_PRODUCT_POLISH_CSS"',
    'curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/product-polish.css" -o "$PREVIEW_PRODUCT_POLISH_CSS"\ncurl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/quality.js" -o "$PREVIEW_QUALITY_JS"\ncurl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/quality.css" -o "$PREVIEW_QUALITY_CSS"',
)
replace_once(
    deploy,
    "grep -Fq 'finops-product-panel' \"$PREVIEW_PRODUCT_POLISH_CSS\"",
    "grep -Fq 'finops-product-panel' \"$PREVIEW_PRODUCT_POLISH_CSS\"\ngrep -Fq '/silver-workflows?limit=50' \"$PREVIEW_QUALITY_JS\"\ngrep -Fq 'BLOCK_LOAD' \"$PREVIEW_QUALITY_JS\"\ngrep -Fq '.quality-section' \"$PREVIEW_QUALITY_CSS\"",
)
replace_once(
    deploy,
    'echo "FINOPS_URL=$PREVIEW_URL/#view/finops"',
    'echo "FINOPS_URL=$PREVIEW_URL/#view/finops"\necho "QUALITY_URL=$PREVIEW_URL/#view/quality"',
)

print('PASS: Quality Governance preview shell aplicado.')
print('Nueva ruta #view/quality; sin mocks; usa solo contratos/evidencia observable.')
print('No modifica src/ ni .github/workflows.')
