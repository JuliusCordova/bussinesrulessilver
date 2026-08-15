from __future__ import annotations

import re
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from .memory_models import (
    MemoryEventCreate,
    MemoryRecord,
    MemorySearchHit,
    MemorySearchRequest,
    MemorySession,
    MemorySessionCreate,
)


@runtime_checkable
class MemoryRepository(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def vector_index_ready(self) -> bool: ...

    def health(self) -> dict[str, Any]: ...

    def create_session(self, request: MemorySessionCreate) -> MemorySession: ...

    def get_session(self, session_id: str) -> MemorySession | None: ...

    def add_event(self, request: MemoryEventCreate) -> MemoryRecord: ...

    def list_session_memories(self, session_id: str) -> list[MemoryRecord]: ...

    def search(self, request: MemorySearchRequest) -> list[MemorySearchHit]: ...


class SharedMemoryRepository:
    """Thread-safe in-process repository implementing the memory contract."""

    _sessions: dict[str, MemorySession] = {}
    _records: dict[str, MemoryRecord] = {}
    _lock = Lock()

    @property
    def provider(self) -> str:
        return "IN_MEMORY"

    @property
    def vector_index_ready(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "provider": self.provider,
            "vector_index_ready": self.vector_index_ready,
            "session_count": len(self._sessions),
            "memory_count": len(self._records),
        }

    def create_session(self, request: MemorySessionCreate) -> MemorySession:
        now = datetime.now(timezone.utc)
        session_id = request.session_id or f"session_{uuid4().hex}"

        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                return existing

            session = MemorySession(
                session_id=session_id,
                execution_id=request.execution_id,
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                pipeline_id=request.pipeline_id,
                user_id=request.user_id,
                metadata=request.metadata,
                created_at=now,
                updated_at=now,
            )
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> MemorySession | None:
        return self._sessions.get(session_id)

    def add_event(self, request: MemoryEventCreate) -> MemoryRecord:
        session = self._sessions.get(request.session_id)
        if session is None:
            raise KeyError(f"Sesión no encontrada: {request.session_id}")

        record = MemoryRecord(
            memory_id=f"memory_{uuid4().hex}",
            session_id=request.session_id,
            execution_id=request.execution_id or session.execution_id,
            tenant_id=request.tenant_id or session.tenant_id,
            project_id=request.project_id or session.project_id,
            pipeline_id=request.pipeline_id or session.pipeline_id,
            agent_id=request.agent_id,
            memory_type=request.memory_type.upper(),
            content=request.content,
            importance_score=request.importance_score,
            confidence_score=request.confidence_score,
            is_shared=request.is_shared,
            metadata=request.metadata,
            created_at=datetime.now(timezone.utc),
            expires_at=request.expires_at,
        )
        with self._lock:
            self._records[record.memory_id] = record
            current = self._sessions[request.session_id]
            self._sessions[request.session_id] = current.model_copy(
                update={"updated_at": datetime.now(timezone.utc)}
            )
        return record

    def list_session_memories(self, session_id: str) -> list[MemoryRecord]:
        return sorted(
            [item for item in self._records.values() if item.session_id == session_id],
            key=lambda item: item.created_at,
        )

    def search(self, request: MemorySearchRequest) -> list[MemorySearchHit]:
        query_tokens = self._tokens(request.query)
        now = datetime.now(timezone.utc)
        candidates = [
            item
            for item in self._records.values()
            if item.expires_at is None or item.expires_at > now
        ]

        if request.session_id:
            candidates = [item for item in candidates if item.session_id == request.session_id]
        if request.execution_id:
            candidates = [item for item in candidates if item.execution_id == request.execution_id]
        if request.tenant_id:
            candidates = [item for item in candidates if item.tenant_id == request.tenant_id]
        if request.project_id:
            candidates = [item for item in candidates if item.project_id == request.project_id]
        if request.pipeline_id:
            candidates = [item for item in candidates if item.pipeline_id == request.pipeline_id]
        if request.agent_id:
            candidates = [item for item in candidates if item.agent_id == request.agent_id]
        if request.shared_only is not None:
            candidates = [item for item in candidates if item.is_shared is request.shared_only]
        if request.memory_types:
            allowed = {item.upper() for item in request.memory_types}
            candidates = [item for item in candidates if item.memory_type in allowed]

        hits: list[MemorySearchHit] = []
        for memory in candidates:
            content_tokens = self._tokens(memory.content)
            overlap = len(query_tokens & content_tokens)
            lexical = overlap / max(len(query_tokens), 1)
            score = min(
                (lexical * 0.65)
                + (memory.importance_score * 0.20)
                + (memory.confidence_score * 0.15),
                1.0,
            )
            if overlap or not query_tokens:
                hits.append(
                    MemorySearchHit(
                        memory=memory,
                        score=round(score, 4),
                        match_type="LEXICAL_FALLBACK",
                    )
                )
        return sorted(
            hits,
            key=lambda item: (item.score, item.memory.created_at),
            reverse=True,
        )[: request.limit]

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-záéíóúñ0-9_]+", value.lower())
            if len(token) > 2
        }
