#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-proyectopersonal-480420}"
REGION="${REGION:-us-central1}"
BACKEND_SERVICE="silver-refinement-agent-merge-test"
FRONTEND_SERVICE="business-rules-silver-ui-agents-test"

echo "=== SYNC MAIN ==="
git pull --ff-only origin main

echo "=== BUILD + TEST + DEPLOY BACKEND CANDIDATE ==="
gcloud builds submit .   --project="$PROJECT_ID"   --config=cloudbuild.backend-agents-candidate.yaml

echo "=== BUILD + TEST + DEPLOY FRONTEND CANDIDATE ==="
gcloud builds submit .   --project="$PROJECT_ID"   --config=cloudbuild.frontend-agents-candidate.yaml

BACKEND_URL="$(gcloud run services describe "$BACKEND_SERVICE"   --project="$PROJECT_ID"   --region="$REGION"   --format='value(status.url)')"
FRONTEND_URL="$(gcloud run services describe "$FRONTEND_SERVICE"   --project="$PROJECT_ID"   --region="$REGION"   --format='value(status.url)')"

echo "=== CANDIDATES READY ==="
echo "BACKEND_URL=$BACKEND_URL"
echo "FRONTEND_URL=$FRONTEND_URL"
echo
echo "Prueba manual obligatoria:"
echo "1. Selecciona seguros_bronce.pagos_primas."
echo "2. Confirma que el schema no contiene producto_id."
echo "3. Abre la lista Silver y prueba tabla existente/nombre nuevo."
echo "4. Ejecuta perfilamiento: sin clave segura debe proponer FULL."
echo "5. Edita estrategia y confirma que queda marcada como USER."
echo "6. Genera el PDF, visualizalo y descargalo."
