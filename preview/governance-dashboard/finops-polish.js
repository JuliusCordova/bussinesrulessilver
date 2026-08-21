(() => {
  'use strict';

  const DEFAULT_API = 'https://silver-refinement-agent-merge-test-mkqutd4koq-uc.a.run.app';
  const params = new URLSearchParams(window.location.search);
  const API_BASE = (params.get('api') || DEFAULT_API).replace(/\/$/, '');
  const $ = (id) => document.getElementById(id);
  const int = (v) => new Intl.NumberFormat('es-PE').format(Number(v || 0));
  const money = (v) => v == null || Number.isNaN(Number(v))
    ? 'No disponible'
    : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(v));
  const dateLabel = (v) => {
    if (!v) return 'sin cobertura';
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? String(v) : new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short', year: 'numeric' }).format(d);
  };
  const execLabel = (status) => {
    if (status === 'WAITING_TEMPORAL_OVERLAP') return 'Pendiente por cobertura';
    if (status === 'DIRECT_ATTRIBUTION_AVAILABLE') return 'Atribución directa parcial';
    if (status === 'BILLING_EXPORT_PENDING') return 'Billing pendiente';
    return status || 'Estado no informado';
  };

  let refreshTimer = null;

  async function getProduct(days) {
    const response = await fetch(`${API_BASE}/agentops/finops/product-attribution?days=${days}`, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  }

  function ensurePanel() {
    const finops = $('finops');
    if (!finops) return null;
    let panel = $('finopsProductAttribution');
    if (!panel) {
      panel = document.createElement('article');
      panel.id = 'finopsProductAttribution';
      panel.className = 'finops-panel finops-product-panel';
    }

    const firstGrid = finops.querySelector('.finops-grid');
    if (firstGrid && panel.parentElement !== finops) finops.insertBefore(panel, firstGrid);
    else if (firstGrid && panel.nextElementSibling !== firstGrid) finops.insertBefore(panel, firstGrid);
    else if (!panel.parentElement) finops.appendChild(panel);

    if (!$('finopsProductState') || !$('finopsProductAttributionBody')) {
      panel.innerHTML = `
        <div class="panel-header compact product-panel-header">
          <div>
            <span class="product-panel-kicker">FINOPS POR PRODUCTO</span>
            <h3>Costo por producto · Business Rules Silver</h3>
            <p>Atribución gobernada con Billing real + evidencia AgentOps. Sin estimaciones sintéticas.</p>
          </div>
          <span id="finopsProductState" class="soft-badge">Consultando…</span>
        </div>
        <div id="finopsProductAttributionBody" class="product-attribution-shell"><div class="finops-empty">Consultando atribución real del producto…</div></div>`;
    }
    return panel;
  }

  function render(payload) {
    const panel = ensurePanel();
    const body = $('finopsProductAttributionBody');
    const stateBadge = $('finopsProductState');
    if (!panel || !body || !stateBadge) return;

    const productCost = money(payload?.product_cost_usd);
    const directCost = money(payload?.direct_cost_usd);
    const aiCost = money(payload?.attributed_ai_cost_usd);
    const coverage = payload?.attribution_coverage_pct == null ? 0 : Number(payload.attribution_coverage_pct);
    const waiting = payload?.status === 'WAITING_TEMPORAL_OVERLAP' || payload?.status === 'BILLING_EXPORT_PENDING';
    const statusText = execLabel(payload?.status);
    const billingLast = dateLabel(payload?.billing_last_usage_at);
    const silverFirst = dateLabel(payload?.silver_first_call_at);

    stateBadge.textContent = statusText;
    stateBadge.className = `soft-badge ${waiting ? 'pending' : 'live'}`;
    body.className = 'product-attribution-shell';
    body.innerHTML = `
      <div class="product-attribution-kpis">
        <div class="product-cost-card primary ${payload?.product_cost_usd == null ? 'pending' : ''}"><span>Costo producto</span><strong id="finopsProductCostValue">${productCost}</strong><small>${payload?.product_cost_usd == null ? 'Atribución pendiente' : 'Costo atribuido Silver'}</small></div>
        <div class="product-cost-card"><span>Costo directo</span><strong>${directCost}</strong><small>Recursos identificables con evidencia alta</small></div>
        <div class="product-cost-card"><span>Costo IA atribuido</span><strong>${aiCost}</strong><small>Solo con overlap temporal validado</small></div>
        <div class="product-cost-card"><span>Cobertura</span><strong>${coverage.toFixed(1)}%</strong><small>Billing vs AgentOps</small></div>
        <div class="product-cost-card ${waiting ? 'pending' : ''}"><span>Confianza</span><strong>${payload?.confidence || 'PENDING'}</strong><small>${payload?.temporal_overlap ? 'Solapamiento disponible' : 'Sin solapamiento temporal'}</small></div>
      </div>
      <div class="product-attribution-status ${waiting ? 'pending' : 'ready'}">
        <div class="status-icon">${waiting ? '◴' : '✓'}</div>
        <div><strong>${waiting ? 'Atribución pendiente por cobertura temporal' : statusText}</strong><span>Billing disponible hasta ${billingLast} · AgentOps Silver desde ${silverFirst} · ${payload?.temporal_overlap ? 'periodos solapados' : 'sin overlap temporal'}.</span></div>
      </div>
      <div class="product-evidence-row">
        <div class="product-telemetry-strip">
          <span><b>${int(payload?.silver_llm_calls)}</b> llamadas LLM</span>
          <span>·</span><span><b>${int(payload?.silver_governed_runs)}</b> runs</span>
          <span>·</span><span><b>${int(payload?.silver_tokens)}</b> tokens</span>
          <span>·</span><span><b>${payload?.billing_source_available ? 'Billing real' : 'Billing pendiente'}</b> fuente</span>
        </div>
        <div class="coverage-line"><span>0%</span><div class="coverage-track ${coverage > 0 ? 'live' : ''}"><i style="width:${Math.max(0, Math.min(100, coverage))}%"></i></div><span>100%</span></div>
      </div>`;

    window.dispatchEvent(new CustomEvent('finops:product-rendered', { detail: payload }));
  }

  async function refresh() {
    const days = Number($('periodSelect')?.value || 30);
    try {
      render(await getProduct(days));
    } catch (error) {
      ensurePanel();
      const stateBadge = $('finopsProductState');
      const body = $('finopsProductAttributionBody');
      if (stateBadge) {
        stateBadge.textContent = 'No disponible';
        stateBadge.className = 'soft-badge pending';
      }
      if (body) body.innerHTML = '<div class="finops-empty"><strong>Atribución no disponible</strong><span>No fue posible consultar el contrato real por producto.</span></div>';
      console.error('FinOps product polish:', error);
    }
  }

  function scheduleRefresh(delay = 50) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refresh, delay);
  }

  window.addEventListener('DOMContentLoaded', () => {
    ensurePanel();
    scheduleRefresh(250);
    $('periodSelect')?.addEventListener('change', () => scheduleRefresh(250));
    $('refreshButton')?.addEventListener('click', () => scheduleRefresh(350));
  });
})();
