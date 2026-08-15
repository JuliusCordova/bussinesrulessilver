from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from urllib.parse import urlparse

from google.cloud import storage


@dataclass(frozen=True)
class PackageValidationResult:
    spec_id: str
    mapping_version: int
    package_version: int
    package_uri: str
    current_uri: str
    manifest_uri: str
    package_hash: str
    files_validated: int


class PackageResolver:
    root_prefix = "silver-refinement/specs"

    def __init__(self, client: storage.Client | None = None) -> None:
        self.client = client or storage.Client()

    @staticmethod
    def _split_gs_uri(uri: str) -> tuple[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != "gs" or not parsed.netloc or not parsed.path:
            raise ValueError(f"URI de Cloud Storage inválida: {uri}")
        return parsed.netloc, parsed.path.lstrip("/")

    def _download(self, uri: str) -> bytes:
        bucket_name, object_name = self._split_gs_uri(uri)
        blob = self.client.bucket(bucket_name).blob(object_name)
        if not blob.exists():
            raise ValueError(f"No existe el objeto requerido: {uri}")
        return blob.download_as_bytes()

    def _load_current(self, *, spec_id: str, expected_package_uri: str) -> tuple[str, dict]:
        bucket_name, _ = self._split_gs_uri(expected_package_uri)
        current_uri = f"gs://{bucket_name}/{self.root_prefix}/{spec_id}/current.json"
        current = json.loads(self._download(current_uri).decode("utf-8"))

        if current.get("spec_id") != spec_id:
            raise ValueError("current.json no corresponde al spec solicitado")
        if current.get("package_uri") != expected_package_uri:
            raise ValueError("El package vigente no coincide con la ejecución registrada")
        return current_uri, current

    def resolve_artifact_uri(
        self,
        *,
        spec_id: str,
        expected_package_uri: str,
        artifact_type: str,
    ) -> str:
        _, current = self._load_current(
            spec_id=spec_id,
            expected_package_uri=expected_package_uri,
        )
        entry = next(
            (
                item
                for item in (current.get("files") or [])
                if item.get("artifact_type") == artifact_type
            ),
            None,
        )
        if entry is None or not entry.get("storage_uri"):
            raise ValueError(f"current.json no contiene {artifact_type}")
        uri = str(entry["storage_uri"])
        self._download(uri)
        return uri

    def resolve_artifact_text(
        self,
        *,
        spec_id: str,
        expected_package_uri: str,
        artifact_type: str,
    ) -> str:
        uri = self.resolve_artifact_uri(
            spec_id=spec_id,
            expected_package_uri=expected_package_uri,
            artifact_type=artifact_type,
        )
        return self._download(uri).decode("utf-8")

    def resolve_and_validate(self, *, spec_id: str, expected_package_uri: str) -> PackageValidationResult:
        current_uri, current = self._load_current(
            spec_id=spec_id,
            expected_package_uri=expected_package_uri,
        )

        files = current.get("files") or []
        manifest_entry = next(
            (item for item in files if item.get("artifact_type") == "MANIFEST_JSON"),
            None,
        )
        if manifest_entry is None or not manifest_entry.get("storage_uri"):
            raise ValueError("current.json no contiene MANIFEST_JSON")

        validated = 0
        for item in files:
            uri = item.get("storage_uri")
            expected_hash = item.get("content_hash")
            if not uri:
                raise ValueError(f"Artefacto sin storage_uri: {item.get('name')}")
            payload = self._download(uri)
            if expected_hash:
                actual_hash = "sha256:" + hashlib.sha256(payload).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"Hash inválido para {item.get('name')}")
            validated += 1

        manifest_uri = manifest_entry["storage_uri"]
        json.loads(self._download(manifest_uri).decode("utf-8"))

        package_bytes = self._download(expected_package_uri)
        package_hash = "sha256:" + hashlib.sha256(package_bytes).hexdigest()

        return PackageValidationResult(
            spec_id=spec_id,
            mapping_version=int(current["mapping_version"]),
            package_version=int(current["package_version"]),
            package_uri=expected_package_uri,
            current_uri=current_uri,
            manifest_uri=manifest_uri,
            package_hash=package_hash,
            files_validated=validated,
        )
