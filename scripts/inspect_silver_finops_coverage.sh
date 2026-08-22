#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-proyectopersonal-480420}"
OUTPUT_DIR="${OUTPUT_DIR:-docs/evidence/finops-silver-coverage}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUTPUT_DIR/$STAMP"
mkdir -p "$OUT"

command -v bq >/dev/null

printf '=== BUSINESS RULES SILVER · FINOPS TELEMETRY COVERAGE ===\n'
printf 'Project: %s\n' "$PROJECT_ID"
printf 'Output : %s\n\n' "$OUT"

SILVER_AGENTS=(
  business-rule-validator
  mapping-advisor
  notebook-generator
  orchestrator
  quality-rule-advisor
  table-profiler
)

AGENT_LIST=""
for AGENT in "${SILVER_AGENTS[@]}"; do
  if [[ -n "$AGENT_LIST" ]]; then AGENT_LIST+=","; fi
  AGENT_LIST+="'$AGENT'"
done

printf '[1/3] Cobertura de los seis agentes Silver en fact_llm_calls...\n'
QUERY1="SELECT agent_name, COUNT(*) AS llm_calls, MIN(call_ts) AS first_call_ts, MAX(call_ts) AS last_call_ts, SUM(prompt_tokens) AS prompt_tokens, SUM(response_tokens) AS response_tokens, SUM(total_tokens) AS total_tokens FROM \`$PROJECT_ID.agentops.fact_llm_calls\` WHERE agent_name IN ($AGENT_LIST) GROUP BY agent_name ORDER BY agent_name"
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=prettyjson "$QUERY1" >"$OUT/silver-agents-coverage.json"
cat "$OUT/silver-agents-coverage.json"

printf '\n[2/3] Agentes presentes actualmente en fact_llm_calls...\n'
QUERY2="SELECT agent_name, COUNT(*) AS llm_calls, MIN(call_ts) AS first_call_ts, MAX(call_ts) AS last_call_ts FROM \`$PROJECT_ID.agentops.fact_llm_calls\` GROUP BY agent_name ORDER BY llm_calls DESC"
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=prettyjson "$QUERY2" >"$OUT/all-agent-coverage.json"
cat "$OUT/all-agent-coverage.json"

printf '\n[3/3] Resultado de cobertura Silver...\n'
python3 - "$OUT/silver-agents-coverage.json" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
rows = json.loads(p.read_text() or '[]')
expected = {
    'business-rule-validator',
    'mapping-advisor',
    'notebook-generator',
    'orchestrator',
    'quality-rule-advisor',
    'table-profiler',
}
found = {r.get('agent_name') for r in rows}
missing = sorted(expected - found)
print(f'FOUND_SILVER_AGENTS={len(found)}')
print(f'EXPECTED_SILVER_AGENTS={len(expected)}')
if missing:
    print('RESULT: SILVER_LLM_TELEMETRY_INCOMPLETE')
    print('MISSING=' + ','.join(missing))
else:
    print('RESULT: SILVER_LLM_TELEMETRY_COMPLETE')
PY

printf '\n=== COVERAGE CHECK COMPLETADO ===\n'
printf 'EVIDENCE_DIR=%s\n' "$OUT"
printf '\nCriterio:\n'
printf '1) No reutilizar consumo de agentes ajenos como FinOps de Business Rules Silver.\n'
printf '2) Solo agentes Silver observados pueden alimentar KPIs de consumo IA del dashboard.\n'
printf '3) Si no hay cobertura, el siguiente paso es instrumentar el backend Silver.\n'
