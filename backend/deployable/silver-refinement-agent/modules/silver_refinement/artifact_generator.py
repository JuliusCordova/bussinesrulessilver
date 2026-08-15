from __future__ import annotations

import hashlib
import re
import uuid

from modules.silver_intelligent_mapping.compiler import compile_bigquery_ddl
from modules.silver_intelligent_mapping.models import IntelligentMappingColumn

from .artifact_models import (
    ArtifactRecord,
    ArtifactStatus,
    ArtifactType,
    GenerateSilverDDLRequest,
)

_ALLOWED_TYPES = {
    "STRING", "BYTES", "INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC",
    "BIGNUMERIC", "BOOL", "BOOLEAN", "DATE", "DATETIME", "GEOGRAPHY",
    "JSON", "TIME", "TIMESTAMP",
}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")


def _identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} contiene caracteres no permitidos: {value}")
    return value


def _data_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in _ALLOWED_TYPES:
        raise ValueError(f"Tipo BigQuery no soportado: {value}")
    return normalized


class ArtifactGeneratorService:
    template_name = "silver_ddl"
    template_version = "1.2.0"

    def build_silver_ddl(self, request: GenerateSilverDDLRequest) -> str:
        project = _identifier(request.target_project, "target_project")
        dataset = _identifier(request.target_dataset, "target_dataset")
        table = _identifier(request.target_table, "target_table")

        seen: set[str] = set()
        intelligent_columns: list[IntelligentMappingColumn] = []
        for column in request.columns:
            name = _identifier(column.name, "column.name")
            if name.lower() in seen:
                raise ValueError(f"Columna duplicada: {name}")
            seen.add(name.lower())

            # DDL-only legacy requests did not require source_column. For physical
            # schema generation, defaulting the source to the target name is safe
            # and preserves the previous public contract.
            source_column = column.source_column or name
            intelligent_columns.append(
                IntelligentMappingColumn(
                    source_column=source_column,
                    target_column=name,
                    target_type=_data_type(column.data_type),
                    nullable=column.nullable,
                    include=column.include,
                    transformation=column.normalized_transformation(),
                    confidence=column.confidence,
                    reason=column.recommendation_reason,
                    risk=column.recommendation_risk,
                    requires_approval=column.requires_approval,
                )
            )

        return compile_bigquery_ddl(
            project_id=project,
            dataset_id=dataset,
            table_id=table,
            columns=intelligent_columns,
            physical_design=request.physical_design,
        )

    def create_record(
        self,
        spec_id: str,
        artifact_version: int,
        request: GenerateSilverDDLRequest,
    ) -> ArtifactRecord:
        ddl = self.build_silver_ddl(request)
        digest = hashlib.sha256(ddl.encode("utf-8")).hexdigest()
        return ArtifactRecord(
            artifact_id=str(uuid.uuid4()),
            spec_id=spec_id,
            mapping_version=request.mapping_version,
            artifact_type=ArtifactType.SILVER_DDL,
            artifact_name=f"{request.target_table}.sql",
            artifact_version=artifact_version,
            generation_status=ArtifactStatus.GENERATED,
            validation_status="PENDING",
            content_text=ddl,
            content_hash=f"sha256:{digest}",
            template_name=self.template_name,
            template_version=self.template_version,
            generated_by=request.generated_by,
            is_current=True,
            metadata=request.metadata,
        )
