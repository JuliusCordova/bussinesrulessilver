from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from .settings import AlloyDBAvailabilitySettings


IdentityTokenProvider = Callable[[str], str]


def _default_identity_token_provider(audience: str) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return id_token.fetch_id_token(Request(), audience)


class AlloyDBPowerControllerClient:
    def __init__(
        self,
        *,
        settings: AlloyDBAvailabilitySettings,
        http_client: httpx.Client | None = None,
        token_provider: IdentityTokenProvider | None = None,
    ) -> None:
        if not settings.controller_url:
            raise ValueError("controller_url es obligatorio para crear el cliente")
        if not settings.audience:
            raise ValueError("audience es obligatorio para crear el cliente")
        self.settings = settings
        self._http_client = http_client
        self._token_provider = token_provider or _default_identity_token_provider

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    def start_business_traffic(
        self,
        *,
        correlation_id: str,
        requested_by: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/start",
            correlation_id=correlation_id,
            json={
                "reason": "BUSINESS_TRAFFIC",
                "correlation_id": correlation_id,
                "requested_by": requested_by,
                "idempotency_key": idempotency_key,
            },
        )

    def record_activity(
        self,
        *,
        domain: str,
        operation: str,
        correlation_id: str,
        actor: str,
        workflow_id: str | None = None,
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/activity",
            correlation_id=correlation_id,
            json={
                "domain": domain,
                "operation": operation,
                "correlation_id": correlation_id,
                "actor": actor,
                "workflow_id": workflow_id,
                "execution_id": execution_id,
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        correlation_id: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = self._token_provider(self.settings.audience or "")
        headers = {"Authorization": f"Bearer {token}"}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

        url = f"{self.settings.controller_url.rstrip('/')}{path}"
        if self._http_client is not None:
            response = self._http_client.request(
                method,
                url,
                headers=headers,
                json=json,
            )
        else:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("El controlador devolvió un payload no válido")
        return payload
