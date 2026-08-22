from pathlib import Path

APP = Path('src/App.tsx')
ROOT = Path('src/ProductRoot.tsx')


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Patron no encontrado en {path}: {old[:80]!r}')
    if text.count(old) != 1:
        raise SystemExit(f'Patron ambiguo en {path}: {text.count(old)} coincidencias')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


replace_once(
    APP,
    "export function App() {\n  const [workflow, setWorkflow] = useState<WorkflowState>({\n    status: 'DRAFT',\n    activeStep: 'source',\n  });",
    "export function App({ initialWorkflow }: { initialWorkflow?: WorkflowState }) {\n  const [workflow, setWorkflow] = useState<WorkflowState>(() =>\n    initialWorkflow ?? {\n      status: 'DRAFT',\n      activeStep: 'source',\n    },\n  );",
)

replace_once(
    ROOT,
    "import { silverApi, type SilverWorkflowRecord } from './api';\nimport './processes.css';",
    "import { silverApi, type SilverWorkflowRecord } from './api';\nimport { hydrateWorkflowForResume } from './workflowResume';\nimport type { WorkflowState } from './types';\nimport './processes.css';",
)

replace_once(
    ROOT,
    "  const [selected, setSelected] = useState<SilverWorkflowRecord | null>(null);\n  const [statusFilter, setStatusFilter] = useState('ALL');",
    "  const [selected, setSelected] = useState<SilverWorkflowRecord | null>(null);\n  const [resumeWorkflow, setResumeWorkflow] = useState<WorkflowState>();\n  const [statusFilter, setStatusFilter] = useState('ALL');",
)

replace_once(
    ROOT,
    "  const statuses = Array.from(new Set(workflows.map((workflow) => workflow.status)));\n\n  if (mode === 'wizard') {",
    "  const statuses = Array.from(new Set(workflows.map((workflow) => workflow.status)));\n\n  async function openProcess(workflowId: string) {\n    setLoading(true);\n    setError(undefined);\n    try {\n      const latest = await silverApi.getWorkflow(workflowId);\n      setSelected(latest);\n      setResumeWorkflow(hydrateWorkflowForResume(latest));\n      setMode('wizard');\n    } catch (openError) {\n      setError(openError instanceof Error ? openError.message : String(openError));\n    } finally {\n      setLoading(false);\n    }\n  }\n\n  function startNewProcess() {\n    setResumeWorkflow(undefined);\n    setMode('wizard');\n  }\n\n  if (mode === 'wizard') {",
)

replace_once(
    ROOT,
    "        <App />",
    "        <App initialWorkflow={resumeWorkflow} />",
)

replace_once(
    ROOT,
    "          <button className=\"primaryProcessAction\" onClick={() => setMode('wizard')}>\n            + Nuevo proceso Silver\n          </button>",
    "          <button className=\"primaryProcessAction\" onClick={startNewProcess}>\n            + Nuevo proceso Silver\n          </button>",
)

replace_once(
    ROOT,
    "              <div className=\"processDetailNotice\">\n                La reapertura editable se habilitará en el siguiente incremento. Este corte muestra únicamente evidencia real persistida.\n              </div>",
    "              <div className=\"processDetailNotice\">\n                El proceso se reabrirá usando la versión más reciente persistida en backend.\n              </div>\n              <button\n                className=\"primaryProcessAction\"\n                disabled={loading}\n                onClick={() => void openProcess(selected.workflow_id)}\n              >\n                {loading ? 'Abriendo…' : 'Abrir proceso'}\n              </button>",
)

print('PASS: UI de reapertura de Procesos Silver aplicada de forma controlada.')
