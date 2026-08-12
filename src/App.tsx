import { useMemo, useState } from 'react';
import { demoWorkflowPatch } from './api';
import { businessRules, mappingRules, seedColumns, seedSource } from './seed';
import type { StepId, WorkflowState } from './types';

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
  return (
    <section className="grid twoColumns">
      <article className="card">
        <h2>Caso semilla cat_producto</h2>
        <p>Origen y destino probados en BigQuery para demo controlada.</p>
        <div className="formGrid">
          <Field label="Project ID" value={seedSource.projectId} />
          <Field label="Dataset origen Bronze" value={seedSource.sourceDataset} />
          <Field label="Tabla origen Bronze" value={seedSource.sourceTable} />
          <Field label="Dataset destino Silver" value={seedSource.targetDataset} />
          <Field label="Tabla destino Silver" value={seedSource.targetTable} />
        </div>
        <span className="warningPill">Crear tabla si no existe</span>
        <div className="actions">
          <button className="primary" onClick={onNext}>Crear workflow</button>
          <button>Ver schema</button>
        </div>
      </article>
      <SchemaPreview />
    </section>
  );
}

function SchemaPreview() {
  return (
    <article className="card schemaCard">
      <h2>Schema detectado</h2>
      {seedColumns.map((column) => (
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

