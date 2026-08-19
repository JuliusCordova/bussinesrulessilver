(() => {
  'use strict';

  const DEFAULT_API = 'https://silver-refinement-agent-mkqutd4koq-uc.a.run.app';
  const params = new URLSearchParams(window.location.search);
  const API_BASE = (params.get('api') || DEFAULT_API).replace(/\/$/, '');
  const state = { health: null, dashboard: null, healthMeta: null, summary: null, runs: [], executions: [], alerts: [], unread: 0, agents: [] };
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
    return Number.isNaN(d.getTime()) ? text(value) : new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(d);
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

  function statusClass(status) {
    const s = text(status, 'unknown').toLowerCase();
    if (/fail|error|cancel/.test(s)) return 'failed';
    if (/run/.test(s)) return 'running';
    if (/queue|pend/.test(s)) return 'queued';
    return '';
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
    const dots = points.map(([, v], i) => `<circle cx="${x(i)}" cy="${y(v)}" r="3.6" fill="#7557ff" stroke="#fff" stroke-width="2"><title>${points[i][0]}: ${v} runs</title></circle>`).join('');
    const labels = points.map(([d], i) => {
      if (points.length > 8 && i % Math.ceil(points.length / 6) !== 0 && i !== points.length - 1) return '';
      const label = new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short' }).format(new Date(`${d}T12:00:00`));
      return `<text x="${x(i)}" y="${H - 7}" text-anchor="middle" fill="#8a93a4" font-size="9">${label}</text>`;
    }).join('');
    svg.innerHTML = `<defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#7557ff" stop-opacity=".22"/><stop offset="100%" stop-color="#7557ff" stop-opacity=".02"/></linearGradient></defs>${grid}<path d="${area}" fill="url(#areaFill)"/><path d="${path}" fill="none" stroke="#7557ff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>${dots}${labels}`;
    $('trendLegend').innerHTML = `<span>${int(runs.length)} runs en el periodo observado</span>`;
  }

  function renderTopAgents() {
    const map = new Map();
    runsInPeriod().forEach((r) => {
      const name = text(r.agent_name, 'unknown');
      const item = map.get(name) || { total: 0, success: 0 };
      item.total += 1;
      if (/complete|success|succeed/i.test(text(r.status))) item.success += 1;
      map.set(name, item);
    });
    const rows = [...map.entries()].sort((a, b) => b[1].total - a[1].total).slice(0, 6);
    const max = Math.max(1, ...rows.map(([, v]) => v.total));
    $('agentCountBadge').textContent = `${state.agents.length} agentes`;
    $('topAgents').innerHTML = rows.length ? rows.map(([name, v]) => `<div class="agent-row"><strong title="${esc(name)}">${esc(name)}</strong><div class="agent-bar"><i style="width:${Math.max(5, v.total * 100 / max)}%"></i></div><div class="agent-rate">${v.total} · ${v.total ? Math.round(v.success * 100 / v.total) : 0}%</div></div>`).join('') : '<div class="empty-state">Aún no hay runs por agente.</div>';
  }

  function renderStatus() {
    const c = { success: 0, failed: 0, active: 0, other: 0 };
    runsInPeriod().forEach((r) => {
      const s = text(r.status).toLowerCase();
      if (/complete|success|succeed/.test(s)) c.success += 1;
      else if (/fail|error|cancel/.test(s)) c.failed += 1;
      else if (/run|queue|pend/.test(s)) c.active += 1;
      else c.other += 1;
    });
    const seg = [['Completadas', c.success, '#1aa36f'], ['Fallidas', c.failed, '#d94a53'], ['En curso', c.active, '#7557ff'], ['Otros', c.other, '#20a7c9']];
    const total = seg.reduce((n, [, v]) => n + v, 0);
    let cursor = 0;
    const stops = seg.map(([, v, color]) => { const start = cursor; cursor += total ? v * 100 / total : 0; return `${color} ${start.toFixed(1)}% ${cursor.toFixed(1)}%`; }).join(', ');
    $('statusDonut').style.background = total ? `conic-gradient(${stops})` : '#eef0f5';
    $('donutTotal').textContent = int(total);
    $('statusLegend').innerHTML = seg.map(([name, v, color]) => `<div class="status-item"><i style="background:${color}"></i><span>${name}</span><b>${int(v)}</b></div>`).join('');
  }

  function renderRuns() {
    $('runsTable').innerHTML = state.runs.length ? state.runs.slice(0, 50).map((r) => `<tr><td><strong>${esc(r.agent_name)}</strong><small title="${esc(r.run_id)}">${esc(r.run_id)}</small></td><td><span class="status-chip ${statusClass(r.status)}">${esc(r.status)}</span></td><td>${esc(r.source_table)}</td><td>${esc(r.target_table)}</td><td>${esc(r.requested_by)}</td><td>${int(r.event_count)}</td><td>${duration(r.duration_ms)}</td><td>${esc(dateText(r.finished_at))}</td></tr>`).join('') : '<tr><td colspan="8" class="empty-state">Aún no hay ejecuciones agénticas persistidas.</td></tr>';
  }

  function renderHealth() {
    const h = state.healthMeta || {};
    $('healthOverall').textContent = text(h.overall_status, 'PENDIENTE');
    $('healthOverall').style.color = /healthy|ok/i.test(text(h.overall_status)) ? '#118e5e' : '#b8750d';
    const components = Array.isArray(h.components) ? h.components : [];
    $('healthList').innerHTML = components.length ? components.map((c) => {
      const ok = /healthy|ok|operat|up|ready/i.test(text(c.status));
      return `<div class="health-row"><i class="health-dot ${ok ? '' : 'warn'}"></i><div><strong>${esc(c.component)}</strong><span>${esc(c.detail)}</span></div><small>${esc(c.status)} · ${duration(c.latency_ms)}</small></div>`;
    }).join('') : '<div class="empty-state">Sin componentes de salud reportados.</div>';
  }

  function renderAlerts() {
    $('alertsBadge').textContent = `${state.unread} sin leer`;
    $('alertsList').innerHTML = state.alerts.length ? state.alerts.slice(0, 7).map((a) => {
      const severity = text(a.severity ?? a.level ?? a.priority, 'INFO').toUpperCase();
      const title = a.title ?? a.type ?? 'Alerta AgentOps';
      const message = a.message ?? a.detail ?? a.description ?? 'Sin detalle';
      const time = a.created_at ?? a.timestamp ?? a.generated_at ?? '';
      const iconClass = /critical|high|error/.test(severity.toLowerCase()) ? severity.toLowerCase() : '';
      return `<div class="alert-row"><div class="alert-icon ${iconClass}">!</div><div><strong>${esc(title)}</strong><span>${esc(message)}</span></div><small>${esc(severity)}${time ? ` · ${esc(dateText(time))}` : ''}</small></div>`;
    }).join('') : '<div class="empty-state">Sin alertas activas.</div>';
  }

  function renderRegistry() {
    $('registryBadge').textContent = `${state.agents.length} registrados`;
    const status = new Map((state.dashboard?.agents || []).map((a) => [a.name, a.status]));
    $('agentRegistry').innerHTML = state.agents.length ? state.agents.map((a) => `<article class="agent-card"><div class="agent-card-header"><strong>${esc(a.name)}</strong><i class="agent-status" title="${esc(status.get(a.name) || 'registrado')}"></i></div><p>${esc(a.purpose)}</p><div class="agent-meta"><span>${esc(a.model)}</span><span>${int(a.deterministic_tools?.length || 0)} tools</span></div></article>`).join('') : '<div class="empty-state">No se pudo recuperar el registro de agentes.</div>';
  }

  function renderExecutions() {
    $('executionBadge').textContent = `${state.executions.length} visibles`;
    $('executionsList').innerHTML = state.executions.length ? state.executions.slice(0, 9).map((e, i) => {
      const id = text(e.execution_id, `execution-${i + 1}`), spec = text(e.spec_id, 'Sin spec'), status = text(e.status, 'N/A');
      return `<div class="compact-row"><div><strong>${esc(id)}</strong><span>${esc(spec)}</span></div><span class="status-chip ${statusClass(status)}">${esc(status)}</span></div>`;
    }).join('') : '<div class="empty-state">Sin ejecuciones recientes.</div>';
  }

  function renderMeta() {
    $('backendHost').textContent = API_BASE.replace(/^https?:\/\//, '');
    $('backendVersion').textContent = state.health?.version ? `v${state.health.version}` : text(state.health?.status, 'Sin versión');
    $('lastUpdated').textContent = `Actualizado: ${new Intl.DateTimeFormat('es-PE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date())}`;
  }

  function renderAll() { renderKpis(); renderTrend(); renderTopAgents(); renderStatus(); renderRuns(); renderHealth(); renderAlerts(); renderRegistry(); renderExecutions(); renderMeta(); }

  async function load() {
    const button = $('refreshButton'), banner = $('errorBanner');
    banner.classList.add('hidden'); button.disabled = true; button.textContent = 'Actualizando...';
    try {
      const [health, dashboard, healthMeta, summary, runs, executions, alerts, agents] = await Promise.all([
        get('/health'), get('/agentops/dashboard'), get('/agentops/health'), get('/agentops/governance/summary'), get('/agentops/governance/runs?limit=100'), get('/agentops/executions?limit=25'), get('/agentops/alerts?limit=25'), get('/silver-agents')
      ]);
      Object.assign(state, { health, dashboard, healthMeta, summary, runs: Array.isArray(runs?.runs) ? runs.runs : [], executions: Array.isArray(executions?.executions) ? executions.executions : [], alerts: Array.isArray(alerts?.alerts) ? alerts.alerts : [], unread: Number(alerts?.unread || 0), agents: Array.isArray(agents) ? agents : [] });
      renderAll();
    } catch (error) {
      console.error(error);
      banner.textContent = `No se pudo cargar AgentOps desde ${API_BASE}. ${error.message}`;
      banner.classList.remove('hidden'); renderAll();
    } finally { button.disabled = false; button.textContent = 'Actualizar tablero'; }
  }

  $('refreshButton').addEventListener('click', load);
  $('periodSelect').addEventListener('change', () => { renderTrend(); renderTopAgents(); renderStatus(); });
  load();
})();
