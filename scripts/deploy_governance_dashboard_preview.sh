#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-proyectopersonal-480420}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-business-rules-silver-governance-preview}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_DIR="$ROOT_DIR/preview/governance-dashboard"
EXPECTED_BACKEND_URL="${SILVER_API_URL:-https://silver-refinement-agent-mkqutd4koq-uc.a.run.app}"
FINOPS_API_URL="${FINOPS_API_URL:-https://silver-refinement-agent-merge-test-mkqutd4koq-uc.a.run.app}"

command -v gcloud >/dev/null
command -v curl >/dev/null

test -f "$PREVIEW_DIR/Dockerfile"
test -f "$PREVIEW_DIR/index.html"
test -f "$PREVIEW_DIR/app.js"
test -f "$PREVIEW_DIR/styles.css"
test -f "$PREVIEW_DIR/finops.js"
test -f "$PREVIEW_DIR/finops.css"
test -f "$PREVIEW_DIR/theme-red.css"

echo "=== Gobierno DataOps interactive preview ==="
echo "Project : $PROJECT_ID"
echo "Region  : $REGION"
echo "Service : $SERVICE"
echo "Backend : $EXPECTED_BACKEND_URL"
echo "FinOps  : $FINOPS_API_URL"
echo

echo "[1/6] Validando frontend preview..."
if command -v node >/dev/null 2>&1; then
  node --check "$PREVIEW_DIR/app.js"
  node --check "$PREVIEW_DIR/finops.js"
fi
grep -Fq 'detailDrawer' "$PREVIEW_DIR/index.html"
grep -Fq 'data-kpi-detail="runs"' "$PREVIEW_DIR/index.html"
grep -Fq 'id="finops"' "$PREVIEW_DIR/index.html"
grep -Fq 'finopsTokenTrend' "$PREVIEW_DIR/index.html"
grep -Fq 'finopsServiceCosts' "$PREVIEW_DIR/index.html"
grep -Fq 'FACTURADO' "$PREVIEW_DIR/index.html"
grep -Fq 'ATRIBUIDO' "$PREVIEW_DIR/index.html"
grep -Fq 'openRunDetail' "$PREVIEW_DIR/app.js"
grep -Fq 'openAgentDetail' "$PREVIEW_DIR/app.js"
grep -Fq 'data-run-id' "$PREVIEW_DIR/app.js"
for path in summary daily agents runs services; do
  grep -Fq "/agentops/finops/$path" "$PREVIEW_DIR/finops.js"
done
echo "PASS: shell interactivo, drill-downs y FinOps Billing-aware presentes"

echo
echo "[2/6] Validando backend canónico..."
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/health" >/tmp/governance-preview-backend-health.json
grep -Fq '"status"' /tmp/governance-preview-backend-health.json
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/agentops/governance/summary" >/tmp/governance-preview-summary.json
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/agentops/governance/runs?limit=1" >/tmp/governance-preview-runs.json
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/agentops/health" >/tmp/governance-preview-health.json
curl -fsS --retry 3 --retry-delay 1 "$EXPECTED_BACKEND_URL/silver-agents" >/tmp/governance-preview-agents.json
echo "PASS: backend y contratos AgentOps accesibles"

echo
echo "[3/6] Validando FinOps real del candidato..."
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/summary?days=30" >/tmp/governance-preview-finops-summary.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/daily?days=30" >/tmp/governance-preview-finops-daily.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/agents?days=30" >/tmp/governance-preview-finops-agents.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/runs?days=30&limit=20" >/tmp/governance-preview-finops-runs.json
curl -fsS --retry 3 --retry-delay 1 "$FINOPS_API_URL/agentops/finops/services?days=30" >/tmp/governance-preview-finops-services.json
python3 - <<'PY'
import json
from pathlib import Path
s = json.loads(Path('/tmp/governance-preview-finops-summary.json').read_text())
d = json.loads(Path('/tmp/governance-preview-finops-daily.json').read_text())
a = json.loads(Path('/tmp/governance-preview-finops-agents.json').read_text())
r = json.loads(Path('/tmp/governance-preview-finops-runs.json').read_text())
v = json.loads(Path('/tmp/governance-preview-finops-services.json').read_text())
assert int(s.get('llm_calls') or 0) > 0, s
assert int(s.get('total_tokens') or 0) > 0, s
assert isinstance(d.get('series'), list) and d['series'], d
assert isinstance(a.get('agents'), list) and a['agents'], a
assert a.get('cost_semantics') == 'ATRIBUCION_PENDIENTE', a
assert a.get('cost_usd') is None, a
assert isinstance(r.get('runs'), list) and r['runs'], r
assert r.get('cost_semantics') == 'ATRIBUCION_PENDIENTE', r
assert r.get('cost_usd') is None, r
billing = s.get('billing_cost_available') is True
assert v.get('billing_cost_available') is billing, (s, v)
if billing:
    assert s.get('cost_usd') is not None, s
    assert s.get('cost_semantics') == 'FACTURADO', s
    assert v.get('cost_semantics') == 'FACTURADO', v
    assert v.get('cost_usd') is not None, v
    print(f"PASS: FinOps real + Billing real disponible ({s.get('currency') or 'USD'} {s.get('cost_usd')})")
else:
    assert s.get('cost_usd') is None, s
    assert s.get('cost_semantics') == 'NO_DISPONIBLE', s
    assert v.get('cost_semantics') == 'NO_DISPONIBLE', v
    assert v.get('services') == [], v
    print('PASS: FinOps real disponible; Billing aún pendiente sin USD sintéticos')
PY

echo
echo "[4/6] Desplegando preview aislado en Cloud Run..."
gcloud run deploy "$SERVICE" \
  --source "$PREVIEW_DIR" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --quiet

PREVIEW_URL="$(gcloud run services describe "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format='value(status.url)')"

test -n "$PREVIEW_URL"

echo
echo "[5/6] Smoke test del frontend desplegado..."
PREVIEW_HTML=/tmp/governance-preview-index.html
PREVIEW_JS=/tmp/governance-preview-app.js
PREVIEW_FINOPS_JS=/tmp/governance-preview-finops.js
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/" -o "$PREVIEW_HTML"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/app.js" -o "$PREVIEW_JS"
curl -fsS --retry 3 --retry-delay 1 "$PREVIEW_URL/finops.js" -o "$PREVIEW_FINOPS_JS"

grep -Fq 'Gobierno DataOps — Business Rules Silver' "$PREVIEW_HTML"
grep -Fq 'Preview interactivo' "$PREVIEW_HTML"
grep -Fq 'FinOps IA · consumo real' "$PREVIEW_HTML"
grep -Fq 'Facturación por servicio GCP' "$PREVIEW_HTML"
grep -Fq '/agentops/governance/summary' "$PREVIEW_JS"
grep -Fq '/silver-agents' "$PREVIEW_JS"
grep -Fq 'openRunDetail' "$PREVIEW_JS"
grep -Fq 'openAgentDetail' "$PREVIEW_JS"
grep -Fq '/agentops/finops/services' "$PREVIEW_FINOPS_JS"
grep -Fq 'Costo atribuido: pendiente' "$PREVIEW_FINOPS_JS"
echo "PASS: preview interactivo servido con Gobierno + FinOps Billing-aware"

echo
echo "[6/6] Preview listo"
echo "========================================================"
echo "PREVIEW_URL=$PREVIEW_URL"
echo "DIRECT_DASHBOARD_URL=$PREVIEW_URL/"
echo "DEEP_LINK_FORMAT=$PREVIEW_URL/#run/<run_id>"
echo "BACKEND_URL=$EXPECTED_BACKEND_URL"
echo "FINOPS_API_URL=$FINOPS_API_URL"
echo "========================================================"
