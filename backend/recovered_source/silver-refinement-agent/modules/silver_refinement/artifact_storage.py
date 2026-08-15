from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from dataclasses import dataclass

from google.cloud import storage

from .artifact_models import ArtifactRecord


@dataclass(frozen=True)
class StoredPackage:
    base_uri: str
    package_uri: str
    current_uri: str
    package_hash: str
    package_size_bytes: int


class ArtifactStorageService:
    """Persists immutable Silver artifact packages in Google Cloud Storage."""

    root_prefix = "silver-refinement/specs"

    def __init__(
        self,
        client: storage.Client | None = None,
        bucket_name: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name or os.getenv("ARTIFACT_BUCKET")
        if not self.bucket_name:
            raise ValueError("ARTIFACT_BUCKET es obligatorio")
        self.client = client or storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)

    @classmethod
    def package_prefix(
        cls,
        spec_id: str,
        mapping_version: int,
        package_version: int,
    ) -> str:
        return (
            f"{cls.root_prefix}/{spec_id}/mapping-v{mapping_version}/"
            f"package-v{package_version}"
        )

    @staticmethod
    def build_zip(records: list[ArtifactRecord]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for record in sorted(records, key=lambda item: item.artifact_name):
                if record.content_text is None:
                    continue
                archive.writestr(record.artifact_name, record.content_text.encode("utf-8"))
        return buffer.getvalue()

    def _upload(
        self,
        object_name: str,
        payload: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        blob = self.bucket.blob(object_name)
        blob.metadata = metadata or {}
        blob.upload_from_string(payload, content_type=content_type)
        return f"gs://{self.bucket_name}/{object_name}"

    def persist_package(
        self,
        *,
        spec_id: str,
        mapping_version: int,
        package_version: int,
        records: list[ArtifactRecord],
        generated_by: str,
    ) -> StoredPackage:
        prefix = self.package_prefix(spec_id, mapping_version, package_version)
        base_uri = f"gs://{self.bucket_name}/{prefix}"

        for record in records:
            if record.content_text is None:
                continue
            object_name = f"{prefix}/{record.artifact_name}"
            content_type = "application/json" if record.artifact_name.endswith((".json", ".ipynb")) else "text/plain; charset=utf-8"
            record.storage_uri = self._upload(
                object_name,
                record.content_text.encode("utf-8"),
                content_type,
                {
                    "spec_id": spec_id,
                    "mapping_version": str(mapping_version),
                    "artifact_type": record.artifact_type.value,
                    "artifact_version": str(record.artifact_version),
                },
            )

        package_bytes = self.build_zip(records)
        package_hash = "sha256:" + hashlib.sha256(package_bytes).hexdigest()
        package_uri = self._upload(
            f"{prefix}/artifact-package.zip",
            package_bytes,
            "application/zip",
            {
                "spec_id": spec_id,
                "mapping_version": str(mapping_version),
                "package_version": str(package_version),
                "content_hash": package_hash,
            },
        )

        current_payload = json.dumps(
            {
                "spec_id": spec_id,
                "mapping_version": mapping_version,
                "package_version": package_version,
                "package_uri": package_uri,
                "generated_by": generated_by,
                "files": [
                    {
                        "artifact_type": record.artifact_type.value,
                        "name": record.artifact_name,
                        "storage_uri": record.storage_uri,
                        "content_hash": record.content_hash,
                    }
                    for record in records
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        current_uri = self._upload(
            f"{self.root_prefix}/{spec_id}/current.json",
            current_payload,
            "application/json",
            {"spec_id": spec_id, "package_version": str(package_version)},
        )

        return StoredPackage(
            base_uri=base_uri,
            package_uri=package_uri,
            current_uri=current_uri,
            package_hash=package_hash,
            package_size_bytes=len(package_bytes),
        )
