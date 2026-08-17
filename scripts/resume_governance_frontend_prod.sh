#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="proyectopersonal-480420"
REGION="us-central1"
BACKEND_SERVICE="silver-refinement-agent"
FRONTEND_SERVICE="business-rules-silver-ui"
BACKEND_URL="https://silver-refinement-agent-mkqutd4koq-uc.a.run.app"
FRONTEND_URL="https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app"
EXPECTED_BACKEND_DIGEST="us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent@sha256:cafdc4322ca6e38c43560d5350ab32872f720b4ce111e1c88ea5318d06d8cb26"
FRONTEND_IMAGE="us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/business-rules-silver-ui:agents-prod-5c718b1-20260817021109"
STAMP="$(date -u +%Y%m%d%H%M%S)"
FRONTEND_REVISION="business-rules-silver-ui-governance-${STAMP}"
SOURCE_JSON="/tmp/business-rules-silver-ui-source-${STAMP}.json"
TARGET_JSON="/tmp/business-rules-silver-ui-governance-${STAMP}.json"

echo "=== VERIFY PROMOTED BACKEND ==="
BACKEND_REVISION="$(gcloud run services describe "$BACKEND_SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(status.traffic[0].revisionName)')"
BACKEND_DIGEST="$(gcloud run revisions describe "$BACKEND_REVISION" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(status.imageDigest)')"
test "$BACKEND_DIGEST" = "$EXPECTED_BACKEND_DIGEST"
curl -fsS "$BACKEND_URL/health" | jq -e '.status == "ok" and .version == "8.2.0"'
curl -fsS "$BACKEND_URL/agentops/governance/summary" | jq -e 'has("total_runs")'

echo "=== VERIFY BUILT FRONTEND IMAGE ==="
FRONTEND_ARTIFACT_DIGEST="$(gcloud artifacts docker images describe "$FRONTEND_IMAGE" \
  --project="$PROJECT_ID" --format='value(image_summary.digest)')"
test -n "$FRONTEND_ARTIFACT_DIGEST"
echo "FRONTEND_ARTIFACT_DIGEST=$FRONTEND_ARTIFACT_DIGEST"

echo "=== PREPARE CLOUD RUN SERVICE JSON ==="
gcloud run services describe "$FRONTEND_SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format=json > "$SOURCE_JSON"

jq --arg image "$FRONTEND_IMAGE" --arg revision "$FRONTEND_REVISION" '
  del(
    .status,
    .spec.traffic,
    .metadata.uid,
    .metadata.resourceVersion,
    .metadata.generation,
    .metadata.creationTimestamp,
    .metadata.selfLink
  )
  | .spec.template.metadata.name = $revision
  | .spec.template.spec.containers[0].image = $image
' "$SOURCE_JSON" > "$TARGET_JSON"

jq -e --arg image "$FRONTEND_IMAGE" --arg revision "$FRONTEND_REVISION" '
  .spec.template.metadata.name == $revision
  and .spec.template.spec.containers[0].image == $image
  and (.spec | has("traffic") | not)
  and (has("status") | not)
' "$TARGET_JSON"

echo "=== REPLACE FRONTEND TEMPLATE ==="
gcloud run services replace "$TARGET_JSON" \
  --project="$PROJECT_ID" --region="$REGION" --quiet

gcloud run services update-traffic "$FRONTEND_SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --to-revisions="${FRONTEND_REVISION}=100" --quiet

echo "=== VERIFY FRONTEND REVISION AND DIGEST ==="
DEPLOYED_DIGEST="$(gcloud run revisions describe "$FRONTEND_REVISION" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(status.imageDigest)')"
gcloud run revisions describe "$FRONTEND_REVISION" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='yaml(metadata.name,spec.containers[0].image,status.imageDigest)'
case "$DEPLOYED_DIGEST" in
  *@"$FRONTEND_ARTIFACT_DIGEST") ;;
  *) echo "ERROR: deployed digest does not match built image" >&2; exit 1 ;;
esac

INDEX_HTML="$(curl -fsS "$FRONTEND_URL")"
ASSET_PATH="$(printf '%s' "$INDEX_HTML" | sed -n 's/.*src="\([^"]*\.js\)".*/\1/p' | head -1)"
test -n "$ASSET_PATH"
curl -fsS "${FRONTEND_URL}${ASSET_PATH}" > /tmp/business-rules-silver-governance-prod.js
grep -Fq "$BACKEND_URL" /tmp/business-rules-silver-governance-prod.js
! grep -Fq "silver-refinement-agent-merge-test" /tmp/business-rules-silver-governance-prod.js
grep -Fq "Ejecutar Quality Review" /tmp/business-rules-silver-governance-prod.js
grep -Fq "Gobierno agéntico persistente" /tmp/business-rules-silver-governance-prod.js
grep -Fq "Persistencia BigQuery" /tmp/business-rules-silver-governance-prod.js
curl -fsSI "$FRONTEND_URL" | sed -n '1,20p'

echo "=== GOVERNANCE RELEASE PRODUCTION CONFORME ==="
echo "BACKEND_REVISION=$BACKEND_REVISION"
echo "BACKEND_DIGEST=$BACKEND_DIGEST"
echo "FRONTEND_REVISION=$FRONTEND_REVISION"
echo "FRONTEND_DIGEST=$DEPLOYED_DIGEST"
echo "FRONTEND_URL=$FRONTEND_URL"
