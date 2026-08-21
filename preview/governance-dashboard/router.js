(() => {
  'use strict';

  const VIEW_META = {
    overview: {
      label: 'Resumen ejecutivo',
      title: 'Gobierno DataOps — Business Rules Silver',
      subtitle: 'Observabilidad, trazabilidad y gobierno del refinamiento Bronze → Silver.',
      eyebrow: 'Gemini ADK + AgentOps · Persistencia BigQuery',
    },
    finops: {
      label: 'FinOps IA',
      title: 'FinOps IA · Consumo & Costos',
      subtitle: 'Visión financiera y operativa del consumo real de IA en Business Rules Silver.',
      eyebrow: 'Cloud Billing + AgentOps · Costo real y atribución gobernada',
    },
    agents: {
      label: 'Agentes',
      title: 'Agentes · Catálogo & desempeño',
      subtitle: 'Capacidades ADK, modelos, tools, actividad y trazabilidad por agente.',
      eyebrow: 'Gemini ADK · Registro gobernado',
    },
    runs: {
      label: 'Ejecuciones',
      title: 'Ejecuciones · Trazabilidad operativa',
      subtitle: 'Historial persistente, estados, duración y drill-down de runs gobernados.',
      eyebrow: 'AgentOps · BigQuery persistente',
    },
    health: {
      label: 'Calidad & salud',
      title: 'Calidad & salud · Plataforma',
      subtitle: 'Disponibilidad, latencia y señales operativas de los componentes DataOps.',
      eyebrow: 'Observabilidad · Health checks',
    },
    artifacts: {
      label: 'Artefactos',
      title: 'Artefactos · Entregables gobernados',
      subtitle: 'Packages, DDL, PySpark y evidencia generada por el flujo Bronze → Silver.',
      eyebrow: 'Trazabilidad · Artefactos versionados',
    },
    alerts: {
      label: 'Alertas',
      title: 'Alertas · Riesgos & acciones',
      subtitle: 'Señales AgentOps priorizadas para revisión y acción operativa.',
      eyebrow: 'AgentOps · Gestión de excepciones',
    },
    governance: {
      label: 'Gobierno',
      title: 'Gobierno · Arquitectura & controles',
      subtitle: 'Componentes, responsabilidades y controles del producto Business Rules Silver.',
      eyebrow: 'Gobierno DataOps · Arquitectura',
    },
  };

  const navViewByText = new Map(Object.entries(VIEW_META).map(([key, value]) => [value.label.toLowerCase(), key]));
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  function buildView(name) {
    const section = document.createElement('section');
    section.className = `governance-view view-${name}`;
    section.dataset.view = name;
    section.hidden = true;
    return section;
  }

  function quickCard(icon, title, body, action, view) {
    return `<button class="overview-quick-card" type="button" data-view-link="${view}">
      <span class="overview-quick-icon">${icon}</span>
      <span><strong>${title}</strong><small>${body}</small></span>
      <b>${action} →</b>
    </button>`;
  }

  function createExecutiveRail() {
    const rail = document.createElement('aside');
    rail.className = 'overview-executive-rail';
    rail.innerHTML = `
      <article class="overview-rail-card finops-rail-card">
        <header><span>FinOps IA</span><button type="button" data-view-link="finops">Ver detalle →</button></header>
        <div class="rail-metrics">
          <div><small>Tokens</small><strong id="overviewFinopsTokens">—</strong></div>
          <div><small>Runs</small><strong id="overviewFinopsRuns">—</strong></div>
          <div><small>Costo producto</small><strong id="overviewFinopsCost">No disponible</strong></div>
        </div>
        <div id="overviewFinopsState" class="rail-state pending">Consultando cobertura real…</div>
      </article>
      <article class="overview-rail-card">
        <header><span>Agentes</span><button type="button" data-view-link="agents">Ver catálogo →</button></header>
        <div class="rail-highlight"><strong id="overviewAgentCount">—</strong><span>agentes registrados</span></div>
        <p>Modelos, tools, desempeño y actividad observable.</p>
      </article>
      <article class="overview-rail-card">
        <header><span>Operación</span><button type="button" data-view-link="runs">Ver ejecuciones →</button></header>
        <div class="rail-metrics two">
          <div><small>Runs</small><strong id="overviewRuns">—</strong></div>
          <div><small>Alertas</small><strong id="overviewAlerts">—</strong></div>
        </div>
      </article>`;
    return rail;
  }

  function createArtifactsView() {
    const wrap = document.createElement('div');
    wrap.className = 'standalone-view-card artifacts-view-card';
    wrap.innerHTML = `
      <div class="standalone-view-icon">▣</div>
      <div>
        <span class="view-kicker">Artefactos gobernados</span>
        <h2>Packages, DDL, PySpark y evidencia</h2>
        <p>Consulta el agregado vigente y abre el detalle ejecutivo disponible en AgentOps.</p>
      </div>
      <button class="primary-button" type="button" data-kpi-detail="artifacts">Abrir detalle</button>`;
    return wrap;
  }

  function syncMirror(sourceId, targetId, fallback = '—') {
    const source = document.getElementById(sourceId);
    const target = document.getElementById(targetId);
    if (target) target.textContent = source?.textContent?.trim() || fallback;
  }

  function syncExecutiveMirrors() {
    syncMirror('finopsTokens', 'overviewFinopsTokens');
    syncMirror('finopsRunsCount', 'overviewFinopsRuns');
    syncMirror('kpiAgents', 'overviewAgentCount');
    syncMirror('kpiRuns', 'overviewRuns');
    syncMirror('kpiAlerts', 'overviewAlerts');

    const costSource = document.getElementById('finopsProductCostValue') || document.getElementById('finopsCost');
    const costTarget = document.getElementById('overviewFinopsCost');
    if (costTarget) costTarget.textContent = costSource?.textContent?.trim() || 'No disponible';

    const productState = document.getElementById('finopsProductState');
    const finopsStatus = document.getElementById('finopsStatus');
    const stateTarget = document.getElementById('overviewFinopsState');
    if (stateTarget) {
      const stateText = productState?.textContent?.trim() || finopsStatus?.textContent?.trim() || 'Consultando cobertura real…';
      stateTarget.textContent = stateText;
      stateTarget.classList.toggle('live', /disponible|facturado|atribuido/i.test(stateText) && !/pendiente|no disponible|sin overlap/i.test(stateText));
      stateTarget.classList.toggle('pending', !stateTarget.classList.contains('live'));
    }
  }

  function applyView(name, { updateHash = true } = {}) {
    if (!VIEW_META[name]) name = 'overview';
    $$('.governance-view').forEach((view) => { view.hidden = view.dataset.view !== name; });
    document.body.dataset.currentView = name;

    $$('.nav-item').forEach((item) => {
      const key = item.dataset.viewTarget || navViewByText.get(item.textContent.trim().toLowerCase());
      item.classList.toggle('active', key === name);
    });

    const meta = VIEW_META[name];
    const topbar = $('.topbar');
    if (topbar) {
      const eyebrow = $('.eyebrow', topbar);
      const h1 = $('h1', topbar);
      const p = $('p', topbar);
      if (eyebrow) eyebrow.textContent = meta.eyebrow;
      if (h1) h1.textContent = meta.title;
      if (p) p.textContent = meta.subtitle;
    }

    if (updateHash && location.hash !== `#view/${name}`) history.pushState(null, '', `#view/${name}`);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    syncExecutiveMirrors();
  }

  function viewFromHash() {
    const match = location.hash.match(/^#view\/([a-z-]+)/i);
    return match && VIEW_META[match[1]] ? match[1] : null;
  }

  function prepareNavigation() {
    $$('.nav-item').forEach((item) => {
      const key = navViewByText.get(item.textContent.trim().toLowerCase());
      if (!key) return;
      item.dataset.viewTarget = key;
      item.removeAttribute('data-scroll-target');
      item.removeAttribute('data-kpi-detail');
    });
  }

  function prepareViews() {
    const main = $('.main-content');
    const topbar = $('.topbar');
    const errorBanner = document.getElementById('errorBanner');
    const footer = $('.footer');
    if (!main || !topbar) return;

    const host = document.createElement('div');
    host.id = 'viewHost';
    host.className = 'view-host';
    if (errorBanner?.nextSibling) main.insertBefore(host, errorBanner.nextSibling);
    else main.appendChild(host);

    const views = Object.fromEntries(Object.keys(VIEW_META).map((name) => [name, buildView(name)]));
    Object.values(views).forEach((view) => host.appendChild(view));

    const kpis = $('.kpi-grid');
    const topGrid = $('.top-grid');
    const statusPanel = $('.execution-state-panel');
    if (kpis) views.overview.appendChild(kpis);

    const overviewContent = document.createElement('div');
    overviewContent.className = 'overview-content-grid';
    const overviewMain = document.createElement('div');
    overviewMain.className = 'overview-main-column';
    if (topGrid) overviewMain.appendChild(topGrid);
    overviewContent.appendChild(overviewMain);
    const rail = createExecutiveRail();
    if (statusPanel) rail.prepend(statusPanel);
    overviewContent.appendChild(rail);
    views.overview.appendChild(overviewContent);

    const quick = document.createElement('div');
    quick.className = 'overview-quick-grid';
    quick.innerHTML = [
      quickCard('↗', 'FinOps IA', 'Consumo real, costo y atribución gobernada.', 'Abrir FinOps', 'finops'),
      quickCard('◇', 'Agentes', 'Catálogo ADK, tools y desempeño observable.', 'Abrir agentes', 'agents'),
      quickCard('↻', 'Ejecuciones', 'Historial, estados y trazabilidad por run.', 'Abrir runs', 'runs'),
    ].join('');
    views.overview.appendChild(quick);

    const finops = document.getElementById('finops');
    if (finops) {
      const subnav = document.createElement('nav');
      subnav.className = 'finops-subnav';
      subnav.setAttribute('aria-label', 'Secciones FinOps');
      subnav.innerHTML = `
        <button type="button" data-finops-anchor="finops">Resumen</button>
        <button type="button" data-finops-anchor="finopsServiceCosts">Costos por servicio</button>
        <button type="button" data-finops-anchor="finopsProductAttribution">Costo por producto</button>
        <button type="button" data-finops-anchor="finopsRuns">Runs con consumo</button>`;
      views.finops.appendChild(subnav);
      views.finops.appendChild(finops);
    }

    const lowerGrid = $('.lower-grid');
    const agentRegistryPanel = $('.agents-registry-panel');
    const executionsPanel = $('.executions-panel');
    if (agentRegistryPanel) views.agents.appendChild(agentRegistryPanel);
    if (executionsPanel) views.runs.appendChild(executionsPanel);
    if (lowerGrid && !lowerGrid.children.length) lowerGrid.remove();

    const historyPanel = document.getElementById('historyPanel');
    if (historyPanel) views.runs.prepend(historyPanel);

    const health = document.getElementById('health');
    if (health) views.health.appendChild(health);
    const alerts = document.getElementById('alerts');
    if (alerts) views.alerts.appendChild(alerts);
    const middleGrid = $('.middle-grid');
    if (middleGrid && !middleGrid.querySelector('.history-panel, .health-panel, .alerts-panel')) middleGrid.remove();

    views.artifacts.appendChild(createArtifactsView());

    const architecture = document.getElementById('architecture');
    if (architecture) views.governance.appendChild(architecture);

    if (footer) main.appendChild(footer);
  }

  function handleClick(event) {
    const nav = event.target.closest('.nav-item');
    if (nav?.dataset.viewTarget) {
      event.preventDefault();
      event.stopPropagation();
      applyView(nav.dataset.viewTarget);
      return;
    }
    const link = event.target.closest('[data-view-link]');
    if (link) {
      event.preventDefault();
      applyView(link.dataset.viewLink);
      return;
    }
    const anchor = event.target.closest('[data-finops-anchor]');
    if (anchor) {
      const target = document.getElementById(anchor.dataset.finopsAnchor);
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function init() {
    prepareNavigation();
    prepareViews();
    document.addEventListener('click', handleClick, true);

    const observer = new MutationObserver(() => syncExecutiveMirrors());
    observer.observe(document.querySelector('.main-content') || document.body, { subtree: true, childList: true, characterData: true });

    const initial = viewFromHash() || 'overview';
    applyView(initial, { updateHash: !viewFromHash() });
    setTimeout(syncExecutiveMirrors, 250);
  }

  window.governanceRouter = { navigate: (name) => applyView(name), current: () => document.body.dataset.currentView || 'overview' };
  window.addEventListener('hashchange', () => {
    const view = viewFromHash();
    if (view) applyView(view, { updateHash: false });
  });
  window.addEventListener('DOMContentLoaded', init);
})();
