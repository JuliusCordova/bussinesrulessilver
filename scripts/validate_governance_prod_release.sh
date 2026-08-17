#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="proyectopersonal-480420"
REGION="us-central1"
BACKEND_SERVICE="silver-refinement-agent"
FRONTEND_SERVICE="business-rules-silver-ui"
BACKEND_URL="https://silver-refinement-agent-mkqutd4koq-uc.a.run.app"
FRONTEND_URL="https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app"
EXPECTED_BACKEND_REVISION="silver-refinement-agent-agents820-20260817021109"
EXPECTED_FRONTEND_REVISION="business-rules-silver-ui-governance-20260817022003"
EXPECTED_BACKEND_DIGEST="us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent@sha256:cafdc4322ca6e38c43560d5350ab32872f720b4ce111e1c88ea5318d06d8cb26"
EXPECTED_FRONTEND_DIGEST="us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/business-rules-silver-ui@sha256:81ef71c401d16949f81f1f998120d42fa85960efb8fe49431093c9454bc0f9d4"

echo "=== 1. TRAFFIC AND DIGESTS ==="
BACKEND_TRAFFIC="$(gcloud run services describe "$BACKEND_SERVICE" --project="$PROJECT_ID" --region="$REGION" --format=json)"
FRONTEND_TRAFFIC="$(gcloud run services describe "$FRONTEND_SERVICE" --project="$PROJECT_ID" --region="$REGION" --format=json)"
printf '%s' "$BACKEND_TRAFFIC" | jq -e --arg revision "$EXPECTED_BACKEND_REVISION" '
  any(.status.traffic[]; .revisionName == $revision and .percent == 100)'
printf '%s' "$FRONTEND_TRAFFIC" | jq -e --arg revision "$EXPECTED_FRONTEND_REVISION" '
  any(.status.traffic[]; .revisionName == $revision and .percent == 100)'

BACKEND_DIGEST="$(gcloud run revisions describe "$EXPECTED_BACKEND_REVISION" --project="$PROJECT_ID" --region="$REGION" --format='value(status.imageDigest)')"
FRONTEND_DIGEST="$(gcloud run revisions describe "$EXPECTED_FRONTEND_REVISION" --project="$PROJECT_ID" --region="$REGION" --format='value(status.imageDigest)')"
test "$BACKEND_DIGEST" = "$EXPECTED_BACKEND_DIGEST"
test "$FRONTEND_DIGEST" = "$EXPECTED_FRONTEND_DIGEST"
echo "Digests y tráfico: PASS"

echo "=== 2. BACKEND HEALTH, CORS AND AGENTS ==="
curl -fsS "$BACKEND_URL/health" | jq -e '.status == "ok" and .version == "8.2.0"'
curl -fsS -D /tmp/silver-final-cors.headers -o /tmp/silver-final-cors.body \
  -X OPTIONS "$BACKEND_URL/silver-agents" \
  -H "Origin: $FRONTEND_URL" \
  -H "Access-Control-Request-Method: GET"
grep -qi '^access-control-allow-origin: \*' /tmp/silver-final-cors.headers
curl -fsS "$BACKEND_URL/silver-agents" | jq -e '
  map(.name) | sort ==
  ["business-rule-validator","mapping-advisor","notebook-generator","orchestrator","quality-rule-advisor","table-profiler"]'
echo "Health, CORS y agentes: PASS"

echo "=== 3. GOVERNANCE PERSISTENCE ==="
SUMMARY="$(curl -fsS "$BACKEND_URL/agentops/governance/summary")"
printf '%s' "$SUMMARY" | jq -e '
  has("total_runs") and has("active_agents") and has("completed")
  and (.total_runs >= 1) and (.active_agents >= 1)'
curl -fsS "$BACKEND_URL/agentops/governance/runs?limit=10" | jq -e '
  (.runs | type == "array") and (.total >= 1)'
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=json \
  'SELECT COUNT(*) AS total_runs FROM `proyectopersonal-480420.dataops_control.silver_agent_governance_runs`' \
  | jq -e '.[0].total_runs | tonumber >= 1'
echo "Persistencia AgentOps/BigQuery: PASS"

echo "=== 4. API CONTRACTS ==="
curl -fsS "$BACKEND_URL/openapi.json" | jq -e '
  .paths
  | has("/agentops/governance/summary")
    and has("/agentops/governance/runs")
    and has("/silver-refinement/specs/{spec_id}/artifacts/current/{artifact_type}/download")
    and has("/silver-workflows/{workflow_id}/quality-review")'
echo "Contratos API: PASS"

echo "=== 5. PRODUCTION FRONTEND BUNDLE ==="
curl -fsSI "$FRONTEND_URL" | grep -q '200'
INDEX_HTML="$(curl -fsS "$FRONTEND_URL")"
ASSET_PATH="$(printf '%s' "$INDEX_HTML" | sed -n 's/.*src="\([^"]*\.js\)".*/\1/p' | head -1)"
test -n "$ASSET_PATH"
curl -fsS "${FRONTEND_URL}${ASSET_PATH}" > /tmp/business-rules-silver-final-prod.js
grep -Fq "$BACKEND_URL" /tmp/business-rules-silver-final-prod.js
! grep -Fq "silver-refinement-agent-merge-test" /tmp/business-rules-silver-final-prod.js
for expected in \
  "Ejecutar Quality Review" \
  "Generar package" \
  "Gobierno agéntico persistente" \
  "Persistencia BigQuery" \
  "Historial persistente de agentes" \
  "Alertas AgentOps"
do
  grep -Fq "$expected" /tmp/business-rules-silver-final-prod.js
done
echo "Bundle frontend productivo: PASS"

echo "=== FINAL PRODUCTION VALIDATION: CONFORME ==="
echo "BACKEND_REVISION=$EXPECTED_BACKEND_REVISION"
echo "BACKEND_DIGEST=$BACKEND_DIGEST"
echo "FRONTEND_REVISION=$EXPECTED_FRONTEND_REVISION"
echo "FRONTEND_DIGEST=$FRONTEND_DIGEST"
echo "FRONTEND_URL=$FRONTEND_URL"
