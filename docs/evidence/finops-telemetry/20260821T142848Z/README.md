# FinOps telemetry inspection — 2026-08-21 14:28:48Z

## Resultado validado

Proyecto: `proyectopersonal-480420`

Billing:
- `billingEnabled = true`
- `billingAccountName = billingAccounts/018A15-4691E8-C0A72F`

Telemetría AgentOps disponible:
- `agentops.fact_llm_calls`
- `agentops.vw_llm_usage_summary`
- `agentops.vw_tool_usage`

Schema relevante de `fact_llm_calls`:
- `call_ts`
- `trace_id`
- `session_id`
- `agent_name`
- `intent`
- `model_name`
- `prompt_tokens`
- `response_tokens`
- `total_tokens`
- `latency_ms`
- `status`
- `user_email`
- `message`

Volumen observado:
- 199 registros
- primera llamada: `2026-06-30 06:17:13`
- última llamada: `2026-07-13 21:23:03`

La muestra de `vw_llm_usage_summary` contiene agentes como:
- `enterprise-reconciliation-agent`
- `jarvis-intercorp-fest-api`

## Conclusión

La telemetría de LLM es real y contiene tokens, modelo, latencia, estado y trazabilidad de sesión. Sin embargo, esta evidencia todavía **no demuestra cobertura de Business Rules Silver**. Antes de exponer consumo IA en el dashboard Silver debe verificarse la presencia de los seis agentes canónicos Silver en `agentops.fact_llm_calls`.

Tampoco existe aún Cloud Billing Export confirmado, por lo que no se habilitan KPIs USD de costo facturado.
