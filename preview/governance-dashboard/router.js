(() => {
  'use strict';

  const META = {
    overview: ['Gobierno DataOps — Business Rules Silver','Observabilidad, trazabilidad y gobierno del refinamiento Bronze → Silver.','Gemini ADK + AgentOps · Persistencia BigQuery'],
    finops: ['FinOps IA · Consumo & Costos','Visión financiera y operativa del consumo real de IA en Business Rules Silver.','Cloud Billing + AgentOps · Costo real y atribución gobernada'],
    agents: ['Agentes · Catálogo & desempeño','Capacidades ADK, modelos, tools, actividad y trazabilidad por agente.','Gemini ADK · Registro gobernado'],
    runs: ['Ejecuciones · Trazabilidad operativa','Historial persistente, estados, duración y drill-down de runs gobernados.','AgentOps · BigQuery persistente'],
    health: ['Calidad & salud · Plataforma','Disponibilidad, latencia y señales operativas de los componentes DataOps.','Observabilidad · Health checks'],
    artifacts: ['Artefactos · Entregables gobernados','Packages, DDL, PySpark y evidencia generada por el flujo Bronze → Silver.','Trazabilidad · Artefactos versionados'],
    alerts: ['Alertas · Riesgos & acciones','Señales AgentOps priorizadas para revisión y acción operativa.','AgentOps · Gestión de excepciones'],
    governance: ['Gobierno · Arquitectura & controles','Componentes, responsabilidades y controles del producto Business Rules Silver.','Gobierno DataOps · Arquitectura']
  };

  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => [...r.querySelectorAll(s)];

  function page(name) {
    const el = document.createElement('section');
    el.className = `governance-view view-${name}`;
    el.dataset.view = name;
    el.hidden = true;
    return el;
  }

  function executiveRail() {
    const rail = document.createElement('aside');
    rail.className = 'overview-executive-rail';
    rail.innerHTML = `
      <article class="overview-rail-card finops-rail-card"><header><span>FinOps IA</span><button type="button" data-view-link="finops">Ver detalle →</button></header><div class="rail-metrics"><div><small>Tokens</small><strong id="overviewFinopsTokens">—</strong></div><div><small>Runs</small><strong id="overviewFinopsRuns">—</strong></div><div><small>Costo producto</small><strong id="overviewFinopsCost">No disponible</strong></div></div><div id="overviewFinopsState" class="rail-state pending">Consultando cobertura real…</div></article>
      <article class="overview-rail-card"><header><span>Agentes</span><button type="button" data-view-link="agents">Ver catálogo →</button></header><div class="rail-highlight"><strong id="overviewAgentCount">—</strong><span>agentes registrados</span></div><p>Modelos, tools, desempeño y actividad observable.</p></article>
      <article class="overview-rail-card"><header><span>Operación</span><button type="button" data-view-link="runs">Ver ejecuciones →</button></header><div class="rail-metrics two"><div><small>Runs</small><strong id="overviewRuns">—</strong></div><div><small>Alertas</small><strong id="overviewAlerts">—</strong></div></div></article>`;
    return rail;
  }

  function quick(view, icon, title, body) {
    return `<button class="overview-quick-card" type="button" data-view-link="${view}"><span class="overview-quick-icon">${icon}</span><span><strong>${title}</strong><small>${body}</small></span><b>Abrir →</b></button>`;
  }

  function artifactCard() {
    const el = document.createElement('div');
    el.className = 'standalone-view-card artifacts-view-card';
    el.innerHTML = `<div class="standalone-view-icon">▣</div><div><span class="view-kicker">Artefactos gobernados</span><h2>Packages, DDL, PySpark y evidencia</h2><p>Consulta el agregado vigente y abre el detalle ejecutivo disponible en AgentOps.</p></div><button class="primary-button" type="button" data-kpi-detail="artifacts">Abrir detalle</button>`;
    return el;
  }

  function sync(sourceId,targetId,fallback='—') {
    const t=document.getElementById(targetId); if(t) t.textContent=document.getElementById(sourceId)?.textContent?.trim()||fallback;
  }

  function syncOverview() {
    sync('finopsTokens','overviewFinopsTokens'); sync('finopsRunsCount','overviewFinopsRuns'); sync('kpiAgents','overviewAgentCount'); sync('kpiRuns','overviewRuns'); sync('kpiAlerts','overviewAlerts');
    const cost=document.getElementById('finopsProductCostValue')||document.getElementById('finopsCost');
    const costTarget=document.getElementById('overviewFinopsCost'); if(costTarget) costTarget.textContent=cost?.textContent?.trim()||'No disponible';
    const state=(document.getElementById('finopsProductState')||document.getElementById('finopsStatus'))?.textContent?.trim()||'Consultando cobertura real…';
    const stateTarget=document.getElementById('overviewFinopsState'); if(stateTarget){stateTarget.textContent=state; const live=/disponible|facturado|atribuido/i.test(state)&&!/pendiente|no disponible|sin overlap/i.test(state); stateTarget.classList.toggle('live',live); stateTarget.classList.toggle('pending',!live);}
  }

  function mount() {
    const main=$('.main-content'); const error=document.getElementById('errorBanner'); if(!main||!error) throw new Error('main-content/errorBanner no encontrados');
    if(document.getElementById('viewHost')) return;

    const host=document.createElement('div'); host.id='viewHost'; host.className='view-host'; error.insertAdjacentElement('afterend',host);
    const views={}; Object.keys(META).forEach(n=>{views[n]=page(n);host.appendChild(views[n]);});

    const kpis=$('.kpi-grid'); const top=$('.top-grid'); const status=$('.execution-state-panel');
    if(kpis) views.overview.appendChild(kpis);
    const content=document.createElement('div'); content.className='overview-content-grid';
    const mainCol=document.createElement('div'); mainCol.className='overview-main-column'; if(top) mainCol.appendChild(top); content.appendChild(mainCol);
    const rail=executiveRail(); if(status) rail.prepend(status); content.appendChild(rail); views.overview.appendChild(content);
    const shortcuts=document.createElement('div'); shortcuts.className='overview-quick-grid'; shortcuts.innerHTML=quick('finops','↗','FinOps IA','Consumo real, costo y atribución gobernada.')+quick('agents','◇','Agentes','Catálogo ADK, tools y desempeño observable.')+quick('runs','↻','Ejecuciones','Historial, estados y trazabilidad por run.'); views.overview.appendChild(shortcuts);

    const finops=document.getElementById('finops'); if(finops){const nav=document.createElement('nav');nav.className='finops-subnav';nav.innerHTML='<button type="button" data-finops-anchor="finops">Resumen</button><button type="button" data-finops-anchor="finopsServiceCosts">Costos por servicio</button><button type="button" data-finops-anchor="finopsProductAttribution">Costo por producto</button><button type="button" data-finops-anchor="finopsRuns">Runs con consumo</button>';views.finops.append(nav,finops);}

    const agentPanel=$('.agents-registry-panel'); if(agentPanel) views.agents.appendChild(agentPanel);
    const history=document.getElementById('historyPanel'); if(history) views.runs.appendChild(history);
    const exec=$('.executions-panel'); if(exec) views.runs.appendChild(exec);
    const health=document.getElementById('health'); if(health) views.health.appendChild(health);
    const alerts=document.getElementById('alerts'); if(alerts) views.alerts.appendChild(alerts);
    views.artifacts.appendChild(artifactCard());
    const architecture=document.getElementById('architecture'); if(architecture) views.governance.appendChild(architecture);

    $$('.middle-grid,.lower-grid').forEach(el=>{if(!el.children.length||!el.querySelector('.panel')) el.remove();});
  }

  function show(name,updateHash=true) {
    if(!META[name]) name='overview';
    $$('.governance-view').forEach(v=>{v.hidden=v.dataset.view!==name;});
    document.body.dataset.currentView=name;
    $$('[data-view-target]').forEach(n=>n.classList.toggle('active',n.dataset.viewTarget===name));
    const [title,subtitle,eyebrow]=META[name]; const top=$('.topbar'); if(top){const h=$('h1',top),p=$('p',top),e=$('.eyebrow',top);if(h)h.textContent=title;if(p)p.textContent=subtitle;if(e)e.textContent=eyebrow;}
    if(updateHash&&location.hash!==`#view/${name}`) history.replaceState(null,'',`#view/${name}`);
    window.scrollTo(0,0); syncOverview();
  }

  function hashView(){const m=location.hash.match(/^#view\/([a-z-]+)/);return m&&META[m[1]]?m[1]:null;}

  function init(){
    try{
      mount();
      document.addEventListener('click',e=>{
        const nav=e.target.closest('[data-view-target]'); if(nav){e.preventDefault();e.stopPropagation();show(nav.dataset.viewTarget);return;}
        const link=e.target.closest('[data-view-link]'); if(link){e.preventDefault();e.stopPropagation();show(link.dataset.viewLink);return;}
        const anchor=e.target.closest('[data-finops-anchor]'); if(anchor){document.getElementById(anchor.dataset.finopsAnchor)?.scrollIntoView({behavior:'smooth',block:'start'});}
      },true);
      const obs=new MutationObserver(syncOverview); obs.observe($('.main-content')||document.body,{subtree:true,childList:true,characterData:true});
      show(hashView()||'overview',!hashView()); setTimeout(syncOverview,300);
      document.body.classList.add('spa-ready');
    }catch(error){console.error('Governance SPA init failed',error);document.body.classList.add('spa-error');}
  }

  window.governanceRouter={navigate:n=>show(n),current:()=>document.body.dataset.currentView||'overview'};
  window.addEventListener('hashchange',()=>{const v=hashView();if(v)show(v,false);});
  window.addEventListener('DOMContentLoaded',init);
})();