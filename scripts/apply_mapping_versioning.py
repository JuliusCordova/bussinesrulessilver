from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    file_path = ROOT / path
    text = file_path.read_text()
    if old not in text:
        raise SystemExit(f"FAIL: no se encontro bloque esperado en {path}")
    if text.count(old) != 1:
        raise SystemExit(f"FAIL: bloque ambiguo en {path}: {text.count(old)} coincidencias")
    file_path.write_text(text.replace(old, new, 1))


# 1) Backend model contract.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/models.py",
    "\n\nclass ReviewQualityRequest(BaseModel):\n",
    '''\n\nclass SaveSilverMappingRequest(BaseModel):
    expected_version: int = Field(ge=1)
    target: SilverTargetReference
    columns: list[SilverMappingColumn] = Field(min_length=1)
    edited_by: str = Field(min_length=2, max_length=200)
    change_reason: str = Field(min_length=2, max_length=2000)

    @model_validator(mode="after")
    def validate_unique_target_columns(self) -> "SaveSilverMappingRequest":
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Cada columna destino Silver debe tener un nombre único")
        return self


class ReviewQualityRequest(BaseModel):
''',
)

# 2) Repository protocol.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py",
    "    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord: ...\n",
    "    def save_mapping_version(self, workflow_id: str, *, expected_version: int, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], edited_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord: ...\n    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord: ...\n",
)

# 3) In-memory versioned mapping mutation.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py",
    "    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:\n",
    '''    def save_mapping_version(self, workflow_id: str, *, expected_version: int, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], edited_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
        with self._lock:
            record = self._require_record(workflow_id)
            self._require_version(record, expected_version, "guardar una nueva versión del mapping")
            metadata = dict(record.metadata)
            metadata.update({
                "mapping_last_edited_by": edited_by,
                "mapping_last_change_reason": change_reason,
                "mapping_last_changed_at": updated_at.isoformat(),
                "superseded_spec_id": record.spec_id,
                "superseded_execution_id": record.execution_id,
                "superseded_mapping_version": record.mapping_version,
            })
            return self._store(record.model_copy(deep=True, update={
                "version": record.version + 1,
                "status": WorkflowStatus.IN_PROGRESS,
                "active_step": 4,
                "mapping_version": mapping_version,
                "silver_target": target,
                "mapping_rules": mapping_rules,
                "spec_id": None,
                "quality_review": None,
                "artifact_package": None,
                "governance": None,
                "execution": None,
                "validation": None,
                "execution_id": None,
                "updated_at": updated_at,
                "metadata": metadata,
            }))

    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
''',
)

# 4) GCS versioned mapping mutation. _update already writes immutable workflow snapshots.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/gcs_repository.py",
    "    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:\n",
    '''    def save_mapping_version(self, workflow_id: str, *, expected_version: int, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], edited_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
        def mutate(record: SilverWorkflowRecord) -> SilverWorkflowRecord:
            metadata = dict(record.metadata)
            metadata.update({
                "mapping_last_edited_by": edited_by,
                "mapping_last_change_reason": change_reason,
                "mapping_last_changed_at": updated_at.isoformat(),
                "superseded_spec_id": record.spec_id,
                "superseded_execution_id": record.execution_id,
                "superseded_mapping_version": record.mapping_version,
            })
            return record.model_copy(deep=True, update={
                "version": record.version + 1,
                "status": WorkflowStatus.IN_PROGRESS,
                "active_step": 4,
                "mapping_version": mapping_version,
                "silver_target": target,
                "mapping_rules": mapping_rules,
                "spec_id": None,
                "quality_review": None,
                "artifact_package": None,
                "governance": None,
                "execution": None,
                "validation": None,
                "execution_id": None,
                "updated_at": updated_at,
                "metadata": metadata,
            })
        return self._update(workflow_id, expected_version, mutate)

    def save_specification(self, workflow_id: str, *, expected_version: int, spec_id: str, mapping_version: int, target: SilverTargetReference, mapping_rules: list[dict[str, object]], created_by: str, change_reason: str, updated_at: datetime) -> SilverWorkflowRecord:
''',
)

# 5) Service contract + validation.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py",
    "    SaveBusinessRulesDraftRequest,\n    SaveSilverSpecificationRequest,\n",
    "    SaveBusinessRulesDraftRequest,\n    SaveSilverMappingRequest,\n    SaveSilverSpecificationRequest,\n",
)
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/service.py",
    "    def save_specification(self, workflow_id: str, request: SaveSilverSpecificationRequest) -> SilverWorkflowRecord:\n",
    '''    def save_mapping_version(self, workflow_id: str, request: SaveSilverMappingRequest) -> SilverWorkflowRecord:
        current = self._require_version(workflow_id, request.expected_version)
        if not current.source_confirmed or current.schema_context is None:
            raise WorkflowStateConflictError("La fuente y el esquema deben estar confirmados antes de editar el mapping")
        if current.business_rules.status != BusinessRuleStatus.CONFIRMED:
            raise WorkflowStateConflictError("Las Business Rules deben estar confirmadas antes de versionar el mapping")
        if current.status == WorkflowStatus.EXECUTING:
            raise WorkflowStateConflictError("No se puede editar el mapping mientras el proceso está ejecutándose")

        source_columns = {column.name for column in current.schema_context.columns}
        unknown = sorted({
            column.source_column
            for column in request.columns
            if column.source_column and column.source_column not in source_columns
        })
        if unknown:
            raise ValueError("Las columnas de origen no existen en el esquema confirmado: " + ", ".join(unknown))

        next_mapping_version = (current.mapping_version or 0) + 1
        return self._with_actions(self.repository.save_mapping_version(
            workflow_id,
            expected_version=request.expected_version,
            mapping_version=next_mapping_version,
            target=request.target,
            mapping_rules=[column.model_dump(mode="json") for column in request.columns],
            edited_by=request.edited_by,
            change_reason=request.change_reason,
            updated_at=datetime.now(timezone.utc),
        ))

    def save_specification(self, workflow_id: str, request: SaveSilverSpecificationRequest) -> SilverWorkflowRecord:
''',
)

# 6) Router endpoint.
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py",
    "    ReviewQualityRequest,\n    SaveBusinessRulesDraftRequest,\n    SaveSilverSpecificationRequest,\n",
    "    ReviewQualityRequest,\n    SaveBusinessRulesDraftRequest,\n    SaveSilverMappingRequest,\n    SaveSilverSpecificationRequest,\n",
)
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py",
    "require_workflow_get = workflow_business_operation(\"workflow_get\")\n",
    "require_workflow_get = workflow_business_operation(\"workflow_get\")\nrequire_workflow_mapping = workflow_business_operation(\"workflow_mapping\")\n",
)
replace_once(
    "backend/deployable/silver-refinement-agent/modules/silver_workflow/router.py",
    "\n\n@router.post(\"/{workflow_id}/mapping-recommendations\", response_model=MappingRecommendationResponse)\n",
    '''\n\n@router.put("/{workflow_id}/mapping", response_model=SilverWorkflowRecord)
def save_workflow_mapping(workflow_id: str, request: SaveSilverMappingRequest, business: WorkflowBusinessOperation = Depends(require_workflow_mapping)) -> SilverWorkflowRecord:
    try:
        record = business.workflow_service.save_mapping_version(workflow_id, request)
        business.record_success(workflow_id=workflow_id)
        return record
    except WorkflowNotFoundError as exc:
        raise _not_found(exc) from exc
    except (WorkflowVersionConflictError, WorkflowStateConflictError) as exc:
        raise _conflict(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{workflow_id}/mapping-recommendations", response_model=MappingRecommendationResponse)
''',
)

# 7) Frontend API.
replace_once(
    "src/api.ts",
    "  generateMapping: (workflowId: string, payload: unknown) =>\n    request<MappingRecommendationResponse>(`/silver-workflows/${workflowId}/mapping-recommendations`, {\n      method: 'POST',\n      body: JSON.stringify(payload),\n    }),\n",
    "  generateMapping: (workflowId: string, payload: unknown) =>\n    request<MappingRecommendationResponse>(`/silver-workflows/${workflowId}/mapping-recommendations`, {\n      method: 'POST',\n      body: JSON.stringify(payload),\n    }),\n\n  saveMapping: (workflowId: string, payload: unknown) =>\n    request<SilverWorkflowRecord>(`/silver-workflows/${workflowId}/mapping`, {\n      method: 'PUT',\n      body: JSON.stringify(payload),\n    }),\n",
)

# 8) Mark resumed workflows explicitly.
replace_once(
    "src/types.ts",
    "  backendMessage?: string;\n",
    "  backendMessage?: string;\n  resumedFromBackend?: boolean;\n",
)
replace_once(
    "src/workflowResume.ts",
    "    backendMessage: JSON.stringify({\n",
    "    resumedFromBackend: true,\n    backendMessage: JSON.stringify({\n",
)

# 9) Persist edits from MappingStep only for resumed processes; preserve new-process behavior.
replace_once(
    "src/App.tsx",
    "            onNext={() => {\n              const rules = workflow.mappingRules?.length\n",
    "            onNext={async () => {\n              const rules = workflow.mappingRules?.length\n",
)
replace_once(
    "src/App.tsx",
    "              setWorkflow((current) => ({\n                ...current,\n                mappingRules: rules,\n                mappingSource: current.mappingSource ?? 'DIRECT',\n                mappingVersion: current.mappingVersion ?? 1,\n                activeStep: 'rules',\n                ...demoWorkflowPatch('Mapping editado y confirmado'),\n              }));\n",
    '''              if (workflow.resumedFromBackend && workflow.workflowId) {
                await runAction('Persistiendo nueva versión gobernada del mapping...', async () => {
                  const includedRules = rules.filter((rule) => rule.include);
                  const updated = await silverApi.saveMapping(workflow.workflowId!, {
                    expected_version: currentVersion(workflow),
                    target: {
                      project_id: workflow.projectId ?? seedSource.projectId,
                      dataset_id: workflow.targetDataset ?? seedSource.targetDataset,
                      table_id: workflow.targetTable ?? seedSource.targetTable,
                    },
                    columns: includedRules.map((rule) => ({
                      name: rule.targetColumn,
                      data_type: rule.targetType,
                      nullable: rule.nullable,
                      source_column: rule.sourceColumn || null,
                      transformation: toBackendTransformation(rule.transformationType),
                    })),
                    edited_by: REQUESTED_BY,
                    change_reason: 'Mapping editado desde Procesos Silver; downstream requiere revalidación.',
                  });
                  setWorkflow((current) => ({
                    ...current,
                    ...workflowPatchFromRecord(updated),
                    mappingRules: rules,
                    mappingSource: 'USER',
                    mappingVersion: updated.mapping_version ?? current.mappingVersion,
                    specId: undefined,
                    executionId: undefined,
                    executionStatus: undefined,
                    generatedArtifacts: undefined,
                    qualityReviewed: false,
                    qualityReviewDecision: undefined,
                    activeStep: 'artifacts',
                    resumedFromBackend: true,
                    ...demoWorkflowPatch(`Mapping v${updated.mapping_version ?? '?'} persistido; Spec y Package requieren regeneración`),
                    backendMessage: JSON.stringify(updated),
                  }));
                });
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
''',
)

# 10) Focused backend test created locally with the patch.
test_path = ROOT / "backend/deployable/silver-refinement-agent/tests/test_mapping_versioning.py"
if test_path.exists():
    raise SystemExit(f"FAIL: {test_path.relative_to(ROOT)} ya existe")
test_path.write_text('''from datetime import datetime, timezone\n\nfrom modules.silver_workflow.models import (\n    BronzeSourceReference, BusinessRule, BusinessRulesSection, BusinessRuleSeverity,\n    BusinessRuleStatus, BusinessRuleType, SaveSilverMappingRequest, SchemaColumnEvidence,\n    SchemaContextEvidence, SilverMappingColumn, SilverTargetReference, SilverWorkflowRecord,\n    WorkflowStatus,\n)\nfrom modules.silver_workflow.repository import InMemoryWorkflowRepository\nfrom modules.silver_workflow.service import SilverWorkflowService\n\n\ndef test_mapping_edit_creates_new_version_and_invalidates_downstream():\n    now = datetime.now(timezone.utc)\n    repo = InMemoryWorkflowRepository()\n    record = SilverWorkflowRecord(\n        workflow_id="workflow_test", version=7, status=WorkflowStatus.SUCCEEDED, active_step=8,\n        source=BronzeSourceReference(connection_id="bq", project_id="p", dataset_id="bronze", table_id="ventas"),\n        source_confirmed=True,\n        schema_context=SchemaContextEvidence(columns=[\n            SchemaColumnEvidence(name="id", data_type="INT64", nullable=False),\n            SchemaColumnEvidence(name="monto", data_type="NUMERIC", nullable=True),\n        ]),\n        business_rules=BusinessRulesSection(\n            status=BusinessRuleStatus.CONFIRMED,\n            rules=[BusinessRule(\n                rule_id="r1", name="id valido", description="id requerido",\n                rule_type=BusinessRuleType.VALIDATION, expression="id IS NOT NULL",\n                severity=BusinessRuleSeverity.ERROR, source_columns=["id"],\n                target_columns=["id"], rationale="clave",\n            )],\n            confirmed_by="tester", confirmed_at=now,\n        ),\n        mapping_rules=[{"name": "id", "data_type": "INT64", "source_column": "id"}],\n        mapping_version=3, silver_target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),\n        quality_rules=[{"rule_name": "id_not_null"}], quality_review={"decision": "APPROVED"},\n        artifact_package={"package_version": 2}, governance={"decision": "APPROVED"},\n        execution={"status": "SUCCEEDED"}, validation={"status": "SUCCEEDED"},\n        spec_id="spec_old", execution_id="exec_old", correlation_id="corr", created_by="tester",\n        created_at=now, updated_at=now,\n    )\n    repo.create(record)\n    service = SilverWorkflowService(repository=repo)\n\n    updated = service.save_mapping_version("workflow_test", SaveSilverMappingRequest(\n        expected_version=7,\n        target=SilverTargetReference(project_id="p", dataset_id="silver", table_id="ventas"),\n        columns=[\n            SilverMappingColumn(name="id", data_type="INT64", nullable=False, source_column="id"),\n            SilverMappingColumn(name="monto", data_type="NUMERIC", nullable=True, source_column="monto"),\n        ],\n        edited_by="tester", change_reason="agregar monto",\n    ))\n\n    assert updated.version == 8\n    assert updated.mapping_version == 4\n    assert updated.status == WorkflowStatus.IN_PROGRESS\n    assert updated.active_step == 4\n    assert updated.spec_id is None\n    assert updated.quality_review is None\n    assert updated.artifact_package is None\n    assert updated.execution is None\n    assert updated.execution_id is None\n    assert updated.metadata["superseded_spec_id"] == "spec_old"\n    assert updated.metadata["superseded_execution_id"] == "exec_old"\n    assert updated.metadata["superseded_mapping_version"] == 3\n''')

print("PASS: versionamiento gobernado de Mapping aplicado.")
print("Cambios esperados: models/repositories/service/router + API/UI + test_mapping_versioning.py")
