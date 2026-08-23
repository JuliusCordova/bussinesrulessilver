import { useEffect, useMemo, useState } from 'react';
import { App } from './App';
import { silverApi, type SilverWorkflowRecord, type SilverWorkflowVersionSummary } from './api';
import { hydrateWorkflowForResume } from './workflowResume';
import type { WorkflowState } from './types';
import './processes.css';

type ProductMode = 'processes' | 'wizard';

function formatDate(value?: string) {
  if (!value) return 'Sin fecha';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('es-PE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
}

function processName(workflow: SilverWorkflowRecord) {
  const metadataName = workflow.metadata?.process_name;
  if (typeof metadataName === 'string' && metadataName.trim()) return metadataName.trim();
  const source = workflow.source;
  const target = workflow.silver_target;
  if (source && target) {
    return `${source.dataset_id}.${source.table_id} → ${target.dataset_id}.${target.table_id}`;
  }
  if (source) return `${source.dataset_id}.${source.table_id}`;
  return workflow.workflow_id;
}

function packageVersion(workflow: SilverWorkflowRecord) {
  const execution = workflow.execution && typeof workflow.execution === 'object'
    ? workflow.execution as Record<string, unknown>
    : undefined;
  const value = workflow.artifact_package?.package_version ?? execution?.package_version;
  return typeof value === 'number' ? `v${value}` : 'Pendiente';
}

function packageStorage(workflow: SilverWorkflowRecord) {
  const execution = workflow.execution && typeof workflow.execution === 'object'
    ? workflow.execution as Record<string, unknown>
    : undefined;
  const artifactPackage = workflow.artifact_package && typeof workflow.artifact_package === 'object'
    ? workflow.artifact_package as Record<string, unknown>
    : undefined;
  const value = artifactPackage?.storage_uri ?? artifactPackage?.current_uri ?? execution?.artifact_package_uri;
  return typeof value === 'string' && value ? value : 'Pendiente';
}

function targetName(workflow: SilverWorkflowRecord) {
  const target = workflow.silver_target;
  return target ? `${target.project_id}.${target.dataset_id}.${target.table_id}` : 'Pendiente';
}

export function ProductRoot() {
  const [mode, setMode] = useState<ProductMode>('processes');
  const [workflows, setWorkflows] = useState<SilverWorkflowRecord[]>([]);
  const [selected, setSelected] = useState<SilverWorkflowRecord | null>(null);
  const [versionHistory, setVersionHistory] = useState<SilverWorkflowVersionSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [packageDownloadLoading, setPackageDownloadLoading] = useState(false);
  const [resumeWorkflow, setResumeWorkflow] = useState<WorkflowState>();
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  async function loadProcesses() {
    setLoading(true);
    setError(undefined);
    try {
      const response = await silverApi.listWorkflows(100);
      setWorkflows(response.workflows ?? []);
      if (selected) {
        setSelected(response.workflows.find((item) => item.workflow_id === selected.workflow_id) ?? null);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProcesses();
  }, []);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return workflows.filter((workflow) => {
      if (statusFilter !== 'ALL' && workflow.status !== statusFilter) return false;
      if (!normalizedQuery) return true;
      return [
        workflow.workflow_id,
        processName(workflow),
        workflow.source?.fully_qualified_name,
        targetName(workflow),
        workflow.created_by,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedQuery));
    });
  }, [query, statusFilter, workflows]);

  const statuses = Array.from(new Set(workflows.map((workflow) => workflow.status)));

  async function openProcess(workflowId: string, requestedStep?: WorkflowState['activeStep']) {
    setLoading(true);
    setError(undefined);
    try {
      const latest = await silverApi.getWorkflow(workflowId);
      const hydrated = hydrateWorkflowForResume(latest);
      if (requestedStep) hydrated.activeStep = requestedStep;
      if (latest.spec_id) {
        try {
          const artifacts = await silverApi.listArtifacts(latest.spec_id);
          hydrated.generatedArtifacts = artifacts;
        } catch {
          // The workflow remains reopenable even if historical artifact listing is unavailable.
        }
      }
      const execution = latest.execution && typeof latest.execution === 'object'
        ? latest.execution as Record<string, unknown>
        : undefined;
      const packageData = latest.artifact_package && typeof latest.artifact_package === 'object'
        ? latest.artifact_package as Record<string, unknown>
        : undefined;
      const rawPackageVersion = packageData?.package_version ?? execution?.package_version;
      if (typeof rawPackageVersion === 'number') hydrated.packageVersion = rawPackageVersion;
      setSelected(latest);
      setResumeWorkflow(hydrated);
      setMode('wizard');
    } catch (openError) {
      setError(openError instanceof Error ? openError.message : String(openError));
    } finally {
      setLoading(false);
    }
  }

  function startNewProcess() {
    setResumeWorkflow(undefined);
    setMode('wizard');
  }

  function executionState(workflow: SilverWorkflowRecord) {
    const execution = workflow.execution && typeof workflow.execution === 'object'
      ? workflow.execution as Record<string, unknown>
      : undefined;
    return typeof execution?.status === 'string' ? execution.status.toUpperCase() : undefined;
  }

  function nextOperationalStep(workflow: SilverWorkflowRecord): WorkflowState['activeStep'] {
    if (workflow.execution_id || workflow.execution) return 'execution';
    if (workflow.artifact_package || workflow.spec_id || workflow.quality_review) return 'artifacts';
    if ((workflow.quality_rules?.length ?? 0) > 0 || (workflow.business_rules?.rules?.length ?? 0) > 0) return 'rules';
    if ((workflow.mapping_rules?.length ?? 0) > 0 || workflow.mapping_version) return 'mapping';
    return workflow.source_confirmed ? 'incremental' : 'source';
  }

  function launchLabel(workflow: SilverWorkflowRecord) {
    const state = executionState(workflow);
    if (state === 'VALIDATED') return 'Listo para lanzar';
    if (state === 'QUEUED' || state === 'RUNNING') return 'En ejecución';
    if (state === 'SUCCEEDED') return 'Ejecutado';
    if (state === 'FAILED') return 'Revisar fallo';
    if (workflow.artifact_package || workflow.spec_id) return 'Preparar ejecución';
    return 'Diseño pendiente';
  }

  async function downloadGovernedPackage(workflow: SilverWorkflowRecord) {
    if (!workflow.spec_id) {
      setError('El proceso todavía no tiene spec_id; no existe un package gobernado descargable.');
      return;
    }
    setPackageDownloadLoading(true);
    setError(undefined);
    try {
      const artifacts = await silverApi.listArtifacts(workflow.spec_id);
      const packageArtifact = artifacts.find((artifact) =>
        artifact.artifact_type === 'ARTIFACT_PACKAGE' && artifact.is_current !== false,
      );
      if (!packageArtifact) {
        throw new Error('No existe un ARTIFACT_PACKAGE vigente para esta especificación.');
      }
      const blob = await silverApi.downloadArtifact(workflow.spec_id, 'ARTIFACT_PACKAGE');
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = packageArtifact.artifact_name || 'artifact-package.zip';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : String(downloadError));
    } finally {
      setPackageDownloadLoading(false);
    }
  }

  async function loadVersionHistory(workflowId: string) {
    setHistoryLoading(true);
    setError(undefined);
    try {
      const response = await silverApi.listWorkflowVersions(workflowId);
      setVersionHistory(response.versions ?? []);
    } catch (historyError) {
      setError(historyError instanceof Error ? historyError.message : String(historyError));
    } finally {
      setHistoryLoading(false);
    }
  }

  if (mode === 'wizard') {
    return (
      <div className="productRootWizard">
        <button className="backToProcesses" onClick={() => setMode('processes')}>
          ← Volver a Procesos Silver
        </button>
        <App initialWorkflow={resumeWorkflow} />
      </div>
    );
  }

  return (
    <div className="processesShell">
      <header className="processesHero">
        <div>
          <p className="processesEyebrow">BUSINESS RULES SILVER</p>
          <h1>Procesos Silver</h1>
          <p>
            Catálogo gobernado de procesos Bronze → Silver. Consulta estado, versión, destino,
            package y trazabilidad antes de continuar su evolución.
          </p>
        </div>
        <div className="processesHeroActions">
          <button onClick={() => void loadProcesses()} disabled={loading}>
            {loading ? 'Actualizando…' : 'Actualizar'}
          </button>
          <button className="primaryProcessAction" onClick={startNewProcess}>
            + Nuevo proceso Silver
          </button>
        </div>
      </header>

      <section className="processesMetrics" aria-label="Resumen de procesos">
        <article><span>Procesos</span><strong>{workflows.length}</strong></article>
        <article><span>Aprobados</span><strong>{workflows.filter((item) => item.status === 'APPROVED').length}</strong></article>
        <article><span>Ejecutando</span><strong>{workflows.filter((item) => item.status === 'EXECUTING').length}</strong></article>
        <article><span>Con package</span><strong>{workflows.filter((item) => Boolean(item.artifact_package)).length}</strong></article>
      </section>

      <section className="processesToolbar">
        <input
          aria-label="Buscar procesos"
          placeholder="Buscar workflow, tabla, destino o responsable…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="ALL">Todos los estados</option>
          {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
        </select>
      </section>

      {error && <div className="processesError">No se pudo cargar el catálogo real: {error}</div>}

      <section className="processesContent">
        <div className="processesTableWrap">
          <table className="processesTable">
            <thead>
              <tr>
                <th>Proceso</th>
                <th>Estado</th>
                <th>Workflow</th>
                <th>Mapping</th>
                <th>Package</th>
                <th>Última modificación</th>
                <th>Operación</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((workflow) => (
                <tr key={workflow.workflow_id}>
                  <td>
                    <strong>{processName(workflow)}</strong>
                    <small>{workflow.source?.fully_qualified_name ?? 'Origen pendiente'}</small>
                  </td>
                  <td><span className={`processStatus processStatus-${workflow.status.toLowerCase()}`}>{workflow.status}</span></td>
                  <td>v{workflow.version}</td>
                  <td>{workflow.mapping_version ? `v${workflow.mapping_version}` : 'Pendiente'}</td>
                  <td>{packageVersion(workflow)}</td>
                  <td>{formatDate(workflow.updated_at)}</td>
                  <td>
                    <div className="processRowActions">
                      <button onClick={() => { setSelected(workflow); setVersionHistory([]); }}>Ver</button>
                      <button onClick={() => void openProcess(workflow.workflow_id, 'mapping')}>Editar</button>
                      <button
                        className={executionState(workflow) === 'VALIDATED' ? 'launchReady' : ''}
                        onClick={() => void openProcess(workflow.workflow_id, nextOperationalStep(workflow))}
                      >
                        {launchLabel(workflow)}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={7} className="processesEmpty">No hay procesos que coincidan con el filtro.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <aside className="processDetailPanel">
          {selected ? (
            <>
              <p className="processesEyebrow">DETALLE DEL PROCESO</p>
              <h2>{processName(selected)}</h2>
              <span className={`processStatus processStatus-${selected.status.toLowerCase()}`}>{selected.status}</span>
              <dl>
                <div><dt>workflow_id</dt><dd>{selected.workflow_id}</dd></div>
                <div><dt>Workflow version</dt><dd>v{selected.version}</dd></div>
                <div><dt>Mapping version</dt><dd>{selected.mapping_version ? `v${selected.mapping_version}` : 'Pendiente'}</dd></div>
                <div><dt>Spec</dt><dd>{selected.spec_id ?? 'Pendiente'}</dd></div>
                <div><dt>Package</dt><dd>{packageVersion(selected)}</dd></div>
                <div><dt>Storage package</dt><dd title={packageStorage(selected)}>{packageStorage(selected)}</dd></div>
                <div><dt>Origen</dt><dd>{selected.source?.fully_qualified_name ?? 'Pendiente'}</dd></div>
                <div><dt>Destino</dt><dd>{targetName(selected)}</dd></div>
                <div><dt>Responsable</dt><dd>{selected.created_by ?? 'No disponible'}</dd></div>
                <div><dt>Actualizado</dt><dd>{formatDate(selected.updated_at)}</dd></div>
              </dl>
              <div className="processDetailNotice">
                El proceso se reabrirá usando la versión más reciente persistida en backend. La ejecución nunca se dispara desde el catálogo: se abre el paso operativo y requiere confirmación explícita.
              </div>
              {!!selected.available_actions?.length && (
                <div className="availableActions">
                  <strong>Acciones habilitadas por backend</strong>
                  <div>{selected.available_actions.map((action) => <span key={action}>{action}</span>)}</div>
                </div>
              )}
              <div className="processOperationalActions">
                <button onClick={() => void openProcess(selected.workflow_id, 'mapping')}>Editar mapping</button>
                <button onClick={() => void openProcess(selected.workflow_id, 'rules')}>Editar reglas</button>
                <button disabled={!selected.spec_id && !selected.artifact_package} onClick={() => void openProcess(selected.workflow_id, 'artifacts')}>Package & versiones</button>
                <button
                  className={executionState(selected) === 'VALIDATED' ? 'primaryProcessAction' : ''}
                  disabled={!selected.spec_id && !selected.execution_id && !selected.artifact_package}
                  onClick={() => void openProcess(selected.workflow_id, nextOperationalStep(selected))}
                >
                  {launchLabel(selected)}
                </button>
                <button onClick={() => void openProcess(selected.workflow_id, 'governance')}>Gobierno</button>
              </div>
              <div className="processHistoryActions">
                <button
                  disabled={!selected.spec_id || packageDownloadLoading}
                  onClick={() => void downloadGovernedPackage(selected)}
                >
                  {packageDownloadLoading ? 'Descargando package…' : 'Descargar package ZIP'}
                </button>
                <button
                  disabled={historyLoading}
                  onClick={() => void loadVersionHistory(selected.workflow_id)}
                >
                  {historyLoading ? 'Cargando historial…' : 'Ver historial de versiones'}
                </button>
                <button
                  className="primaryProcessAction"
                  disabled={loading}
                  onClick={() => void openProcess(selected.workflow_id)}
                >
                  {loading ? 'Abriendo…' : 'Abrir proceso'}
                </button>
              </div>
              {versionHistory.length > 0 && (
                <section className="processVersionHistory">
                  <h3>Historial inmutable</h3>
                  {versionHistory.map((version) => (
                    <article key={version.workflow_version}>
                      <div>
                        <strong>Workflow v{version.workflow_version}</strong>
                        <span>{version.lifecycle_status}</span>
                      </div>
                      <small>Mapping: {version.mapping_version ? `v${version.mapping_version}` : 'N/A'}</small>
                      <small>Spec: {version.spec_id ?? 'N/A'}</small>
                      <small>Package: {version.package_version ? `v${version.package_version}` : 'N/A'}</small>
                      <small>Execution: {version.execution_id ?? 'N/A'}</small>
                      <small>{version.status} · {formatDate(version.updated_at)}</small>
                    </article>
                  ))}
                </section>
              )}
            </>
          ) : (
            <div className="processDetailEmpty">
              <strong>Selecciona un proceso</strong>
              <p>Verás aquí su identidad, versiones y estado real persistido.</p>
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}
