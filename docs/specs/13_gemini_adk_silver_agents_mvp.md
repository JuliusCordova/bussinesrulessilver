# Gemini ADK Silver Agents - MVP

## Estado

Implementación inicial en el backend desplegable:

`backend/deployable/silver-refinement-agent/modules/silver_agents/`

No requiere RAG. Usa Gemini mediante Google ADK y herramientas determinísticas para
BigQuery, validación contractual y generación del blueprint técnico.

## Agentes

1. `silver_table_profiler`
   - Lee la tabla BigQuery seleccionada.
   - Devuelve schema, nulos, cardinalidad, partición y clustering.
   - Identifica campos críticos y candidatos a business key.

2. `silver_quality_rule_advisor`
   - Propone reglas respaldadas por el perfil.
   - Campos críticos: propone `NOT_NULL`.
   - Business keys: propone `NOT_NULL` y `UNIQUE`.
   - Si ya existen nulos o duplicados, la propuesta se marca `FAILING`.
   - Todas las propuestas quedan `PENDING_APPROVAL`.

3. `silver_business_rule_validator`
   - Verifica tipos de regla soportados.
   - Verifica referencias a columnas.
   - Verifica parámetros obligatorios.
   - No sustituye la aprobación funcional humana.

4. `silver_notebook_generator`
   - Produce un blueprint gobernado de notebook.
   - Conserva source, target, mapping, estrategia, business keys, watermark,
     quality gates y validación post-ejecución.
   - Para `MERGE` y `CDC` bloquea la generación si faltan business keys.

5. `silver_design_orchestrator`
   - Es un `SequentialAgent` de Gemini ADK.
   - Ejecuta los cuatro agentes anteriores en orden.
   - Comparte resultados mediante el estado de sesión de ADK.

## API

- `GET /silver-agents`
- `POST /silver-agents/table-profiler/run`
- `POST /silver-agents/quality-rule-advisor/run`
- `POST /silver-agents/business-rule-validator/run`
- `POST /silver-agents/notebook-generator/run`
- `POST /silver-agents/orchestrator/run`

## Decisiones del MVP

- Gemini interpreta, prioriza y explica.
- BigQuery entrega los hechos.
- Las tools validan contratos ejecutables.
- Ninguna regla se activa sin aprobación humana.
- El generador entrega primero un blueprint; la persistencia del `.ipynb` y su
  conexión con el package generator actual serán la siguiente evolución.
- RAG se pospone hasta disponer de políticas corporativas o artefactos aprobados
  que realmente necesiten recuperación semántica.

## Pruebas incluidas

`tests/test_silver_agents.py` cubre:

- construcción de los cinco agentes ADK;
- reglas `NOT_NULL` y `UNIQUE` sobre business keys con incumplimientos;
- rechazo de reglas contra columnas inexistentes;
- bloqueo de notebook `MERGE` sin business key.
