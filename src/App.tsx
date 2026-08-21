import { useEffect, useMemo, useState } from 'react';
import {
  demoWorkflowPatch,
  silverApi,
  type AgentGovernanceRun,
  type AgentGovernanceSummary,
  type AgentOpsDashboard,
  type AgentOpsHealth,
  type CatalogTableDetail,
  type SilverAgentDescriptor,
  type SilverAgentRunRequest,
  type SilverWorkflowRecord,
} from './api';
import { businessRules, seedColumns, seedSource } from './seed';
import { toBackendTransformation } from './transformations';
import type { CatalogField, GeneratedArtifact, MappingRule, StepId, WorkflowState } from './types';

const steps: Array<{ id: StepId; label: string; description: string }> = [
  { id: 'source', label: 'Origen y destino', description: 'Fuente Bronze y tabla Silver' },
  { id: 'incremental', label: 'Incrementalidad', description: 'Business key y watermark' },
  { id: 'mapping', label: 'Mapping', description: 'Transformaciones y campos derivados' },
  { id: 'rules', label: 'Reglas', description: 'Reglas editables y aprobacion' },
  { id: 'artifacts', label: 'Artefactos', description: 'DDL, notebook y paquete' },
  { id: 'execution', label: 'Dataproc', description: 'Validacion y ejecucion' },
  { id: 'governance', label: 'Gobierno', description: 'AgentOps, auditoria y salud' },
];

const artifacts = [
  'SILVER_DDL',
  'NOTEBOOK',
  'PYSPARK_SCRIPT',
  'MANIFEST_JSON',
  'SPECIFICATION_JSON',
  'MAPPING_JSON',
];

const stepOrder = steps.map((step) => step.id);
const REQUESTED_BY = 'julio.cordova@gmail.com';
const seedSchemaColumns = seedColumns.map((column) => ({
  name: column.name,
  data_type: column.type,
  mode: column.usage === 'business_key' ? 'REQUIRED' : 'NULLABLE',
  usage: column.usage,
}));

function workflowPatchFromRecord(record: SilverWorkflowRecord): Partial<WorkflowState> {
  return {
    workflowId: record.workflow_id,
    version: record.version,
    status: record.status,
    specId: record.spec_id ?? undefined,
    executionId: record.execution_id ?? undefined,
    mappingVersion: record.mapping_version ?? undefined,
  };
}

function currentVersion(workflow: WorkflowState) {
  return workflow.version ?? 1;
}

function toExecutionStatus(status?: string | null): WorkflowState['executionStatus'] | undefined {
  if (!status) return undefined;
  const normalized = status.toUpperCase();
  if (
    normalized === 'PENDING' ||
    normalized === 'VALIDATED' ||
    normalized === 'QUEUED' ||
    normalized === 'RUNNING' ||
    normalized === 'SUCCEEDED' ||
    normalized === 'FAILED' ||
    normalized === 'CANCELLED'
  ) {
    return normalized;
  }
  return undefined;
}

function normalizeError(error: unknown) {
  const raw = error instanceof Error ? error.message : String(error);
  const backendMatch = raw.match(/^Backend\s+(\d+):\s*(.*)$/s);

  if (!backendMatch) {
    return { summary: raw, detail: raw };
  }

  const [, status, detailText] = backendMatch;
  try {
    const parsed = JSON.parse(detailText);
    const detail = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
    return {
      summary: `Backend ${status}: ${detail}`,
      detail: JSON.stringify(parsed, null, 2),
    };
  } catch {
    return {
      summary: `Backend ${status}: ${detailText}`,
      detail: detailText,
    };
  }
}

function normalizedFieldType(field: CatalogField) {
  return String(field.type || '').toUpperCase();
}

function normalizeCatalogFields(detail: CatalogTableDetail | null): CatalogField[] {
  if (!detail) return [];
  const rawSchema = Array.isArray(detail.schema)
    ? detail.schema
    : detail.schema?.fields ??
      detail.fields ??
      detail.columns ??
      (Array.isArray(detail.table?.schema) ? detail.table.schema : detail.table?.schema?.fields) ??
      detail.table?.fields ??
      detail.table?.columns ??
      [];

  return rawSchema
    .map((field) => {
      const candidate = field as CatalogField & { data_type?: string };
      return {
        name: String(candidate.name ?? ''),
        type: String(candidate.type ?? candidate.data_type ?? ''),
        mode: candidate.mode ?? 'NULLABLE',
        description: candidate.description,
      };
    })
    .filter((field) => Boolean(field.name && field.type));
}

function inferTableContract(fields: CatalogField[]) {
  const names = new Set(fields.map((field) => field.name));
  const preferredKey = fields.find(
    (field) => /_id$/i.test(field.name) && !field.name.startsWith('bronze_'),
  );
  const requiredKey = fields.find(
    (field) => field.mode === 'REQUIRED' && /id|key|codigo/i.test(field.name),
  );
  const businessKey = preferredKey?.name ?? requiredKey?.name;

  const watermark = fields.find(
    (field) =>
      ['TIMESTAMP', 'DATETIME', 'DATE'].includes(normalizedFieldType(field)) &&
      /watermark|fecha_ingesta|updated|modified|timestamp|fecha/i.test(field.name),
  )?.name;

  const metric = fields.find(
    (field) =>
      ['INT64', 'INTEGER', 'FLOAT64', 'FLOAT', 'NUMERIC', 'BIGNUMERIC'].includes(normalizedFieldType(field)) &&
      field.name !== businessKey &&
      !field.name.startsWith('bronze_'),
  )?.name;

  return {
    sourceColumns: fields,
    businessKeys: businessKey && names.has(businessKey) ? [businessKey] : [],
    watermarkColumn: watermark,
    metricColumn: metric,
  };
}

function inferProfileContract(profile: Record<string, unknown>, fallback: CatalogField[]) {
  const rawColumns = Array.isArray(profile.columns) ? profile.columns : [];
  const profileColumns = rawColumns
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => ({
      name: String(item.name ?? ''),
      type: String(item.type ?? item.data_type ?? ''),
      mode: String(item.mode ?? 'NULLABLE'),
      description: typeof item.description === 'string' ? item.description : undefined,
    }))
    .filter((field) => Boolean(field.name && field.type));
  const columns = profileColumns.length ? profileColumns : fallback;
  const names = new Set(columns.map((column) => column.name));
  const candidates = Array.isArray(profile.business_key_candidates)
    ? profile.business_key_candidates.map(String).filter((name) => names.has(name))
    : [];
  const partitioning = typeof profile.partitioning === 'string' && names.has(profile.partitioning)
    ? profile.partitioning
    : undefined;
  const schemaContract = inferTableContract(columns);
  const businessKeys = candidates.slice(0, 1);
  const watermarkColumn = partitioning ?? schemaContract.watermarkColumn;
  const metricColumn = schemaContract.metricColumn;
  const loadStrategy: 'FULL' | 'MERGE' = businessKeys.length ? 'MERGE' : 'FULL';
  const inferenceReasons = businessKeys.length
    ? [
        `MERGE propuesto: ${businessKeys[0]} tiene cero nulos y cardinalidad compatible con el total de filas.`,
        watermarkColumn
          ? `Watermark propuesto por tipo temporal/nombre o particion: ${watermarkColumn}.`
          : 'No se detecto watermark seguro; MERGE opera por clave.',
      ]
    : [
        'FULL propuesto: el perfil no encontro una clave candidata simultaneamente no nula y unica.',
        'Puedes seleccionar manualmente una clave y cambiar a MERGE bajo tu aprobacion.',
      ];
  return {
    sourceColumns: columns,
    businessKeys,
    watermarkColumn,
    metricColumn,
    loadStrategy,
    inferenceSource: 'BIGQUERY_PROFILE' as const,
    inferenceReasons,
  };
}

function directMappingFromColumns(columns: CatalogField[]): MappingRule[] {
  return columns.map((column) => ({
    sourceColumn: column.name,
    targetColumn: column.name,
    targetType: column.type,
    transformationType: 'DIRECT',
    include: true,
    nullable: column.mode !== 'REQUIRED',
    confidence: 1,
    reason: 'Mapping directo inicial desde el schema confirmado.',
    requiresApproval: false,
  }));
}

function mappingFromRecommendation(columns: Array<Record<string, unknown>>): MappingRule[] {
  return columns.map((column) => {
    const transformation =
      column.transformation && typeof column.transformation === 'object'
        ? column.transformation as Record<string, unknown>
        : {};
    return {
      sourceColumn: String(
        column.source_column ??
        (Array.isArray(transformation.source_columns) ? transformation.source_columns[0] : '') ??
        '',
      ),
      targetColumn: String(column.target_column ?? ''),
      targetType: String(column.target_type ?? 'STRING'),
      transformationType: String(transformation.type ?? column.transformation_type ?? 'DIRECT'),
      include: column.include !== false,
      nullable: column.nullable !== false,
      parameters:
        transformation.parameters && typeof transformation.parameters === 'object'
          ? transformation.parameters as Record<string, unknown>
          : {},
      confidence: typeof column.confidence === 'number' ? column.confidence : undefined,
      reason: typeof column.reason === 'string' ? column.reason : undefined,
      risk: typeof column.risk === 'string' ? column.risk : undefined,
      requiresApproval: Boolean(column.requires_approval),
    };
  }).filter((row) => Boolean(row.sourceColumn && row.targetColumn));
}

function toBackendQualityRules(workflow: WorkflowState) {
  const rules: Array<Record<string, unknown>> = [];

  for (const key of workflow.businessKeys ?? []) {
    rules.push(
      {
        rule_name: `${key}_not_null`,
        rule_dimension: 'VALIDITY',
        rule_type: 'NOT_NULL',
        column_name: key,
        rule_parameters: {},
        warning_threshold: 0,
        critical_threshold: 1,
        severity_level: 'CRITICAL',
        active_flag: true,
      },
      {
        rule_name: `${key}_unique`,
        rule_dimension: 'UNIQUENESS',
        rule_type: 'UNIQUE',
        column_name: key,
        rule_parameters: {},
        warning_threshold: 0,
        critical_threshold: 1,
        severity_level: 'CRITICAL',
        active_flag: true,
      },
    );
  }

  if (workflow.watermarkColumn) {
    rules.push({
      rule_name: `${workflow.watermarkColumn}_not_null`,
      rule_dimension: 'COMPLETENESS',
      rule_type: 'NOT_NULL',
      column_name: workflow.watermarkColumn,
      rule_parameters: {},
      warning_threshold: 0,
      critical_threshold: 1,
      severity_level: 'HIGH',
      active_flag: true,
    });
  }

  if (!rules.length) {
    const requiredColumn = workflow.sourceColumns?.find((column) => column.mode === 'REQUIRED');
    if (requiredColumn) {
      rules.push({
        rule_name: `${requiredColumn.name}_not_null`,
        rule_dimension: 'COMPLETENESS',
        rule_type: 'NOT_NULL',
        column_name: requiredColumn.name,
        rule_parameters: {},
        warning_threshold: 0,
        critical_threshold: 1,
        severity_level: 'HIGH',
        active_flag: true,
      });
    }
  }

  return rules;
}


function parseAgentJson(output: string): Record<string, unknown> {
  const cleaned = output.trim().replace(/^\`\`\`(?:json)?\s*/i, '').replace(/\s*\`\`\`$/, '');
  const parsed = JSON.parse(cleaned);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('El agente no devolvio un objeto JSON valido.');
  }
  return parsed as Record<string, unknown>;
}

function buildAgentRequest(workflow: WorkflowState): SilverAgentRunRequest {
  if (!workflow.projectId || !workflow.sourceDataset || !workflow.sourceTable) {
    throw new Error('Selecciona una tabla origen antes de ejecutar agentes.');
  }
  if (!workflow.targetDataset || !workflow.targetTable) {
    throw new Error('Define la tabla destino antes de ejecutar agentes.');
  }

  return {
    project_id: workflow.projectId,
    source_dataset: workflow.sourceDataset,
    source_table: workflow.sourceTable,
    target_project_id: workflow.projectId,
    target_dataset: workflow.targetDataset,
    target_table: workflow.targetTable,
    columns: (workflow.sourceColumns ?? []).map((column) => ({
      name: column.name,
      type: column.type,
      mode: column.mode ?? 'NULLABLE',
    })),
    load_strategy: workflow.loadStrategy === 'MERGE'
      ? {
          type: 'MERGE',
          business_keys: workflow.businessKeys ?? [],
          watermark_column: workflow.watermarkColumn ?? null,
        }
      : { type: 'FULL', business_keys: [] },
    physical_design: {
      partitioning: workflow.watermarkColumn
        ? { enabled: true, column: workflow.watermarkColumn, granularity: 'DAY' }
        : { enabled: false },
      clustering_columns: (workflow.businessKeys ?? []).slice(0, 4),
    },
    business_keys: workflow.businessKeys ?? [],
    watermark_column: workflow.watermarkColumn ?? null,
    business_rules: toBackendQualityRules(workflow),
    approved_quality_rules: workflow.approvedQualityRules ?? [],
    context: 'MVP gobernado: toda recomendacion requiere aprobacion humana.',
    requested_by: REQUESTED_BY,
  };
}

function buildArtifactContract(workflow: WorkflowState) {
  const mapping = workflow.mappingRules?.length
    ? workflow.mappingRules
    : directMappingFromColumns(workflow.sourceColumns ?? []);
  const columns = mapping
    .filter((rule) => rule.include)
    .map((rule) => ({
      name: rule.targetColumn,
      data_type: rule.targetType,
      nullable:
        rule.nullable &&
        !(workflow.businessKeys ?? []).includes(rule.targetColumn),
      source_column: rule.sourceColumn,
      transformation: toBackendTransformation(rule.transformationType),
      include: true,
      confidence: rule.confidence,
      recommendation_reason: rule.reason,
      recommendation_risk: rule.risk,
      requires_approval: rule.requiresApproval ?? false,
    }));
  const loadStrategy = workflow.loadStrategy === 'MERGE'
    ? {
        type: 'MERGE',
        watermark_column: workflow.watermarkColumn ?? null,
        initial_watermark: workflow.watermarkColumn ? seedSource.initialWatermark : null,
        business_keys: workflow.businessKeys ?? [],
      }
    : { type: 'FULL', business_keys: [] };
  const physicalDesign = {
    partitioning: workflow.watermarkColumn
      ? { enabled: true, column: workflow.watermarkColumn, granularity: 'DAY' }
      : { enabled: false },
    clustering_columns: (workflow.businessKeys ?? []).slice(0, 4),
  };
  const qualityRules = workflow.approvedQualityRules?.length
    ? workflow.approvedQualityRules
    : toBackendQualityRules(workflow);
  return { columns, loadStrategy, physicalDesign, qualityRules };
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function proposalToBackendRule(proposal: Record<string, unknown>) {
  const columnName = String(proposal.column_name ?? '');
  const ruleType = String(proposal.rule_type ?? '');
  return {
    rule_name: `${columnName}_${ruleType.toLowerCase()}`,
    rule_dimension: ruleType === 'UNIQUE' ? 'UNIQUENESS' : 'VALIDITY',
    rule_type: ruleType,
    column_name: columnName,
    rule_parameters: (proposal.rule_parameters as Record<string, unknown> | undefined) ?? {},
    warning_threshold: 0,
    critical_threshold: 1,
    severity_level: String(proposal.severity_level ?? 'MEDIUM'),
    active_flag: true,
    agent_evidence: proposal.evidence ?? null,
    agent_confidence: proposal.confidence ?? null,
  };
}

export function App({ initialWorkflow }: { initialWorkflow?: WorkflowState }) {
  const [workflow, setWorkflow] = useState<WorkflowState>(() =>
    initialWorkflow ?? {
      status: 'DRAFT',
      activeStep: 'source',
    },
  );
  const [showDataprocConfirm, setShowDataprocConfirm] = useState(false);

  const activeIndex = stepOrder.indexOf(workflow.activeStep);
  const activeStep = steps[activeIndex];

  function moveTo(step: StepId) {
    setWorkflow((current) => ({ ...current, activeStep: step }));
  }

  function applyWorkflowRecord(record: SilverWorkflowRecord, activeStep: StepId, action: string) {
    setWorkflow((current) => ({
      ...current,
      ...workflowPatchFromRecord(record),
      ...demoWorkflowPatch(action),
      activeStep,
      error: undefined,
      errorDetail: undefined,
      processingLabel: undefined,
      backendMessage: JSON.stringify({
        workflow_id: record.workflow_id,
        version: record.version,
        status: record.status,
        spec_id: record.spec_id,
        execution_id: record.execution_id,
      }),
    }));
  }

  function applyError(error: unknown) {
    const normalized = normalizeError(error);
    setWorkflow((current) => ({
      ...current,
      error: normalized.summary,
      errorDetail: normalized.detail,
      processingLabel: undefined,
    }));
  }

  async function runAction(label: string, action: () => Promise<void>) {
    setWorkflow((current) => ({
      ...current,
      processingLabel: label,
      error: undefined,
      errorDetail: undefined,
    }));

    try {
      await action();
    } catch (error) {
      applyError(error);
    } finally {
      setWorkflow((current) => ({ ...current, processingLabel: undefined }));
    }
  }

  async function syncExecutionStatus(showProcessing = true) {
    const run = async () => {
      if (!workflow.executionId) throw new Error('Primero crea execution.');
      const result = await silverApi.syncExecution(workflow.executionId);
      const executionStatus =
        toExecutionStatus(result.execution.status) ?? toExecutionStatus(result.dataproc_state) ?? workflow.executionStatus;
      setWorkflow((current) => ({
        ...current,
        ...demoWorkflowPatch('Estado Dataproc sincronizado'),
        executionStatus,
        status: executionStatus === 'SUCCEEDED' ? 'SUCCEEDED' : executionStatus === 'FAILED' ? 'FAILED' : current.status,
        stateMessage: result.state_message ?? undefined,
        validationResult: result.validation_result ?? current.validationResult,
        backendMessage: JSON.stringify(result),
        error: executionStatus === 'FAILED' ? (result.state_message ?? 'La ejecucion o la validacion BigQuery fallo.') : undefined,
        errorDetail: executionStatus === 'FAILED' ? JSON.stringify(result, null, 2) : undefined,
      }));
    };

    if (showProcessing) {
      await runAction('Sincronizando estado de Dataproc...', run);
      return;
    }

    try {
      await run();
    } catch (error) {
      applyError(error);
    }
  }

  useEffect(() => {
    if (workflow.activeStep !== 'execution') return undefined;
    if (workflow.executionStatus !== 'QUEUED' && workflow.executionStatus !== 'RUNNING') return undefined;

    const interval = window.setInterval(() => {
      void syncExecutionStatus(false);
    }, 30000);

    return () => window.clearInterval(interval);
  }, [workflow.activeStep, workflow.executionId, workflow.executionStatus]);

  const statusCaption = useMemo(() => {
    if (workflow.executionStatus) return workflow.executionStatus;
    if (workflow.status === 'DRAFT') return 'DRAFT';
    return workflow.status;
  }, [workflow.executionStatus, workflow.status]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <strong>Business Rules Silver</strong>
          <span>Bronze to Silver governed rules</span>
        </div>
        <nav className="sideNav">
          {steps.map((step, index) => (
            <button
              key={step.id}
              className={step.id === workflow.activeStep ? 'active' : ''}
              onClick={() => moveTo(step.id)}
            >
              <strong>{index + 1}. {step.label}</strong>
              <span>{step.description}</span>
            </button>
          ))}
        </nav>
        <small>Demo sin login · Backend silver-refinement-agent</small>
      </aside>

      <main className="content">
        <header className="hero">
          <div>
            <p className="eyebrow">SDD Prototype / Wizard operacional</p>
            <h1>{activeStep.label}</h1>
            <p>{activeStep.description}</p>
          </div>
          <WorkflowPanel workflow={workflow} statusCaption={statusCaption} />
        </header>

        <ol className="stepper">
          {steps.map((step, index) => (
            <li key={step.id} className={step.id === workflow.activeStep ? 'active' : index < activeIndex ? 'done' : ''}>
              {index + 1} {step.label.split(' ')[0]}
            </li>
          ))}
        </ol>

        {workflow.processingLabel && <ProcessingBox label={workflow.processingLabel} />}
        {workflow.error && <ErrorBox summary={workflow.error} detail={workflow.errorDetail} />}

        {workflow.activeStep === 'source' && (
          <SourceStep
            onWorkflowCreated={(record, selection) => {
              setWorkflow((current) => ({
                ...current,
                ...workflowPatchFromRecord(record),
                ...selection,
                ...demoWorkflowPatch('Workflow creado en backend'),
                activeStep: 'incremental',
                error: undefined,
                backendMessage: JSON.stringify(record),
              }));
            }}
            onError={applyError}
          />
        )}
        {workflow.activeStep === 'incremental' && (
          <IncrementalStep
            workflow={workflow}
            onProfile={async () => {
              await runAction('Perfilando tabla seleccionada con Gemini ADK y BigQuery...', async () => {
                const response = await silverApi.runSilverAgent('table-profiler', buildAgentRequest(workflow));
                const profile = response.evidence ?? parseAgentJson(response.output);
                const inferred = inferProfileContract(profile, workflow.sourceColumns ?? []);
                setWorkflow((current) => ({
                  ...current,
                  ...inferred,
                  ...demoWorkflowPatch('Perfilamiento ADK e inferencia completados'),
                  agentProfile: profile,
                  agentSessionId: response.session_id,
                  backendMessage: JSON.stringify(response),
                }));
              });
            }}
            onContractChange={(patch) => {
              setWorkflow((current) => ({
                ...current,
                ...patch,
                inferenceSource: 'USER',
                inferenceReasons: ['Estrategia ajustada manualmente y pendiente de confirmacion.'],
              }));
            }}
            onReport={async () => {
              await runAction('Generando informe PDF de perfilamiento...', async () => {
                if (!workflow.agentProfile) throw new Error('Primero perfila la tabla seleccionada.');
                const blob = await silverApi.generateTableProfileReport(buildAgentRequest(workflow));
                const url = URL.createObjectURL(blob);
                setWorkflow((current) => {
                  if (current.profileReportUrl) URL.revokeObjectURL(current.profileReportUrl);
                  return {
                    ...current,
                    profileReportUrl: url,
                    ...demoWorkflowPatch('Informe PDF de perfilamiento generado'),
                  };
                });
              });
            }}
            onNext={async () => {
              await runAction('Confirmando origen y estrategia incremental...', async () => {
                if (!workflow.workflowId) throw new Error('Primero crea el workflow.');
                const record = await silverApi.confirmSource(workflow.workflowId, {
                  expected_version: currentVersion(workflow),
                  schema_context: {
                    source_project: workflow.projectId ?? seedSource.projectId,
                    source_dataset: workflow.sourceDataset ?? seedSource.sourceDataset,
                    source_table: workflow.sourceTable ?? seedSource.sourceTable,
                    columns: (workflow.sourceColumns ?? seedSchemaColumns).map((column) => ({
                      name: column.name,
                      data_type: 'data_type' in column ? column.data_type : column.type,
                      mode: column.mode ?? 'NULLABLE',
                    })),
                    business_key_candidates: workflow.businessKeys ?? [],
                    watermark_candidates: workflow.watermarkColumn ? [workflow.watermarkColumn] : [],
                    metric_candidates: workflow.metricColumn ? [workflow.metricColumn] : [],
                  },
                  confirmed_by: REQUESTED_BY,
                });
                applyWorkflowRecord(record, 'mapping', 'Origen confirmado en backend');
              });
            }}
          />
        )}
        {workflow.activeStep === 'mapping' && (
          <MappingStep
            workflow={workflow}
            onGenerateDeterministic={async () => {
              await runAction('Generando mapping deterministico desde el schema confirmado...', async () => {
                if (!workflow.workflowId) throw new Error('Primero crea el workflow.');
                const recommendation = await silverApi.generateMapping(workflow.workflowId, {
                  expected_version: currentVersion(workflow),
                  target_project: workflow.projectId ?? seedSource.projectId,
                  target_dataset: workflow.targetDataset ?? seedSource.targetDataset,
                  target_table: workflow.targetTable ?? seedSource.targetTable,
                });
                setWorkflow((current) => ({
                  ...current,
                  mappingRules: mappingFromRecommendation(recommendation.columns),
                  mappingSource: 'DETERMINISTIC',
                  mappingVersion: recommendation.source_workflow_version,
                  ...demoWorkflowPatch('Mapping deterministico generado desde tabla seleccionada'),
                  backendMessage: JSON.stringify(recommendation),
                }));
              });
            }}
            onGenerateAgent={async () => {
              await runAction('Generando recomendaciones de mapping con Gemini ADK...', async () => {
                const response = await silverApi.runSilverAgent('mapping-advisor', buildAgentRequest(workflow));
                const output = response.evidence ?? parseAgentJson(response.output);
                const columns = Array.isArray(output.columns)
                  ? output.columns.filter(
                      (item): item is Record<string, unknown> =>
                        Boolean(item) && typeof item === 'object' && !Array.isArray(item),
                    )
                  : [];
                if (!columns.length) throw new Error('El agente no devolvio columnas de mapping.');
                setWorkflow((current) => ({
                  ...current,
                  mappingRules: mappingFromRecommendation(columns),
                  mappingSource: 'AGENT',
                  agentSessionId: response.session_id,
                  ...demoWorkflowPatch('Mapping ADK generado con evidencia'),
                  backendMessage: JSON.stringify(response),
                }));
              });
            }}
            onMappingChange={(rules) => {
              setWorkflow((current) => ({
                ...current,
                mappingRules: rules,
                mappingSource: 'USER',
              }));
            }}
            onNext={() => {
              const rules = workflow.mappingRules?.length
                ? workflow.mappingRules
                : directMappingFromColumns(workflow.sourceColumns ?? []);
              const included = rules.filter((rule) => rule.include);
              const targets = included.map((rule) => rule.targetColumn.trim());
              if (!included.length) {
                applyError(new Error('El mapping debe incluir al menos una columna.'));
                return;
              }
              if (targets.some((target) => !target) || new Set(targets).size !== targets.length) {
                applyError(new Error('Las columnas destino deben tener nombres unicos y no vacios.'));
                return;
              }
              setWorkflow((current) => ({
                ...current,
                mappingRules: rules,
                mappingSource: current.mappingSource ?? 'DIRECT',
                mappingVersion: current.mappingVersion ?? 1,
                activeStep: 'rules',
                ...demoWorkflowPatch('Mapping editado y confirmado'),
              }));
            }}
          />
        )}
        {workflow.activeStep === 'rules' && (
          <RulesStep
            workflow={workflow}
            onRecommend={async () => {
              await runAction('Generando recomendaciones de calidad con Gemini ADK...', async () => {
                const response = await silverApi.runSilverAgent(
                  'quality-rule-advisor',
                  buildAgentRequest(workflow),
                );
                const output = response.evidence ?? parseAgentJson(response.output);
                const proposals = Array.isArray(output.candidates)
                  ? output.candidates.filter(
                      (item): item is Record<string, unknown> =>
                        Boolean(item) && typeof item === 'object' && !Array.isArray(item),
                    )
                  : [];
                setWorkflow((current) => ({
                  ...current,
                  ...demoWorkflowPatch('Recomendaciones ADK generadas'),
                  qualityRuleProposals: proposals,
                  approvedQualityRules: [],
                  agentSessionId: response.session_id,
                  backendMessage: JSON.stringify(response),
                }));
              });
            }}
            onApproveProposal={(proposal, approved) => {
              const rule = proposalToBackendRule(proposal);
              setWorkflow((current) => {
                const existing = current.approvedQualityRules ?? [];
                const ruleName = String(rule.rule_name);
                return {
                  ...current,
                  approvedQualityRules: approved
                    ? [...existing.filter((item) => item.rule_name !== ruleName), rule]
                    : existing.filter((item) => item.rule_name !== ruleName),
                };
              });
            }}
            onNext={async () => {
              await runAction('Generando y confirmando reglas de negocio...', async () => {
                if (!workflow.workflowId) throw new Error('Primero crea el workflow.');
                const generated = await silverApi.generateBusinessRules(workflow.workflowId, {
                  expected_version: currentVersion(workflow),
                  generation_reason: `Generar reglas deterministicas iniciales para ${workflow.sourceDataset}.${workflow.sourceTable}.`,
                  max_rules: 8,
                });
                const confirmed = await silverApi.confirmBusinessRules(workflow.workflowId, {
                  expected_version: generated.version,
                  confirmed_by: REQUESTED_BY,
                  confirmation_reason: 'Reglas semilla confirmadas para MVP deterministico.',
                  selected_proposal_id: generated.business_rules?.proposal_id ?? null,
                });
                applyWorkflowRecord(confirmed, 'artifacts', 'Reglas generadas y confirmadas en backend');
              });
            }}
          />
        )}
        {workflow.activeStep === 'artifacts' && (
          <ArtifactsStep
            workflow={workflow}
            onQualityReview={async () => {
              await runAction('Ejecutando Quality Review gobernado...', async () => {
                if (!workflow.workflowId) throw new Error('Primero crea el workflow.');
                const contract = buildArtifactContract(workflow);
                const specified = await silverApi.saveSpecification(workflow.workflowId, {
                  expected_version: currentVersion(workflow),
                  mapping_version: workflow.mappingVersion ?? 1,
                  target: {
                    project_id: workflow.projectId ?? seedSource.projectId,
                    dataset_id: workflow.targetDataset ?? seedSource.targetDataset,
                    table_id: workflow.targetTable ?? seedSource.targetTable,
                  },
                  columns: contract.columns,
                  created_by: REQUESTED_BY,
                  change_reason: 'Guardar especificacion antes del Quality Review.',
                });
                const reviewed = await silverApi.reviewQuality(workflow.workflowId, {
                  expected_version: specified.version,
                  decision: 'APPROVED',
                  reviewed_by: REQUESTED_BY,
                  review_notes: workflow.approvedQualityRules?.length
                    ? 'Reglas recomendadas por agente y aprobadas por usuario.'
                    : 'Reglas deterministicas revisadas y aprobadas.',
                  quality_rules: contract.qualityRules,
                });
                setWorkflow((current) => ({
                  ...current,
                  ...workflowPatchFromRecord(reviewed),
                  specId: specified.spec_id ?? reviewed.spec_id ?? current.specId,
                  qualityReviewed: true,
                  qualityReviewDecision: 'APPROVED',
                  activeStep: 'artifacts',
                  ...demoWorkflowPatch('Quality Review aprobado y persistido'),
                  backendMessage: JSON.stringify(reviewed),
                }));
              });
            }}
            onDownload={async (artifact) => {
              await runAction(`Descargando ${artifact.artifact_name}...`, async () => {
                if (!workflow.specId) throw new Error('No existe spec_id para descargar.');
                const blob = await silverApi.downloadArtifact(
                  workflow.specId,
                  artifact.artifact_type,
                );
                saveBlob(blob, artifact.artifact_name);
              });
            }}
            onNext={async () => {
              await runAction('Generando paquete tecnico gobernado...', async () => {
                if (!workflow.workflowId) throw new Error('Primero crea el workflow.');
                if (!workflow.qualityReviewed) {
                  throw new Error('Ejecuta y aprueba Quality Review antes de generar el package.');
                }
                if (!workflow.specId) throw new Error('Quality Review no devolvio spec_id.');
                const contract = buildArtifactContract(workflow);
                const pkg = await silverApi.generateArtifacts(workflow.specId, {
                  mapping_version: workflow.mappingVersion ?? 1,
                  target_project: workflow.projectId ?? seedSource.projectId,
                  target_dataset: workflow.targetDataset ?? seedSource.targetDataset,
                  target_table: workflow.targetTable ?? seedSource.targetTable,
                  columns: contract.columns,
                  load_strategy: contract.loadStrategy,
                  physical_design: contract.physicalDesign,
                  specification: {
                    load_strategy: contract.loadStrategy,
                    physical_design: contract.physicalDesign,
                  },
                  source_project: workflow.projectId ?? seedSource.projectId,
                  source_dataset: workflow.sourceDataset ?? seedSource.sourceDataset,
                  source_table: workflow.sourceTable ?? seedSource.sourceTable,
                  generated_by: REQUESTED_BY,
                  quality_rules: contract.qualityRules,
                });
                const execution = await silverApi.createExecution({
                  spec_id: pkg.spec_id,
                  requested_by: REQUESTED_BY,
                });
                setWorkflow((current) => ({
                  ...current,
                  ...demoWorkflowPatch('Artefactos descargables y execution creados'),
                  specId: pkg.spec_id,
                  mappingVersion: pkg.mapping_version,
                  generatedArtifacts: pkg.artifacts,
                  executionId: execution.execution_id,
                  executionStatus: 'PENDING',
                  activeStep: 'execution',
                  error: undefined,
                  backendMessage: JSON.stringify({ package: pkg, execution }),
                }));
              });
            }}
          />
        )}
        {workflow.activeStep === 'execution' && (
          <ExecutionStep
            batchId={workflow.batchId}
            executionStatus={workflow.executionStatus}
            stateMessage={workflow.stateMessage}
            onValidate={async () => {
              await runAction('Validando package generado...', async () => {
                if (!workflow.executionId) throw new Error('Primero crea execution.');
                const result = await silverApi.validatePackage(workflow.executionId);
                setWorkflow((current) => ({
                  ...current,
                  ...demoWorkflowPatch('Package validado en backend'),
                  executionStatus: 'VALIDATED',
                  backendMessage: JSON.stringify(result),
                  error: undefined,
                  errorDetail: undefined,
                }));
              });
            }}
            onSubmit={() => setShowDataprocConfirm(true)}
            onSync={async () => {
              await syncExecutionStatus();
            }}
            onResult={async () => {
              await runAction('Consultando validacion BigQuery post-ejecucion...', async () => {
                if (!workflow.executionId) throw new Error('Primero crea execution.');
                const result = await silverApi.getExecutionResult(workflow.executionId);
                setWorkflow((current) => ({
                  ...current,
                  ...demoWorkflowPatch('Resultado BigQuery validado'),
                  validationResult: result,
                  executionStatus: result.conformant ? 'SUCCEEDED' : 'FAILED',
                  status: result.conformant ? 'SUCCEEDED' : 'FAILED',
                  stateMessage: result.conformant
                    ? 'Dataproc y validacion BigQuery conformes.'
                    : 'Validacion BigQuery no conforme.',
                  backendMessage: JSON.stringify(result),
                  error: result.conformant ? undefined : 'La validacion BigQuery post-ejecucion no es conforme.',
                  errorDetail: result.conformant ? undefined : JSON.stringify(result, null, 2),
                }));
              });
            }}
            validationResult={workflow.validationResult}
          />
        )}
        {workflow.activeStep === 'governance' && (
          <GovernanceStep />
        )}
      </main>

      {showDataprocConfirm && (
        <div className="modalBackdrop">
          <section className="modal">
            <h2>Confirmar ejecucion Dataproc</h2>
            <p>Esta accion enviara el paquete validado a Dataproc. Continuar solo en demo controlada.</p>
            <div className="actions">
              <button
                className="primary"
                onClick={() => {
                  setShowDataprocConfirm(false);
                  void (async () => {
                    await runAction('Enviando ejecucion a Dataproc Serverless...', async () => {
                      if (!workflow.executionId) throw new Error('Primero crea execution.');
                      const result = await silverApi.submitDataproc(workflow.executionId);
                      setWorkflow((current) => ({
                        ...current,
                        ...demoWorkflowPatch('Submit Dataproc enviado al backend'),
                        status: 'EXECUTING',
                        executionStatus: 'QUEUED',
                        batchId: result.batch_id,
                        stateMessage: 'Dataproc acepto el submit. Esperando inicio del batch.',
                        backendMessage: JSON.stringify(result),
                        error: undefined,
                        errorDetail: undefined,
                      }));
                    });
                  })();
                }}
              >
                Ejecutar Dataproc
              </button>
              <button onClick={() => setShowDataprocConfirm(false)}>Cancelar</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function ProcessingBox({ label }: { label: string }) {
  return (
    <section className="processingBox">
      <span className="spinner" />
      <div>
        <strong>Procesando</strong>
        <p>{label}</p>
      </div>
    </section>
  );
}

function ErrorBox({ summary, detail }: { summary: string; detail?: string }) {
  return (
    <section className="errorBox">
      <strong>Error de backend</strong>
      <p>{summary}</p>
      {detail && detail !== summary && (
        <details>
          <summary>Ver detalle tecnico</summary>
          <pre>{detail}</pre>
        </details>
      )}
    </section>
  );
}

function WorkflowPanel({ workflow, statusCaption }: { workflow: WorkflowState; statusCaption: string }) {
  return (
    <aside className="workflowPanel">
      <strong>Estado workflow</strong>
      <span className="statusPill">{statusCaption}</span>
      <dl>
        <div><dt>workflow_id</dt><dd>{workflow.workflowId ?? 'pendiente'}</dd></div>
        <div><dt>version</dt><dd>{workflow.version ?? 'pendiente'}</dd></div>
        <div><dt>spec_id</dt><dd>{workflow.specId ?? 'pendiente'}</dd></div>
        <div><dt>execution_id</dt><dd>{workflow.executionId ?? 'pendiente'}</dd></div>
      </dl>
      {workflow.lastAction && <p className="lastAction">{workflow.lastAction}</p>}
      {workflow.backendMessage && <pre className="backendTrace">{workflow.backendMessage}</pre>}
    </aside>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} readOnly />
    </label>
  );
}

function SourceStep({
  onWorkflowCreated,
  onError,
}: {
  onWorkflowCreated: (
    record: SilverWorkflowRecord,
    selection: Pick<
      WorkflowState,
      | 'projectId'
      | 'sourceDataset'
      | 'sourceTable'
      | 'targetDataset'
      | 'targetTable'
      | 'sourceColumns'
      | 'businessKeys'
      | 'watermarkColumn'
      | 'metricColumn'
      | 'loadStrategy'
      | 'inferenceSource'
      | 'inferenceReasons'
    >,
  ) => void;
  onError: (error: unknown) => void;
}) {
  const [projectId, setProjectId] = useState(seedSource.projectId);
  const [sourceDataset, setSourceDataset] = useState(seedSource.sourceDataset);
  const [sourceTable, setSourceTable] = useState(seedSource.sourceTable);
  const [targetDataset, setTargetDataset] = useState(seedSource.targetDataset);
  const [targetTable, setTargetTable] = useState(seedSource.targetTable);
  const [datasets, setDatasets] = useState<string[]>([]);
  const [sourceTables, setSourceTables] = useState<string[]>([]);
  const [targetTables, setTargetTables] = useState<string[]>([]);
  const [tableDetail, setTableDetail] = useState<CatalogTableDetail | null>(null);
  const [catalogStatus, setCatalogStatus] = useState<string>('Catalogo real pendiente de carga.');
  const [loading, setLoading] = useState(false);

  const sourceColumns = normalizeCatalogFields(tableDetail);

  function normalizeList(value: unknown, preferredKeys: string[]) {
    const list = Array.isArray(value)
      ? value
      : Array.isArray((value as { datasets?: unknown[] })?.datasets)
        ? (value as { datasets: unknown[] }).datasets
        : Array.isArray((value as { tables?: unknown[] })?.tables)
          ? (value as { tables: unknown[] }).tables
          : Array.isArray((value as { items?: unknown[] })?.items)
            ? (value as { items: unknown[] }).items
            : [];

    return list
      .map((item) => {
        if (typeof item === 'string') return item;
        if (!item || typeof item !== 'object') return '';
        const record = item as Record<string, unknown>;
        for (const key of preferredKeys) {
          if (typeof record[key] === 'string') return record[key] as string;
        }
        return '';
      })
      .filter(Boolean);
  }

  async function loadDatasets() {
    setLoading(true);
    setCatalogStatus('Consultando datasets reales...');
    try {
      const response = await silverApi.listDatasets(projectId);
      const names = normalizeList(response, ['dataset_id', 'datasetId', 'id', 'name']);
      setDatasets(names);
      setCatalogStatus(`Datasets cargados: ${names.length}`);
      if (sourceDataset) void loadTables(sourceDataset);
      if (targetDataset && targetDataset !== sourceDataset) void loadTables(targetDataset, true);
    } catch (error) {
      setCatalogStatus(`No se pudo consultar catalogo real: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function loadTables(datasetId: string, target = false) {
    setLoading(true);
    setCatalogStatus(`Consultando tablas de ${datasetId}...`);
    try {
      const response = await silverApi.listTables(projectId, datasetId);
      const names = normalizeList(response, ['table_id', 'tableId', 'id', 'name']);
      if (target) {
        setTargetTables(names);
      } else {
        setSourceTables(names);
        const selected = names.includes(sourceTable) ? sourceTable : (names[0] ?? '');
        if (selected) {
          setSourceTable(selected);
          void inspectTable(selected, datasetId);
        }
      }
      setCatalogStatus(`Tablas cargadas para ${datasetId}: ${names.length}`);
    } catch (error) {
      setCatalogStatus(`No se pudo consultar tablas: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function inspectTable(tableId = sourceTable, datasetId = sourceDataset) {
    if (!tableId || !datasetId) return;
    setLoading(true);
    setTableDetail(null);
    setCatalogStatus(`Leyendo schema real de ${datasetId}.${tableId}...`);
    try {
      const response = await silverApi.getTable(projectId, datasetId, tableId);
      setTableDetail(response);
      const fields = normalizeCatalogFields(response);
      setCatalogStatus(`Schema real cargado: ${fields.length} columnas de ${datasetId}.${tableId}.`);
    } catch (error) {
      setCatalogStatus(`No se pudo leer schema real: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDatasets();
  }, []);

  function resetSeed() {
    setProjectId(seedSource.projectId);
    setSourceDataset(seedSource.sourceDataset);
    setSourceTable(seedSource.sourceTable);
    setTargetDataset(seedSource.targetDataset);
    setTargetTable(seedSource.targetTable);
    setTableDetail({ schema: seedColumns });
    setCatalogStatus('Caso semilla cargado explicitamente.');
  }

  const targetAlreadyExists = targetTables.includes(targetTable);

  async function createWorkflow() {
    setLoading(true);
    setCatalogStatus('Creando workflow real en backend...');
    try {
      const record = await silverApi.createWorkflow({
        source: {
          connection_id: 'CONN_BQ_DEMO',
          project_id: projectId,
          dataset_id: sourceDataset,
          table_id: sourceTable,
          fully_qualified_name: `${projectId}.${sourceDataset}.${sourceTable}`,
        },
        requested_by: REQUESTED_BY,
        metadata: {
          ui: 'business-rules-silver',
          target_project: projectId,
          target_dataset: targetDataset,
          target_table: targetTable,
          create_target_if_missing: !targetAlreadyExists,
        },
      });
      let effectiveColumns = sourceColumns;
      if (!effectiveColumns.length) {
        const detail = await silverApi.getTable(projectId, sourceDataset, sourceTable);
        effectiveColumns = normalizeCatalogFields(detail);
        setTableDetail(detail);
      }
      if (!effectiveColumns.length) {
        throw new Error('La tabla origen no devolvio un schema utilizable.');
      }
      const contract = inferTableContract(effectiveColumns);
      onWorkflowCreated(record, {
        projectId,
        sourceDataset,
        sourceTable,
        targetDataset,
        targetTable,
        ...contract,
        loadStrategy: contract.businessKeys.length ? 'MERGE' : 'FULL',
        inferenceSource: 'SCHEMA',
        inferenceReasons: ['Inferencia inicial basada en nombres y tipos del schema; el perfil BigQuery la confirmara o reemplazara.'],
      });
    } catch (error) {
      setCatalogStatus('El backend rechazo la creacion del workflow.');
      onError(error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="grid twoColumns">
      <article className="card">
        <h2>Seleccion real Bronze → Silver</h2>
        <p>Busca datasets y tablas desde el backend Silver. El caso semilla queda como fallback operativo.</p>
        <div className="formGrid">
          <EditableField label="Project ID" value={projectId} onChange={setProjectId} />
          <SelectField
            label="Dataset origen Bronze"
            value={sourceDataset}
            options={datasets}
            onChange={(value) => {
              setSourceDataset(value);
              void loadTables(value);
            }}
          />
          <SelectField
            label="Tabla origen Bronze"
            value={sourceTable}
            options={sourceTables}
            onChange={(value) => {
              setSourceTable(value);
              setTableDetail(null);
              void inspectTable(value, sourceDataset);
            }}
          />
          <SelectField
            label="Dataset destino Silver"
            value={targetDataset}
            options={datasets}
            onChange={(value) => {
              setTargetDataset(value);
              void loadTables(value, true);
            }}
          />
          <EditableSelectField
            label="Tabla destino Silver"
            value={targetTable}
            options={targetTables}
            onChange={setTargetTable}
            placeholder="tabla_silver"
          />
        </div>
        <span className={targetAlreadyExists ? 'statusPill' : 'warningPill'}>
          {targetAlreadyExists ? 'Tabla destino existente' : 'Crear tabla si no existe'}
        </span>
        <p className="catalogStatus">{loading ? 'Cargando...' : catalogStatus}</p>
        <div className="actions">
          <button className="primary" onClick={createWorkflow}>Crear workflow</button>
          <button onClick={loadDatasets}>Buscar datasets</button>
          <button onClick={() => void inspectTable()}>Ver schema</button>
          <button onClick={resetSeed}>Cargar semilla</button>
        </div>
      </article>
      <SchemaPreview fields={sourceColumns} />
    </section>
  );
}

function EditableField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  const mergedOptions = Array.from(new Set([value, ...options].filter(Boolean)));
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {mergedOptions.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function EditableSelectField({
  label,
  value,
  options,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const existing = options.includes(value);
  return (
    <fieldset className="field hybridField">
      <legend>{label}</legend>
      <select
        aria-label={`${label}: seleccionar existente`}
        value={existing ? value : '__new__'}
        onChange={(event) => onChange(event.target.value === '__new__' ? '' : event.target.value)}
      >
        <option value="__new__">Crear una tabla nueva...</option>
        {options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
      {!existing && (
        <input
          aria-label={`${label}: nuevo nombre`}
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </fieldset>
  );
}

function SchemaPreview({
  fields,
}: {
  fields?: CatalogField[];
}) {
  const visibleFields = fields?.length
    ? fields.map((field) => ({
        name: field.name,
        type: field.type,
        usage:
          /_id$/i.test(field.name) && !field.name.startsWith('bronze_')
            ? 'business_key'
            : ['TIMESTAMP', 'DATETIME', 'DATE'].includes(normalizedFieldType(field)) &&
                /watermark|fecha_ingesta|updated|modified|timestamp|fecha/i.test(field.name)
              ? 'watermark'
              : ['INT64', 'INTEGER', 'FLOAT64', 'FLOAT', 'NUMERIC', 'BIGNUMERIC'].includes(
                    normalizedFieldType(field),
                  ) && !field.name.startsWith('bronze_')
                ? 'metric'
                : field.name.startsWith('bronze_')
                  ? 'traceability'
                  : 'dimension',
      }))
    : seedColumns;

  return (
    <article className="card schemaCard">
      <h2>Schema detectado</h2>
      {visibleFields.map((column) => (
        <div key={column.name} className={`schemaRow ${column.usage}`}>
          <strong>{column.name}</strong>
          <span>{column.type}</span>
        </div>
      ))}
    </article>
  );
}

function ContractSelectField({
  label,
  value,
  options,
  onChange,
  emptyLabel = 'No seleccionada',
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  emptyLabel?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{emptyLabel}</option>
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  );
}

function IncrementalStep({
  workflow,
  onProfile,
  onContractChange,
  onReport,
  onNext,
}: {
  workflow: WorkflowState;
  onProfile: () => void;
  onContractChange: (patch: Partial<WorkflowState>) => void;
  onReport: () => void;
  onNext: () => void;
}) {
  const columns = workflow.sourceColumns ?? [];
  const profileColumns = Array.isArray(workflow.agentProfile?.columns)
    ? workflow.agentProfile.columns.filter(
        (item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object',
      )
    : [];
  const profileByName = new Map(profileColumns.map((column) => [String(column.name), column]));
  const columnNames = columns.map((column) => column.name);
  const temporalColumns = columns
    .filter((column) => ['TIMESTAMP', 'DATETIME', 'DATE'].includes(normalizedFieldType(column)))
    .map((column) => column.name);
  const numericColumns = columns
    .filter((column) =>
      ['INT64', 'INTEGER', 'FLOAT64', 'FLOAT', 'NUMERIC', 'BIGNUMERIC'].includes(normalizedFieldType(column)),
    )
    .map((column) => column.name);
  const strategy = workflow.loadStrategy ?? ((workflow.businessKeys ?? []).length ? 'MERGE' : 'FULL');
  const profileTable = String(workflow.agentProfile?.table ?? '');
  const expectedTable = `${workflow.projectId}.${workflow.sourceDataset}.${workflow.sourceTable}`;
  const profileMatches = Boolean(workflow.agentProfile) && profileTable === expectedTable;
  const selectedKey = workflow.businessKeys?.[0] ?? '';
  const keyEvidence = selectedKey ? profileByName.get(selectedKey) : undefined;

  const validationChecks = [
    {
      label: 'Perfil corresponde a la tabla seleccionada',
      ok: profileMatches,
      detail: profileMatches
        ? `BigQuery perfilo exactamente ${expectedTable}.`
        : `Esperado: ${expectedTable}; perfil disponible: ${profileTable || 'ninguno'}.`,
    },
    {
      label: 'Estrategia de carga consistente',
      ok: strategy === 'FULL' || Boolean(selectedKey && columns.some((column) => column.name === selectedKey)),
      detail: strategy === 'FULL'
        ? 'FULL no exige business key.'
        : keyEvidence?.business_key_candidate
          ? `${selectedKey} es candidata por cero nulos y unicidad observada.`
          : `${selectedKey || 'Sin clave'} fue seleccionada manualmente; MERGE requiere confirmar este criterio.`,
    },
    {
      label: 'Watermark compatible',
      ok: !workflow.watermarkColumn || temporalColumns.includes(workflow.watermarkColumn),
      detail: workflow.watermarkColumn
        ? `${workflow.watermarkColumn} existe y su tipo es temporal.`
        : 'Sin watermark: permitido para FULL o MERGE sin filtro incremental.',
    },
    {
      label: 'Metrica de reconciliacion compatible',
      ok: !workflow.metricColumn || numericColumns.includes(workflow.metricColumn),
      detail: workflow.metricColumn
        ? `${workflow.metricColumn} existe y tiene tipo numerico.`
        : 'Sin metrica numerica seleccionada; se validaran filas y claves.',
    },
  ];

  return (
    <section className="card">
      <h2>Estrategia de carga inferida y editable</h2>
      <p>
        La propuesta usa el perfil BigQuery de la tabla seleccionada. Puedes ajustarla antes de
        confirmarla; una edicion queda identificada como decision humana.
      </p>
      <div className="formGrid three">
        <ContractSelectField
          label="Modo"
          value={strategy}
          options={['FULL', 'MERGE']}
          emptyLabel="Selecciona modo"
          onChange={(value) => onContractChange({
            loadStrategy: value as 'FULL' | 'MERGE',
            businessKeys: value === 'FULL' ? [] : workflow.businessKeys,
          })}
        />
        <ContractSelectField
          label="Business key"
          value={selectedKey}
          options={columnNames}
          onChange={(value) => onContractChange({
            businessKeys: value ? [value] : [],
            loadStrategy: value ? 'MERGE' : 'FULL',
          })}
        />
        <ContractSelectField
          label="Watermark"
          value={workflow.watermarkColumn ?? ''}
          options={temporalColumns}
          onChange={(value) => onContractChange({ watermarkColumn: value || undefined })}
        />
        <ContractSelectField
          label="Metrica de reconciliacion"
          value={workflow.metricColumn ?? ''}
          options={numericColumns}
          onChange={(value) => onContractChange({ metricColumn: value || undefined })}
        />
        <Field
          label="Deduplicacion"
          value={strategy === 'MERGE' && selectedKey ? `${selectedKey} + orden temporal` : 'No aplica'}
        />
        <Field label="Workflow version" value={String(currentVersion(workflow))} />
      </div>
      <div className="profileBox">
        <strong>Contrato detectado</strong>
        <p>Tabla: {expectedTable}</p>
        <p>Columnas: {columns.length} · Estrategia propuesta: {strategy}</p>
        <p>Origen de inferencia: {workflow.inferenceSource ?? 'SCHEMA'}</p>
        {(workflow.inferenceReasons ?? []).map((reason) => <small key={reason}>{reason}</small>)}
        <div className="actions">
          <button onClick={onProfile}>Perfilar tabla con agente</button>
          <button onClick={onReport} disabled={!workflow.agentProfile}>Generar informe PDF</button>
        </div>
      </div>
      {workflow.agentProfile && (
        <AgentProfilePanel profile={workflow.agentProfile} sessionId={workflow.agentSessionId} />
      )}
      {workflow.profileReportUrl && (
        <section className="pdfReportPanel">
          <div className="sectionHeader">
            <div>
              <h3>Informe PDF de perfilamiento</h3>
              <p>Documento generado desde evidencia BigQuery de {expectedTable}.</p>
            </div>
            <a href={workflow.profileReportUrl} download={`perfil-${workflow.sourceTable}.pdf`}>
              Descargar PDF
            </a>
          </div>
          <iframe title="Visor del informe de perfilamiento" src={workflow.profileReportUrl} />
        </section>
      )}
      <div className="validationBox">
        <strong>Validacion explicada del perfil y contrato</strong>
        {validationChecks.map((check) => (
          <article key={check.label} className={check.ok ? 'checkOk' : 'checkFail'}>
            <strong>{check.ok ? 'OK' : 'REVISAR'} · {check.label}</strong>
            <span>{check.detail}</span>
          </article>
        ))}
      </div>
      <button
        className="primary"
        disabled={validationChecks.some((check) => !check.ok)}
        onClick={onNext}
      >
        Confirmar estrategia
      </button>
    </section>
  );
}

function AgentProfilePanel({
  profile,
  sessionId,
}: {
  profile: Record<string, unknown>;
  sessionId?: string;
}) {
  const columns = Array.isArray(profile.columns) ? profile.columns : [];
  const criticalColumns = Array.isArray(profile.critical_columns) ? profile.critical_columns : [];
  const keyCandidates = Array.isArray(profile.business_key_candidates)
    ? profile.business_key_candidates
    : [];

  return (
    <section className="agentPanel">
      <div className="resultHeader">
        <div>
          <span className="resultEyebrow">Gemini ADK + evidencia BigQuery</span>
          <h3>Perfilamiento completado</h3>
        </div>
        <span className="resultStatus">AGENT</span>
      </div>
      <p><strong>Tabla perfilada:</strong> {String(profile.table ?? 'No informada')}</p>
      <div className="resultMetrics">
        <article><span>Filas</span><strong>{String(profile.row_count ?? 'N/A')}</strong></article>
        <article><span>Columnas perfiladas</span><strong>{columns.length}</strong></article>
        <article><span>Campos criticos</span><strong>{criticalColumns.length}</strong></article>
        <article><span>Claves candidatas</span><strong>{keyCandidates.length}</strong></article>
      </div>
      <p>Claves candidatas: {keyCandidates.map(String).join(', ') || 'Ninguna'}</p>
      <small>Session: {sessionId ?? 'no informada'} · Toda metrica proviene de BigQuery.</small>
    </section>
  );
}

function MappingStep({
  workflow,
  onGenerateDeterministic,
  onGenerateAgent,
  onMappingChange,
  onNext,
}: {
  workflow: WorkflowState;
  onGenerateDeterministic: () => void;
  onGenerateAgent: () => void;
  onMappingChange: (rules: MappingRule[]) => void;
  onNext: () => void;
}) {
  const sourceColumns = workflow.sourceColumns ?? [];
  const rows = workflow.mappingRules?.length
    ? workflow.mappingRules
    : directMappingFromColumns(sourceColumns);
  const typeOptions = Array.from(new Set(sourceColumns.map((column) => column.type)));
  const transformations = ['DIRECT', 'TRIM', 'UPPER', 'LOWER', 'CAST', 'EXCLUDE'];

  function updateRow(index: number, patch: Partial<MappingRule>) {
    onMappingChange(rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row));
  }

  function addRow() {
    const first = sourceColumns[0];
    onMappingChange([
      ...rows,
      {
        sourceColumn: first?.name ?? '',
        targetColumn: '',
        targetType: first?.type ?? 'STRING',
        transformationType: 'DIRECT',
        include: true,
        nullable: true,
        reason: 'Fila agregada manualmente.',
        requiresApproval: true,
      },
    ]);
  }

  return (
    <section className="card">
      <div className="sectionHeader">
        <div>
          <h2>Mapping Bronze → Silver</h2>
          <p>
            Fuente: {workflow.projectId}.{workflow.sourceDataset}.{workflow.sourceTable} ·
            Origen del mapping: {workflow.mappingSource ?? 'DIRECT'}
          </p>
        </div>
        <div className="actions">
          <button onClick={onGenerateDeterministic}>Generar deterministico</button>
          <button className="primary" onClick={onGenerateAgent}>Recomendar con Gemini ADK</button>
        </div>
      </div>

      <div className="mappingEditor">
        <div className="mappingEditorHeader">
          <strong>Usar</strong><strong>Origen</strong><strong>Destino</strong>
          <strong>Tipo</strong><strong>Transformacion</strong><strong>Accion</strong>
        </div>
        {rows.map((row, index) => (
          <article key={`${index}-${row.sourceColumn}-${row.targetColumn}`} className="mappingEditorRow">
            <input
              aria-label={`Incluir ${row.targetColumn}`}
              type="checkbox"
              checked={row.include}
              onChange={(event) => updateRow(index, {
                include: event.target.checked,
                transformationType: event.target.checked ? row.transformationType : 'EXCLUDE',
              })}
            />
            <select
              value={row.sourceColumn}
              onChange={(event) => {
                const field = sourceColumns.find((column) => column.name === event.target.value);
                updateRow(index, {
                  sourceColumn: event.target.value,
                  targetColumn: row.targetColumn || event.target.value,
                  targetType: field?.type ?? row.targetType,
                  nullable: field?.mode !== 'REQUIRED',
                });
              }}
            >
              {sourceColumns.map((column) => (
                <option key={column.name} value={column.name}>{column.name}</option>
              ))}
            </select>
            <input
              value={row.targetColumn}
              onChange={(event) => updateRow(index, { targetColumn: event.target.value })}
            />
            <select
              value={row.targetType}
              onChange={(event) => updateRow(index, { targetType: event.target.value })}
            >
              {Array.from(new Set([row.targetType, ...typeOptions])).map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
            <select
              value={row.transformationType}
              onChange={(event) => updateRow(index, {
                transformationType: event.target.value,
                include: event.target.value !== 'EXCLUDE',
              })}
            >
              {transformations.map((transformation) => (
                <option key={transformation} value={transformation}>{transformation}</option>
              ))}
            </select>
            <button
              className="dangerText"
              onClick={() => onMappingChange(rows.filter((_, rowIndex) => rowIndex !== index))}
            >
              Quitar
            </button>
            <div className="mappingEvidence">
              <span>{row.reason ?? 'Sin justificacion registrada.'}</span>
              {row.confidence != null && <small>Confianza: {Math.round(row.confidence * 100)}%</small>}
              {row.risk && <small className="riskText">Riesgo: {row.risk}</small>}
              {row.requiresApproval && <em>REQUIERE APROBACION</em>}
            </div>
          </article>
        ))}
      </div>

      <div className="actions">
        <button onClick={addRow}>Agregar mapping</button>
      </div>
      <p className="catalogStatus">
        {rows.filter((row) => row.include).length} de {rows.length} columnas incluidas · Target:{' '}
        {workflow.projectId ?? seedSource.projectId}.{workflow.targetDataset ?? seedSource.targetDataset}.
        {workflow.targetTable ?? seedSource.targetTable}
      </p>
      <button className="primary" onClick={onNext}>Guardar mapping aprobado</button>
    </section>
  );
}


function RulesStep({
  workflow,
  onRecommend,
  onApproveProposal,
  onNext,
}: {
  workflow: WorkflowState;
  onRecommend: () => void;
  onApproveProposal: (proposal: Record<string, unknown>, approved: boolean) => void;
  onNext: () => void;
}) {
  const proposals = workflow.qualityRuleProposals ?? [];
  const approvedNames = new Set(
    (workflow.approvedQualityRules ?? []).map((rule) => String(rule.rule_name)),
  );

  return (
    <section className="card">
      <div className="sectionHeader">
        <div>
          <h2>Reglas de calidad gobernadas</h2>
          <p>Las propuestas del agente no se aplican hasta que las apruebes.</p>
        </div>
        <div className="actions">
          <button className="primary" onClick={onRecommend}>Recomendar con Gemini ADK</button>
        </div>
      </div>

      <div className="sprintNote">
        <strong>Fallback deterministico</strong>
        <span>
          {toBackendQualityRules(workflow).length} reglas base disponibles si el agente no responde.
          El sistema nunca aprueba automáticamente una recomendación.
        </span>
      </div>

      {proposals.length ? (
        <div className="agentRuleList">
          {proposals.map((proposal, index) => {
            const backendRule = proposalToBackendRule(proposal);
            const ruleName = String(backendRule.rule_name);
            const approved = approvedNames.has(ruleName);
            return (
              <article key={`${ruleName}-${index}`} className={approved ? 'approved' : ''}>
                <label>
                  <input
                    type="checkbox"
                    checked={approved}
                    onChange={(event) => onApproveProposal(proposal, event.target.checked)}
                  />
                  <div>
                    <strong>{String(proposal.rule_type ?? 'RULE')} · {String(proposal.column_name ?? '')}</strong>
                    <span>{String(proposal.evidence ?? 'Sin evidencia textual.')}</span>
                    <small>
                      Estado actual: {String(proposal.current_status ?? 'UNKNOWN')} · Confianza:{' '}
                      {proposal.confidence == null ? 'N/A' : String(proposal.confidence)}
                    </small>
                  </div>
                </label>
                <em>{approved ? 'APROBADA' : 'PENDIENTE'}</em>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="agentEmpty">
          <strong>Sin propuestas agenticas</strong>
          <span>Ejecuta el recomendador para analizar nulos, unicidad y cardinalidad.</span>
        </div>
      )}

      <p className="catalogStatus">
        Aprobadas: {workflow.approvedQualityRules?.length ?? 0} · Workflow version backend:{' '}
        {currentVersion(workflow)}
      </p>
      <button className="primary" onClick={onNext}>Confirmar reglas aprobadas</button>
    </section>
  );
}

function ArtifactsStep({
  workflow,
  onQualityReview,
  onDownload,
  onNext,
}: {
  workflow: WorkflowState;
  onQualityReview: () => void;
  onDownload: (artifact: GeneratedArtifact) => void;
  onNext: () => void;
}) {
  const generated = workflow.generatedArtifacts ?? [];
  const displayArtifacts = generated.length
    ? generated
    : artifacts.map((artifactType) => ({
        artifact_id: undefined,
        artifact_type: artifactType,
        artifact_name: artifactType,
        generation_status: 'PENDING',
      }));

  return (
    <section className="card">
      <div className="sectionHeader">
        <div>
          <h2>Artefactos gobernados</h2>
          <p>Quality Review es obligatorio antes de generar y descargar el package.</p>
        </div>
        <div className="actions">
          <button
            className={workflow.qualityReviewed ? 'approvedButton' : ''}
            onClick={onQualityReview}
          >
            {workflow.qualityReviewed ? 'Quality Review aprobado' : 'Ejecutar Quality Review'}
          </button>
          <button
            className="primary"
            disabled={!workflow.qualityReviewed}
            onClick={onNext}
          >
            Generar package
          </button>
        </div>
      </div>
      <div className="qualityGateSummary">
        <strong>Gate de calidad: {workflow.qualityReviewDecision ?? 'PENDIENTE'}</strong>
        <span>
          {workflow.qualityReviewed
            ? 'Revisión persistida en backend. La generación está habilitada.'
            : 'Revisa y aprueba las reglas antes de crear artefactos.'}
        </span>
      </div>
      <div className="artifactGrid">
        {displayArtifacts.map((artifact) => (
          <article key={artifact.artifact_id ?? artifact.artifact_type}>
            <strong>{artifact.artifact_type}</strong>
            <span>{artifact.artifact_name}</span>
            <em>{artifact.generation_status ?? 'GENERATED'}</em>
            {generated.length > 0 && (
              <button onClick={() => onDownload(artifact)}>Descargar</button>
            )}
          </article>
        ))}
      </div>
      {generated.length > 0 && (
        <p className="catalogStatus">
          {generated.length} artefactos versionados disponibles. Incluye notebook,
          PySpark, manifiesto, especificación, mapping y package ZIP.
        </p>
      )}
    </section>
  );
}

function ExecutionStep({
  batchId,
  executionStatus,
  stateMessage,
  onValidate,
  onSubmit,
  onSync,
  onResult,
  validationResult,
}: {
  batchId?: string;
  executionStatus?: WorkflowState['executionStatus'];
  stateMessage?: string;
  onValidate: () => void;
  onSubmit: () => void;
  onSync: () => void;
  onResult: () => void;
  validationResult?: WorkflowState['validationResult'];
}) {
  const flow = ['Crear execution', 'Validar package', 'Confirmar ejecucion', 'Submit Dataproc', 'Sync status', 'Ver resultado'];
  const canSubmit = executionStatus === 'VALIDATED';
  const canSync = executionStatus === 'QUEUED' || executionStatus === 'RUNNING' || executionStatus === 'FAILED';
  const canValidate = executionStatus === 'PENDING' || executionStatus === undefined;
  const canViewResult = executionStatus === 'SUCCEEDED' || executionStatus === 'FAILED';
  const statusText =
    executionStatus === 'QUEUED'
      ? 'Ejecucion enviada. Dataproc esta en cola.'
      : executionStatus === 'RUNNING'
        ? 'Dataproc esta procesando el batch.'
        : executionStatus === 'SUCCEEDED'
          ? 'Ejecucion completada correctamente.'
          : executionStatus === 'FAILED'
            ? 'Dataproc reporto error. Revisa el detalle tecnico.'
            : `Estado requerido para ejecutar Dataproc: VALIDATED. Estado actual: ${executionStatus ?? 'pendiente'}.`;

  return (
    <section className="card">
      <h2>Ejecucion controlada</h2>
      <div className="executionGrid">
        {flow.map((item, index) => (
          <article key={item} className={index < 2 ? 'ready' : index === 2 ? 'warning' : ''}>
            <strong>{item}</strong>
            <span>{index === 3 ? '/executions/{id}/submit' : index === 4 ? '/sync-status' : 'Backend action'}</span>
          </article>
        ))}
      </div>
      <p className="catalogStatus">
        {statusText}
        {batchId && <span className="inlineDetail">Batch: {batchId}</span>}
        {stateMessage && <span className="inlineDetail">Detalle: {stateMessage}</span>}
      </p>
      <div className="actions">
        <button disabled={!canValidate} onClick={onValidate}>Validar package</button>
        <button className="primary" disabled={!canSubmit} onClick={onSubmit}>Ejecutar Dataproc</button>
        <button disabled={!canSync} onClick={onSync}>Sincronizar estado</button>
        <button disabled={!canViewResult} onClick={onResult}>Ver resultado</button>
      </div>
      {validationResult && <BigQueryResultPanel result={validationResult} />}
    </section>
  );
}



function GovernanceStep() {
  const [dashboard, setDashboard] = useState<AgentOpsDashboard | null>(null);
  const [health, setHealth] = useState<AgentOpsHealth | null>(null);
  const [summary, setSummary] = useState<AgentGovernanceSummary | null>(null);
  const [runs, setRuns] = useState<AgentGovernanceRun[]>([]);
  const [agents, setAgents] = useState<SilverAgentDescriptor[]>([]);
  const [executions, setExecutions] = useState<Array<Record<string, unknown>>>([]);
  const [alerts, setAlerts] = useState<Array<Record<string, unknown>>>([]);
  const [unreadAlerts, setUnreadAlerts] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  async function refresh() {
    setLoading(true);
    setError(undefined);
    try {
      const [
        dashboardResult,
        healthResult,
        summaryResult,
        runsResult,
        executionsResult,
        alertsResult,
        agentsResult,
      ] = await Promise.all([
        silverApi.getAgentOpsDashboard(),
        silverApi.getAgentOpsHealth(),
        silverApi.getAgentGovernanceSummary(),
        silverApi.getAgentGovernanceRuns(50),
        silverApi.getAgentOpsExecutions(25),
        silverApi.getAgentOpsAlerts(25),
        silverApi.listSilverAgents(),
      ]);
      setDashboard(dashboardResult);
      setHealth(healthResult);
      setSummary(summaryResult);
      setRuns(runsResult.runs);
      setExecutions(executionsResult.executions);
      setAlerts(alertsResult.alerts);
      setUnreadAlerts(alertsResult.unread);
      setAgents(agentsResult);
    } catch (requestError) {
      setError(normalizeError(requestError).summary);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const executionText = (execution: Record<string, unknown>, key: string, fallback = 'N/A') => {
    const value = execution[key];
    return value == null || value === '' ? fallback : String(value);
  };
  const alertText = (alert: Record<string, unknown>, key: string, fallback = 'Sin detalle') => {
    const value = alert[key];
    return value == null || value === '' ? fallback : String(value);
  };
  const completionRate = summary?.total_runs
    ? Math.round((summary.completed / summary.total_runs) * 100)
    : 0;

  return (
    <section className="card governanceBoard">
      <div className="sectionHeader">
        <div>
          <span className="resultEyebrow">Gemini ADK + AgentOps</span>
          <h2>Gobierno agéntico persistente</h2>
          <p>
            Ejecuciones, evidencia, salud y alertas del ecosistema Silver. El historial de agentes
            se conserva en BigQuery y no depende de la sesión del navegador.
          </p>
        </div>
        <div className="actions">
          <span className="persistenceBadge">Persistencia BigQuery</span>
          <button onClick={() => void refresh()} disabled={loading}>
            {loading ? 'Actualizando...' : 'Actualizar tablero'}
          </button>
        </div>
      </div>

      {error && <ErrorBox summary={error} />}
      {loading && !dashboard && <ProcessingBox label="Consultando gobierno y AgentOps..." />}

      <div className="governanceMetrics">
        <article><span>Runs agénticos</span><strong>{summary?.total_runs ?? 0}</strong></article>
        <article><span>Agentes activos</span><strong>{summary?.active_agents ?? agents.length}</strong></article>
        <article><span>Completitud</span><strong>{completionRate}%</strong></article>
        <article>
          <span>Éxito ejecuciones</span>
          <strong>{Math.round(dashboard?.summary.success_rate ?? 0)}%</strong>
        </article>
        <article><span>Artefactos</span><strong>{dashboard?.artifacts.total_artifacts ?? 0}</strong></article>
        <article><span>Alertas sin leer</span><strong>{unreadAlerts}</strong></article>
      </div>

      <div className="governanceColumns">
        <section className="governanceSection">
          <div className="governanceSectionHeader">
            <h3>Registro de agentes ADK</h3>
            <span>{agents.length} registrados</span>
          </div>
          <div className="agentRegistry">
            {agents.map((agent) => (
              <article key={agent.name}>
                <strong>{agent.name}</strong>
                <span>{agent.purpose}</span>
                <small>Modelo: {agent.model}</small>
                <small>Tools: {agent.deterministic_tools.join(', ') || 'Ninguna'}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="governanceSection">
          <div className="governanceSectionHeader">
            <h3>Salud de plataforma</h3>
            <span className={health?.overall_status === 'HEALTHY' ? 'healthOk' : 'healthWarn'}>
              {health?.overall_status ?? 'PENDIENTE'}
            </span>
          </div>
          <div className="healthList">
            {(health?.components ?? []).map((component) => (
              <article key={component.component}>
                <div>
                  <strong>{component.component}</strong>
                  <span>{component.detail}</span>
                </div>
                <small>{component.status} · {component.latency_ms} ms</small>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className="governanceSection">
        <div className="governanceSectionHeader">
          <h3>Historial persistente de agentes</h3>
          <span>Últimos {runs.length}</span>
        </div>
        <div className="governanceTableWrap">
          <table className="governanceTable">
            <thead>
              <tr>
                <th>Agente</th><th>Estado</th><th>Origen</th><th>Destino</th>
                <th>Solicitado por</th><th>Eventos</th><th>Duración</th><th>Finalizado</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.run_id}>
                  <td><strong>{run.agent_name}</strong><small>{run.run_id}</small></td>
                  <td><span className={`runStatus ${run.status.toLowerCase()}`}>{run.status}</span></td>
                  <td>{run.source_table ?? 'N/A'}</td>
                  <td>{run.target_table ?? 'N/A'}</td>
                  <td>{run.requested_by ?? 'N/A'}</td>
                  <td>{run.event_count}</td>
                  <td>{run.duration_ms} ms</td>
                  <td>{new Date(run.finished_at).toLocaleString('es-PE')}</td>
                </tr>
              ))}
              {!runs.length && !loading && (
                <tr><td colSpan={8}>Aún no hay ejecuciones agénticas persistidas.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div className="governanceColumns">
        <section className="governanceSection">
          <div className="governanceSectionHeader">
            <h3>Ejecuciones Silver recientes</h3>
            <span>{executions.length} visibles</span>
          </div>
          <div className="compactList">
            {executions.slice(0, 10).map((execution, index) => (
              <article key={executionText(execution, 'execution_id', String(index))}>
                <div>
                  <strong>{executionText(execution, 'execution_id')}</strong>
                  <span>{executionText(execution, 'spec_id')}</span>
                </div>
                <span className="runStatus">{executionText(execution, 'status')}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="governanceSection">
          <div className="governanceSectionHeader">
            <h3>Alertas AgentOps</h3>
            <span>{unreadAlerts} sin leer</span>
          </div>
          <div className="compactList">
            {alerts.slice(0, 10).map((alert, index) => (
              <article key={alertText(alert, 'alert_id', String(index))}>
                <div>
                  <strong>{alertText(alert, 'title', alertText(alert, 'type', 'Alerta'))}</strong>
                  <span>{alertText(alert, 'message')}</span>
                </div>
                <span className="runStatus">{alertText(alert, 'severity', 'INFO')}</span>
              </article>
            ))}
            {!alerts.length && !loading && <p>Sin alertas activas.</p>}
          </div>
        </section>
      </div>
    </section>
  );
}


function BigQueryResultPanel({ result }: { result: NonNullable<WorkflowState['validationResult']> }) {
  const metricSum = result.metric_sum == null
    ? 'No aplica'
    : new Intl.NumberFormat('es-PE', { maximumFractionDigits: 6 }).format(result.metric_sum);

  return (
    <section className={`resultPanel ${result.conformant ? 'conformant' : 'nonConformant'}`}>
      <div className="resultHeader">
        <div>
          <span className="resultEyebrow">Validacion BigQuery post-ejecucion</span>
          <h3>{result.conformant ? 'CONFORME' : 'NO CONFORME'}</h3>
        </div>
        <span className="resultStatus">{result.status}</span>
      </div>

      <div className="resultMetrics">
        <article><span>Filas Silver</span><strong>{result.row_count}</strong></article>
        <article><span>Claves distintas</span><strong>{result.distinct_business_key_count ?? 'N/A'}</strong></article>
        <article><span>Duplicados</span><strong>{result.duplicate_count}</strong></article>
        <article><span>Diferencias Bronze/Silver</span><strong>{result.diff_count ?? 'N/A'}</strong></article>
        <article><span>Suma {result.metric_column ?? 'metrica'}</span><strong>{metricSum}</strong></article>
      </div>

      <dl className="resultTables">
        <div><dt>Origen</dt><dd>{result.source_table ?? 'No informado'}</dd></div>
        <div><dt>Destino</dt><dd>{result.target_table}</dd></div>
        <div><dt>Business key</dt><dd>{result.business_keys.join(', ') || 'No definida'}</dd></div>
        <div><dt>Validado</dt><dd>{new Date(result.validated_at).toLocaleString('es-PE')}</dd></div>
      </dl>

      <div className="resultChecks">
        {result.checks.map((check) => (
          <article key={check.name} className={check.status.toLowerCase()}>
            <span className="checkBadge">{check.status}</span>
            <div>
              <strong>{check.name.replace(/_/g, ' ')}</strong>
              {(check.expected != null || check.actual != null) && (
                <small>Esperado: {check.expected ?? 'N/A'} · Actual: {check.actual ?? 'N/A'}</small>
              )}
              {check.details && <small>{check.details}</small>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
