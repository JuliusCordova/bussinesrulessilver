# 13. FinOps real para Gobierno DataOps Preview

## Objetivo

Extender el dashboard interactivo de Gobierno DataOps de Business Rules Silver con una capa FinOps basada exclusivamente en datos reales, trazables y auditables.

## Principio no negociable

El dashboard no debe inventar, simular ni presentar como real ningún costo.

Si una fuente de costo no está disponible o no puede correlacionarse de forma confiable, la UI debe mostrar explícitamente `Sin datos disponibles` o `No atribuible`, según corresponda.

## Fuentes canónicas esperadas

### 1. Costo facturado de infraestructura

Fuente primaria: Cloud Billing Export hacia BigQuery.

Servicios de interés para Business Rules Silver, sujetos a evidencia real del export:

- Cloud Run;
- BigQuery;
- Dataproc;
- Cloud Storage;
- Vertex AI / Gemini;
- Cloud Logging / Monitoring;
- otros servicios efectivamente asociados al producto.

El costo mostrado como `Facturado` debe provenir del export de Cloud Billing y conservar referencia a:

- billing account;
- project id;
- service / sku;
- usage start/end time;
- cost;
- credits;
- currency;
- export table.

### 2. Uso de IA por ejecución

El objetivo es persistir telemetría por `run_id`, `session_id` y `agent_name` cuando el SDK/API utilizado exponga métricas de uso confiables.

Campos objetivo:

- `run_id`;
- `session_id`;
- `agent_name`;
- `model`;
- `input_tokens`;
- `output_tokens`;
- `total_tokens`;
- `request_count`;
- `started_at`;
- `finished_at`;
- referencia de evidencia de uso.

No se calculará costo monetario desde tokens hasta validar el precio/modelo aplicable o disponer del costo facturado correspondiente.

## Semántica de costo

El dashboard debe diferenciar claramente:

### Facturado
Costo observado directamente en Cloud Billing Export.

### Atribuido
Costo facturado distribuido a agente/run mediante una regla de atribución documentada y reproducible.

### No atribuible
Costo real del proyecto/producto que no puede asociarse confiablemente a un agente o run específico.

Nunca se etiquetará un costo atribuido como si fuera facturación directa del run.

## Modelo objetivo

Persistencia recomendada en BigQuery `dataops_control`:

- `silver_finops_billing_daily` — agregación de costo facturado por día/servicio/SKU;
- `silver_finops_agent_usage` — telemetría real de uso IA por agente/run;
- `silver_finops_run_cost` — vista o tabla de costo atribuible por run con método de atribución;
- `silver_finops_service_cost` — costo por servicio y período.

La implementación final dependerá de las fuentes realmente disponibles durante discovery.

## Contratos API objetivo

Solo se implementarán después de validar las fuentes reales:

- `GET /agentops/finops/summary?days=7|14|30`
- `GET /agentops/finops/daily?days=7|14|30`
- `GET /agentops/finops/agents?days=7|14|30`
- `GET /agentops/finops/runs?days=7|14|30&limit=N`
- `GET /agentops/finops/services?days=7|14|30`

Todos los contratos deben incluir metadatos de procedencia, por ejemplo:

- `source_type`;
- `source_table`;
- `generated_at`;
- `currency`;
- `cost_semantics` (`BILLED`, `ATTRIBUTED`, `NOT_ATTRIBUTABLE`).

## UX objetivo del preview

### KPIs

- Costo total facturado del período;
- Costo IA facturado/identificado;
- Costo infraestructura;
- Costo promedio por run, solo si es atribuible;
- agente de mayor costo atribuible;
- variación vs período anterior.

### Gráficos

- tendencia diaria de costo real;
- costo por agente;
- distribución IA vs infraestructura;
- costo por servicio/SKU;
- costo vs volumen de runs.

### Drill-down

Dashboard → Agente → Run → evidencia de uso/costo.

Cada detalle debe indicar si el valor es `Facturado`, `Atribuido` o `No atribuible`.

## Criterios de aceptación

1. No existe archivo de mocks FinOps ni valores monetarios hardcodeados.
2. Cada valor monetario visible tiene procedencia verificable.
3. Si Cloud Billing Export no está disponible, el dashboard muestra ausencia de datos y no inventa valores.
4. Los filtros de 7/14/30 días afectan KPIs y gráficos con consultas reales.
5. El detalle por agente/run expone la semántica del costo y su fuente.
6. La implementación permanece inicialmente en el servicio Cloud Run de preview y no modifica la vista productiva hasta aceptación explícita.

## Secuencia de implementación

1. Discovery de Billing Export y telemetría real de Gemini/Vertex.
2. Registrar evidencia y decidir modelo físico final.
3. Implementar consultas/repositorio BigQuery FinOps.
4. Implementar endpoints `/agentops/finops/*` con pruebas.
5. Integrar el dashboard preview con estados vacíos seguros.
6. Desplegar preview aislado.
7. Validar cifras contra Billing/BigQuery y AgentOps.
8. Solo después decidir promoción.
