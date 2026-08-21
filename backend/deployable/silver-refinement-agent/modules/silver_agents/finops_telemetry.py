from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.cloud import bigquery

logger = logging.getLogger(__name__)

_START_KEY_PREFIX = "temp:finops_llm_start_ns:"


def _project_id() -> str | None:
    return os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")


def _table_id() -> str | None:
    explicit = os.getenv("AGENTOPS_LLM_CALLS_TABLE")
    if explicit:
        return explicit
    project = _project_id()
    if not project:
        return None
    return f"{project}.agentops.fact_llm_calls"


def _usage_value(usage: Any, field: str) -> int:
    value = getattr(usage, field, None) if usage is not None else None
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_finops_callbacks(*, canonical_agent_name: str, model_name: str):
    """Return ADK callbacks that persist real LLM usage into AgentOps.

    Telemetry is deliberately best-effort: an observability write failure must not
    fail the governed Bronze-to-Silver execution. No USD cost is calculated here.
    """

    start_key = f"{_START_KEY_PREFIX}{canonical_agent_name}"

    async def before_model_callback(
        callback_context: CallbackContext,
        llm_request: LlmRequest,
    ) -> None:
        del llm_request
        callback_context.state[start_key] = time.perf_counter_ns()
        return None

    async def after_model_callback(
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> None:
        table_id = _table_id()
        if not table_id:
            logger.warning(
                "FinOps telemetry skipped for %s: GCP project/table unavailable",
                canonical_agent_name,
            )
            return None

        started_ns = callback_context.state.get(start_key)
        latency_ms = None
        if isinstance(started_ns, int):
            latency_ms = max(int((time.perf_counter_ns() - started_ns) / 1_000_000), 0)

        usage = getattr(llm_response, "usage_metadata", None)
        prompt_tokens = _usage_value(usage, "prompt_token_count")
        response_tokens = _usage_value(usage, "candidates_token_count")
        total_tokens = _usage_value(usage, "total_token_count")
        if not total_tokens:
            total_tokens = prompt_tokens + response_tokens

        error_code = getattr(llm_response, "error_code", None)
        error_message = getattr(llm_response, "error_message", None)
        status = "FAILED" if error_code or error_message else "SUCCESS"

        state = callback_context.state
        row = {
            "call_ts": datetime.now(timezone.utc).isoformat(),
            "trace_id": state.get("finops_trace_id") or callback_context.invocation_id,
            "session_id": callback_context.session.id,
            "agent_name": canonical_agent_name,
            "intent": f"BUSINESS_RULES_SILVER:{canonical_agent_name}",
            "model_name": model_name,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            "status": status,
            "user_email": state.get("finops_requested_by") or callback_context.user_id,
            "message": str(error_message or error_code or "") or None,
        }

        def _insert() -> list[dict[str, Any]]:
            client = bigquery.Client(project=_project_id())
            return client.insert_rows_json(table_id, [row])

        try:
            errors = await asyncio.to_thread(_insert)
            if errors:
                logger.warning(
                    "FinOps telemetry insert returned errors for %s: %s",
                    canonical_agent_name,
                    errors,
                )
        except Exception as exc:  # Observability must not break business execution.
            logger.warning(
                "FinOps telemetry insert failed for %s: %s",
                canonical_agent_name,
                exc,
            )
        return None

    return before_model_callback, after_model_callback
