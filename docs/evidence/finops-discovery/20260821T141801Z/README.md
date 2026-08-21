# FinOps Real Discovery — 2026-08-21 14:18:01Z

## Contexto
- Proyecto GCP: `proyectopersonal-480420`
- Región: `us-central1`
- Rama: `feat/finops-real-preview`
- Objetivo: validar fuentes reales antes de implementar KPIs y gráficos FinOps en el Governance Preview.

## Evidencia ejecutada
El script `scripts/discover_finops_sources.sh` fue ejecutado desde Cloud Shell y reportó:

- asociación de billing consultada correctamente;
- datasets BigQuery listados correctamente;
- candidatos detectados inicialmente:
  - `agentops.vw_llm_usage_summary`
  - `agentops.vw_tool_usage`
- servicios Cloud Run relacionados detectados:
  - `business-rules-silver-governance-preview`
  - `business-rules-silver-ui`
  - `business-rules-silver-ui-agents-test`
  - `silver-refinement-agent`
  - `silver-refinement-agent-merge-test`
- configuración de `silver-refinement-agent` capturada correctamente;
- APIs relevantes habilitadas: Vertex AI, BigQuery, Monitoring y Cloud Run.

## Conclusión técnica
`agentops.vw_llm_usage_summary` y `agentops.vw_tool_usage` son fuentes de telemetría/uso AgentOps y **no constituyen por sí mismas una tabla de Cloud Billing Export**.

Por lo tanto, con esta evidencia todavía no existe base suficiente para mostrar costo facturado de infraestructura en el dashboard.

## Decisión de gobierno
- No usar datos sintéticos.
- No hardcodear costos.
- No presentar telemetría de uso como si fuera facturación.
- Los KPIs de costo facturado solo se habilitarán si se identifica una tabla oficial de Cloud Billing BigQuery Export.
- La telemetría AgentOps sí podrá utilizarse para consumo IA y posterior atribución de costo, siempre que el contrato y la trazabilidad queden documentados.
- Cuando no haya una fuente válida, la UI mostrará `Sin datos disponibles` / `Billing Export no configurado`.

## Corrección posterior
El discovery original clasificaba candidatos por palabras genéricas como `usage`, lo cual podía confundir telemetría con Billing Export. El script fue corregido para reconocer por separado los prefijos oficiales de exportación de Cloud Billing (`gcp_billing_export_v1_`, `gcp_billing_export_resource_v1_`, `cloud_pricing_export`) y las fuentes operacionales/IA.
