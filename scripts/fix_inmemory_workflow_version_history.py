from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py"

text = PATH.read_text()

if "class InMemoryWorkflowRepository:" not in text:
    raise SystemExit("InMemoryWorkflowRepository no encontrado")

class_start = text.index("class InMemoryWorkflowRepository:")
class_text = text[class_start:]

if "    def list_versions(self, workflow_id: str) -> list[SilverWorkflowRecord]:" in class_text:
    print("PASS: InMemoryWorkflowRepository ya contiene list_versions().")
    raise SystemExit(0)

anchor = '''    def list(self, *, limit: int, status: WorkflowStatus | None = None) -> list[SilverWorkflowRecord]:
        with self._lock:
            records = list(self._records.values())
            if status is not None:
                records = [record for record in records if record.status == status]
            records.sort(key=lambda record: record.updated_at, reverse=True)
            return [deepcopy(record) for record in records[:limit]]
'''

replacement = anchor + '''
    def list_versions(self, workflow_id: str) -> list[SilverWorkflowRecord]:
        with self._lock:
            if workflow_id not in self._records:
                raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}")
            snapshots = list(self._snapshots.get(workflow_id, {}).values())
            snapshots.sort(key=lambda record: record.version, reverse=True)
            return [deepcopy(record) for record in snapshots]
'''

if anchor not in class_text:
    raise SystemExit("No se encontro el bloque list() de InMemoryWorkflowRepository")

before = text[:class_start]
after = class_text.replace(anchor, replacement, 1)
PATH.write_text(before + after)

print("PASS: list_versions() agregado a InMemoryWorkflowRepository.")
