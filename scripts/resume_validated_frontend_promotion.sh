#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="proyectopersonal-480420"
REGION="us-central1"
BACKEND_SERVICE="silver-refinement-agent"
FRONTEND_SERVICE="business-rules-silver-ui"
BACKEND_URL="https://silver-refinement-agent-mkqutd4koq-uc.a.run.app"
FRONTEND_URL="https://business-rules-silver-ui-mkqutd4koq-uc.a.run.app"
EXPECTED_BACKEND_DIGEST="us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/silver-refinement-agent@sha256:e40cb0ba612a78040020619082ce316bb648755d5817178ceceee9915ae79bfc"
FRONTEND_IMAGE="us-central1-docker.pkg.dev/proyectopersonal-480420/dataops/business-rules-silver-ui:validated-de7f84b-20260817012813"
STAMP="$(date -u +%Y%m%d%H%M%S)"
SUFFIX="validated-$STAMP"

echo "=== VERIFY VALIDATED BACKEND IS IN PRODUCTION ==="
BACKEND_REVISION="$(gcloud run services describe "$BACKEND_SERVICE"   --project="$PROJECT_ID" --region="$REGION"   --format='value(status.latestReadyRevisionName)')"
BACKEND_DIGEST="$(gcloud run revisions describe "$BACKEND_REVISION"   --project="$PROJECT_ID" --region="$REGION"   --format='value(status.imageDigest)')"
test "$BACKEND_DIGEST" = "$EXPECTED_BACKEND_DIGEST"
curl -fsS "$BACKEND_URL/health" | jq -e '.status == "ok" and .version == "8.2.0"'

echo "=== SNAPSHOT CURRENT FRONTEND TRAFFIC ==="
gcloud run services describe "$FRONTEND_SERVICE"   --project="$PROJECT_ID" --region="$REGION"   --format='yaml(status.latestReadyRevisionName,status.traffic)'   | tee "/tmp/frontend-before-resume-$STAMP.yaml"

echo "=== DEPLOY VALIDATED FRONTEND WITH NO TRAFFIC ==="
gcloud run deploy "$FRONTEND_SERVICE"   --project="$PROJECT_ID"   --region="$REGION"   --image="$FRONTEND_IMAGE"   --platform=managed   --allow-unauthenticated   --port=8080   --memory=512Mi   --cpu=1   --timeout=300   --revision-suffix="$SUFFIX"   --no-traffic   --quiet

NEW_REVISION="$(gcloud run services describe "$FRONTEND_SERVICE"   --project="$PROJECT_ID" --region="$REGION"   --format='value(status.latestReadyRevisionName)')"
test -n "$NEW_REVISION"

echo "=== VERIFY REVISION IMAGE ==="
gcloud run revisions describe "$NEW_REVISION"   --project="$PROJECT_ID" --region="$REGION"   --format='yaml(metadata.name,spec.containers[0].image,status.imageDigest)'

REVISION_URL="https://$SUFFIX---business-rules-silver-ui-mkqutd4koq-uc.a.run.app"
INDEX_HTML="$(curl -fsS "$REVISION_URL")"
ASSET_PATH="$(printf '%s' "$INDEX_HTML" | sed -n 's/.*src="\([^"]*\.js\)".*/\1/p' | head -1)"
test -n "$ASSET_PATH"
curl -fsS "$REVISION_URL$ASSET_PATH" > "/tmp/frontend-resume-$STAMP.js"
grep -Fq "$BACKEND_URL" "/tmp/frontend-resume-$STAMP.js"
! grep -Fq "silver-refinement-agent-merge-test" "/tmp/frontend-resume-$STAMP.js"

echo "=== ROUTE 100 PERCENT TO VALIDATED FRONTEND ==="
gcloud run services update-traffic "$FRONTEND_SERVICE"   --project="$PROJECT_ID" --region="$REGION"   --to-revisions="$NEW_REVISION=100"   --quiet

curl -fsSI "$FRONTEND_URL" | sed -n '1,20p'
PROD_HTML="$(curl -fsS "$FRONTEND_URL")"
PROD_ASSET="$(printf '%s' "$PROD_HTML" | sed -n 's/.*src="\([^"]*\.js\)".*/\1/p' | head -1)"
curl -fsS "$FRONTEND_URL$PROD_ASSET" > "/tmp/frontend-prod-resume-$STAMP.js"
grep -Fq "$BACKEND_URL" "/tmp/frontend-prod-resume-$STAMP.js"
! grep -Fq "silver-refinement-agent-merge-test" "/tmp/frontend-prod-resume-$STAMP.js"

echo "=== PRODUCTION VALIDATED CUT CONFORME ==="
echo "BACKEND_REVISION=$BACKEND_REVISION"
echo "BACKEND_DIGEST=$BACKEND_DIGEST"
echo "FRONTEND_REVISION=$NEW_REVISION"
echo "FRONTEND_IMAGE=$FRONTEND_IMAGE"
echo "FRONTEND_URL=$FRONTEND_URL"
