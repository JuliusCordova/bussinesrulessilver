# Gemini ADK Silver Agents - CI Evidence

Date: 2026-08-16  
Status: **CONFORME EN CÓDIGO / PENDIENTE DE DESPLIEGUE**

## Resultado

El bloque inicial de agentes Gemini ADK quedó implementado y verificado automáticamente en GitHub Actions.

Workflow:

- Name: `Silver Agents Tests`
- Run: `31974118933`
- Commit: `167ede70f27be2eb4578e9ac1f2c3555438b42a0`
- Event: `push`
- Conclusion: `success`
- URL: https://github.com/JuliusCordova/bussinesrulessilver/actions/runs/31974118933

Pasos conformes:

1. Checkout
2. Python 3.11 setup
3. Dependency installation
4. Python compilation
5. Focused agent and post-execution tests

## Agentes implementados

Ubicación:

`backend/deployable/silver-refinement-agent/modules/silver_agents/`

Incluye:

- Table Profiler Agent
- Quality Rules Advisor Agent
- Business Rules Validator Agent
- Notebook Generator Agent
- Sequential Orchestrator

## Contrato compartido

El orquestador inicializa una sesión ADK con estado compartido y propaga:

- source and target tables;
- schema/columns;
- business keys;
- business rules;
- load strategy;
- physical design;
- profiling output;
- quality-rule proposals;
- business-rule validation;
- notebook specification.

La estrategia por defecto es:

- `MERGE` cuando existen business keys;
- `FULL` cuando no existen business keys.

## Configuración Vertex AI

El backend adapta su configuración actual al contrato esperado por Google ADK:

- `PROJECT_ID` -> `GOOGLE_CLOUD_PROJECT`
- `GEMINI_LOCATION` -> `GOOGLE_CLOUD_LOCATION`
- `GOOGLE_GENAI_USE_VERTEXAI=TRUE`
- modelo configurable mediante `GEMINI_MODEL`, con default `gemini-2.5-flash`

## Alcance validado

Las pruebas cubren:

- construcción de todos los agentes;
- payload y estado compartido completos;
- sugerencias por nulos;
- sugerencias de unicidad/duplicados;
- rechazo de columnas inválidas;
- rechazo de MERGE sin business key;
- validación BigQuery post-ejecución existente.

## Límites actuales

- Los agentes están implementados y probados, pero todavía no desplegados en Cloud Run.
- Las reglas sugeridas permanecen `PENDING_APPROVAL`; no se ejecutan automáticamente.
- El Notebook Generator produce un blueprint gobernado. La conexión final con el generador de package/notebook ejecutable es el siguiente incremento.
- No se usa RAG en este MVP.

## Próximo bloque

1. Integrar el panel frontend para perfilamiento, propuestas y aprobación.
2. Conectar el blueprint aprobado al package generator.
3. Desplegar una revisión candidata del backend.
4. Ejecutar smoke test con una tabla seleccionada.
5. Promover a producción únicamente con evidencia conforme.
