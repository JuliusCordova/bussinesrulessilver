# Checkpoint — Gobierno SPA + FinOps real

**Fecha:** 2026-08-21  
**Repositorio:** `JuliusCordova/bussinesrulessilver`  
**Rama:** `feat/finops-real-preview`  
**Baseline de código validado:** `e2967dd41f961c383cc8d5bf8d571821649a9f9e`

## Objetivo del checkpoint

Registrar el estado validado del dashboard de Gobierno DataOps de **Business Rules Silver** después de separar la experiencia en vistas SPA, estabilizar el runtime y aplicar la primera pulida ejecutiva de Overview + FinOps.

## Estado funcional validado

La navegación lateral funciona como SPA con vistas independientes y hash routing:

- `#view/overview`
- `#view/finops`
- `#view/agents`
- `#view/runs`
- `#view/health`
- `#view/artifacts`
- `#view/alerts`
- `#view/governance`

La vista activa se controla con `hidden/display:none`; ya no se utiliza una página larga como mecanismo principal de navegación.

## Correcciones técnicas incorporadas

1. Se agregó `router.js` para navegación explícita entre vistas.
2. Se agregó `spa.css` para aislamiento visual de cada vista.
3. Se agregó `finops-polish.js` para la capa de atribución por producto.
4. Se agregó `product-polish.css` como capa visual desacoplada para iteración de diseño sin alterar contratos de datos.
5. El `Dockerfile` copia explícitamente los assets SPA y de pulida visual.
6. El deploy smoke test valida que los assets sean realmente servidos por Cloud Run.
7. Se eliminaron patrones `MutationObserver` recursivos que podían congelar el render y dejar el dashboard en `Actualizando...`.
8. El validador local falla si se reintroducen observers recursivos en router o FinOps polish.

## Validaciones locales

`bash scripts/validate_governance_preview_spa.sh`

Resultado validado:

```text
PASS: navegación explícita por vistas y hash routing presentes
PASS: una sola vista queda visible mediante hidden/display:none
PASS: router y FinOps polish sin observers recursivos
PASS: pulida ejecutiva de Overview + FinOps presente
PASS: FinOps conserva costo real y No disponible sin evidencia
```

## Deployment validado

Servicio preview:

`business-rules-silver-governance-preview`

Revisión desplegada y validada:

`business-rules-silver-governance-preview-00013-5tc`

Tráfico:

`100%`

URLs:

- Overview: `https://business-rules-silver-governance-preview-mkqutd4koq-uc.a.run.app/#view/overview`
- FinOps: `https://business-rules-silver-governance-preview-mkqutd4koq-uc.a.run.app/#view/finops`

Smoke test final:

```text
PASS: preview desplegado contiene SPA, pulida ejecutiva y FinOps real
```

## Overview — estado visual aprobado

La vista Overview fue revisada visualmente y aceptada como baseline para continuar.

Características validadas:

- composición ejecutiva compacta;
- KPIs principales visibles en una sola lectura;
- tendencia de ejecuciones y top agentes como foco operativo;
- estado de ejecuciones integrado en rail derecho;
- bloque compacto FinOps con tokens, runs y costo de producto;
- navegación lateral de producto;
- ausencia del antiguo patrón de página larga.

Datos observados en la validación visual:

- Runs agénticos: `40`
- Agentes activos: `3`
- Tasa de éxito: `50%`
- Duración p90: `42.3 s`
- Artefactos: `456`
- Alertas sin leer: `25`
- FinOps Silver: `127,941` tokens
- Runs gobernados FinOps: `15`
- Costo producto: `No disponible`

## FinOps — principio de verdad financiera

La UI no debe fabricar ni estimar costos como si fueran reales.

Semántica vigente:

- `FACTURADO`: costo real desde Cloud Billing Export.
- `ATRIBUIDO_DIRECTO`: costo con evidencia directa suficiente.
- `ATRIBUIDO_COMPARTIDO`: asignación gobernada sobre consumo compartido.
- `NO_DISPONIBLE`: evidencia insuficiente para mostrar un costo real.

Regla obligatoria:

> Si Billing no soporta un monto real para el periodo/producto, la UI muestra `No disponible` o estado pendiente; nunca `$0` ni una estimación sintética presentada como real.

## Estado actual de Billing

Cloud Billing Export está materializado y continúa en backfill.

Último uso observado en el deploy validado:

`2026-07-07T16:00:00Z`

La telemetría real de Silver comienza en agosto de 2026, por lo que todavía no existe solapamiento temporal defendible entre Billing y la telemetría Silver para atribuir costo IA por producto.

Consecuencia esperada y correcta:

- `product_cost_usd = null`
- `attributed_ai_cost_usd = null`
- cobertura de atribución pendiente
- UI = `No disponible`

## Diseño FinOps implementado

La vista FinOps prioriza ahora:

1. Costo producto
2. Costo directo
3. Costo IA atribuido
4. Cobertura
5. Confianza

Seguido por:

- estado de cobertura temporal;
- llamadas LLM;
- runs gobernados;
- tokens;
- evolución temporal;
- consumo por agente;
- facturación por servicio GCP;
- semántica de costos;
- runs con consumo IA.

## Decisiones que quedan congeladas en este checkpoint

- No volver a navegación por scroll como patrón principal.
- No volver a una única página larga para Overview + FinOps.
- No usar observers recursivos para sincronización de UI.
- No presentar costo estimado como costo real.
- No asignar el costo completo del proyecto GCP a Business Rules Silver.
- No atribuir Vertex AI a Silver sin overlap temporal y cobertura de denominador defendible.
- Mantener Overview aprobado como baseline visual; futuras iteraciones deben ser incrementales.

## Próximo bloque recomendado

Continuar con la misma familia visual para:

1. `Agentes`
2. `Ejecuciones`
3. `Calidad & salud`
4. `Alertas`
5. `Gobierno`

Sin modificar la arquitectura FinOps ya validada salvo que aparezca nueva evidencia real de Billing o de atribución.