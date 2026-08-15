from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.api_core.exceptions import Conflict, Forbidden, NotFound
from google.cloud import bigquery
from pydantic import BaseModel, Field, model_validator

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_RESOURCE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")


class DatasetSummary(BaseModel):
    project_id: str
    dataset_id: str
    location: str | None = None
    friendly_name: str | None = None
    description: str | None = None
    table_count: int | None = None


class TableSummary(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    table_type: str | None = None
    friendly_name: str | None = None
    description: str | None = None
    location: str | None = None
    num_rows: int | None = None


class TableDetail(TableSummary):
    schema: list[dict[str, Any]] = Field(default_factory=list)
    partitioning: dict[str, Any] | None = None
    clustering_columns: list[str] = Field(default_factory=list)


class CreateDatasetRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=1024)
    location: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    friendly_name: str | None = Field(default=None, max_length=300)
    labels: dict[str, str] = Field(default_factory=dict)
    confirm_creation: bool = False

    @model_validator(mode="after")
    def validate_creation(self) -> "CreateDatasetRequest":
        if not _RESOURCE_ID.fullmatch(self.dataset_id):
            raise ValueError("dataset_id contiene caracteres no permitidos")
        if not self.confirm_creation:
            raise ValueError("La creación física requiere confirm_creation=true")
        return self


class DestinationCatalogService:
    def __init__(self, client: bigquery.Client | None = None) -> None:
        self.client = client or bigquery.Client()

    @staticmethod
    def _validate_project(value: str) -> str:
        if not _PROJECT_ID.fullmatch(value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="project_id contiene caracteres no permitidos",
            )
        return value

    @staticmethod
    def _validate_resource(value: str, label: str) -> str:
        if not _RESOURCE_ID.fullmatch(value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{label} contiene caracteres no permitidos",
            )
        return value

    def list_datasets(self, project_id: str) -> list[DatasetSummary]:
        project = self._validate_project(project_id)
        try:
            datasets = list(self.client.list_datasets(project=project))
        except Forbidden as exc:
            raise HTTPException(status_code=403, detail="Sin permisos para listar datasets") from exc

        result: list[DatasetSummary] = []
        for item in datasets:
            dataset_id = getattr(item, "dataset_id", None)
            if not dataset_id:
                continue
            try:
                dataset = self.client.get_dataset(f"{project}.{dataset_id}")
                table_count = sum(1 for _ in self.client.list_tables(dataset.reference))
                result.append(
                    DatasetSummary(
                        project_id=project,
                        dataset_id=dataset.dataset_id,
                        location=dataset.location,
                        friendly_name=dataset.friendly_name,
                        description=dataset.description,
                        table_count=table_count,
                    )
                )
            except Forbidden:
                result.append(DatasetSummary(project_id=project, dataset_id=dataset_id))
        return sorted(result, key=lambda item: item.dataset_id.lower())

    def create_dataset(self, project_id: str, request: CreateDatasetRequest) -> DatasetSummary:
        project = self._validate_project(project_id)
        dataset_id = self._validate_resource(request.dataset_id, "dataset_id")
        dataset_ref = f"{project}.{dataset_id}"

        try:
            existing = self.client.get_dataset(dataset_ref)
        except NotFound:
            existing = None
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"El dataset {dataset_ref} ya existe")

        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = request.location
        dataset.description = request.description
        dataset.friendly_name = request.friendly_name
        if request.labels:
            dataset.labels = request.labels
        try:
            created = self.client.create_dataset(dataset, exists_ok=False)
        except Conflict as exc:
            raise HTTPException(status_code=409, detail=f"El dataset {dataset_ref} ya existe") from exc
        except Forbidden as exc:
            raise HTTPException(status_code=403, detail="Sin permisos para crear datasets") from exc

        return DatasetSummary(
            project_id=project,
            dataset_id=created.dataset_id,
            location=created.location,
            friendly_name=created.friendly_name,
            description=created.description,
            table_count=0,
        )

    def list_tables(self, project_id: str, dataset_id: str) -> list[TableSummary]:
        project = self._validate_project(project_id)
        dataset = self._validate_resource(dataset_id, "dataset_id")
        dataset_ref = f"{project}.{dataset}"
        try:
            dataset_resource = self.client.get_dataset(dataset_ref)
            tables = list(self.client.list_tables(dataset_ref))
        except NotFound as exc:
            raise HTTPException(status_code=404, detail=f"Dataset no encontrado: {dataset_ref}") from exc
        except Forbidden as exc:
            raise HTTPException(status_code=403, detail="Sin permisos para listar tablas") from exc

        return sorted(
            [
                TableSummary(
                    project_id=project,
                    dataset_id=dataset,
                    table_id=table.table_id,
                    table_type=getattr(table, "table_type", None),
                    location=dataset_resource.location,
                )
                for table in tables
            ],
            key=lambda item: item.table_id.lower(),
        )

    def get_table(self, project_id: str, dataset_id: str, table_id: str) -> TableDetail:
        project = self._validate_project(project_id)
        dataset = self._validate_resource(dataset_id, "dataset_id")
        table = self._validate_resource(table_id, "table_id")
        table_ref = f"{project}.{dataset}.{table}"
        try:
            resource = self.client.get_table(table_ref)
            dataset_resource = self.client.get_dataset(f"{project}.{dataset}")
        except NotFound as exc:
            raise HTTPException(status_code=404, detail=f"Tabla no encontrada: {table_ref}") from exc
        except Forbidden as exc:
            raise HTTPException(status_code=403, detail="Sin permisos para consultar la tabla") from exc

        partitioning: dict[str, Any] | None = None
        if resource.time_partitioning is not None:
            partitioning = {
                "type": getattr(resource.time_partitioning, "type_", None),
                "field": resource.time_partitioning.field,
                "expiration_ms": resource.time_partitioning.expiration_ms,
            }
        elif resource.range_partitioning is not None:
            partitioning = {
                "type": "RANGE",
                "field": resource.range_partitioning.field,
            }

        return TableDetail(
            project_id=project,
            dataset_id=dataset,
            table_id=table,
            table_type=resource.table_type,
            friendly_name=resource.friendly_name,
            description=resource.description,
            location=dataset_resource.location,
            num_rows=resource.num_rows,
            schema=[
                {
                    "name": field.name,
                    "data_type": field.field_type,
                    "mode": field.mode,
                    "description": field.description,
                }
                for field in resource.schema
            ],
            partitioning=partitioning,
            clustering_columns=list(resource.clustering_fields or []),
        )


def get_destination_catalog_service() -> DestinationCatalogService:
    return DestinationCatalogService()


def register_destination_catalog_routes(router: APIRouter) -> None:
    @router.get("/catalog/projects/{project_id}/datasets", response_model=list[DatasetSummary])
    def list_destination_datasets(
        project_id: str,
        service: DestinationCatalogService = Depends(get_destination_catalog_service),
    ) -> list[DatasetSummary]:
        return service.list_datasets(project_id)

    @router.post(
        "/catalog/projects/{project_id}/datasets",
        response_model=DatasetSummary,
        status_code=status.HTTP_201_CREATED,
    )
    def create_destination_dataset(
        project_id: str,
        request: CreateDatasetRequest,
        service: DestinationCatalogService = Depends(get_destination_catalog_service),
    ) -> DatasetSummary:
        return service.create_dataset(project_id, request)

    @router.get(
        "/catalog/projects/{project_id}/datasets/{dataset_id}/tables",
        response_model=list[TableSummary],
    )
    def list_destination_tables(
        project_id: str,
        dataset_id: str,
        service: DestinationCatalogService = Depends(get_destination_catalog_service),
    ) -> list[TableSummary]:
        return service.list_tables(project_id, dataset_id)

    @router.get(
        "/catalog/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}",
        response_model=TableDetail,
    )
    def get_destination_table(
        project_id: str,
        dataset_id: str,
        table_id: str,
        service: DestinationCatalogService = Depends(get_destination_catalog_service),
    ) -> TableDetail:
        return service.get_table(project_id, dataset_id, table_id)
