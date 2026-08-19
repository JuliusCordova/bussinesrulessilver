(() => {
  'use strict';

  const DEFAULT_API = 'https://silver-refinement-agent-mkqutd4koq-uc.a.run.app';
  const params = new URLSearchParams(window.location.search);
  const API_BASE = (params.get('api') || DEFAULT_API).replace(/\/$/, '');
  const state = {
    health: null, dashboard: null, healthMeta: null, summary: null,
    runs: [], executions: [], alerts: [], unread: 0, agents: [],
    filters: { agent: null, status: null, date: null },
  };

  const $ = (id) => document.getElementById(id);
  const int = (v) => new Intl.NumberFormat('es-PE').format(Number(v || 0));
  const pct = (v) => `${Math.round(Number(v || 0))}%`;
  const text = (v, fallback = 'N/A') => v == null || v === '' ? fallback : String(v);
  const esc = (v) => text(v, '').replace(/[&<>'"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));

  const duration = (ms) => {
    const v = Number(ms || 0);
    if (!Number.isFinite(v) || v <= 0) return '0 ms';
    if (v < 1000) return `${Math.round(v)} ms`;
    if (v < 60000) return `${(v / 1000).toFixed(1)} s`;
    return `${(v / 60000).toFixed(1)} min`;
  };

  const dateText = (value) => {
    if (!value) return 'N/A';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? text(value) : new Intl.DateTimeFormat('es-PE', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
    }).format(d);
  };

  const shortDate = (value) => {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? text(value) : new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short' }).format(d);
  };

  async function get(path) {
    const response = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${(await response.text()).slice(0, 180)}`);
    return response.json();
  }

  function percentile(values, p) {
    const clean = values.map(Number).filter((v) => Number.isFinite(v) && v >= 0).sort((a, b) => a - b);
    if (!clean.length) return 0;
    return clean[Math.min(clean.length - 1, Math.max(0, Math.ceil(p / 100 * clean.length) - 1))];
  }

  function statusBucket(status) {
    const s = text(status, 'unknown').toLowerCase();
    if (/complete|success|succeed/.test(s)) return 'success';
    if (/fail|error|cancel/.test(s)) return 'failed';
    if (/run|queue|pend/.test(s)) return 'active';
    return 'other';
  }

  function statusClass(status) {
    const b = statusBucket(status);
    return b === 'success' ? '' : b === 'active' ? 'running' : b;
  }

  function runsInPeriod() {
    const days = Number($('periodSelect').value || 14);
    const min = Date.now() - days * 86400000;
    const filtered = state.runs.filter((r) => {
      const t = new Date(r.finished_at || r.started_at).getTime();
      return Number.isFinite(t) && t >= min;
    });
    return filtered.length ? filtered : state.runs;
  }

  function filteredRuns() {
    return runsInPeriod().filter((r) => {
      if (state.filters.agent && r.agent_name !== state.filters.agent) return false;
      if (state.filters.status && statusBucket(r.status) !== state.filters.status) return false;
      if (state.filters.date) {
        const raw = r.finished_at || r.started_at;
        const d = new Date(raw);
        if (Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== state.filters.date) return false;
      }
      return true;
    });
  }

  function setFilter(key, value) {
    state.filters[key] = state.filters[key] === value ? null : value;
    renderRuns();
    renderFilterBar();
    $('historyPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function clearFilters() {
    state.filters = { agent: null, status: null, date: null };
    renderRuns();
    renderFilterBar();
  }

  function renderFilterBar() {
    const filters = [];
    if (state.filters.agent) filters.push(`<button data-clear-filter="agent">Agente: <b>${esc(state.filters.agent)}</b> ×</button>`);
    if (state.filters.status) filters.push(`<button data-clear-filter="status">Estado: <b>${esc(state.filters.status)}</b> ×</button>`);
    if (state.filters.date) filters.push(`<button data-clear-filter="date">Fecha: <b>${esc(state.filters.date)}</b> ×</button>`);
    $('filterBar').innerHTML = filters.length
      ? `<span>Filtros activos</span>${filters.join('')}<button class="clear-all" id="clearAllFilters">Limpiar todos</button>`
      : '<span>Haz clic en un agente, estado o punto de tendencia para filtrar el historial.</span>';
    $('filterBar').classList.toggle('active', filters.length > 0);
  }

  function renderKpis() {
    const s = state.summary || {};
    const d = state.dashboard || {};
    $('kpiRuns').textContent = int(s.total_runs ?? state.runs.length);
    $('kpiRunsDelta').textContent = `${int(s.runs_today || 0)} hoy · BigQuery persistente`;
    $('kpiAgents').textContent = int(s.active_agents ?? state.agents.length);
    $('kpiAgentsDelta').textContent = `${int(state.agents.length)} agentes registrados`;
    $('kpiSuccess').textContent = pct(d.summary?.success_rate || 0);
    $('kpiSuccessDelta').textContent = `${int(d.summary?.succeeded || 0)} exitosas · ${int(d.summary?.failed || 0)} fallidas`;
    $('kpiP90').textContent = duration(percentile(state.runs.map((r) => r.duration_ms), 90));
    $('kpiAvgDuration').textContent = `Promedio ${duration(s.avg_duration_ms || 0)}`;
    $('kpiArtifacts').textContent = int(d.artifacts?.total_artifacts || 0);
    $('kpiPackages').textContent = `Packages vigentes ${int(d.artifacts?.current_packages || 0)}`;
    $('kpiAlerts').textContent = int(state.unread);
    $('kpiAlertsTotal').textContent = `Total ${int(state.alerts.length)}`;
  }

  function renderTrend() {
    const svg = $('trendChart');
    const runs = runsInPeriod();
    const buckets = new Map();
    runs.forEach((r) => {
      const d = new Date(r.finished_at || r.started_at);
      if (Number.isNaN(d.getTime())) return;
      const key = d.toISOString().slice(0, 10);
      buckets.set(key, (buckets.get(key) || 0) + 1);
    });
    const points = [...buckets.entries()].sort((a, b) => a[0].localeCompare(b[0]));
    if (!points.length) {
      svg.innerHTML = '<text x="380" y="125" text-anchor="middle" fill="#8a93a4" font-size="12">Sin runs persistidos para graficar</text>';
      $('trendLegend').innerHTML = '<span>Runs agénticos</span>';
      return;
    }
    const W = 760, H = 250, PX = 42, PY = 28, max = Math.max(1, ...points.map(([, v]) => v));
    const x = (i) => PX + (points.length === 1 ? (W - PX * 2) / 2 : i * ((W - PX * 2) / (points.length - 1)));
    const y = (v) => H - PY - (v / max) * (H - PY * 2);
    const path = points.map(([, v], i) => `${i ? 'L' : 'M'} ${x(i).toFixed(2)} ${y(v).toFixed(2)}`).join(' ');
    const area = `${path} L ${x(points.length - 1)} ${H - PY} L ${x(0)} ${H - PY} Z`;
    const grid = [0, .25, .5, .75, 1].map((r) => {
      const yy = PY + r * (H - PY * 2);
      return `<line x1="${PX}" y1="${yy}" x2="${W - PX}" y2="${yy}" stroke="#eef0f5"/><text x="${PX - 9}" y="${yy + 3}" text-anchor="end" fill="#9aa3b3" font-size="9">${Math.round(max * (1 - r))}</text>`;
    }).join('');
    const dots = points.map(([date, v], i) => `<circle class="trend-point" data-date="${date}" cx="${x(i)}" cy="${y(v)}" r="5" fill="#7557ff" stroke="#fff" stroke-width="2"><title>${date}: ${v} runs · clic para filtrar</title></circle>`).join('');
    const labels = points.map(([d], i) => {
      if (points.length > 8 && i % Math.ceil(points.length / 6) !== 0 && i !== points.length - 1) return '';
      return `<text x="${x(i)}" y="${H - 7}" text-anchor="middle" fill="#8a93a4" font-size="9">${shortDate(`${d}T12:00:00`)}</text>`;
    }).join('');
    svg.innerHTML = `<defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#7557ff" stop-opacity=".22"/><stop offset="100%" stop-color="#7557ff" stop-opacity=".02"/></linearGradient></defs>${grid}<path d="${area}" fill="url(#areaFill)"/><path d="${path}" fill="none" stroke="#7557ff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>${dots}${labels}`;
    $('trendLegend').innerHTML = `<span>${int(runs.length)} runs en el periodo observado · clic en un punto para filtrar</span>`;
  }

  function renderTopAgents() {
    const map = new Map();
    runsInPeriod().forEach((r) => {
      const name = text(r.agent_name, 'unknown');
      const item = map.get(name) || { total: 0, success: 0, durations: [] };
      item.total += 1;
      item.durations.push(Number(r.duration_ms || 0));
      if (statusBucket(r.status) === 'success') item.success += 1;
      map.set(name, item);
    });
    const rows = [...map.entries()].sort((a, b) => b[1].total - a[1].total).slice(0, 6);
    const max = Math.max(1, ...rows.map(([, v]) => v.total));
    $('agentCountBadge').textContent = `${state.agents.length} agentes`;
    $('topAgents').innerHTML = rows.length ? rows.map(([name, v]) => `<button class="agent-row interactive-row" data-agent="${esc(name)}"><strong title="${esc(name)}">${esc(name)}</strong><div class="agent-bar"><i style="width:${Math.max(5, v.total * 100 / max)}%"></i></div><div class="agent-rate">${v.total} · ${v.total ? Math.round(v.success * 100 / v.total) : 0}%</div></button>`).join('') : '<div class="empty-state">Aún no hay runs por agente.</div>';
  }

  function renderStatus() {
    const c = { success: 0, failed: 0, active: 0, other: 0 };
    runsInPeriod().forEach((r) => { c[statusBucket(r.status)] += 1; });
    const seg = [['Completadas', 'success', c.success, '#1aa36f'], ['Fallidas', 'failed', c.failed, '#d94a53'], ['En curso', 'active', c.active, '#7557ff'], ['Otros', 'other', c.other, '#20a7c9']];
    const total = seg.reduce((n, [, , v]) => n + v, 0);
    let cursor = 0;
    const stops = seg.map(([, , v, color]) => { const start = cursor; cursor += total ? v * 100 / total : 0; return `${color} ${start.toFixed(1)}% ${cursor.toFixed(1)}%`; }).join(', ');
    $('statusDonut').style.background = total ? `conic-gradient(${stops})` : '#eef0f5';
    $('donutTotal').textContent = int(total);
    $('statusLegend').innerHTML = seg.map(([name, bucket, v, color]) => `<button class="status-item interactive-row" data-status="${bucket}"><i style="background:${color}"></i><span>${name}</span><b>${int(v)}</b></button>`).join('');
  }

  function renderRuns() {
    const runs = filteredRuns();
    $('historyCount').textContent = `${runs.length} visibles`;
    $('runsTable').innerHTML = runs.length ? runs.slice(0, 50).map((r) => `<tr class="run-row" data-run-id="${esc(r.run_id)}"><td><strong>${esc(r.agent_name)}</strong><small title="${esc(r.run_id)}">${esc(r.run_id)}</small></td><td><span class="status-chip ${statusClass(r.status)}">${esc(r.status)}</span></td><td>${esc(r.source_table)}</td><td>${esc(r.target_table)}</td><td>${esc(r.requested_by)}</td><td>${int(r.event_count)}</td><td>${duration(r.duration_ms)}</td><td>${esc(dateText(r.finished_at))}</td></tr>`).join('') : '<tr><td colspan="8" class="empty-state">No hay runs para los filtros seleccionados.</td></tr>';
  }

  function renderHealth() {
    const h = state.healthMeta || {};
    $('healthOverall').textContent = text(h.overall_status, 'PENDIENTE');
    $('healthOverall').style.color = /healthy|ok/i.test(text(h.overall_status)) ? '#118e5e' : '#b8750d';
    const components = Array.isArray(h.components) ? h.components : [];
    $('healthList').innerHTML = components.length ? components.map((c, index) => {
      const ok = /healthy|ok|operat|up|ready/i.test(text(c.status));
      return `<button class="health-row interactive-row" data-health-index="${index}"><i class="health-dot ${ok ? '' : 'warn'}"></i><div><strong>${esc(c.component)}</strong><span>${esc(c.detail)}</span></div><small>${esc(c.status)} · ${duration(c.latency_ms)}</small></button>`;
    }).join('') : '<div class="empty-state">Sin componentes de salud reportados.</div>';
  }

  function renderAlerts() {
    $('alertsBadge').textContent = `${state.unread} sin leer`;
    $('alertsList').innerHTML = state.alerts.length ? state.alerts.slice(0, 7).map((a, index) => {
      const severity = text(a.severity ?? a.level ?? a.priority, 'INFO').toUpperCase();
      const title = a.title ?? a.type ?? 'Alerta AgentOps';
      const message = a.message ?? a.detail ?? a.description ?? 'Sin detalle';
      const time = a.created_at ?? a.timestamp ?? a.generated_at ?? '';
      const iconClass = /critical|high|error/.test(severity.toLowerCase()) ? severity.toLowerCase() : '';
      return `<button class="alert-row interactive-row" data-alert-index="${index}"><div class="alert-icon ${iconClass}">!</div><div><strong>${esc(title)}</strong><span>${esc(message)}</span></div><small>${esc(severity)}${time ? ` · ${esc(shortDate(time))}` : ''}</small></button>`;
    }).join('') : '<div class="empty-state">Sin alertas activas.</div>';
  }

  function renderRegistry() {
    $('registryBadge').textContent = `${state.agents.length} registrados`;
    const status = new Map((state.dashboard?.agents || []).map((a) => [a.name, a.status]));
    $('agentRegistry').innerHTML = state.agents.length ? state.agents.map((a) => `<button class="agent-card" data-agent-detail="${esc(a.name)}"><div class="agent-card-header"><strong>${esc(a.name)}</strong><i class="agent-status" title="${esc(status.get(a.name) || 'registrado')}"></i></div><p>${esc(a.purpose)}</p><div class="agent-meta"><span>${esc(a.model)}</span><span>${int(a.deterministic_tools?.length || 0)} tools</span></div><small>Ver detalle →</small></button>`).join('') : '<div class="empty-state">No se pudo recuperar el registro de agentes.</div>';
  }

  function renderExecutions() {
    $('executionBadge').textContent = `${state.executions.length} visibles`;
    $('executionsList').innerHTML = state.executions.length ? state.executions.slice(0, 9).map((e, i) => {
      const id = text(e.execution_id, `execution-${i + 1}`), spec = text(e.spec_id, 'Sin spec'), status = text(e.status, 'N/A');
      return `<button class="compact-row interactive-row" data-execution-index="${i}"><div><strong>${esc(id)}</strong><span>${esc(spec)}</span></div><span class="status-chip ${statusClass(status)}">${esc(status)}</span></button>`;
    }).join('') : '<div class="empty-state">Sin ejecuciones recientes.</div>';
  }

  function renderMeta() {
    $('backendHost').textContent = API_BASE.replace(/^https?:\/\//, '');
    $('backendVersion').textContent = state.health?.version ? `v${state.health.version}` : text(state.health?.status, 'Sin versión');
    $('lastUpdated').textContent = `Actualizado: ${new Intl.DateTimeFormat('es-PE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date())}`;
  }

  function detailMetric(label, value) {
    return `<div class="detail-metric"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
  }

  function detailField(label, value) {
    return `<div class="detail-field"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
  }

  function openDrawer(title, eyebrow, body, hash) {
    $('drawerTitle').textContent = title;
    $('drawerEyebrow').textContent = eyebrow;
    $('drawerBody').innerHTML = body;
    $('detailDrawer').classList.add('open');
    $('drawerBackdrop').classList.add('open');
    document.body.classList.add('drawer-open');
    if (hash) history.replaceState(null, '', `${location.pathname}${location.search}#${hash}`);
  }

  function closeDrawer() {
    $('detailDrawer').classList.remove('open');
    $('drawerBackdrop').classList.remove('open');
    document.body.classList.remove('drawer-open');
    if (location.hash) history.replaceState(null, '', `${location.pathname}${location.search}`);
  }

  function openRunDetail(run) {
    if (!run) return;
    const error = run.error_message ? `<div class="detail-callout error"><strong>Error reportado</strong><span>${esc(run.error_message)}</span></div>` : '<div class="detail-callout ok"><strong>Sin error reportado</strong><span>El registro persistente no contiene error_message.</span></div>';
    const body = `
      <div class="detail-hero"><div><span>Estado</span><strong class="status-chip ${statusClass(run.status)}">${esc(run.status)}</strong></div><div><span>Agente</span><strong>${esc(run.agent_name)}</strong></div></div>
      <div class="detail-metrics">${detailMetric('Eventos', int(run.event_count))}${detailMetric('Duración', duration(run.duration_ms))}${detailMetric('Inicio', dateText(run.started_at))}${detailMetric('Fin', dateText(run.finished_at))}</div>
      <section class="detail-section"><h3>Trazabilidad</h3><div class="detail-fields">${detailField('Run ID', run.run_id)}${detailField('Session ID', run.session_id)}${detailField('Solicitado por', run.requested_by)}${detailField('Origen Bronze', run.source_table)}${detailField('Destino Silver', run.target_table)}</div></section>
      <section class="detail-section"><h3>Timeline operacional</h3><div class="timeline"><div><i></i><strong>Run iniciado</strong><span>${esc(dateText(run.started_at))}</span></div><div><i></i><strong>${int(run.event_count)} eventos procesados</strong><span>Eventos registrados por Gemini ADK / AgentOps</span></div><div><i></i><strong>Run finalizado · ${esc(run.status)}</strong><span>${esc(dateText(run.finished_at))}</span></div></div></section>
      ${error}
      <div class="detail-note">Preview: esta vista usa exclusivamente el contrato persistente actual. El siguiente nivel puede exponer evidence JSON completo desde BigQuery.</div>`;
    openDrawer('Detalle del run', 'AgentOps · ejecución agéntica persistente', body, `run/${encodeURIComponent(run.run_id)}`);
  }

  function openAgentDetail(name) {
    const agent = state.agents.find((a) => a.name === name);
    if (!agent) return;
    const runs = state.runs.filter((r) => r.agent_name === name);
    const successes = runs.filter((r) => statusBucket(r.status) === 'success').length;
    const failures = runs.filter((r) => statusBucket(r.status) === 'failed').length;
    const avg = runs.length ? runs.reduce((sum, r) => sum + Number(r.duration_ms || 0), 0) / runs.length : 0;
    const tools = Array.isArray(agent.deterministic_tools) && agent.deterministic_tools.length ? agent.deterministic_tools.map((t) => `<span>${esc(t)}</span>`).join('') : '<span>Sin tools determinísticas declaradas</span>';
    const recent = runs.slice(0, 8).map((r) => `<button class="detail-run-link" data-run-id="${esc(r.run_id)}"><div><strong>${esc(r.run_id)}</strong><span>${esc(r.source_table)} → ${esc(r.target_table)}</span></div><span class="status-chip ${statusClass(r.status)}">${esc(r.status)}</span></button>`).join('') || '<div class="empty-state">Sin runs persistidos para este agente.</div>';
    const body = `
      <div class="detail-agent-title"><div class="detail-agent-icon">AI</div><div><h3>${esc(agent.name)}</h3><p>${esc(agent.purpose)}</p></div></div>
      <div class="detail-metrics">${detailMetric('Runs', int(runs.length))}${detailMetric('Éxito', runs.length ? `${Math.round(successes * 100 / runs.length)}%` : '0%')}${detailMetric('Fallidas', int(failures))}${detailMetric('Duración media', duration(avg))}</div>
      <section class="detail-section"><h3>Configuración ADK</h3><div class="detail-fields">${detailField('Modelo', agent.model)}${detailField('Estado', state.dashboard?.agents?.find((a) => a.name === name)?.status || 'Registrado')}</div><div class="tool-tags">${tools}</div></section>
      <section class="detail-section"><h3>Runs recientes</h3><div class="detail-run-list">${recent}</div></section>`;
    openDrawer(agent.name, 'Gemini ADK · agente especializado', body, `agent/${encodeURIComponent(name)}`);
  }

  function openExecutionDetail(index) {
    const e = state.executions[index];
    if (!e) return;
    const fields = Object.entries(e).slice(0, 18).map(([k, v]) => detailField(k.replace(/_/g, ' '), typeof v === 'object' ? JSON.stringify(v) : text(v))).join('');
    openDrawer(text(e.execution_id, 'Ejecución Silver'), 'AgentOps · ejecución del pipeline', `<div class="detail-metrics">${detailMetric('Estado', text(e.status))}${detailMetric('Spec', text(e.spec_id))}</div><section class="detail-section"><h3>Contrato observado</h3><div class="detail-fields">${fields}</div></section>`, `execution/${encodeURIComponent(text(e.execution_id, index))}`);
  }

  function openAlertDetail(index) {
    const a = state.alerts[index];
    if (!a) return;
    const severity = text(a.severity ?? a.level ?? a.priority, 'INFO').toUpperCase();
    const title = text(a.title ?? a.type, 'Alerta AgentOps');
    const fields = Object.entries(a).slice(0, 20).map(([k, v]) => detailField(k.replace(/_/g, ' '), typeof v === 'object' ? JSON.stringify(v) : text(v))).join('');
    openDrawer(title, `AgentOps · alerta ${severity}`, `<div class="detail-callout ${/critical|high|error/i.test(severity) ? 'error' : 'warn'}"><strong>${esc(severity)}</strong><span>${esc(text(a.message ?? a.detail ?? a.description, 'Sin detalle'))}</span></div><section class="detail-section"><h3>Detalle registrado</h3><div class="detail-fields">${fields}</div></section>`, `alert/${index}`);
  }

  function openHealthDetail(index) {
    const c = state.healthMeta?.components?.[index];
    if (!c) return;
    const body = `<div class="detail-metrics">${detailMetric('Estado', text(c.status))}${detailMetric('Latencia', duration(c.latency_ms))}</div><section class="detail-section"><h3>Componente</h3><div class="detail-fields">${detailField('Nombre', c.component)}${detailField('Detalle', c.detail)}${detailField('Chequeado', state.healthMeta?.checked_at ? dateText(state.healthMeta.checked_at) : 'N/A')}</div></section>`;
    openDrawer(text(c.component), 'Salud de plataforma · AgentOps', body, `health/${index}`);
  }

  function openKpiDetail(kind) {
    const d = state.dashboard || {}, s = state.summary || {};
    const bodies = {
      runs: `<div class="detail-metrics">${detailMetric('Total', int(s.total_runs || state.runs.length))}${detailMetric('Hoy', int(s.runs_today || 0))}${detailMetric('Completados', int(s.completed || 0))}${detailMetric('Fallidos', int(s.failed || 0))}</div><section class="detail-section"><h3>Últimos runs</h3><div class="detail-run-list">${state.runs.slice(0, 10).map((r) => `<button class="detail-run-link" data-run-id="${esc(r.run_id)}"><div><strong>${esc(r.agent_name)}</strong><span>${esc(r.run_id)}</span></div><span class="status-chip ${statusClass(r.status)}">${esc(r.status)}</span></button>`).join('')}</div></section>`,
      agents: `<div class="detail-metrics">${detailMetric('Activos', int(s.active_agents || 0))}${detailMetric('Registrados', int(state.agents.length))}</div><section class="detail-section"><h3>Registro ADK</h3><div class="detail-run-list">${state.agents.map((a) => `<button class="detail-run-link" data-agent-detail="${esc(a.name)}"><div><strong>${esc(a.name)}</strong><span>${esc(a.purpose)}</span></div><span>→</span></button>`).join('')}</div></section>`,
      success: `<div class="detail-metrics">${detailMetric('Tasa', pct(d.summary?.success_rate || 0))}${detailMetric('Exitosas', int(d.summary?.succeeded || 0))}${detailMetric('Fallidas', int(d.summary?.failed || 0))}${detailMetric('Running', int(d.summary?.running || 0))}</div><div class="detail-note">Haz clic en el donut del dashboard para filtrar el historial por categoría de estado.</div>`,
      performance: `<div class="detail-metrics">${detailMetric('p90', duration(percentile(state.runs.map((r) => r.duration_ms), 90)))}${detailMetric('Promedio', duration(s.avg_duration_ms || 0))}${detailMetric('Runs medidos', int(state.runs.length))}</div><section class="detail-section"><h3>Runs más lentos</h3><div class="detail-run-list">${[...state.runs].sort((a, b) => Number(b.duration_ms || 0) - Number(a.duration_ms || 0)).slice(0, 8).map((r) => `<button class="detail-run-link" data-run-id="${esc(r.run_id)}"><div><strong>${esc(r.agent_name)}</strong><span>${esc(r.run_id)}</span></div><b>${duration(r.duration_ms)}</b></button>`).join('')}</div></section>`,
      artifacts: `<div class="detail-metrics">${detailMetric('Artefactos', int(d.artifacts?.total_artifacts || 0))}${detailMetric('Packages vigentes', int(d.artifacts?.current_packages || 0))}${detailMetric('Última versión', int(d.artifacts?.latest_package_version || 0))}</div><div class="detail-note">El preview muestra el agregado AgentOps actual. El drill-down por spec_id y descarga individual puede conectarse después a los endpoints de artefactos existentes.</div>`,
      alerts: `<div class="detail-metrics">${detailMetric('Sin leer', int(state.unread))}${detailMetric('Total cargadas', int(state.alerts.length))}</div><section class="detail-section"><h3>Alertas recientes</h3><div class="detail-run-list">${state.alerts.map((a, i) => `<button class="detail-run-link" data-alert-index="${i}"><div><strong>${esc(text(a.title ?? a.type, 'Alerta'))}</strong><span>${esc(text(a.message ?? a.detail ?? a.description, 'Sin detalle'))}</span></div><span>→</span></button>`).join('')}</div></section>`,
    };
    const titles = { runs: 'Runs agénticos', agents: 'Agentes activos', success: 'Tasa de éxito', performance: 'Rendimiento', artifacts: 'Artefactos', alerts: 'Alertas AgentOps' };
    openDrawer(titles[kind] || 'Detalle', 'Gobierno DataOps · indicador ejecutivo', bodies[kind] || '<div class="empty-state">Sin detalle disponible.</div>', `kpi/${kind}`);
  }

  function renderAll() {
    renderKpis(); renderTrend(); renderTopAgents(); renderStatus(); renderRuns();
    renderHealth(); renderAlerts(); renderRegistry(); renderExecutions(); renderMeta(); renderFilterBar();
  }

  function handleInteractiveClick(event) {
    const run = event.target.closest('[data-run-id]');
    if (run) { openRunDetail(state.runs.find((r) => r.run_id === run.dataset.runId)); return; }
    const agentDetail = event.target.closest('[data-agent-detail]');
    if (agentDetail) { openAgentDetail(agentDetail.dataset.agentDetail); return; }
    const agent = event.target.closest('[data-agent]');
    if (agent) { setFilter('agent', agent.dataset.agent); openAgentDetail(agent.dataset.agent); return; }
    const status = event.target.closest('[data-status]');
    if (status) { setFilter('status', status.dataset.status); return; }
    const trend = event.target.closest('[data-date]');
    if (trend) { setFilter('date', trend.dataset.date); return; }
    const alert = event.target.closest('[data-alert-index]');
    if (alert) { openAlertDetail(Number(alert.dataset.alertIndex)); return; }
    const execution = event.target.closest('[data-execution-index]');
    if (execution) { openExecutionDetail(Number(execution.dataset.executionIndex)); return; }
    const health = event.target.closest('[data-health-index]');
    if (health) { openHealthDetail(Number(health.dataset.healthIndex)); return; }
    const kpi = event.target.closest('[data-kpi-detail]');
    if (kpi) { openKpiDetail(kpi.dataset.kpiDetail); return; }
    const clear = event.target.closest('[data-clear-filter]');
    if (clear) { state.filters[clear.dataset.clearFilter] = null; renderRuns(); renderFilterBar(); return; }
    if (event.target.closest('#clearAllFilters')) { clearFilters(); return; }
    const nav = event.target.closest('[data-scroll-target]');
    if (nav) {
      document.querySelector(nav.dataset.scrollTarget)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      document.querySelectorAll('.nav-item').forEach((n) => n.classList.toggle('active', n === nav));
    }
  }

  function openHashDetail() {
    if (!location.hash) return;
    const raw = location.hash.slice(1);
    const [kind, value] = raw.split('/');
    const decoded = value ? decodeURIComponent(value) : '';
    if (kind === 'run') openRunDetail(state.runs.find((r) => r.run_id === decoded));
    else if (kind === 'agent') openAgentDetail(decoded);
    else if (kind === 'execution') openExecutionDetail(state.executions.findIndex((e) => text(e.execution_id) === decoded));
    else if (kind === 'alert') openAlertDetail(Number(value));
    else if (kind === 'health') openHealthDetail(Number(value));
    else if (kind === 'kpi') openKpiDetail(decoded);
  }

  async function load() {
    const button = $('refreshButton'), banner = $('errorBanner');
    banner.classList.add('hidden'); button.disabled = true; button.textContent = 'Actualizando...';
    try {
      const [health, dashboard, healthMeta, summary, runs, executions, alerts, agents] = await Promise.all([
        get('/health'), get('/agentops/dashboard'), get('/agentops/health'), get('/agentops/governance/summary'),
        get('/agentops/governance/runs?limit=100'), get('/agentops/executions?limit=25'), get('/agentops/alerts?limit=25'), get('/silver-agents')
      ]);
      Object.assign(state, {
        health, dashboard, healthMeta, summary,
        runs: Array.isArray(runs?.runs) ? runs.runs : [],
        executions: Array.isArray(executions?.executions) ? executions.executions : [],
        alerts: Array.isArray(alerts?.alerts) ? alerts.alerts : [],
        unread: Number(alerts?.unread || 0),
        agents: Array.isArray(agents) ? agents : []
      });
      renderAll();
      openHashDetail();
    } catch (error) {
      console.error(error);
      banner.textContent = `No se pudo cargar AgentOps desde ${API_BASE}. ${error.message}`;
      banner.classList.remove('hidden'); renderAll();
    } finally {
      button.disabled = false; button.textContent = 'Actualizar tablero';
    }
  }

  $('refreshButton').addEventListener('click', load);
  $('periodSelect').addEventListener('change', () => { clearFilters(); renderTrend(); renderTopAgents(); renderStatus(); });
  $('drawerClose').addEventListener('click', closeDrawer);
  $('drawerBackdrop').addEventListener('click', closeDrawer);
  document.addEventListener('click', handleInteractiveClick);
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeDrawer(); });
  window.addEventListener('hashchange', openHashDetail);
  load();
})();
