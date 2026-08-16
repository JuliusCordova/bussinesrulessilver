from __future__ import annotations

import json
import uuid
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .models import AgentRunRequest, AgentRunResponse


class SilverAgentRunner:
    APP_NAME = "silver_refinement_design"

    def __init__(self, session_service: InMemorySessionService | None = None) -> None:
        self.session_service = session_service or InMemorySessionService()

    async def run(
        self,
        agent: BaseAgent,
        request: AgentRunRequest,
        user_id: str = "business-rules-silver",
    ) -> AgentRunResponse:
        session_id = f"silver-{uuid.uuid4().hex}"
        payload = self._payload(request)
        await self.session_service.create_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state=self._initial_state(payload),
        )
        runner = Runner(
            agent=agent,
            app_name=self.APP_NAME,
            session_service=self.session_service,
        )
        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=json.dumps(payload, ensure_ascii=False)
                )
            ],
        )

        final_text = ""
        event_count = 0
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
        ):
            event_count += 1
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(
                    part.text or ""
                    for part in event.content.parts
                    if getattr(part, "text", None) is not None
                )

        if not final_text:
            raise RuntimeError("El agente ADK no produjo una respuesta final")

        return AgentRunResponse(
            agent_name=agent.name,
            session_id=session_id,
            status="COMPLETED",
            output=final_text,
            events=event_count,
        )

    @staticmethod
    def _payload(request: AgentRunRequest) -> dict[str, Any]:
        target_project = request.target_project_id or request.project_id
        source = ".".join([
            request.project_id,
            request.source_dataset,
            request.source_table,
        ])
        target = ".".join([
            target_project,
            request.target_dataset,
            request.target_table,
        ])
        load_strategy = dict(request.load_strategy)
        if not load_strategy:
            load_strategy = {
                "type": "MERGE" if request.business_keys else "FULL",
                "business_keys": request.business_keys,
                "watermark_column": request.watermark_column,
            }
        else:
            load_strategy.setdefault("business_keys", request.business_keys)
            load_strategy.setdefault("watermark_column", request.watermark_column)

        notebook_spec = {
            "source_project": request.project_id,
            "source_dataset": request.source_dataset,
            "source_table": request.source_table,
            "target_project": target_project,
            "target_dataset": request.target_dataset,
            "target_table": request.target_table,
            "columns": request.columns,
            "load_strategy": load_strategy,
            "physical_design": request.physical_design,
            "quality_rules": request.approved_quality_rules,
        }
        return {
            "task": "Diseñar pipeline gobernado Bronze-to-Silver",
            "project_id": request.project_id,
            "source_dataset": request.source_dataset,
            "source_table": request.source_table,
            "source": source,
            "target_project": target_project,
            "target_dataset": request.target_dataset,
            "target_table": request.target_table,
            "target": target,
            "columns": request.columns,
            "load_strategy": load_strategy,
            "business_keys": request.business_keys,
            "watermark_column": request.watermark_column,
            "business_rules": request.business_rules,
            "approved_quality_rules": request.approved_quality_rules,
            "notebook_spec": notebook_spec,
            "context": request.context,
            "constraints": {
                "human_approval_required": True,
                "no_rag": True,
                "post_execution_bigquery_validation": True,
            },
        }

    @staticmethod
    def _initial_state(payload: dict[str, Any]) -> dict[str, str]:
        return {
            "request_json": json.dumps(payload, ensure_ascii=False),
            "business_keys_json": json.dumps(
                payload["business_keys"], ensure_ascii=False
            ),
            "business_rules_json": json.dumps(
                payload["business_rules"], ensure_ascii=False
            ),
            "notebook_spec_json": json.dumps(
                payload["notebook_spec"], ensure_ascii=False
            ),
        }
