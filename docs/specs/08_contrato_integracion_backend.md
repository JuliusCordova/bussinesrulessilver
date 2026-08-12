# Contrato de Integracion Backend - Business Rules Silver

## Backend

Servicio validado:

- `silver-refinement-agent`

URL validada:

- `https://silver-refinement-agent-mkqutd4koq-uc.a.run.app`

Health:

- `module`: `silver-refinement`
- `version`: `8.1.3`

## Documentos fuente

- `docs/discovery/openapi/silver-refinement-openapi.json`
- `docs/discovery/openapi/core-endpoints.json`
- `docs/discovery/openapi/key-schemas.json`
- `docs/discovery/openapi/states-and-actions.json`

## Endpoints por modulo

### Workflow

- `POST /silver-workflows`
- `GET /silver-workflows`
- `GET /silver-workflows/{workflow_id}`

Schemas clave:

- `CreateSilverWorkflowRequest`
- `SilverWorkflowRecord`
- `WorkflowStatus`
- `WorkflowAction`

### Catalogo

- `GET /silver-workflows/catalog/projects/{project_id}/datasets`
- `GET /silver-workflows/catalog/projects/{project_id}/datasets/{dataset_id}/tables`
- `GET /silver-workflows/catalog/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}`

Uso UI:

- selector de proyecto
- selector de dataset
- selector de tabla
- inspector de schema

### Fuente y mapping

- `POST /silver-workflows/{workflow_id}/confirm-source`
- `POST /silver-workflows/{workflow_id}/mapping-recommendations`

Schemas clave:

- `ConfirmWorkflowSourceRequest`
- `GenerateMappingRecommendationRequest`
- `MappingRecommendationResponse`

### Reglas de negocio

- `POST /silver-workflows/{workflow_id}/business-rules/generate`
- `PUT /silver-workflows/{workflow_id}/business-rules/draft`
- `POST /silver-workflows/{workflow_id}/business-rules/confirm`

Schemas clave:

- `GenerateBusinessRulesRequest`
- `SaveBusinessRulesDraftRequest`
- `ConfirmBusinessRulesRequest`
- `BusinessRulesSection`

### Calidad y specification

- `POST /silver-workflows/{workflow_id}/quality-review`
- `POST /silver-workflows/{workflow_id}/specification`

Schemas clave:

- `ReviewQualityRequest`
- `SaveSilverSpecificationRequest`

### Artefactos

- `GET /silver-refinement/specs/{spec_id}/artifacts`
- `POST /silver-refinement/specs/{spec_id}/artifacts/generate`
- `POST /silver-refinement/specs/{spec_id}/artifacts/ddl`
- `GET /silver-refinement/specs/{spec_id}/artifacts/current/{artifact_type}`
- `GET /silver-refinement/specs/{spec_id}/artifacts/current/{artifact_type}/content`

Schemas clave:

- `GenerateArtifactPackageRequest`
- `GenerateSilverDDLRequest`
- `ArtifactPackageResponse`
- `ArtifactRecord`

### Ejecucion

- `POST /executions`
- `GET /executions/{execution_id}`
- `POST /executions/{execution_id}/validate-package`
- `POST /executions/{execution_id}/submit`
- `POST /executions/{execution_id}/sync-status`

Schemas clave:

- `CreateExecutionRequest`
- `ExecutionRecord`
- `PackageValidationResponse`
- `DataprocSubmissionResponse`
- `ExecutionMonitoringResponse`

## Estados

Workflow:

- `DRAFT`
- `IN_PROGRESS`
- `AWAITING_REVIEW`
- `APPROVED`
- `EXECUTING`
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`

Acciones:

- `CONFIRM_SOURCE`
- `DEFINE_BUSINESS_RULES`
- `GENERATE_BUSINESS_RULES`
- `CONFIRM_BUSINESS_RULES`
- `REVIEW_MAPPING`
- `REVIEW_QUALITY`
- `GENERATE_ARTIFACTS`
- `REVIEW_GOVERNANCE`
- `CREATE_EXECUTION`
- `MONITOR_EXECUTION`
- `VALIDATE_SILVER`
- `VIEW_RESULT`

Execution:

- `PENDING`
- `VALIDATED`
- `QUEUED`
- `RUNNING`
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`

## Nota de gobernanza

`GovernanceStatus` no aparece como schema formal en el discovery actual. Para MVP, gobernanza se tratara por endpoints y respuestas reales, no como enum cerrado.
