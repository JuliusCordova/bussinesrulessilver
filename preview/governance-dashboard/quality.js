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

  function workflowList(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.workflows)) return payload.workflows;
    return [];
  }

  function runtimeList(payload) {
    return Array.isArray(payload?.executions) ? payload.executions : [];
  }

  function rulesOf(workflow) {
    return Array.isArray(workflow?.quality_rules) ? workflow.quality_rules : [];
  }

  function processName(workflow) {
    return workflow?.silver_target?.table_id || workflow?.source?.table_id || workflow?.workflow_id || 'Proceso Silver';
  }

  function runtimeDecision(evidence) {
    return String(evidence?.runtime_decision || '').toUpperCase();
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

  function renderConfigured(workflows, runtimeExecutions) {
    const governed = workflows.filter((workflow) => rulesOf(workflow).length || workflow?.quality_rules_version != null);
    const rows = governed.flatMap((workflow) => rulesOf(workflow).map((rule) => ({ workflow, rule, process: processName(workflow) })));
    const approved = rows.filter(({rule}) => String(rule?.status || '').toUpperCase() === 'APPROVED');
    const versions = governed
      .map((workflow) => workflow?.quality_rules_version)
      .filter((value) => value !== null && value !== undefined && value !== '')
      .map(Number)
      .filter(Number.isFinite);
    const runtimeBySpec = new Map(runtimeExecutions.map((item) => [String(item.spec_id || ''), item]));

    setText('qualityApprovedRules', int(approved.length), '0');
    setText('qualityRulesVersion', versions.length ? `v${Math.max(...versions)}` : null);
    setText('qualityRuleCountBadge', `${rows.length} reglas observables`, '0 reglas observables');
    setText('overviewQualityRules', int(approved.length), '0');
    setText('overviewQualityVersion', versions.length ? `v${Math.max(...versions)}` : '—', '—');

    $('qualityProcessCoverage').innerHTML = governed.length
      ? governed.slice(0, 12).map((workflow) => {
          const evidence = runtimeBySpec.get(String(workflow.spec_id || ''));
          const decision = runtimeDecision(evidence) || 'SIN EVIDENCIA RUNTIME';
          return `<div class="quality-process-row"><div><strong>${esc(processName(workflow))}</strong><small>${esc(workflow.workflow_id || '')}</small></div><span>v${esc(workflow.quality_rules_version ?? '—')}</span><b class="quality-chip ${decision.toLowerCase().replaceAll('_','-')}">${esc(decision.replaceAll('_',' '))}</b></div>`;
        }).join('')
      : '<div class="quality-empty">No hay procesos con reglas de calidad observables.</div>';

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
    const message = governed.length ? `${governed.length} procesos con reglas observables` : 'Sin reglas de calidad observables';
    [source, overviewState].forEach((node) => {
      if (!node) return;
      node.textContent = message;
      node.classList.toggle('live', governed.length > 0);
      node.classList.toggle('pending', governed.length === 0);
    });
  }

  function renderRuntime(summary, executionsPayload) {
    const sourceAvailable = summary?.source_available === true && executionsPayload?.source_available === true;
    const executions = sourceAvailable ? runtimeList(executionsPayload) : [];

    if (!sourceAvailable) {
      setText('qualityScore', null);
      setText('qualityWarnings', null);
      setText('qualityQuarantineRows', null);
      setText('qualityBlockedLoads', null);
      $('qualityRuntimeDecisions').innerHTML = '<div class="quality-empty">Sin evidencia runtime persistida. El dashboard no infiere resultados desde la configuración.</div>';
      return executions;
    }

    setText('qualityScore', summary.latest_quality_score != null ? `${Number(summary.latest_quality_score).toFixed(1)}%` : null);
    setText('qualityWarnings', summary.evidence_count > 0 ? int(summary.total_warning_rows) : null);
    setText('qualityQuarantineRows', summary.evidence_count > 0 ? int(summary.total_quarantined_rows) : null);
    setText('qualityBlockedLoads', summary.evidence_count > 0 ? int(summary.block_load_executions) : null);

    const decisionCounts = new Map();
    executions.forEach((evidence) => {
      const decision = runtimeDecision(evidence);
      if (decision) decisionCounts.set(decision, (decisionCounts.get(decision) || 0) + 1);
    });
    const order = ['PASS','OBSERVE_ONLY','WARN','QUARANTINE','BLOCK_LOAD'];
    $('qualityRuntimeDecisions').innerHTML = decisionCounts.size
      ? order.map((name) => `<div class="quality-decision ${name.toLowerCase().replace('_','-')}"><span>${name.replace('_',' ')}</span><strong>${int(decisionCounts.get(name) || 0)}</strong><small>ejecuciones con evidencia</small></div>`).join('')
      : '<div class="quality-empty">La fuente runtime existe, pero todavía no contiene ejecuciones con evidencia.</div>';
    return executions;
  }

  async function load() {
    const [workflowsResult, summaryResult, executionsResult] = await Promise.allSettled([
      get('/silver-workflows?limit=50'),
      get('/agentops/quality/summary'),
      get('/agentops/quality/executions?limit=50'),
    ]);

    const workflows = workflowsResult.status === 'fulfilled' ? workflowList(workflowsResult.value) : [];
    const summary = summaryResult.status === 'fulfilled' ? summaryResult.value : { source_available: false };
    const executionsPayload = executionsResult.status === 'fulfilled' ? executionsResult.value : { source_available: false, executions: [] };
    const runtimeExecutions = renderRuntime(summary, executionsPayload);
    renderConfigured(workflows, runtimeExecutions);

    if (workflowsResult.status === 'rejected') {
      console.warn('Quality governance preview: workflow contracts unavailable', workflowsResult.reason);
      const source = $('qualitySourceStatus');
      if (source) source.textContent = 'Backend sin contratos de calidad disponibles';
    }
    if (summaryResult.status === 'rejected' || executionsResult.status === 'rejected') {
      console.warn('Quality governance preview: runtime evidence unavailable', summaryResult.reason || executionsResult.reason);
    }
  }

  window.addEventListener('DOMContentLoaded', load);
  document.getElementById('refreshButton')?.addEventListener('click', load);
})();
