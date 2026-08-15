from __future__ import annotations

import re
from collections.abc import Iterable

from .memory_models import MemorySearchHit
from .models import AgentMemoryContext, InjectedMemory


class ControlledMemoryContextBuilder:
    """Builds an auditable, bounded memory context for one specialized agent."""

    SUPERVISOR_AGENT_ID = "agent-supervisor"
    GLOBAL_MEMORY_TYPES = {"SEMANTIC"}

    def build(
        self,
        *,
        agent_id: str,
        hits: Iterable[MemorySearchHit],
        mode: str = "STRICT",
        min_score: float = 0.25,
        max_items: int = 3,
        max_chars: int = 1800,
        enabled: bool = True,
    ) -> AgentMemoryContext:
        normalized_mode = mode.upper()
        if normalized_mode not in {"STRICT", "COLLABORATIVE"}:
            raise ValueError(f"Unsupported memory context mode: {mode}")

        candidates = list(hits)
        context = AgentMemoryContext(
            agent_id=agent_id,
            mode=normalized_mode,
            candidate_count=len(candidates),
            max_items=max_items,
            max_chars=max_chars,
        )
        if not enabled:
            context.rejected_count = len(candidates)
            return context

        seen_content: set[str] = set()
        rejected = 0
        truncated = False

        for hit in candidates:
            if hit.score < min_score:
                rejected += 1
                continue

            reason = self._injection_reason(
                agent_id=agent_id,
                hit=hit,
                mode=normalized_mode,
            )
            if reason is None:
                rejected += 1
                continue

            fingerprint = self._fingerprint(hit.memory.content)
            if fingerprint in seen_content:
                rejected += 1
                continue

            if len(context.memories) >= max_items:
                truncated = True
                rejected += 1
                continue

            remaining_chars = max_chars - context.total_chars
            if remaining_chars <= 0:
                truncated = True
                rejected += 1
                continue

            excerpt = hit.memory.content.strip()
            if len(excerpt) > remaining_chars:
                if remaining_chars < 24:
                    truncated = True
                    rejected += 1
                    continue
                excerpt = excerpt[: remaining_chars - 1].rstrip() + "…"
                truncated = True

            context.memories.append(
                InjectedMemory(
                    memory_id=hit.memory.memory_id,
                    memory_type=hit.memory.memory_type,
                    source_agent_id=hit.memory.agent_id,
                    score=hit.score,
                    match_type=hit.match_type,
                    excerpt=excerpt,
                    injection_reason=reason,
                )
            )
            context.total_chars += len(excerpt)
            seen_content.add(fingerprint)

        context.injected_count = len(context.memories)
        context.rejected_count = rejected
        context.truncated = truncated
        return context

    def build_for_agents(
        self,
        *,
        agent_ids: Iterable[str],
        hits: Iterable[MemorySearchHit],
        mode: str = "STRICT",
        min_score: float = 0.25,
        max_items: int = 3,
        max_chars: int = 1800,
        enabled: bool = True,
    ) -> dict[str, AgentMemoryContext]:
        cached_hits = list(hits)
        return {
            agent_id: self.build(
                agent_id=agent_id,
                hits=cached_hits,
                mode=mode,
                min_score=min_score,
                max_items=max_items,
                max_chars=max_chars,
                enabled=enabled,
            )
            for agent_id in agent_ids
        }

    def _injection_reason(
        self,
        *,
        agent_id: str,
        hit: MemorySearchHit,
        mode: str,
    ) -> str | None:
        memory = hit.memory
        if not memory.is_shared:
            return None

        source_agent = memory.agent_id
        memory_type = memory.memory_type.upper()
        target_agents = self._target_agents(memory.metadata)

        if agent_id in target_agents:
            return "EXPLICIT_TARGET"
        if source_agent == agent_id:
            return "SAME_AGENT"
        if source_agent in {None, self.SUPERVISOR_AGENT_ID}:
            return "SUPERVISOR_OR_GLOBAL"
        if memory_type in self.GLOBAL_MEMORY_TYPES:
            return "SHARED_SEMANTIC"
        if mode == "COLLABORATIVE":
            return "COLLABORATIVE_SHARED"
        return None

    @staticmethod
    def _target_agents(metadata: dict) -> set[str]:
        raw = metadata.get("target_agents", [])
        if isinstance(raw, str):
            return {raw}
        if isinstance(raw, list):
            return {str(item) for item in raw if item}
        return set()

    @staticmethod
    def _fingerprint(content: str) -> str:
        return re.sub(r"\s+", " ", content.strip().lower())
