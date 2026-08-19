#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-proyectopersonal-480420}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-business-rules-silver-governance-preview}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_DIR="$ROOT_DIR/preview/governance-dashboard"
EXPECTED_BACKEND_URL="${SILVER_API_URL:-https://silver-refinement-agent-mkqutd4koq-uc.a.run.app}"

command -v gcloud >/dev/null
command -v curl >/dev/null

test -f "$PREVIEW_DIR/Dockerfile"
test -f "$PREVIEW_DIR/index.html"
test -f "$PREVIEW_DIR/app.js"

echo "=== Gobierno DataOps preview ==="
echo "Project: $PROJECT_ID"
echo "Region : $REGION"
echo "Service: $SERVICE"
echo "Backend: $EXPECTED_BACKEND_URL"
echo

echo "[1/4] Validando backend canónico..."
curl -fsS "$EXPECTED_BACKEND_URL/health" | grep -q '"status"'
curl -fsS "$EXPECTED_BACKEND_URL/agentops/governance/summary" >/tmp/governance-preview-summary.json
curl -fsS "$EXPECTED_BACKEND_URL/agentops/governance/runs?limit=1" >/tmp/governance-preview-runs.json
echo "PASS: backend y contratos AgentOps accesibles"

echo
echo "[2/4] Desplegando preview aislado en Cloud Run..."
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
echo "[3/4] Smoke test del frontend preview..."
curl -fsS "$PREVIEW_URL" | grep -Fq 'Gobierno DataOps — Business Rules Silver'
curl -fsS "$PREVIEW_URL/app.js" | grep -Fq '/agentops/governance/summary'
curl -fsS "$PREVIEW_URL/app.js" | grep -Fq '/silver-agents'
echo "PASS: preview servido y enlazado a contratos canónicos"

echo
echo "[4/4] Preview listo"
echo "=============================================="
echo "PREVIEW_URL=$PREVIEW_URL"
echo "DIRECT_DASHBOARD_URL=$PREVIEW_URL/"
echo "BACKEND_URL=$EXPECTED_BACKEND_URL"
echo "=============================================="
