#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-proyectopersonal-480420}"
OUTPUT_DIR="${OUTPUT_DIR:-docs/evidence/finops-telemetry}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUTPUT_DIR/$STAMP"
mkdir -p "$OUT"

command -v gcloud >/dev/null
command -v bq >/dev/null

printf '=== FINOPS TELEMETRY INSPECTION ===\n'
printf 'Project: %s\n' "$PROJECT_ID"
printf 'Output : %s\n\n' "$OUT"

printf '[1/5] Billing project association...\n'
gcloud billing projects describe "$PROJECT_ID" --format=json \
  >"$OUT/billing-project.json" 2>"$OUT/billing-project.err" || true
python3 - "$OUT/billing-project.json" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
if not p.exists() or not p.read_text().strip():
    print('WARN: billing association unavailable')
    raise SystemExit(0)
d = json.loads(p.read_text())
print('billingEnabled =', d.get('billingEnabled'))
print('billingAccountName =', d.get('billingAccountName') or d.get('name') or 'N/A')
PY

printf '\n[2/5] Schemas de telemetría AgentOps...\n'
for OBJ in fact_llm_calls vw_llm_usage_summary vw_tool_usage; do
  echo "--- agentops.$OBJ ---"
  if bq show --project_id="$PROJECT_ID" --format=prettyjson "agentops.$OBJ" >"$OUT/${OBJ}-schema.json" 2>"$OUT/${OBJ}-schema.err"; then
    python3 - "$OUT/${OBJ}-schema.json" <<'PY'
import json, pathlib, sys
d = json.loads(pathlib.Path(sys.argv[1]).read_text())
for f in d.get('schema', {}).get('fields', []):
    print(f"{f.get('name')}\t{f.get('type')}\t{f.get('mode','NULLABLE')}")
PY
  else
    echo 'WARN: no se pudo leer schema'
  fi
  echo
done

printf '[3/5] Volumen y rango temporal de fact_llm_calls...\n'
QUERY="SELECT COUNT(*) AS row_count FROM \\`$PROJECT_ID.agentops.fact_llm_calls\\`"
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=prettyjson "$QUERY" \
  >"$OUT/fact_llm_calls-count.json" 2>"$OUT/fact_llm_calls-count.err" || true
cat "$OUT/fact_llm_calls-count.json" 2>/dev/null || true

printf '\n[4/5] Muestra segura de vw_llm_usage_summary...\n'
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --max_rows=10 --format=prettyjson \
  "SELECT * FROM \\`$PROJECT_ID.agentops.vw_llm_usage_summary\\` LIMIT 10" \
  >"$OUT/vw_llm_usage_summary-sample.json" 2>"$OUT/vw_llm_usage_summary-sample.err" || true
cat "$OUT/vw_llm_usage_summary-sample.json" 2>/dev/null || true

printf '\n[5/5] Muestra segura de vw_tool_usage...\n'
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --max_rows=10 --format=prettyjson \
  "SELECT * FROM \\`$PROJECT_ID.agentops.vw_tool_usage\\` LIMIT 10" \
  >"$OUT/vw_tool_usage-sample.json" 2>"$OUT/vw_tool_usage-sample.err" || true
cat "$OUT/vw_tool_usage-sample.json" 2>/dev/null || true

printf '\n=== INSPECTION COMPLETADA ===\n'
printf 'EVIDENCE_DIR=%s\n' "$OUT"
printf '\nCriterio:\n'
printf '1) Tokens/requests/modelos solo se exponen si existen en telemetría real.\n'
printf '2) Costos USD no se calculan hasta validar fuente de precio/costo facturado.\n'
printf '3) Cloud Billing Export se habilita como paso separado y explícito.\n'
