from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from google.cloud import storage

from .artifact_generator import ArtifactGeneratorService
from .artifact_models import (
    ArtifactPackageResponse,
    ArtifactRecord,
    ArtifactStatus,
    ArtifactType,
    GenerateArtifactPackageRequest,
    GenerateSilverDDLRequest,
)
from .artifact_package_generator import ArtifactPackageGeneratorService
from .artifact_repository import ArtifactRepository
from .artifact_storage import ArtifactStorageService

router = APIRouter(prefix="/silver-refinement", tags=["Silver Refinement"])


def _repository() -> ArtifactRepository:
    return ArtifactRepository()


@router.post(
    "/specs/{spec_id}/artifacts/ddl",
    response_model=ArtifactRecord,
    status_code=201,
)
def generate_silver_ddl(spec_id: str, request: GenerateSilverDDLRequest) -> ArtifactRecord:
    try:
        repository = _repository()
        generator = ArtifactGeneratorService()
        version = repository.next_version(spec_id, ArtifactType.SILVER_DDL)
        record = generator.create_record(spec_id, version, request)
        return repository.save_as_current(record)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo generar el artefacto: {exc}") from exc


@router.post(
    "/specs/{spec_id}/artifacts/generate",
    response_model=ArtifactPackageResponse,
    status_code=201,
)
def generate_artifact_package(
    spec_id: str,
    request: GenerateArtifactPackageRequest,
) -> ArtifactPackageResponse:
    try:
        repository = _repository()
        generator = ArtifactPackageGeneratorService()
        storage = ArtifactStorageService()

        artifact_types = list(generator.build_contents(spec_id, request).keys())
        versions = {
            artifact_type: repository.next_version(spec_id, artifact_type)
            for artifact_type in artifact_types
        }
        package_version = repository.next_version(spec_id, ArtifactType.ARTIFACT_PACKAGE)
        records = generator.create_records(spec_id, request, versions)

        stored = storage.persist_package(
            spec_id=spec_id,
            mapping_version=request.mapping_version,
            package_version=package_version,
            records=records,
            generated_by=request.generated_by,
        )

        saved = [repository.save_as_current(record) for record in records]
        package_record = ArtifactRecord(
            artifact_id=str(uuid.uuid4()),
            spec_id=spec_id,
            mapping_version=request.mapping_version,
            artifact_type=ArtifactType.ARTIFACT_PACKAGE,
            artifact_name="artifact-package.zip",
            artifact_version=package_version,
            generation_status=ArtifactStatus.GENERATED,
            validation_status="PENDING",
            content_text=None,
            storage_uri=stored.package_uri,
            content_hash=stored.package_hash,
            template_name="artifact_package_zip",
            template_version=generator.template_version,
            generated_by=request.generated_by,
            is_current=True,
            metadata={
                **request.metadata,
                "base_uri": stored.base_uri,
                "current_uri": stored.current_uri,
                "package_size_bytes": stored.package_size_bytes,
                "artifact_count": len(records),
            },
        )
        saved.append(repository.save_as_current(package_record))

        return ArtifactPackageResponse(
            spec_id=spec_id,
            mapping_version=request.mapping_version,
            artifacts=saved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo generar el paquete de artefactos: {exc}",
        ) from exc


@router.get("/specs/{spec_id}/artifacts", response_model=list[ArtifactRecord])
def list_artifacts(spec_id: str) -> list[ArtifactRecord]:
    return _repository().list_for_spec(spec_id)


@router.get(
    "/specs/{spec_id}/artifacts/current/{artifact_type}",
    response_model=ArtifactRecord,
)
def get_current_artifact(spec_id: str, artifact_type: ArtifactType) -> ArtifactRecord:
    record = _repository().get_current(spec_id, artifact_type)
    if record is None:
        raise HTTPException(status_code=404, detail="No existe un artefacto vigente")
    return record


@router.get(
    "/specs/{spec_id}/artifacts/current/{artifact_type}/content"
)
def get_current_artifact_content(
    spec_id: str,
    artifact_type: ArtifactType,
) -> dict[str, object]:
    """Return the current text artifact and its governed metadata."""

    record = _repository().get_current(spec_id, artifact_type)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No existe un artefacto vigente de tipo "
                f"{artifact_type.value} para la especificación {spec_id}."
            ),
        )

    storage_uri = str(record.storage_uri or "")

    if not storage_uri.startswith("gs://"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"El artefacto {artifact_type.value} no posee una URI "
                "válida en Cloud Storage."
            ),
        )

    bucket_and_blob = storage_uri[5:].split("/", 1)

    if len(bucket_and_blob) != 2 or not all(bucket_and_blob):
        raise HTTPException(
            status_code=409,
            detail=f"URI de artefacto inválida: {storage_uri}",
        )

    bucket_name, blob_name = bucket_and_blob

    try:
        content = (
            storage.Client()
            .bucket(bucket_name)
            .blob(blob_name)
            .download_as_text(encoding="utf-8")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"No fue posible leer {artifact_type.value} "
                "desde Cloud Storage."
            ),
        ) from exc

    return {
        "artifact": record.model_dump(mode="json"),
        "content": content,
    }
