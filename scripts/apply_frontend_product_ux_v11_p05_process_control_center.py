from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}:\n{old[:180]}")
    path.write_text(text.replace(old, new, 1))


product = ROOT / "src/ProductRoot.tsx"
replace_once(
    product,
    """  async function openProcess(workflowId: string) {\n""",
    """  async function openProcess(workflowId: string, requestedStep?: WorkflowState['activeStep']) {\n""",
)
replace_once(
    product,
    """      const hydrated = hydrateWorkflowForResume(latest);\n""",
    """      const hydrated = hydrateWorkflowForResume(latest);\n      if (requestedStep) hydrated.activeStep = requestedStep;\n""",
)
replace_once(
    product,
    """  function startNewProcess() {\n    setResumeWorkflow(undefined);\n    setMode('wizard');\n  }\n\n""",
    """  function startNewProcess() {\n    setResumeWorkflow(undefined);\n    setMode('wizard');\n  }\n\n  function executionState(workflow: SilverWorkflowRecord) {\n    const execution = workflow.execution && typeof workflow.execution === 'object'\n      ? workflow.execution as Record<string, unknown>\n      : undefined;\n    return typeof execution?.status === 'string' ? execution.status.toUpperCase() : undefined;\n  }\n\n  function nextOperationalStep(workflow: SilverWorkflowRecord): WorkflowState['activeStep'] {\n    if (workflow.execution_id || workflow.execution) return 'execution';\n    if (workflow.artifact_package || workflow.spec_id || workflow.quality_review) return 'artifacts';\n    if ((workflow.quality_rules?.length ?? 0) > 0 || (workflow.business_rules?.rules?.length ?? 0) > 0) return 'rules';\n    if ((workflow.mapping_rules?.length ?? 0) > 0 || workflow.mapping_version) return 'mapping';\n    return workflow.source_confirmed ? 'incremental' : 'source';\n  }\n\n  function launchLabel(workflow: SilverWorkflowRecord) {\n    const state = executionState(workflow);\n    if (state === 'VALIDATED') return 'Listo para lanzar';\n    if (state === 'QUEUED' || state === 'RUNNING') return 'En ejecución';\n    if (state === 'SUCCEEDED') return 'Ejecutado';\n    if (state === 'FAILED') return 'Revisar fallo';\n    if (workflow.artifact_package || workflow.spec_id) return 'Preparar ejecución';\n    return 'Diseño pendiente';\n  }\n\n""",
)
replace_once(
    product,
    """                <th>Última modificación</th>\n                <th></th>\n""",
    """                <th>Última modificación</th>\n                <th>Operación</th>\n""",
)
replace_once(
    product,
    """                  <td>{formatDate(workflow.updated_at)}</td>\n                  <td><button onClick={() => { setSelected(workflow); setVersionHistory([]); }}>Ver detalle</button></td>\n""",
    """                  <td>{formatDate(workflow.updated_at)}</td>\n                  <td>\n                    <div className=\"processRowActions\">\n                      <button onClick={() => { setSelected(workflow); setVersionHistory([]); }}>Ver</button>\n                      <button onClick={() => void openProcess(workflow.workflow_id, 'mapping')}>Editar</button>\n                      <button\n                        className={executionState(workflow) === 'VALIDATED' ? 'launchReady' : ''}\n                        onClick={() => void openProcess(workflow.workflow_id, nextOperationalStep(workflow))}\n                      >\n                        {launchLabel(workflow)}\n                      </button>\n                    </div>\n                  </td>\n""",
)
replace_once(
    product,
    """              <div className=\"processDetailNotice\">\n                El proceso se reabrirá usando la versión más reciente persistida en backend.\n              </div>\n              <div className=\"processHistoryActions\">\n""",
    """              <div className=\"processDetailNotice\">\n                El proceso se reabrirá usando la versión más reciente persistida en backend. La ejecución nunca se dispara desde el catálogo: se abre el paso operativo y requiere confirmación explícita.\n              </div>\n              {!!selected.available_actions?.length && (\n                <div className=\"availableActions\">\n                  <strong>Acciones habilitadas por backend</strong>\n                  <div>{selected.available_actions.map((action) => <span key={action}>{action}</span>)}</div>\n                </div>\n              )}\n              <div className=\"processOperationalActions\">\n                <button onClick={() => void openProcess(selected.workflow_id, 'mapping')}>Editar mapping</button>\n                <button onClick={() => void openProcess(selected.workflow_id, 'rules')}>Editar reglas</button>\n                <button disabled={!selected.spec_id && !selected.artifact_package} onClick={() => void openProcess(selected.workflow_id, 'artifacts')}>Package & versiones</button>\n                <button\n                  className={executionState(selected) === 'VALIDATED' ? 'primaryProcessAction' : ''}\n                  disabled={!selected.spec_id && !selected.execution_id && !selected.artifact_package}\n                  onClick={() => void openProcess(selected.workflow_id, nextOperationalStep(selected))}\n                >\n                  {launchLabel(selected)}\n                </button>\n                <button onClick={() => void openProcess(selected.workflow_id, 'governance')}>Gobierno</button>\n              </div>\n              <div className=\"processHistoryActions\">\n""",
)

css = ROOT / "src/processes.css"
css.write_text(css.read_text() + """\n.processRowActions{display:flex;gap:6px;flex-wrap:wrap}.processRowActions button{padding:7px 9px;font-size:12px}.processRowActions .launchReady{background:#027a48;color:#fff;border-color:#027a48}.processOperationalActions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px}.processOperationalActions button{border:1px solid #d0d5dd;background:#fff;border-radius:10px;padding:10px 11px;cursor:pointer}.processOperationalActions button:disabled{opacity:.45;cursor:not-allowed}.availableActions{margin-top:12px;padding:12px;border:1px solid #e5e7eb;border-radius:10px;background:#fafafa}.availableActions>strong{display:block;font-size:12px;margin-bottom:8px}.availableActions>div{display:flex;gap:6px;flex-wrap:wrap}.availableActions span{font-size:10px;font-weight:800;padding:5px 8px;border-radius:999px;background:#eef2ff;color:#3730a3}.processOperationalActions .primaryProcessAction{grid-column:span 2}\n""")

print("P1.2 applied: Procesos Silver operational control center with view/edit/package/launch/governance actions")
