import { useMemo, useState } from 'react';
import { demoWorkflowPatch, silverApi, type CatalogTableDetail } from './api';
import { businessRules, mappingRules, seedColumns, seedSource } from './seed';
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

  function completeStep(action: string) {
    const nextStep = stepOrder[Math.min(activeIndex + 1, stepOrder.length - 1)];
    setWorkflow((current) => ({
      ...current,
      ...demoWorkflowPatch(action),
      status: nextStep === 'execution' ? 'APPROVED' : 'IN_PROGRESS',
      activeStep: nextStep,
      workflowId: current.workflowId ?? 'WF_CAT_PRODUCTO',
      specId: nextStep === 'execution' || current.activeStep === 'artifacts' ? 'SPEC_CAT_PRODUCTO' : current.specId,
    }));
  }

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

        {workflow.activeStep === 'source' && <SourceStep onNext={() => completeStep('Workflow creado')} />}
        {workflow.activeStep === 'incremental' && <IncrementalStep onNext={() => completeStep('Estrategia confirmada')} />}
        {workflow.activeStep === 'mapping' && <MappingStep onNext={() => completeStep('Mapping guardado')} />}
        {workflow.activeStep === 'rules' && <RulesStep onNext={() => completeStep('Reglas confirmadas')} />}
        {workflow.activeStep === 'artifacts' && <ArtifactsStep onNext={() => completeStep('Artefactos generados')} />}
        {workflow.activeStep === 'execution' && (
          <ExecutionStep
            onValidate={() =>
              setWorkflow((current) => ({
                ...current,
                ...demoWorkflowPatch('Package validado'),
                executionId: current.executionId ?? 'EXEC_CAT_PRODUCTO',
                executionStatus: 'VALIDATED',
              }))
            }
            onSubmit={() => setShowDataprocConfirm(true)}
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
                  setWorkflow((current) => ({
                    ...current,
                    ...demoWorkflowPatch('Submit Dataproc enviado'),
                    status: 'EXECUTING',
                    executionStatus: 'QUEUED',
                    executionId: current.executionId ?? 'EXEC_CAT_PRODUCTO',
                  }));
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

function WorkflowPanel({ workflow, statusCaption }: { workflow: WorkflowState; statusCaption: string }) {
  return (
    <aside className="workflowPanel">
      <strong>Estado workflow</strong>
      <span className="statusPill">{statusCaption}</span>
      <dl>
        <div><dt>workflow_id</dt><dd>{workflow.workflowId ?? 'pendiente'}</dd></div>
        <div><dt>spec_id</dt><dd>{workflow.specId ?? 'pendiente'}</dd></div>
        <div><dt>execution_id</dt><dd>{workflow.executionId ?? 'pendiente'}</dd></div>
      </dl>
      {workflow.lastAction && <p className="lastAction">{workflow.lastAction}</p>}
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

function SourceStep({ onNext }: { onNext: () => void }) {
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
          <button className="primary" onClick={onNext}>Crear workflow</button>
          <button onClick={loadDatasets}>Buscar datasets</button>
          <button onClick={inspectTable}>Ver schema</button>
          <button onClick={resetSeed}>Cargar semilla</button>
        </div>
      </article>
      <SchemaPreview fields={schemaFields} />
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

function IncrementalStep({ onNext }: { onNext: () => void }) {
  return (
    <section className="card">
      <h2>Estrategia de carga</h2>
      <div className="formGrid three">
        <Field label="Modo" value="INCREMENTAL" />
        <Field label="Business key" value={seedSource.businessKey} />
        <Field label="Watermark" value={seedSource.watermark} />
        <Field label="Deduplicacion" value="producto_id + watermark" />
        <Field label="Politica registros tardios" value="Advertir y registrar excepcion" />
      </div>
      <div className="profileBox">
        <strong>Perfil BigQuery semilla</strong>
        <p>Filas: 13 · Distinct producto_id: 13 · SUM prima_base: 21390</p>
        <p>Rango watermark: 2026-07-31 20:30:00 → 2026-08-01 20:30:00</p>
      </div>
      <button className="primary" onClick={onNext}>Confirmar estrategia</button>
    </section>
  );
}

function MappingStep({ onNext }: { onNext: () => void }) {
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
      <button className="primary" onClick={onNext}>Guardar mapping</button>
    </section>
  );
}

function RulesStep({ onNext }: { onNext: () => void }) {
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
      <button className="primary" onClick={onNext}>Confirmar reglas</button>
    </section>
  );
}

function ArtifactsStep({ onNext }: { onNext: () => void }) {
  return (
    <section className="card">
      <div className="sectionHeader">
        <h2>Artefactos generados</h2>
        <div className="actions"><button>Quality review</button><button className="primary" onClick={onNext}>Generar package</button></div>
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
      <pre>CREATE TABLE IF NOT EXISTS seguros_silver.cat_producto (...)</pre>
    </section>
  );
}

function ExecutionStep({ onValidate, onSubmit }: { onValidate: () => void; onSubmit: () => void }) {
  const flow = ['Crear execution', 'Validar package', 'Confirmar ejecucion', 'Submit Dataproc', 'Sync status', 'Ver resultado'];
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
      <div className="actions">
        <button onClick={onValidate}>Validar package</button>
        <button className="primary" onClick={onSubmit}>Ejecutar Dataproc</button>
      </div>
    </section>
  );
}
