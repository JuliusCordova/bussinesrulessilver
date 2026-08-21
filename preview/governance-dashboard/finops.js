(() => {
  'use strict';

  const DEFAULT_API = 'https://silver-refinement-agent-merge-test-mkqutd4koq-uc.a.run.app';
  const params = new URLSearchParams(window.location.search);
  const API_BASE = (params.get('api') || DEFAULT_API).replace(/\/$/, '');

  const $ = (id) => document.getElementById(id);
  const int = (v) => new Intl.NumberFormat('es-PE').format(Number(v || 0));
  const ms = (v) => `${Math.round(Number(v || 0)).toLocaleString('es-PE')} ms`;
  const esc = (v) => String(v ?? '').replace(/[&<>'"]/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
  const shortDate = (value) => {
    const d = new Date(`${value}T12:00:00Z`);
    return Number.isNaN(d.getTime()) ? String(value || '') : new Intl.DateTimeFormat('es-PE', { day:'2-digit', month:'short' }).format(d);
  };

  async function get(path) {
    const response = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${(await response.text()).slice(0, 180)}`);
    return response.json();
  }

  function renderDaily(series) {
    const svg = $('finopsTokenTrend');
    if (!svg) return;
    const rows = Array.isArray(series) ? series : [];
    if (!rows.length) {
      svg.innerHTML = '<text x="380" y="115" text-anchor="middle" fill="#8a93a4" font-size="12">Sin consumo IA Silver registrado en el periodo</text>';
      return;
    }
    const W=760, H=230, PX=48, PY=28;
    const max = Math.max(1, ...rows.map((r) => Number(r.total_tokens || 0)));
    const x=(i)=>PX+(rows.length===1?(W-PX*2)/2:i*((W-PX*2)/(rows.length-1)));
    const y=(v)=>H-PY-(Number(v||0)/max)*(H-PY*2);
    const path=rows.map((r,i)=>`${i?'L':'M'} ${x(i).toFixed(2)} ${y(r.total_tokens).toFixed(2)}`).join(' ');
    const grid=[0,.25,.5,.75,1].map((r)=>{const yy=PY+r*(H-PY*2);return `<line x1="${PX}" y1="${yy}" x2="${W-PX}" y2="${yy}" stroke="#eef0f5"/><text x="${PX-8}" y="${yy+3}" text-anchor="end" fill="#9aa3b3" font-size="9">${int(Math.round(max*(1-r)))}</text>`}).join('');
    const dots=rows.map((r,i)=>`<circle cx="${x(i)}" cy="${y(r.total_tokens)}" r="5" fill="#6b5cff" stroke="#fff" stroke-width="2"><title>${r.call_date}: ${int(r.total_tokens)} tokens · ${int(r.llm_calls)} llamadas</title></circle>`).join('');
    const labels=rows.map((r,i)=>rows.length>8&&i%Math.ceil(rows.length/6)!==0&&i!==rows.length-1?'':`<text x="${x(i)}" y="${H-6}" text-anchor="middle" fill="#8a93a4" font-size="9">${shortDate(r.call_date)}</text>`).join('');
    svg.innerHTML=`${grid}<path d="${path}" fill="none" stroke="#6b5cff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>${dots}${labels}`;
  }

  function renderAgents(rows) {
    const root = $('finopsAgentBars');
    if (!root) return;
    const data = Array.isArray(rows) ? rows : [];
    if (!data.length) {
      root.innerHTML = '<div class="finops-empty">Sin agentes Silver con consumo IA registrado.</div>';
      return;
    }
    const max = Math.max(1, ...data.map((r)=>Number(r.total_tokens||0)));
    root.innerHTML = data.map((r)=>`<div class="finops-agent-row"><div><strong>${esc(r.agent_name)}</strong><span>${int(r.llm_calls)} llamadas · ${ms(r.avg_latency_ms)}</span></div><div class="finops-agent-bar"><i style="width:${Math.max(4,Number(r.total_tokens||0)*100/max)}%"></i></div><b>${int(r.total_tokens)} tokens</b></div>`).join('');
  }

  function renderRuns(rows) {
    const root = $('finopsRuns');
    if (!root) return;
    const data = Array.isArray(rows) ? rows.slice(0, 6) : [];
    root.innerHTML = data.length ? data.map((r)=>`<div class="finops-run"><div><strong>${esc(r.run_id)}</strong><span>${esc((r.agents||[]).join(', '))}</span></div><div><b>${int(r.total_tokens)}</b><span>tokens · ${int(r.llm_calls)} llamadas</span></div></div>`).join('') : '<div class="finops-empty">Sin runs con telemetría IA.</div>';
  }

  async function loadFinOps() {
    const period = Number($('periodSelect')?.value || 14);
    const status = $('finopsStatus');
    if (status) status.textContent = 'Consultando telemetría real…';
    try {
      const [summary,daily,agents,runs] = await Promise.all([
        get(`/agentops/finops/summary?days=${period}`),
        get(`/agentops/finops/daily?days=${period}`),
        get(`/agentops/finops/agents?days=${period}`),
        get(`/agentops/finops/runs?days=${period}&limit=20`),
      ]);
      $('finopsCalls').textContent = int(summary.llm_calls);
      $('finopsTokens').textContent = int(summary.total_tokens);
      $('finopsRunsCount').textContent = int(summary.governed_runs);
      $('finopsLatency').textContent = ms(summary.avg_latency_ms);
      $('finopsCost').textContent = summary.billing_cost_available && summary.cost_usd != null ? `$ ${Number(summary.cost_usd).toFixed(2)}` : 'No disponible';
      $('finopsCostMeta').textContent = summary.billing_cost_available ? 'Cloud Billing Export' : 'Cloud Billing Export no configurado';
      $('finopsPeriodLabel').textContent = `Últimos ${period} días`;
      renderDaily(daily.series);
      renderAgents(agents.agents);
      renderRuns(runs.runs);
      if (status) {
        status.textContent = 'DATOS REALES';
        status.className = 'finops-source-badge live';
      }
    } catch (error) {
      if (status) {
        status.textContent = 'SIN DATOS';
        status.className = 'finops-source-badge unavailable';
      }
      ['finopsCalls','finopsTokens','finopsRunsCount','finopsLatency'].forEach((id)=>{ if($(id)) $(id).textContent='—'; });
      if ($('finopsCost')) $('finopsCost').textContent='No disponible';
      if ($('finopsCostMeta')) $('finopsCostMeta').textContent='No fue posible consultar la fuente';
      if ($('finopsTokenTrend')) $('finopsTokenTrend').innerHTML='<text x="380" y="115" text-anchor="middle" fill="#8a93a4" font-size="12">No fue posible consultar FinOps</text>';
      console.error('FinOps preview:', error);
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    loadFinOps();
    $('periodSelect')?.addEventListener('change', loadFinOps);
    $('refreshButton')?.addEventListener('click', () => setTimeout(loadFinOps, 50));
  });
})();
