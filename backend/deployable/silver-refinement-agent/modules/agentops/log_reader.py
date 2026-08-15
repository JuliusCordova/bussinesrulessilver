from __future__ import annotations

from dataclasses import dataclass

from google.cloud import storage


@dataclass(frozen=True)
class LogFileContent:
    uri: str
    size_bytes: int
    content: str


class CloudStorageLogReader:
    def __init__(self, client: storage.Client | None = None) -> None:
        self.client = client or storage.Client()

    @staticmethod
    def _parse_gs_uri(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            raise ValueError("logs_uri debe ser una URI de Cloud Storage")
        path = uri[5:]
        bucket_name, separator, blob_prefix = path.partition("/")
        if not bucket_name or not separator or not blob_prefix:
            raise ValueError("logs_uri no tiene un bucket y prefijo válidos")
        return bucket_name, blob_prefix

    def read_prefix(self, uri: str) -> list[LogFileContent]:
        bucket_name, blob_prefix = self._parse_gs_uri(uri)
        blobs = sorted(
            self.client.list_blobs(bucket_name, prefix=blob_prefix),
            key=lambda blob: blob.name,
        )
        files: list[LogFileContent] = []
        for blob in blobs:
            if blob.name.endswith("/"):
                continue
            raw_content = blob.download_as_bytes()
            content = raw_content.decode("utf-8", errors="replace")
            files.append(
                LogFileContent(
                    uri=f"gs://{bucket_name}/{blob.name}",
                    size_bytes=int(blob.size or len(raw_content)),
                    content=content,
                )
            )
        return files
