import { useEffect, useMemo, useState } from 'react';
import { demoWorkflowPatch, silverApi, type CatalogTableDetail, type SilverWorkflowRecord } from './api';
import { businessRules, mappingRules, seedColumns, seedSource } from './seed';
import { toBackendTransformation } from './transformations';
import type { CatalogField, StepId, WorkflowState } from './types';

const steps: Array<{ id: StepId; label: string; description: string }> = [
  { id: 'source', label: 'Origen y destino', description: 'Fuente Bronze y tabla Silver' },
  { id: 'incremental', label: 'Incrementalidad', description: 'Business key y watermark' },
  { id: 'mapping', label: 'Mapping', description: 'Transformaciones y campos derivados' },
  { id: 'rules', label: 'Reglas', description: 'Reglas editables y aprobacion' },
  { id: 'artifacts', label: 'Artefactos', description: 'DDL, notebook y paquete' },
  { id: 'execution', label: 'Dataproc', description: 'Validacion y ejecucion' },
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

export function App() {
  const [workflow, setWorkflow] = useState<WorkflowState>({
    status: 'DRAFT',
    activeStep: 'source',
  });
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
            onNext={async () => {
              await runAction('Generando recomendacion de mapping...', async () => {
                if (!workflow.workflowId) throw new Error('Primero crea el workflow.');
                const recommendation = await silverApi.generateMapping(workflow.workflowId, {
                  expected_version: currentVersion(workflow),
                  target_project: workflow.projectId ?? seedSource.projectId,
                  target_dataset: workflow.targetDataset ?? seedSource.targetDataset,
                  target_table: workflow.targetTable ?? seedSource.targetTable,
                });
                setWorkflow((current) => ({
                  ...current,
                  ...demoWorkflowPatch('Mapping recomendado por backend'),
                  mappingVersion: recommendation.source_workflow_version,
                  activeStep: 'rules',
                  error: undefined,
                  backendMessage: JSON.stringify(recommendation),
                }));
              });
            }}
          />
        )}
        {workflow.activeStep === 'rules' && (
          <RulesStep
            workflow={workflow}
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
            onNext={async () => {
              await runAction('Guardando especificacion y generando paquete tecnico...', async () => {
                if (!workflow.workflowId) throw new Error('Primero crea el workflow.');
                const columns = seedColumns.map((column) => ({
                  name: column.name,
                  data_type: column.type,
                  nullable: column.usage !== 'business_key',
                  source_column: column.name,
                  transformation: toBackendTransformation('DIRECT_COPY'),
                }));
                const specified = await silverApi.saveSpecification(workflow.workflowId, {
                  expected_version: currentVersion(workflow),
                  mapping_version: workflow.mappingVersion ?? 1,
                  target: {
                    project_id: workflow.projectId ?? seedSource.projectId,
                    dataset_id: workflow.targetDataset ?? seedSource.targetDataset,
                    table_id: workflow.targetTable ?? seedSource.targetTable,
                  },
                  columns,
                  created_by: REQUESTED_BY,
                  change_reason: 'Guardar especificacion Silver para generar artefactos.',
                });
                const reviewed = await silverApi.reviewQuality(workflow.workflowId, {
                  expected_version: specified.version,
                  decision: 'APPROVED',
                  reviewed_by: REQUESTED_BY,
                  review_notes: 'Quality review aprobada para demo deterministica.',
                  quality_rules: toBackendQualityRules(),
                });
                const specId = specified.spec_id;
                if (!specId) throw new Error('El backend no devolvio spec_id para generar artefactos.');
                const pkg = await silverApi.generateArtifacts(specId, {
                  mapping_version: workflow.mappingVersion ?? reviewed.mapping_version ?? specified.mapping_version ?? 1,
                  target_project: workflow.projectId ?? seedSource.projectId,
                  target_dataset: workflow.targetDataset ?? seedSource.targetDataset,
                  target_table: workflow.targetTable ?? seedSource.targetTable,
                  columns,
                  load_strategy: {
                    type: 'MERGE',
                    watermark_column: seedSource.watermark,
                    initial_watermark: seedSource.initialWatermark,
                    business_keys: [seedSource.businessKey],
                  },
                  physical_design: {
                    partitioning: {
                      enabled: true,
                      column: seedSource.watermark,
                      granularity: 'DAY',
                    },
                    clustering_columns: seedSource.clusteringColumns,
                  },
                  specification: {
                    load_strategy: {
                      type: 'MERGE',
                      watermark_column: seedSource.watermark,
                      initial_watermark: seedSource.initialWatermark,
                      business_keys: [seedSource.businessKey],
                    },
                    physical_design: {
                      partitioning: {
                        enabled: true,
                        column: seedSource.watermark,
                        granularity: 'DAY',
                      },
                      clustering_columns: seedSource.clusteringColumns,
                    },
                  },
                  source_project: workflow.projectId ?? seedSource.projectId,
                  source_dataset: workflow.sourceDataset ?? seedSource.sourceDataset,
                  source_table: workflow.sourceTable ?? seedSource.sourceTable,
                  generated_by: REQUESTED_BY,
                  quality_rules: toBackendQualityRules(),
                });
                const execution = await silverApi.createExecution({
                  spec_id: pkg.spec_id,
                  requested_by: REQUESTED_BY,
                });
                setWorkflow((current) => ({
                  ...current,
                  ...workflowPatchFromRecord(reviewed),
                  ...demoWorkflowPatch('Artefactos y execution creados en backend'),
                  specId: pkg.spec_id,
                  mappingVersion: pkg.mapping_version,
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

  const schemaFields =
    tableDetail?.schema?.fields ??
    tableDetail?.fields ??
    tableDetail?.columns ??
    tableDetail?.table?.schema?.fields ??
    tableDetail?.table?.fields ??
    tableDetail?.table?.columns;

  const sourceColumns = schemaFields?.length ? schemaFields : seedColumns;

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
      if (target) setTargetTables(names);
      else setSourceTables(names);
      setCatalogStatus(`Tablas cargadas para ${datasetId}: ${names.length}`);
    } catch (error) {
      setCatalogStatus(`No se pudo consultar tablas: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function inspectTable() {
    setLoading(true);
    setCatalogStatus(`Leyendo schema real de ${sourceDataset}.${sourceTable}...`);
    try {
      const response = await silverApi.getTable(projectId, sourceDataset, sourceTable);
      setTableDetail(response);
      setCatalogStatus('Schema real cargado desde backend.');
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
    setTableDetail(null);
    setCatalogStatus('Caso semilla cargado. Puedes consultar catalogo real si el backend/CORS lo permite.');
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
      const contract = inferTableContract(sourceColumns);
      onWorkflowCreated(record, {
        projectId,
        sourceDataset,
        sourceTable,
        targetDataset,
        targetTable,
        ...contract,
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
          <SelectField label="Tabla origen Bronze" value={sourceTable} options={sourceTables} onChange={setSourceTable} />
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
            placeholder="cat_producto_silver"
          />
        </div>
        <span className={targetAlreadyExists ? 'statusPill' : 'warningPill'}>
          {targetAlreadyExists ? 'Tabla destino existente' : 'Crear tabla si no existe'}
        </span>
        <p className="catalogStatus">{loading ? 'Cargando...' : catalogStatus}</p>
        <div className="actions">
          <button className="primary" onClick={createWorkflow}>Crear workflow</button>
          <button onClick={loadDatasets}>Buscar datasets</button>
          <button onClick={inspectTable}>Ver schema</button>
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
  return (
    <label className="field">
      <span>{label}</span>
      <input
        list={`${label.replace(/\W+/g, '-')}-options`}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <datalist id={`${label.replace(/\W+/g, '-')}-options`}>
        {options.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </label>
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
          field.name === seedSource.businessKey
            ? 'business_key'
            : field.name === seedSource.watermark
              ? 'watermark'
              : field.name === seedSource.metric
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

function IncrementalStep({ workflow, onNext }: { workflow: WorkflowState; onNext: () => void }) {
  const validationChecks = [
    {
      label: `Business key ${seedSource.businessKey}`,
      ok: seedSchemaColumns.some((column) => column.name === seedSource.businessKey),
    },
    {
      label: `Watermark ${seedSource.watermark}`,
      ok: seedSchemaColumns.some((column) => column.name === seedSource.watermark),
    },
    {
      label: `Metrica ${seedSource.metric}`,
      ok: seedSchemaColumns.some((column) => column.name === seedSource.metric),
    },
    {
      label: 'Columnas con data_type requerido por backend',
      ok: seedSchemaColumns.every((column) => Boolean(column.data_type)),
    },
  ];

  return (
    <section className="card">
      <h2>Estrategia de carga</h2>
      <div className="formGrid three">
        <Field label="Modo" value="INCREMENTAL" />
        <Field label="Business key" value={seedSource.businessKey} />
        <Field label="Watermark" value={seedSource.watermark} />
        <Field label="Deduplicacion" value="producto_id + watermark" />
        <Field label="Politica registros tardios" value="Advertir y registrar excepcion" />
        <Field label="Workflow version" value={String(currentVersion(workflow))} />
      </div>
      <div className="profileBox">
        <strong>Perfil BigQuery semilla</strong>
        <p>Filas: 13 · Distinct producto_id: 13 · SUM prima_base: 21390</p>
        <p>Rango watermark: 2026-07-31 20:30:00 → 2026-08-01 20:30:00</p>
      </div>
      <div className="validationBox">
        <strong>Validacion deterministica de columnas</strong>
        {validationChecks.map((check) => (
          <span key={check.label} className={check.ok ? 'checkOk' : 'checkFail'}>
            {check.ok ? 'OK' : 'ERROR'} · {check.label}
          </span>
        ))}
      </div>
      <button className="primary" onClick={onNext}>Confirmar estrategia</button>
    </section>
  );
}

function MappingStep({ workflow, onNext }: { workflow: WorkflowState; onNext: () => void }) {
  return (
    <section className="card">
      <div className="sectionHeader">
        <h2>Mapping Bronze → Silver</h2>
        <button className="primary">Generar recomendaciones</button>
      </div>
      <div className="table mappingTable">
        <strong>Origen</strong><strong>Destino</strong><strong>Tipo</strong><strong>Transformacion</strong>
        {mappingRules.map((rule) => (
          <div className={rule.transformationType === 'CASE_WHEN' ? 'highlight row' : 'row'} key={rule.targetColumn}>
            <span>{rule.sourceColumn}</span>
            <span>{rule.targetColumn}</span>
            <span>{rule.targetType}</span>
            <span>{rule.transformationType}</span>
          </div>
        ))}
      </div>
      <pre>{mappingRules[2].expression}</pre>
      <p className="catalogStatus">
        Target: {workflow.projectId ?? seedSource.projectId}.{workflow.targetDataset ?? seedSource.targetDataset}.
        {workflow.targetTable ?? seedSource.targetTable}
      </p>
      <button className="primary" onClick={onNext}>Guardar mapping</button>
    </section>
  );
}

function RulesStep({ workflow, onNext }: { workflow: WorkflowState; onNext: () => void }) {
  return (
    <section className="card">
      <div className="sectionHeader">
        <h2>Reglas semilla generadas</h2>
        <div className="actions"><button className="primary">Generar reglas</button><button>Guardar draft</button></div>
      </div>
      <div className="ruleList">
        {businessRules.map((rule) => (
          <article key={rule.name}>
            <div>
              <strong>{rule.name}</strong>
              <span>{rule.expression}</span>
            </div>
            <em className={rule.severity.toLowerCase()}>{rule.severity}</em>
          </article>
        ))}
      </div>
      <div className="sprintNote">
        <strong>Sprint final planificado</strong>
        <span>
          Esquema agentico para sugerir reglas de negocio y calidad a partir del schema,
          perfil de datos y mapping aprobado. El MVP mantiene reglas deterministicas editables.
        </span>
      </div>
      <p className="catalogStatus">Workflow version backend: {currentVersion(workflow)}</p>
      <button className="primary" onClick={onNext}>Confirmar reglas</button>
    </section>
  );
}

function ArtifactsStep({ workflow, onNext }: { workflow: WorkflowState; onNext: () => void }) {
  return (
    <section className="card">
      <div className="sectionHeader">
        <h2>Artefactos generados</h2>
        <div className="actions"><button>Quality review</button><button className="primary" onClick={onNext}>Guardar spec y generar package</button></div>
      </div>
      <div className="artifactGrid">
        {artifacts.map((artifact) => (
          <article key={artifact}>
            <strong>{artifact}</strong>
            <span>{artifact === 'SILVER_DDL' ? 'DDL para crear tabla Silver' : 'Archivo tecnico versionable'}</span>
            <em>READY</em>
          </article>
        ))}
      </div>
      <pre>
        CREATE TABLE IF NOT EXISTS {workflow.targetDataset ?? seedSource.targetDataset}.
        {workflow.targetTable ?? seedSource.targetTable} (...)
      </pre>
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
