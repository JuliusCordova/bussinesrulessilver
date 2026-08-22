(() => {
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
