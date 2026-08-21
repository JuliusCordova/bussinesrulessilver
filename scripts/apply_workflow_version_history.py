from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text()
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1))


# 1) Backend models: read-only version history contract.
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/models.py",
    """class SilverWorkflowListResponse(BaseModel):\n    total: int = Field(ge=0)\n    workflows: list[SilverWorkflowRecord]\n\n\nclass WorkflowRepositoryHealth(BaseModel):""",
    """class SilverWorkflowListResponse(BaseModel):\n    total: int = Field(ge=0)\n    workflows: list[SilverWorkflowRecord]\n\n\nclass SilverWorkflowVersionSummary(BaseModel):\n    workflow_id: str\n    workflow_version: int = Field(ge=1)\n    mapping_version: int | None = Field(default=None, ge=1)\n    spec_id: str | None = None\n    package_version: int | None = Field(default=None, ge=1)\n    execution_id: str | None = None\n    status: WorkflowStatus\n    updated_at: datetime\n    lifecycle_status: str\n\n\nclass SilverWorkflowVersionListResponse(BaseModel):\n    workflow_id: str\n    current_version: int = Field(ge=1)\n    total: int = Field(ge=0)\n    versions: list[SilverWorkflowVersionSummary]\n\n\nclass WorkflowRepositoryHealth(BaseModel):""",
)

# 2) Repository protocol + in-memory immutable snapshots.
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py",
    """    def list(self, *, limit: int, status: WorkflowStatus | None = None) -> list[SilverWorkflowRecord]: ...\n    def confirm_source(""",
    """    def list(self, *, limit: int, status: WorkflowStatus | None = None) -> list[SilverWorkflowRecord]: ...\n    def list_versions(self, workflow_id: str) -> list[SilverWorkflowRecord]: ...\n    def confirm_source(""",
)
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py",
    """        self._records: dict[str, SilverWorkflowRecord] = {}\n        self._lock = RLock()""",
    """        self._records: dict[str, SilverWorkflowRecord] = {}\n        self._snapshots: dict[str, dict[int, SilverWorkflowRecord]] = {}\n        self._lock = RLock()""",
)
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py",
    """            self._records[record.workflow_id] = deepcopy(record)\n            return deepcopy(record)""",
    """            self._records[record.workflow_id] = deepcopy(record)\n            self._snapshots.setdefault(record.workflow_id, {})[record.version] = deepcopy(record)\n            return deepcopy(record)""",
)
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py",
    """    def confirm_source(self, workflow_id: str, *, expected_version: int, schema_context: SchemaContextEvidence, confirmed_by: str, updated_at: datetime) -> SilverWorkflowRecord:""",
    """    def list_versions(self, workflow_id: str) -> list[SilverWorkflowRecord]:\n        with self._lock:\n            if workflow_id not in self._records:\n                raise WorkflowNotFoundError(f\"Workflow no encontrado: {workflow_id}\")\n            snapshots = list(self._snapshots.get(workflow_id, {}).values())\n            snapshots.sort(key=lambda record: record.version, reverse=True)\n            return [deepcopy(record) for record in snapshots]\n\n    def confirm_source(self, workflow_id: str, *, expected_version: int, schema_context: SchemaContextEvidence, confirmed_by: str, updated_at: datetime) -> SilverWorkflowRecord:""",
)
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py",
    """    def _store(self, updated: SilverWorkflowRecord) -> SilverWorkflowRecord:\n        self._records[updated.workflow_id] = deepcopy(updated)\n        return deepcopy(updated)""",
    """    def _store(self, updated: SilverWorkflowRecord) -> SilverWorkflowRecord:\n        self._records[updated.workflow_id] = deepcopy(updated)\n        self._snapshots.setdefault(updated.workflow_id, {})[updated.version] = deepcopy(updated)\n        return deepcopy(updated)""",
)

# 3) GCS repository: expose existing immutable snapshot objects.
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/gcs_repository.py",
    """    def confirm_source(self, workflow_id: str, *, expected_version: int, schema_context: SchemaContextEvidence, confirmed_by: str, updated_at: datetime) -> SilverWorkflowRecord:""",
    """    def list_versions(self, workflow_id: str) -> list[SilverWorkflowRecord]:\n        current = self.get(workflow_id)\n        if current is None:\n            raise WorkflowNotFoundError(f\"Workflow no encontrado: {workflow_id}\")\n        records: list[SilverWorkflowRecord] = []\n        prefix = self._join(f\"workflows/{workflow_id}/versions/\")\n        for blob in self._client.list_blobs(self._bucket, prefix=prefix):\n            if not blob.name.endswith(\".json\"):\n                continue\n            records.append(SilverWorkflowRecord.model_validate_json(blob.download_as_text()))\n        records.sort(key=lambda record: record.version, reverse=True)\n        return [record.model_copy(deep=True) for record in records]\n\n    def confirm_source(self, workflow_id: str, *, expected_version: int, schema_context: SchemaContextEvidence, confirmed_by: str, updated_at: datetime) -> SilverWorkflowRecord:""",
)

# 4) Service: summarize snapshots without mutating them.
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py",
    """    SilverWorkflowListResponse,\n    SilverWorkflowRecord,""",
    """    SilverWorkflowListResponse,\n    SilverWorkflowRecord,\n    SilverWorkflowVersionListResponse,\n    SilverWorkflowVersionSummary,""",
)
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py",
    """    def get_business_rules(self, workflow_id: str) -> BusinessRulesSection:\n        return self.get(workflow_id).business_rules\n\n    def list(self, *, limit: int, status: WorkflowStatus | None) -> SilverWorkflowListResponse:""",
    """    def get_business_rules(self, workflow_id: str) -> BusinessRulesSection:\n        return self.get(workflow_id).business_rules\n\n    def list_versions(self, workflow_id: str) -> SilverWorkflowVersionListResponse:\n        current = self.get(workflow_id)\n        snapshots = self.repository.list_versions(workflow_id)\n        versions: list[SilverWorkflowVersionSummary] = []\n        for record in snapshots:\n            artifact_package = record.artifact_package or {}\n            execution = record.execution or {}\n            raw_package_version = artifact_package.get(\"package_version\") or execution.get(\"package_version\")\n            versions.append(SilverWorkflowVersionSummary(\n                workflow_id=record.workflow_id,\n                workflow_version=record.version,\n                mapping_version=record.mapping_version,\n                spec_id=record.spec_id,\n                package_version=raw_package_version if isinstance(raw_package_version, int) else None,\n                execution_id=record.execution_id,\n                status=record.status,\n                updated_at=record.updated_at,\n                lifecycle_status=\"CURRENT\" if record.version == current.version else \"SUPERSEDED\",\n            ))\n        return SilverWorkflowVersionListResponse(\n            workflow_id=workflow_id,\n            current_version=current.version,\n            total=len(versions),\n            versions=versions,\n        )\n\n    def list(self, *, limit: int, status: WorkflowStatus | None) -> SilverWorkflowListResponse:""",
)

# 5) Router endpoint.
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py",
    """    SilverWorkflowListResponse,\n    SilverWorkflowRecord,""",
    """    SilverWorkflowListResponse,\n    SilverWorkflowRecord,\n    SilverWorkflowVersionListResponse,""",
)
replace(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py",
    """@router.get(\"/{workflow_id}/business-rules\", response_model=BusinessRulesSection)""",
    """@router.get(\"/{workflow_id}/versions\", response_model=SilverWorkflowVersionListResponse)\ndef list_workflow_versions(workflow_id: str, business: WorkflowBusinessOperation = Depends(require_workflow_get)) -> SilverWorkflowVersionListResponse:\n    try:\n        result = business.workflow_service.list_versions(workflow_id)\n        business.record_success(workflow_id=workflow_id)\n        return result\n    except WorkflowNotFoundError as exc:\n        raise _not_found(exc) from exc\n\n\n@router.get(\"/{workflow_id}/business-rules\", response_model=BusinessRulesSection)""",
)

# 6) Frontend API contract.
replace(
    "src/api.ts",
    """  getWorkflow: (workflowId: string) =>\n    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}`),""",
    """  getWorkflow: (workflowId: string) =>\n    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}`),\n\n  listWorkflowVersions: (workflowId: string) =>\n    request<SilverWorkflowVersionListResponse>(`/silver-workflows/${workflowId}/versions`),""",
)
replace(
    "src/api.ts",
    """export interface SilverWorkflowListResponse {\n  total: number;\n  workflows: SilverWorkflowRecord[];\n}\n\nexport interface MappingRecommendationResponse""",
    """export interface SilverWorkflowListResponse {\n  total: number;\n  workflows: SilverWorkflowRecord[];\n}\n\nexport interface SilverWorkflowVersionSummary {\n  workflow_id: string;\n  workflow_version: number;\n  mapping_version?: number | null;\n  spec_id?: string | null;\n  package_version?: number | null;\n  execution_id?: string | null;\n  status: WorkflowState['status'];\n  updated_at: string;\n  lifecycle_status: 'CURRENT' | 'SUPERSEDED' | string;\n}\n\nexport interface SilverWorkflowVersionListResponse {\n  workflow_id: string;\n  current_version: number;\n  total: number;\n  versions: SilverWorkflowVersionSummary[];\n}\n\nexport interface MappingRecommendationResponse""",
)

# 7) Product UI: query and render history on demand.
replace(
    "src/ProductRoot.tsx",
    """import { silverApi, type SilverWorkflowRecord } from './api';""",
    """import { silverApi, type SilverWorkflowRecord, type SilverWorkflowVersionSummary } from './api';""",
)
replace(
    "src/ProductRoot.tsx",
    """  const [selected, setSelected] = useState<SilverWorkflowRecord | null>(null);\n  const [resumeWorkflow, setResumeWorkflow] = useState<WorkflowState>();""",
    """  const [selected, setSelected] = useState<SilverWorkflowRecord | null>(null);\n  const [versionHistory, setVersionHistory] = useState<SilverWorkflowVersionSummary[]>([]);\n  const [historyLoading, setHistoryLoading] = useState(false);\n  const [resumeWorkflow, setResumeWorkflow] = useState<WorkflowState>();""",
)
replace(
    "src/ProductRoot.tsx",
    """  function startNewProcess() {\n    setResumeWorkflow(undefined);\n    setMode('wizard');\n  }""",
    """  function startNewProcess() {\n    setResumeWorkflow(undefined);\n    setMode('wizard');\n  }\n\n  async function loadVersionHistory(workflowId: string) {\n    setHistoryLoading(true);\n    setError(undefined);\n    try {\n      const response = await silverApi.listWorkflowVersions(workflowId);\n      setVersionHistory(response.versions ?? []);\n    } catch (historyError) {\n      setError(historyError instanceof Error ? historyError.message : String(historyError));\n    } finally {\n      setHistoryLoading(false);\n    }\n  }""",
)
replace(
    "src/ProductRoot.tsx",
    """                  <td><button onClick={() => setSelected(workflow)}>Ver detalle</button></td>""",
    """                  <td><button onClick={() => { setSelected(workflow); setVersionHistory([]); }}>Ver detalle</button></td>""",
)
replace(
    "src/ProductRoot.tsx",
    """              <button\n                className=\"primaryProcessAction\"\n                disabled={loading}\n                onClick={() => void openProcess(selected.workflow_id)}\n              >\n                {loading ? 'Abriendo…' : 'Abrir proceso'}\n              </button>""",
    """              <div className=\"processHistoryActions\">\n                <button\n                  disabled={historyLoading}\n                  onClick={() => void loadVersionHistory(selected.workflow_id)}\n                >\n                  {historyLoading ? 'Cargando historial…' : 'Ver historial de versiones'}\n                </button>\n                <button\n                  className=\"primaryProcessAction\"\n                  disabled={loading}\n                  onClick={() => void openProcess(selected.workflow_id)}\n                >\n                  {loading ? 'Abriendo…' : 'Abrir proceso'}\n                </button>\n              </div>\n              {versionHistory.length > 0 && (\n                <section className=\"processVersionHistory\">\n                  <h3>Historial inmutable</h3>\n                  {versionHistory.map((version) => (\n                    <article key={version.workflow_version}>\n                      <div>\n                        <strong>Workflow v{version.workflow_version}</strong>\n                        <span>{version.lifecycle_status}</span>\n                      </div>\n                      <small>Mapping: {version.mapping_version ? `v${version.mapping_version}` : 'N/A'}</small>\n                      <small>Spec: {version.spec_id ?? 'N/A'}</small>\n                      <small>Package: {version.package_version ? `v${version.package_version}` : 'N/A'}</small>\n                      <small>Execution: {version.execution_id ?? 'N/A'}</small>\n                      <small>{version.status} · {formatDate(version.updated_at)}</small>\n                    </article>\n                  ))}\n                </section>\n              )}""",
)

# 8) Lightweight styles.
with (ROOT / "src/processes.css").open("a") as css:
    css.write(".processHistoryActions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.processHistoryActions button{border:1px solid #d0d5dd;background:#fff;border-radius:10px;padding:10px 12px;cursor:pointer}.processVersionHistory{margin-top:16px;border-top:1px solid #eef0f3;padding-top:14px}.processVersionHistory h3{font-size:14px;margin:0 0 10px}.processVersionHistory article{border:1px solid #e5e7eb;border-radius:10px;padding:10px;margin-bottom:8px;display:grid;gap:4px}.processVersionHistory article>div{display:flex;justify-content:space-between;gap:8px}.processVersionHistory article span{font-size:10px;font-weight:800;color:#475467}.processVersionHistory article small{color:#667085;overflow-wrap:anywhere}")

# 9) Unit test for immutable history semantics.
test_path = ROOT / "backend/deployable/silver-refinement-agent/tests/test_workflow_version_history.py"
test_path.write_text('''from datetime import datetime, timezone\n\nfrom modules.silver_workflow.models import (\n    BronzeSourceReference, CreateSilverWorkflowRequest, ConfirmWorkflowSourceRequest,\n    SchemaColumnEvidence, SchemaContextEvidence,\n)\nfrom modules.silver_workflow.repository import InMemoryWorkflowRepository\nfrom modules.silver_workflow.service import SilverWorkflowService\n\n\ndef test_workflow_version_history_returns_current_and_superseded_snapshots():\n    repo = InMemoryWorkflowRepository()\n    service = SilverWorkflowService(repository=repo)\n    created = service.create(CreateSilverWorkflowRequest(\n        source=BronzeSourceReference(\n            connection_id="bq", project_id="p", dataset_id="bronze", table_id="ventas"\n        ),\n        requested_by="tester",\n    ), correlation_id="corr")\n    confirmed = service.confirm_source(created.workflow_id, ConfirmWorkflowSourceRequest(\n        expected_version=created.version,\n        schema_context=SchemaContextEvidence(columns=[\n            SchemaColumnEvidence(name="id", data_type="INT64", nullable=False),\n        ]),\n        confirmed_by="tester",\n    ))\n\n    history = service.list_versions(created.workflow_id)\n\n    assert history.total == 2\n    assert history.current_version == confirmed.version\n    assert history.versions[0].workflow_version == confirmed.version\n    assert history.versions[0].lifecycle_status == "CURRENT"\n    assert history.versions[1].workflow_version == created.version\n    assert history.versions[1].lifecycle_status == "SUPERSEDED"\n''')

print("PASS: historial inmutable de versiones aplicado.")
print("Incluye endpoint read-only, snapshots GCS/InMemory, API frontend y visualización CURRENT/SUPERSEDED.")
