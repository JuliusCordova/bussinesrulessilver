from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend/deployable/silver-refinement-agent/modules/silver_workflow/repository.py"

text = TARGET.read_text()
old = '''    def list_versions(self, workflow_id: str) -> list[SilverWorkflowRecord]: ...\n    def list_versions(self, workflow_id: str) -> list[SilverWorkflowRecord]:\n        with self._lock:\n            if workflow_id not in self._records:\n                raise WorkflowNotFoundError(f"Workflow no encontrado: {workflow_id}")\n            snapshots = list(self._snapshots.get(workflow_id, {}).values())\n            snapshots.sort(key=lambda record: record.version, reverse=True)\n            return [deepcopy(record) for record in snapshots]\n\n'''
new = '''    def list_versions(self, workflow_id: str) -> list[SilverWorkflowRecord]: ...\n'''

if old not in text:
    raise SystemExit("Pattern not found: duplicate concrete list_versions() in WorkflowRepository Protocol")

TARGET.write_text(text.replace(old, new, 1))
print("PASS: WorkflowRepository Protocol saneado; list_versions queda solo como firma abstracta.")
