from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from .artifact_generator import ArtifactGeneratorService
from .artifact_models import (
    ArtifactRecord,
    ArtifactStatus,
    ArtifactType,
    GenerateArtifactPackageRequest,
)
from .execution_artifact_generator import ExecutionArtifactGeneratorService


class ArtifactPackageGeneratorService:
    template_version = "1.3.0"

    @staticmethod
    def _digest(content: str) -> str:
        return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _record(
        self,
        *,
        spec_id: str,
        mapping_version: int,
        artifact_type: ArtifactType,
        artifact_name: str,
        artifact_version: int,
        content: str,
        generated_by: str,
        template_name: str,
        metadata: dict,
    ) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=str(uuid.uuid4()),
            spec_id=spec_id,
            mapping_version=mapping_version,
            artifact_type=artifact_type,
            artifact_name=artifact_name,
            artifact_version=artifact_version,
            generation_status=ArtifactStatus.GENERATED,
            validation_status="PENDING",
            content_text=content,
            content_hash=self._digest(content),
            template_name=template_name,
            template_version=self.template_version,
            generated_by=generated_by,
            is_current=True,
            metadata=metadata,
        )

    def build_contents(
        self,
        spec_id: str,
        request: GenerateArtifactPackageRequest,
    ) -> dict[ArtifactType, tuple[str, str, str]]:
        ddl = ArtifactGeneratorService().build_silver_ddl(request)
        execution_generator = ExecutionArtifactGeneratorService()
        normalized_quality_rules = execution_generator.normalize_quality_rules(
            request.quality_rules
        )
        pyspark_script = execution_generator.build_pyspark_script(spec_id, request)
        notebook = execution_generator.build_notebook(
            spec_id,
            request,
            pyspark_script,
        )

        mapping = {
            "spec_id": spec_id,
            "mapping_version": request.mapping_version,
            "source": {
                "project": request.source_project,
                "dataset": request.source_dataset,
                "table": request.source_table,
            },
            "target": {
                "project": request.target_project,
                "dataset": request.target_dataset,
                "table": request.target_table,
            },
            "columns": [
                column.model_dump(mode="json")
                for column in request.columns
            ],
        }
        mapping_json = json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True)

        specification = {
            "spec_id": spec_id,
            "mapping_version": request.mapping_version,
            "status": "ARTIFACTS_GENERATED",
            "source": mapping["source"],
            "target": mapping["target"],
            "definition": request.specification,
            "load_strategy": request.load_strategy.model_dump(mode="json"),
            "physical_design": request.physical_design.model_dump(mode="json"),
            "quality_rules": normalized_quality_rules,
        }
        specification_json = json.dumps(
            specification, ensure_ascii=False, indent=2, sort_keys=True
        )

        transformations = [
            {
                "source_column": column.source_column or column.name,
                "target_column": column.name,
                "target_type": column.data_type.upper(),
                "nullable": column.nullable,
                "transformation": (
                    column.normalized_transformation().model_dump(mode="json")
                ),
            }
            for column in request.columns
        ]
        transformations_json = json.dumps(
            transformations, ensure_ascii=False, indent=2, sort_keys=True
        )

        readme = (
            f"# Silver Refinement Package: {spec_id}\n\n"
            f"## Source\n"
            f"`{request.source_project}.{request.source_dataset}.{request.source_table}`\n\n"
            f"## Target\n"
            f"`{request.target_project}.{request.target_dataset}.{request.target_table}`\n\n"
            f"## Mapping version\n{request.mapping_version}\n\n"
            "## Generated artifacts\n"
            "- silver_ddl.sql\n"
            "- mapping.json\n"
            "- specification.json\n"
            "- transformations.json\n"
            "- silver_pipeline.py\n"
            "- silver_pipeline.ipynb\n"
            "- README.md\n"
            "- manifest.json\n\n"
            "## Execution\n"
            "The generated PySpark script is designed for Dataproc Serverless "
            "with the Spark BigQuery connector. Governed quality validation runs "
            "before the target table is written. Runtime actions are enforced exactly: "
            "OBSERVE_ONLY records evidence, WARN continues, QUARANTINE excludes failing "
            "rows from Silver and persists them in `<target>__quarantine`, and BLOCK_LOAD "
            "prevents the Silver write.\n"
        )

        generated_at = datetime.now(timezone.utc).isoformat()
        files = [
            {
                "artifact_type": "SILVER_DDL",
                "name": "silver_ddl.sql",
                "sha256": self._digest(ddl),
            },
            {
                "artifact_type": "MAPPING_JSON",
                "name": "mapping.json",
                "sha256": self._digest(mapping_json),
            },
            {
                "artifact_type": "SPECIFICATION_JSON",
                "name": "specification.json",
                "sha256": self._digest(specification_json),
            },
            {
                "artifact_type": "TRANSFORMATIONS_JSON",
                "name": "transformations.json",
                "sha256": self._digest(transformations_json),
            },
            {
                "artifact_type": "PYSPARK_SCRIPT",
                "name": "silver_pipeline.py",
                "sha256": self._digest(pyspark_script),
            },
            {
                "artifact_type": "NOTEBOOK",
                "name": "silver_pipeline.ipynb",
                "sha256": self._digest(notebook),
            },
            {
                "artifact_type": "README",
                "name": "README.md",
                "sha256": self._digest(readme),
            },
        ]
        manifest = {
            "spec_id": spec_id,
            "mapping_version": request.mapping_version,
            "generated_at": generated_at,
            "generated_by": request.generated_by,
            "execution_target": "DATAPROC_SERVERLESS",
            "files": files,
        }
        manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)

        return {
            ArtifactType.SILVER_DDL: ("silver_ddl.sql", ddl, "silver_ddl"),
            ArtifactType.MAPPING_JSON: ("mapping.json", mapping_json, "mapping_json"),
            ArtifactType.SPECIFICATION_JSON: (
                "specification.json",
                specification_json,
                "specification_json",
            ),
            ArtifactType.TRANSFORMATIONS_JSON: (
                "transformations.json",
                transformations_json,
                "transformations_json",
            ),
            ArtifactType.PYSPARK_SCRIPT: (
                "silver_pipeline.py",
                pyspark_script,
                "pyspark_script",
            ),
            ArtifactType.NOTEBOOK: (
                "silver_pipeline.ipynb",
                notebook,
                "notebook",
            ),
            ArtifactType.README: ("README.md", readme, "readme"),
            ArtifactType.MANIFEST_JSON: (
                "manifest.json",
                manifest_json,
                "manifest_json",
            ),
        }

    def create_records(
        self,
        spec_id: str,
        request: GenerateArtifactPackageRequest,
        versions: dict[ArtifactType, int],
    ) -> list[ArtifactRecord]:
        metadata = {
            **request.metadata,
            "source_table": (
                f"{request.source_project}.{request.source_dataset}.{request.source_table}"
            ),
            "target_table": (
                f"{request.target_project}.{request.target_dataset}.{request.target_table}"
            ),
            "execution_target": "DATAPROC_SERVERLESS",
        }
        contents = self.build_contents(spec_id, request)
        return [
            self._record(
                spec_id=spec_id,
                mapping_version=request.mapping_version,
                artifact_type=artifact_type,
                artifact_name=name,
                artifact_version=versions[artifact_type],
                content=content,
                generated_by=request.generated_by,
                template_name=template_name,
                metadata=metadata,
            )
            for artifact_type, (name, content, template_name) in contents.items()
        ]
