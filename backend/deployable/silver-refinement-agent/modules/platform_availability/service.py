from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from .models import (
    AlloyDBAvailability,
    AlloyDBAvailabilityState,
    BusinessAvailabilityContext,
)
from .power_controller_client import AlloyDBPowerControllerClient
from .settings import AlloyDBAvailabilitySettings


Clock = Callable[[], datetime]
LOGGER = logging.getLogger(__name__)


class AlloyDBAvailabilityService:
    def __init__(
        self,
        *,
        settings: AlloyDBAvailabilitySettings,
        client: AlloyDBPowerControllerClient | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if settings.enabled and client is None:
            raise ValueError("client es obligatorio cuando on-demand está habilitado")

    def observe(self) -> AlloyDBAvailability:
        if not self.settings.enabled:
            return self._availability(
                state=AlloyDBAvailabilityState.BYPASSED,
                ready=True,
                managed=False,
                retryable=False,
                reason="La gestión on-demand está deshabilitada; se conserva el comportamiento actual",
            )

        try:
            payload = self.client.status() if self.client else {}
        except Exception:
            return self._availability(
                state=AlloyDBAvailabilityState.UNAVAILABLE,
                ready=False,
                managed=True,
                retryable=True,
                retry_after_seconds=self.settings.retry_after_seconds,
                reason="No fue posible consultar el controlador privado de AlloyDB",
            )

        instance = payload.get("instance") or {}
        instance_state = str(instance.get("state") or "UNKNOWN").upper()
        activation_policy = str(
            instance.get("activation_policy")
            or instance.get("activationPolicy")
            or "UNKNOWN"
        ).upper()

        if activation_policy == "ALWAYS" and instance_state == "READY":
            return self._availability(
                state=AlloyDBAvailabilityState.READY,
                ready=True,
                managed=True,
                retryable=False,
                reason="AlloyDB está disponible",
                instance_state=instance_state,
                activation_policy=activation_policy,
            )

        if instance_state in {"STARTING", "CREATING", "UPDATING"}:
            return self._availability(
                state=AlloyDBAvailabilityState.STARTING,
                ready=False,
                managed=True,
                retryable=True,
                retry_after_seconds=self.settings.retry_after_seconds,
                reason="AlloyDB está iniciando o cambiando de estado",
                instance_state=instance_state,
                activation_policy=activation_policy,
            )

        if activation_policy == "NEVER" or instance_state == "STOPPED":
            return self._availability(
                state=AlloyDBAvailabilityState.STOPPED,
                ready=False,
                managed=True,
                retryable=True,
                retry_after_seconds=self.settings.retry_after_seconds,
                reason="AlloyDB está detenido y puede iniciarse por tráfico de negocio",
                instance_state=instance_state,
                activation_policy=activation_policy,
            )

        if activation_policy == "ALWAYS":
            return self._availability(
                state=AlloyDBAvailabilityState.STARTING,
                ready=False,
                managed=True,
                retryable=True,
                retry_after_seconds=self.settings.retry_after_seconds,
                reason="AlloyDB fue solicitado y todavía no está READY",
                instance_state=instance_state,
                activation_policy=activation_policy,
            )

        return self._availability(
            state=AlloyDBAvailabilityState.UNAVAILABLE,
            ready=False,
            managed=True,
            retryable=True,
            retry_after_seconds=self.settings.retry_after_seconds,
            reason="El estado de AlloyDB no puede resolverse de forma segura",
            instance_state=instance_state,
            activation_policy=activation_policy,
        )

    def ensure_ready(
        self,
        context: BusinessAvailabilityContext,
    ) -> AlloyDBAvailability:
        current = self.observe()
        if current.ready or current.state == AlloyDBAvailabilityState.STARTING:
            return current
        if current.state != AlloyDBAvailabilityState.STOPPED or self.client is None:
            return current

        try:
            payload = self.client.start_business_traffic(
                correlation_id=context.correlation_id,
                requested_by=context.requested_by,
                idempotency_key=context.idempotency_key,
            )
        except Exception:
            return self._availability(
                state=AlloyDBAvailabilityState.UNAVAILABLE,
                ready=False,
                managed=True,
                retryable=True,
                retry_after_seconds=self.settings.retry_after_seconds,
                reason="No fue posible solicitar el encendido de AlloyDB",
                instance_state=current.instance_state,
                activation_policy=current.activation_policy,
            )

        decision = str(payload.get("decision") or "").upper()
        instance = payload.get("instance") or {}
        instance_state = str(instance.get("state") or current.instance_state or "UNKNOWN").upper()
        activation_policy = str(
            instance.get("activation_policy")
            or instance.get("activationPolicy")
            or current.activation_policy
            or "UNKNOWN"
        ).upper()
        request_id = payload.get("request_id")

        if decision == "ALREADY_RUNNING" and instance_state == "READY":
            return self._availability(
                state=AlloyDBAvailabilityState.READY,
                ready=True,
                managed=True,
                retryable=False,
                reason="AlloyDB ya estaba disponible",
                instance_state=instance_state,
                activation_policy=activation_policy,
                request_id=request_id,
            )
        if decision in {"START_REQUESTED", "STARTING", "ALREADY_RUNNING"}:
            return self._availability(
                state=AlloyDBAvailabilityState.STARTING,
                ready=False,
                managed=True,
                retryable=True,
                retry_after_seconds=self.settings.retry_after_seconds,
                reason="El encendido de AlloyDB fue solicitado por tráfico de negocio",
                instance_state=instance_state,
                activation_policy=activation_policy,
                request_id=request_id,
            )

        return self._availability(
            state=AlloyDBAvailabilityState.UNAVAILABLE,
            ready=False,
            managed=True,
            retryable=False,
            reason=f"El controlador rechazó el encendido: {decision or 'UNKNOWN'}",
            instance_state=instance_state,
            activation_policy=activation_policy,
            request_id=request_id,
        )

    def record_business_activity(
        self,
        context: BusinessAvailabilityContext,
        *,
        domain: str,
        workflow_id: str | None = None,
        execution_id: str | None = None,
    ) -> bool:
        """Record successful business use without failing the completed operation.

        Availability and start decisions remain fail-closed. The post-success activity
        signal is best-effort because the business operation may already be committed.
        """

        if not self.settings.enabled or self.client is None:
            return False
        try:
            payload = self.client.record_activity(
                domain=domain,
                operation=context.operation,
                correlation_id=context.correlation_id,
                actor=context.requested_by,
                workflow_id=workflow_id,
                execution_id=execution_id,
            )
        except Exception as exc:
            LOGGER.warning(
                "Could not record AlloyDB business activity",
                extra={
                    "operation": context.operation,
                    "correlation_id": context.correlation_id,
                    "error": str(exc),
                },
            )
            return False
        return payload.get("accepted") is True

    def _availability(
        self,
        *,
        state: AlloyDBAvailabilityState,
        ready: bool,
        managed: bool,
        retryable: bool,
        reason: str,
        retry_after_seconds: int | None = None,
        instance_state: str | None = None,
        activation_policy: str | None = None,
        request_id: str | None = None,
    ) -> AlloyDBAvailability:
        return AlloyDBAvailability(
            state=state,
            ready=ready,
            managed=managed,
            retryable=retryable,
            reason=reason,
            retry_after_seconds=retry_after_seconds,
            instance_state=instance_state,
            activation_policy=activation_policy,
            request_id=request_id,
            observed_at=self.clock(),
        )
