(() => {
  'use strict';

  const state = {
    health: null,
    summary: null,
    agents: [],
    deployments: [],
    findings: [],
  };

  const $ = (id) => document.getElementById(id);
  const int = (value) => new Intl.NumberFormat('es-PE').format(Number(value || 0));
  const text = (value, fallback = 'No disponible') => value == null || value === '' ? fallback : String(value);
  const esc = (value) => text(value, '').replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));

  const humanDate = (value) => {
    if (!value) return 'No disponible';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return text(value);
    return new Intl.DateTimeFormat('es-PE', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    }).format(date);
  };

  const statusLabel = (value) => {
    const labels = {
      governed: 'Gobernado',
      action_required: 'Requiere acción',
      under_review: 'En revisión',
      not_assessed: 'No evaluado',
      discovered: 'Descubierto',
      not_observed: 'No observado',
      bound: 'Asociado',
      unbound: 'Sin asociar',
      open: 'Abierto',
      closed: 'Cerrado',
      remediated: 'Remediado',
      accepted: 'Aceptado',
      low: 'Bajo',
      medium: 'Medio',
      high: 'Alto',
      critical: 'Crítico',
      l0: 'L0 · Informa',
      l1: 'L1 · Recomienda',
      l2: 'L2 · Prepara',
      l3: 'L3 · Ejecuta acotado',
      l4: 'L4 · Autónomo',
    };
    return labels[String(value || '').toLowerCase()] || text(value, 'No evaluado').replaceAll('_', ' ');
  };

  async function request(path, init = {}) {
    const response = await fetch(`/api${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.headers || {}),
      },
      cache: 'no-store',
    });
    const body = await response.text();
    let payload = {};
    try { payload = body ? JSON.parse(body) : {}; } catch { payload = { detail: body }; }
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${text(payload.detail, body).slice(0, 240)}`);
    return payload;
  }

  const profileOf = (agent) => agent.governance_profile || {};
  const governanceStatusOf = (agent) => profileOf(agent).governance_status || agent.governance_status || 'not_assessed';
  const riskOf = (agent) => profileOf(agent).risk_level || 'not_assessed';
  const autonomyOf = (agent) => profileOf(agent).autonomy_level || 'not_assessed';

  function countBy(items, selector) {
    return items.reduce((acc, item) => {
      const key = selector(item);
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
  }

  function renderKpis() {
    const summary = state.summary || {};
    $('kpiAgents').textContent = int(summary.governed_agents ?? state.agents.length);
    $('kpiAgentsHint').textContent = `${int(summary.governed_agents ?? state.agents.length)} identidades lógicas registradas`;
    $('kpiGoverned').textContent = int(summary.governed_compliant || 0);
    $('kpiAction').textContent = int(summary.action_required || 0);
    $('kpiRisk').textContent = int(summary.high_risk || 0);
    $('kpiFindings').textContent = int(summary.open_findings || 0);
    $('kpiDeployments').textContent = int(summary.deployments_adk || state.deployments.length);
    $('kpiDeploymentsHint').textContent = `${int(summary.deployments_unbound || 0)} pendientes de resolver identidad`;
  }

  function renderGovernanceState() {
    const counts = countBy(state.agents, governanceStatusOf);
    const segments = [
      ['Gobernados', 'governed', counts.governed || 0, '#1aa36f'],
      ['Requieren acción', 'action_required', counts.action_required || 0, '#d94a53'],
      ['En revisión', 'under_review', counts.under_review || 0, '#7557ff'],
      ['No evaluados', 'not_assessed', counts.not_assessed || 0, '#e49822'],
    ];
    const total = segments.reduce((sum, item) => sum + item[2], 0);
    let cursor = 0;
    const stops = segments.map(([, , value, color]) => {
      const start = cursor;
      cursor += total ? value * 100 / total : 0;
      return `${color} ${start.toFixed(1)}% ${cursor.toFixed(1)}%`;
    }).join(', ');
    $('governanceDonut').style.background = total ? `conic-gradient(${stops})` : '#eef0f5';
    $('governanceTotal').textContent = int(total);
    $('governanceLegend').innerHTML = segments.map(([label, key, value, color]) => `
      <button class="status-item interactive-row" data-governance-status="${key}">
        <i style="background:${color}"></i><span>${label}</span><b>${int(value)}</b>
      </button>`).join('');
  }

  function renderRisk() {
    const counts = countBy(state.agents, riskOf);
    const evaluated = state.agents.filter((agent) => riskOf(agent) !== 'not_assessed').length;
    $('riskBadge').textContent = `${evaluated} evaluados`;
    const rows = [
      ['Crítico', 'critical', counts.critical || 0],
      ['Alto', 'high', counts.high || 0],
      ['Medio', 'medium', counts.medium || 0],
      ['Bajo', 'low', counts.low || 0],
      ['No evaluado', 'not_assessed', counts.not_assessed || 0],
    ];
    const max = Math.max(1, ...rows.map((item) => item[2]));
    $('riskDistribution').innerHTML = rows.map(([label, key, value]) => `
      <button class="agent-row interactive-row" data-risk="${key}">
        <strong>${label}</strong>
        <div class="agent-bar"><i style="width:${Math.max(value ? 8 : 0, value * 100 / max)}%"></i></div>
        <div class="agent-rate">${int(value)}</div>
      </button>`).join('');
  }

  function renderAutonomy() {
    const counts = countBy(state.agents, autonomyOf);
    const levels = ['l0', 'l1', 'l2', 'l3', 'l4', 'not_assessed'];
    $('autonomyDistribution').innerHTML = levels.map((level) => `
      <button class="compact-row interactive-row" data-autonomy="${level}">
        <div><strong>${esc(statusLabel(level))}</strong><span>${level === 'not_assessed' ? 'Pendiente de declaración' : 'Nivel de autonomía declarado'}</span></div>
        <b>${int(counts[level] || 0)}</b>
      </button>`).join('');
  }

  function governanceChip(status) {
    const normalized = String(status || 'not_assessed').toLowerCase();
    const className = normalized === 'governed' ? '' : normalized === 'action_required' ? 'failed' : 'running';
    return `<span class="status-chip ${className}">${esc(statusLabel(normalized))}</span>`;
  }

  function renderAgents() {
    $('agentCountBadge').textContent = `${state.agents.length} agentes`;
    $('agentsTable').innerHTML = state.agents.length ? state.agents.map((agent) => {
      const profile = profileOf(agent);
      const score = profile.last_assessment?.score;
      const deploymentCount = Array.isArray(agent.deployments) ? agent.deployments.length : Array.isArray(agent.bindings) ? agent.bindings.length : 0;
      return `<tr class="run-row" data-agent-id="${esc(agent.agent_id)}">
        <td><strong>${esc(agent.canonical_name)}</strong><small>${esc(agent.agent_id)}</small></td>
        <td>${governanceChip(governanceStatusOf(agent))}</td>
        <td>${esc(profile.business_owner || 'No definido')}</td>
        <td>${esc(profile.technical_owner || 'No definido')}</td>
        <td>${esc(statusLabel(riskOf(agent)))}</td>
        <td>${esc(statusLabel(autonomyOf(agent)))}</td>
        <td>${score == null ? 'No evaluado' : `${esc(score)}%`}</td>
        <td>${int(deploymentCount)}</td>
      </tr>`;
    }).join('') : '<tr><td colspan="8" class="empty-state">Aún no existen identidades lógicas gobernadas.</td></tr>';
  }

  function findingSeverityClass(finding) {
    return /critical|high|error/i.test(text(finding.severity, '')) ? text(finding.severity, '').toLowerCase() : '';
  }

  function renderFindings() {
    const findings = [...state.findings].sort((a, b) => {
      const ao = String(a.status).toLowerCase() === 'open' ? 0 : 1;
      const bo = String(b.status).toLowerCase() === 'open' ? 0 : 1;
      return ao - bo || String(b.detected_at || '').localeCompare(String(a.detected_at || ''));
    });
    const open = findings.filter((item) => String(item.status).toLowerCase() === 'open').length;
    $('findingsBadge').textContent = `${open} abiertos`;
    $('findingsList').innerHTML = findings.length ? findings.slice(0, 8).map((finding) => `
      <button class="alert-row interactive-row" data-finding-id="${esc(finding.finding_id)}">
        <div class="alert-icon ${findingSeverityClass(finding)}">!</div>
        <div><strong>${esc(finding.title || 'Hallazgo de gobierno')}</strong><span>${esc(text(finding.policy_id, 'Sin política'))}${finding.policy_version ? ` @${esc(finding.policy_version)}` : ''} · ${esc(statusLabel(finding.status))}</span></div>
        <small>${esc(text(finding.severity, 'info'))}</small>
      </button>`).join('') : '<div class="empty-state">No hay hallazgos registrados.</div>';
  }

  function renderReviews() {
    const rows = state.agents.map((agent) => {
      const profile = profileOf(agent);
      const status = governanceStatusOf(agent);
      const ok = status === 'governed';
      return `<button class="health-row interactive-row" data-agent-id="${esc(agent.agent_id)}">
        <i class="health-dot ${ok ? '' : 'warn'}"></i>
        <div><strong>${esc(agent.canonical_name)}</strong><span>${esc(statusLabel(status))}</span></div>
        <small>${esc(humanDate(profile.next_review_at))}</small>
      </button>`;
    });
    const pending = state.agents.filter((agent) => governanceStatusOf(agent) !== 'governed').length;
    $('reviewBadge').textContent = pending ? `${pending} pendientes` : 'CONFORME';
    $('reviewList').innerHTML = rows.length ? rows.join('') : '<div class="empty-state">Sin agentes para revisar.</div>';
  }

  function policyRefsFor(agent) {
    const profile = profileOf(agent);
    const assessmentRefs = Array.isArray(profile.last_assessment?.policy_refs) ? profile.last_assessment.policy_refs : [];
    const declared = Array.isArray(profile.applicable_policies) ? profile.applicable_policies : [];
    return [...new Set([...assessmentRefs, ...declared].filter(Boolean))];
  }

  function renderPolicies() {
    const usage = new Map();
    state.agents.forEach((agent) => {
      policyRefsFor(agent).forEach((ref) => usage.set(ref, (usage.get(ref) || 0) + 1));
    });
    const refs = [...usage.entries()].sort((a, b) => a[0].localeCompare(b[0]));
    $('policyBadge').textContent = `${refs.length} políticas`;
    $('policyRegistry').innerHTML = refs.length ? refs.map(([ref, count]) => {
      const [id, version] = String(ref).split('@');
      return `<button class="agent-card" data-policy-ref="${esc(ref)}">
        <div class="agent-card-header"><strong>${esc(id)}</strong><span class="agent-status"></span></div>
        <p>Política versionada utilizada por el assessment determinístico.</p>
        <div class="agent-meta"><span>Versión ${esc(version || 'activa')}</span><span>${int(count)} agentes</span></div>
        <small>Ver agentes relacionados →</small>
      </button>`;
    }).join('') : '<div class="empty-state">Aún no hay referencias de políticas evaluadas.</div>';
  }

  function renderDeployments() {
    const summary = state.summary || {};
    $('deploymentBadge').textContent = `${int(summary.deployments_unbound || 0)} sin asociar · ${int(state.deployments.length)} total`;
    $('deploymentsList').innerHTML = state.deployments.length ? state.deployments.slice(0, 15).map((deployment) => `
      <button class="compact-row interactive-row" data-deployment-id="${esc(deployment.deployment_id)}">
        <div><strong>${esc(deployment.display_name)}</strong><span>${esc(statusLabel(deployment.binding_status))} · ${esc(text(deployment.deployment_source_kind, 'fuente no disponible'))}</span></div>
        <b>${deployment.binding_status === 'bound' ? '✓' : '→'}</b>
      </button>`).join('') : '<div class="empty-state">No hay deployments ADK observados.</div>';
  }

  function renderAll() {
    renderKpis();
    renderGovernanceState();
    renderRisk();
    renderAutonomy();
    renderAgents();
    renderFindings();
    renderReviews();
    renderPolicies();
    renderDeployments();
    $('lastUpdated').textContent = `Última actualización: ${humanDate(state.summary?.last_observed_at || new Date().toISOString())}`;
    $('backendVersion').textContent = state.health ? `ATLAS API ${text(state.health.version, '')}`.trim() : 'ATLAS API';
  }

  function drawerOpen(eyebrow, title, body) {
    $('drawerEyebrow').textContent = eyebrow;
    $('drawerTitle').textContent = title;
    $('drawerBody').innerHTML = body;
    $('detailDrawer').classList.add('open');
    $('drawerBackdrop').classList.add('open');
    $('detailDrawer').setAttribute('aria-hidden', 'false');
    document.body.classList.add('drawer-open');
  }

  function drawerClose() {
    $('detailDrawer').classList.remove('open');
    $('drawerBackdrop').classList.remove('open');
    $('detailDrawer').setAttribute('aria-hidden', 'true');
    document.body.classList.remove('drawer-open');
    if (window.location.hash.startsWith('#agent/') || window.location.hash.startsWith('#deployment/')) history.replaceState(null, '', window.location.pathname + window.location.search);
  }

  function fieldsHtml(fields) {
    return `<div class="detail-fields">${fields.map(([label, value]) => `<div class="detail-field"><span>${esc(label)}</span><strong>${esc(text(value))}</strong></div>`).join('')}</div>`;
  }

  async function openAgentDetail(agentId, updateHash = true) {
    try {
      const payload = await request(`/agent-governance/agents/${encodeURIComponent(agentId)}`);
      const agent = payload.agent || {};
      const profile = profileOf(agent);
      const assessment = profile.last_assessment || {};
      const policies = policyRefsFor(agent);
      const findings = Array.isArray(agent.findings) ? agent.findings : state.findings.filter((item) => item.agent_id === agentId);
      const deployments = Array.isArray(agent.deployments) ? agent.deployments : [];
      const body = `
        <div class="detail-agent-title"><div class="detail-agent-icon">AG</div><div><h3>${esc(agent.canonical_name)}</h3><p>${esc(text(agent.description, 'Identidad lógica gobernada por el control plane de ATLAS.'))}</p></div></div>
        <div class="detail-metrics">
          <div class="detail-metric"><span>Gobierno</span><strong>${esc(statusLabel(governanceStatusOf(agent)))}</strong></div>
          <div class="detail-metric"><span>Score</span><strong>${assessment.score == null ? 'No evaluado' : `${esc(assessment.score)}%`}</strong></div>
          <div class="detail-metric"><span>Riesgo</span><strong>${esc(statusLabel(riskOf(agent)))}</strong></div>
          <div class="detail-metric"><span>Autonomía</span><strong>${esc(statusLabel(autonomyOf(agent)))}</strong></div>
        </div>
        <section class="detail-section"><h3>Responsabilidad</h3>${fieldsHtml([
          ['Business Owner', profile.business_owner], ['Technical Owner', profile.technical_owner],
          ['Área', profile.business_area], ['Ambiente', profile.environment],
          ['Criticidad', statusLabel(profile.business_criticality)], ['Supervisión humana', statusLabel(profile.human_oversight)]
        ])}</section>
        <section class="detail-section"><h3>Propósito</h3><div class="detail-note">${esc(text(profile.business_purpose, 'Propósito no definido.'))}</div></section>
        <section class="detail-section"><h3>Políticas aplicables</h3><div class="tool-tags">${policies.length ? policies.map((ref) => `<span>${esc(ref)}</span>`).join('') : '<span>No evaluadas</span>'}</div></section>
        <section class="detail-section"><h3>Controles con evidencia</h3><div class="tool-tags">${Array.isArray(profile.required_controls) && profile.required_controls.length ? profile.required_controls.map((control) => `<span>${esc(control)}</span>`).join('') : '<span>Sin evidencia registrada</span>'}</div></section>
        <section class="detail-section"><h3>Hallazgos</h3><div class="detail-run-list">${findings.length ? findings.map((finding) => `<div class="detail-run-link"><div><strong>${esc(finding.title)}</strong><span>${esc(text(finding.policy_id, 'Sin política'))} · ${esc(statusLabel(finding.status))}</span></div><b>${esc(text(finding.severity, 'info'))}</b></div>`).join('') : '<div class="empty-state">Sin hallazgos.</div>'}</div></section>
        <section class="detail-section"><h3>Deployments asociados</h3><div class="detail-run-list">${deployments.length ? deployments.map((deployment) => `<button class="detail-run-link" data-deployment-id="${esc(deployment.deployment_id)}"><div><strong>${esc(deployment.display_name)}</strong><span>${esc(deployment.provider_deployment_id || deployment.deployment_id)}</span></div><b>${esc(statusLabel(deployment.binding_status || 'bound'))}</b></button>`).join('') : '<div class="empty-state">Sin deployments asociados.</div>'}</div></section>
        <div class="detail-callout ${governanceStatusOf(agent) === 'governed' ? 'ok' : 'warn'}"><strong>${governanceStatusOf(agent) === 'governed' ? 'Gobierno conforme' : 'Requiere atención'}</strong><span>La decisión de gobierno se basa en checks determinísticos y evidencia versionada; el runtime ADK no se modifica.</span></div>
      `;
      drawerOpen(agent.agent_id, agent.canonical_name, body);
      if (updateHash) history.replaceState(null, '', `#agent/${encodeURIComponent(agent.agent_id)}`);
    } catch (error) { showError(error); }
  }

  function openDeploymentDetail(deploymentId, updateHash = true) {
    const deployment = state.deployments.find((item) => item.deployment_id === deploymentId);
    if (!deployment) return;
    const body = `
      <div class="detail-callout warn"><strong>Detalle técnico secundario</strong><span>Este Reasoning Engine es una versión técnica observada. No representa por sí solo una identidad lógica de agente.</span></div>
      <section class="detail-section"><h3>Recurso observado</h3>${fieldsHtml([
        ['Nombre', deployment.display_name], ['Framework', 'Google ADK'],
        ['Provider ID', deployment.provider_deployment_id], ['Binding', statusLabel(deployment.binding_status)],
        ['Service Account', deployment.service_account], ['Source', deployment.deployment_source_kind],
        ['Creado', humanDate(deployment.created_at)], ['Última observación', humanDate(deployment.last_seen_at)]
      ])}</section>
      <section class="detail-section"><h3>Identidad gobernada</h3><div class="detail-note">${deployment.governed_agent_id ? `Asociado a ${esc(deployment.governed_agent_id)}.` : 'Pendiente de asociación humana a una identidad lógica gobernada.'}</div></section>
    `;
    drawerOpen('Deployment ADK observado', deployment.display_name, body);
    if (updateHash) history.replaceState(null, '', `#deployment/${encodeURIComponent(deployment.deployment_id)}`);
  }

  function openFindingDetail(findingId) {
    const finding = state.findings.find((item) => item.finding_id === findingId);
    if (!finding) return;
    drawerOpen('Hallazgo de gobierno', finding.title || finding.finding_id, `
      <div class="detail-metrics">
        <div class="detail-metric"><span>Severidad</span><strong>${esc(text(finding.severity, 'info'))}</strong></div>
        <div class="detail-metric"><span>Estado</span><strong>${esc(statusLabel(finding.status))}</strong></div>
      </div>
      <section class="detail-section"><h3>Trazabilidad</h3>${fieldsHtml([
        ['Finding ID', finding.finding_id], ['Agent ID', finding.agent_id],
        ['Política', finding.policy_id], ['Versión', finding.policy_version],
        ['Detectado', humanDate(finding.detected_at)], ['Resuelto', humanDate(finding.resolved_at)]
      ])}</section>
      <div class="detail-note">${esc(text(finding.description, finding.title))}</div>
    `);
  }

  function showError(error) {
    const message = error instanceof Error ? error.message : String(error);
    $('errorBanner').textContent = `No se pudo completar la operación: ${message}`;
    $('errorBanner').classList.remove('hidden');
  }

  function clearError() { $('errorBanner').classList.add('hidden'); }

  async function loadData() {
    clearError();
    const [health, summary, agentsPayload, deploymentsPayload, findingsPayload] = await Promise.all([
      request('/health'),
      request('/agent-governance/summary'),
      request('/agent-governance/agents'),
      request('/agent-governance/deployments'),
      request('/agent-governance/findings'),
    ]);
    state.health = health;
    state.summary = summary;
    state.agents = agentsPayload.agents || [];
    state.deployments = deploymentsPayload.deployments || [];
    state.findings = findingsPayload.findings || [];
    renderAll();
  }

  async function refreshInventory() {
    const button = $('refreshButton');
    button.disabled = true;
    button.textContent = 'Actualizando...';
    try {
      clearError();
      await request('/agent-governance/discovery/refresh', { method: 'POST' });
      await loadData();
    } catch (error) { showError(error); }
    finally { button.disabled = false; button.textContent = 'Actualizar inventario'; }
  }

  function scrollTo(selector) {
    const target = document.querySelector(selector);
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function handleHash() {
    const hash = window.location.hash;
    if (hash.startsWith('#agent/')) openAgentDetail(decodeURIComponent(hash.slice('#agent/'.length)), false);
    if (hash.startsWith('#deployment/')) openDeploymentDetail(decodeURIComponent(hash.slice('#deployment/'.length)), false);
  }

  document.addEventListener('click', (event) => {
    const target = event.target.closest('button, tr');
    if (!target) return;
    if (target.dataset.scrollTarget) scrollTo(target.dataset.scrollTarget);
    if (target.dataset.agentId) openAgentDetail(target.dataset.agentId);
    if (target.dataset.deploymentId) openDeploymentDetail(target.dataset.deploymentId);
    if (target.dataset.findingId) openFindingDetail(target.dataset.findingId);
    if (target.dataset.kpiDetail === 'agents' || target.dataset.kpiDetail === 'governed') scrollTo('#agents');
    if (target.dataset.kpiDetail === 'action' || target.dataset.kpiDetail === 'findings') scrollTo('#findings');
    if (target.dataset.kpiDetail === 'risk') scrollTo('#risk');
    if (target.dataset.kpiDetail === 'deployments') scrollTo('#deployments');
    if (target.dataset.policyRef) {
      const related = state.agents.filter((agent) => policyRefsFor(agent).includes(target.dataset.policyRef));
      drawerOpen('Política versionada', target.dataset.policyRef, `<section class="detail-section"><h3>Agentes relacionados</h3><div class="detail-run-list">${related.map((agent) => `<button class="detail-run-link" data-agent-id="${esc(agent.agent_id)}"><div><strong>${esc(agent.canonical_name)}</strong><span>${esc(statusLabel(governanceStatusOf(agent)))}</span></div><b>→</b></button>`).join('') || '<div class="empty-state">Sin agentes asociados.</div>'}</div></section>`);
    }
  });

  $('refreshButton').addEventListener('click', refreshInventory);
  $('drawerClose').addEventListener('click', drawerClose);
  $('drawerBackdrop').addEventListener('click', drawerClose);
  window.addEventListener('hashchange', handleHash);
  window.addEventListener('keydown', (event) => { if (event.key === 'Escape') drawerClose(); });

  loadData().then(handleHash).catch(showError);
})();
