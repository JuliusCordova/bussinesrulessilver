from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from modules.silver_refinement.artifact_models import ArtifactType
from modules.silver_intelligent_mapping.models import (
    LoadStrategy,
    LoadStrategyType,
)
from modules.silver_refinement.artifact_repository import ArtifactRepository

from .dataproc_launcher import DataprocLauncher
from .execution_models import (
    CreateExecutionRequest,
    DataprocSubmissionResponse,
    ExecutionMonitoringResponse,
    ExecutionRecord,
    ExecutionStatus,
    PackageValidationResponse,
)
from .execution_repository import ExecutionRepository
from .package_resolver import PackageResolver
from .physical_design_materializer import PhysicalDesignMaterializer
from .watermark_repository import WatermarkRepository


class ExecutionService:
    def __init__(
        self,
        execution_repository: ExecutionRepository,
        artifact_repository: ArtifactRepository,
        package_resolver: PackageResolver | None = None,
        dataproc_launcher: DataprocLauncher | None = None,
        watermark_repository: WatermarkRepository | None = None,
        physical_design_materializer: PhysicalDesignMaterializer | None = None,
    ) -> None:
        self.execution_repository = execution_repository
        self.artifact_repository = artifact_repository
        self.package_resolver = package_resolver or PackageResolver()
        self.dataproc_launcher = dataproc_launcher
        self.watermark_repository = watermark_repository
        self.physical_design_materializer = physical_design_materializer

    def create_execution(self, request: CreateExecutionRequest) -> ExecutionRecord:
        package = self.artifact_repository.get_current(
            request.spec_id,
            ArtifactType.ARTIFACT_PACKAGE,
        )
        if package is None:
            raise ValueError(
                f"No existe un paquete de artefactos vigente para spec_id={request.spec_id}"
            )
        if not package.storage_uri:
            raise ValueError("El paquete vigente no tiene storage_uri")

        load_strategy = LoadStrategy()
        specification = self.artifact_repository.get_current(
            request.spec_id,
            ArtifactType.SPECIFICATION_JSON,
        )
        if specification is not None and specification.content_text:
            try:
                payload = json.loads(specification.content_text)
                load_strategy = LoadStrategy.model_validate(
                    payload.get("load_strategy") or {"type": "FULL"}
                )
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"SPECIFICATION_JSON inválido para spec_id={request.spec_id}: {exc}"
                ) from exc

        runtime_watermark = None
        if load_strategy.type == LoadStrategyType.INCREMENTAL_WATERMARK:
            if self.watermark_repository is None:
                raise ValueError(
                    "INCREMENTAL_WATERMARK requiere WatermarkRepository "
                    "configurado con ARTIFACT_BUCKET"
                )

            checkpoint = self.watermark_repository.get(request.spec_id)
            if checkpoint is not None:
                if checkpoint.spec_id != request.spec_id:
                    raise ValueError(
                        "El checkpoint recuperado no corresponde a la especificación"
                    )
                if checkpoint.watermark_column != load_strategy.watermark_column:
                    raise ValueError(
                        "La columna watermark del checkpoint no coincide "
                        "con la especificación vigente"
                    )
                runtime_watermark = checkpoint.current_watermark
            else:
                runtime_watermark = load_strategy.initial_watermark

            self._validate_runtime_watermark(runtime_watermark)

        record = ExecutionRecord(
            execution_id=f"exec_{uuid4().hex}",
            spec_id=request.spec_id,
            mapping_version=package.mapping_version,
            package_version=package.artifact_version,
            artifact_package_uri=package.storage_uri,
            load_strategy=load_strategy.type.value,
            watermark_column=load_strategy.watermark_column,
            runtime_watermark=runtime_watermark,
            lookback_value=load_strategy.lookback_value,
            lookback_unit=load_strategy.lookback_unit,
            status=ExecutionStatus.PENDING,
            requested_by=request.requested_by,
        )
        return self.execution_repository.create(record)

    def validate_package(self, execution_id: str) -> PackageValidationResponse:
        execution = self.execution_repository.get(execution_id)
        if execution is None:
            raise LookupError("Ejecución no encontrada")
        if execution.status not in {ExecutionStatus.PENDING, ExecutionStatus.FAILED}:
            raise ValueError(
                f"La ejecución no puede validarse desde el estado {execution.status.value}"
            )

        try:
            result = self.package_resolver.resolve_and_validate(
                spec_id=execution.spec_id,
                expected_package_uri=execution.artifact_package_uri,
            )
            if result.mapping_version != execution.mapping_version:
                raise ValueError("mapping_version no coincide con la ejecución")
            if result.package_version != execution.package_version:
                raise ValueError("package_version no coincide con la ejecución")
            updated = self.execution_repository.update_status(
                execution_id,
                ExecutionStatus.VALIDATED,
                None,
            )
        except Exception as exc:
            self.execution_repository.update_status(
                execution_id,
                ExecutionStatus.FAILED,
                str(exc),
            )
            raise ValueError(f"Falló la validación del paquete: {exc}") from exc

        return PackageValidationResponse(
            execution=updated,
            current_uri=result.current_uri,
            manifest_uri=result.manifest_uri,
            package_hash=result.package_hash,
            files_validated=result.files_validated,
        )

    def submit_execution(self, execution_id: str) -> DataprocSubmissionResponse:
        execution = self.execution_repository.get(execution_id)
        if execution is None:
            raise LookupError("Ejecución no encontrada")
        if execution.status != ExecutionStatus.VALIDATED:
            raise ValueError(
                f"La ejecución solo puede enviarse desde VALIDATED; estado actual={execution.status.value}"
            )

        try:
            if self.physical_design_materializer is not None:
                ddl = self.package_resolver.resolve_artifact_text(
                    spec_id=execution.spec_id,
                    expected_package_uri=execution.artifact_package_uri,
                    artifact_type=ArtifactType.SILVER_DDL.value,
                )

                specification_text = (
                    self.package_resolver.resolve_artifact_text(
                        spec_id=execution.spec_id,
                        expected_package_uri=execution.artifact_package_uri,
                        artifact_type=ArtifactType.SPECIFICATION_JSON.value,
                    )
                )

                specification_payload = json.loads(
                    specification_text
                )

                target = specification_payload.get(
                    "target"
                ) or {}

                target_project = target.get("project")
                target_dataset = target.get("dataset")
                target_table = target.get("table")

                if not all(
                    [
                        target_project,
                        target_dataset,
                        target_table,
                    ]
                ):
                    raise ValueError(
                        "SPECIFICATION_JSON no contiene "
                        "target completo"
                    )

                target_fqn = ".".join(
                    [
                        str(target_project),
                        str(target_dataset),
                        str(target_table),
                    ]
                )

                self.physical_design_materializer.ensure(
                    ddl=ddl,
                    target_table=target_fqn,
                    physical_design=(
                        specification_payload.get(
                            "physical_design"
                        )
                        or {}
                    ),
                )

            pyspark_uri = self.package_resolver.resolve_artifact_uri(
                spec_id=execution.spec_id,
                expected_package_uri=execution.artifact_package_uri,
                artifact_type=ArtifactType.PYSPARK_SCRIPT.value,
            )
            launcher = self.dataproc_launcher or DataprocLauncher()
            runtime_watermark = None
            if execution.load_strategy == LoadStrategyType.INCREMENTAL_WATERMARK.value:
                runtime_watermark = execution.runtime_watermark
                self._validate_runtime_watermark(runtime_watermark)

            submission = launcher.submit(
                execution_id=execution.execution_id,
                pyspark_uri=pyspark_uri,
                runtime_watermark=runtime_watermark,
            )
            updated = self.execution_repository.mark_queued(
                execution.execution_id,
                submission.batch_id,
            )
        except Exception as exc:
            self.execution_repository.update_status(
                execution_id,
                ExecutionStatus.FAILED,
                str(exc),
            )
            raise ValueError(f"Falló el envío a Dataproc Serverless: {exc}") from exc

        return DataprocSubmissionResponse(
            execution=updated,
            batch_id=submission.batch_id,
            batch_name=submission.batch_name,
            pyspark_uri=submission.pyspark_uri,
            operation_name=submission.operation_name,
        )

    def sync_execution_status(self, execution_id: str) -> ExecutionMonitoringResponse:
        execution = self.execution_repository.get(execution_id)
        if execution is None:
            raise LookupError("Ejecución no encontrada")
        if not execution.dataproc_batch_id:
            raise ValueError("La ejecución todavía no tiene dataproc_batch_id")

        launcher = self.dataproc_launcher or DataprocLauncher()
        snapshot = launcher.get_batch(execution.dataproc_batch_id)
        mapped_status = self._map_dataproc_state(snapshot.state)
        error_message = snapshot.state_message if mapped_status == ExecutionStatus.FAILED else None
        updated = self.execution_repository.update_monitoring(
            execution_id,
            status=mapped_status,
            state_time=snapshot.state_time,
            logs_uri=snapshot.output_uri,
            error_message=error_message,
        )

        return ExecutionMonitoringResponse(
            execution=updated,
            dataproc_state=snapshot.state,
            state_message=snapshot.state_message,
            state_time=snapshot.state_time,
            output_uri=snapshot.output_uri,
            diagnostic_output_uri=snapshot.diagnostic_output_uri,
        )

    @staticmethod
    def _validate_runtime_watermark(value: datetime | None) -> None:
        if value is None:
            raise ValueError(
                "INCREMENTAL_WATERMARK requiere un checkpoint existente "
                "o initial_watermark"
            )
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "El runtime_watermark debe incluir zona horaria"
            )

    @staticmethod
    def _map_dataproc_state(state: str) -> ExecutionStatus:
        mapping = {
            "PENDING": ExecutionStatus.QUEUED,
            "RUNNING": ExecutionStatus.RUNNING,
            "SUCCEEDED": ExecutionStatus.SUCCEEDED,
            "FAILED": ExecutionStatus.FAILED,
            "CANCELLED": ExecutionStatus.CANCELLED,
            "CANCELLING": ExecutionStatus.RUNNING,
            "STATE_UNSPECIFIED": ExecutionStatus.QUEUED,
        }
        return mapping.get(state, ExecutionStatus.QUEUED)

    def get_execution(self, execution_id: str) -> ExecutionRecord | None:
        return self.execution_repository.get(execution_id)

    def list_executions(self, limit: int = 50) -> list[ExecutionRecord]:
        return self.execution_repository.list(limit=limit)
