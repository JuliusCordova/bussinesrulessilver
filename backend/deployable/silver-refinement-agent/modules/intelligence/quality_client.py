from __future__ import annotations

import os
from typing import Any

import httpx


class QualityDomainClient:
    """Reads validated Quality, Profiling and Reconciliation evidence without duplicating it."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or os.getenv("RECONCILIATION_BACKEND_URL") or "").rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("BACKEND_TIMEOUT_SECONDS", "10"))

    def _get_first_available(self, paths: list[str]) -> tuple[dict[str, Any] | None, str | None]:
        if not self.base_url:
            return None, "RECONCILIATION_BACKEND_URL is not configured"
        last_error: str | None = None
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for path in paths:
                try:
                    response = client.get(f"{self.base_url}{path}")
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    return payload if isinstance(payload, dict) else {"items": payload}, None
                except Exception as exc:
                    last_error = str(exc)
        return None, last_error or "No compatible endpoint was found"

    def data_quality(self, execution_id: str, spec_id: str) -> tuple[dict[str, Any] | None, str | None]:
        return self._get_first_available([
            f"/data-quality/executions/{execution_id}/results",
            f"/quality/executions/{execution_id}",
            f"/quality/specs/{spec_id}/latest",
        ])

    def profiling(self, execution_id: str, spec_id: str) -> tuple[dict[str, Any] | None, str | None]:
        return self._get_first_available([
            f"/profiling/executions/{execution_id}",
            f"/profiling/specs/{spec_id}/latest",
            f"/profiles/{spec_id}",
        ])

    def reconciliation(self, execution_id: str, spec_id: str) -> tuple[dict[str, Any] | None, str | None]:
        return self._get_first_available([
            f"/reconciliation/executions/{execution_id}/result",
            f"/reconciliation/executions/{execution_id}",
            f"/reconciliation/specs/{spec_id}/latest",
        ])
