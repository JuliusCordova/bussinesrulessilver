# Checkpoint canónico - Gemini ADK Silver Agents

Fecha: 2026-08-16

## Propósito

Este documento fija el punto exacto de continuación del proyecto Business Rules Silver.
Debe usarse como referencia antes de modificar, probar o desplegar los nuevos agentes.

## Repositorio y componentes canónicos

Repositorio:

`JuliusCordova/bussinesrulessilver`

Frontend:

- Código: raíz del repositorio, principalmente `src/`.
- Servicio Cloud Run: `business-rules-silver-ui`.
- URL productiva: `https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app`.

Backend:

- Código desplegable: `backend/deployable/silver-refinement-agent/`.
- Servicio Cloud Run: `silver-refinement-agent`.
- URL productiva: `https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`.

No se debe volver a realizar descubrimiento del frontend o backend mientras estas
ubicaciones continúen vigentes.

## Estado funcional previo

El flujo determinístico Bronze-to-Silver fue validado en producción:

- Source: `proyectopersonal-480420.seguros_bronce.cat_producto`.
- Target: `proyectopersonal-480420.seguros_silver.cat_producto`.
- Business key: `producto_id`.
- Watermark: `bronze_fecha_ingesta`.
- Estrategia: `MERGE`.
- Resultado: 13 filas, 13 productos distintos y sin duplicados.
- `SUM(prima_base) = 21390`.
- Frontend y backend productivos respondieron correctamente.

## Validación BigQuery post-ejecución

Se implementó en el repositorio:

- modelos para checks y respuesta de validación;
- validador BigQuery genérico;
- integración con sincronización de Dataproc;
- endpoint `POST /executions/{execution_id}/result`;
- regla de estado: una ejecución solo puede quedar `SUCCEEDED` cuando Dataproc y
  la validación BigQuery están conformes;
- documentación y prueba unitaria del validador.

La integración visual completa de `Ver resultado` en `src/App.tsx` sigue pendiente.
El contrato API ya está preparado en `src/api.ts`.

## Gemini ADK Silver Agents implementados

Ubicación:

`backend/deployable/silver-refinement-agent/modules/silver_agents/`

### 1. silver_table_profiler

Responsabilidades:

- perfilar la tabla BigQuery seleccionada;
- obtener schema, nulos y cardinalidad;
- detectar partición y clustering;
- identificar campos críticos;
- identificar candidatos a business key.

### 2. silver_quality_rule_advisor

Responsabilidades:

- recomendar reglas usando evidencia del perfil;
- proponer `NOT_NULL` para campos críticos;
- proponer `NOT_NULL` y `UNIQUE` para business keys;
- marcar una propuesta como `FAILING` si actualmente existen nulos o duplicados;
- mantener las propuestas en `PENDING_APPROVAL`.

Ninguna recomendación se activa automáticamente.

### 3. silver_business_rule_validator

Responsabilidades:

- validar tipos de regla soportados;
- validar referencias a columnas;
- validar parámetros obligatorios;
- devolver errores accionables;
- impedir que Gemini declare válida una regla rechazada por la herramienta
  determinística.

Tipos iniciales soportados:

- `NOT_NULL`;
- `UNIQUE`;
- `ALLOWED_VALUES`;
- `VALUE_RANGE`;
- `REGEX`.

### 4. silver_notebook_generator

Estado MVP:

- genera un blueprint gobernado del notebook;
- preserva source, target, columnas, business keys, watermark, estrategia de carga,
  quality gates y validación post-ejecución;
- bloquea `MERGE` o `CDC` cuando faltan business keys.

Pendiente de evolución:

- convertir el blueprint aprobado en el `.ipynb` definitivo mediante el package
  generator existente;
- persistirlo y versionarlo como artefacto gobernado.

### 5. silver_design_orchestrator

Implementado como `SequentialAgent` de Gemini ADK.

Orden:

1. perfilamiento;
2. recomendación de reglas de calidad;
3. validación de reglas de negocio;
4. generación del blueprint del notebook.

Los agentes especialistas también pueden ejecutarse individualmente.

## API agregada

- `GET /silver-agents`
- `POST /silver-agents/table-profiler/run`
- `POST /silver-agents/quality-rule-advisor/run`
- `POST /silver-agents/business-rule-validator/run`
- `POST /silver-agents/notebook-generator/run`
- `POST /silver-agents/orchestrator/run`

La API se registró en:

`backend/deployable/silver-refinement-agent/modules/silver_refinement/app.py`

La versión declarada del backend quedó en `8.2.0`.

## Pruebas agregadas

Archivo:

`backend/deployable/silver-refinement-agent/tests/test_silver_agents.py`

Cobertura inicial:

- construcción de los cuatro especialistas y el orquestador ADK;
- recomendación `NOT_NULL` para business key con nulos;
- recomendación `UNIQUE` para business key con duplicados;
- rechazo de reglas referidas a columnas inexistentes;
- bloqueo de notebook `MERGE` sin business key.

## Estado real de verificación

- El código y las pruebas están guardados en GitHub.
- Se contrastó el patrón de `LlmAgent`, `SequentialAgent`, `Runner`,
  `InMemorySessionService` y `run_async` con la documentación oficial de
  Google ADK.
- Las pruebas no se ejecutaron dentro del entorno de Codex porque no dispone del
  paquete `google-adk`.
- Los agentes nuevos todavía no fueron construidos ni desplegados en Cloud Run.
- Producción continúa usando el backend anterior, sin estos endpoints.

## Decisiones de alcance

- Se usa Gemini ADK.
- Gemini interpreta, prioriza y explica.
- BigQuery y las tools determinísticas producen y validan los hechos.
- No se usa RAG en este MVP.
- La aprobación humana de reglas es obligatoria.
- Se prioriza un corte funcional y evolutivo antes que una plataforma perfecta.

## Próximo bloque exacto

1. Actualizar el checkout de Cloud Shell con `git pull`.
2. Instalar dependencias del backend desplegable.
3. Ejecutar:
   - compilación Python;
   - `tests/test_silver_agents.py`;
   - pruebas existentes de validación post-BigQuery.
4. Corregir cualquier incompatibilidad con la versión efectiva de `google-adk`.
5. Construir una imagen candidata del backend.
6. Desplegarla primero en un servicio de prueba.
7. Validar:
   - `GET /health`;
   - `GET /silver-agents`;
   - ejecución del perfilador sobre `seguros_bronce.cat_producto`;
   - recomendaciones para `producto_id`;
   - ejecución completa del orquestador.
8. Solo después promover la imagen a producción.
9. Integrar en el frontend:
   - recomendaciones de reglas;
   - aprobación humana;
   - resultado del orquestador;
   - panel BigQuery de `Ver resultado`.

## Referencias relacionadas

- `docs/specs/12_post_execution_bigquery_result_validation.md`
- `docs/specs/13_gemini_adk_silver_agents_mvp.md`
- `docs/specs/10_sprint_plan_bronze_to_silver.md`
- `docs/deployment/evidence/generated/20260815_silver_merge_fix/`
- `docs/deployment/evidence/generated/20260815_silver_prod_promotion/`
- `docs/deployment/evidence/generated/20260815_silver_frontend_prod/`
