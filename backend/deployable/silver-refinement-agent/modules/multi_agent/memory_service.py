from __future__ import annotations

from typing import Any

from .memory_models import (
    MemoryEventCreate,
    MemoryRecord,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySession,
    MemorySessionCreate,
)
from .memory_repository import MemoryRepository
from .memory_repository_factory import get_memory_repository


class SharedMemoryService:
    def __init__(self, repository: MemoryRepository | None = None) -> None:
        self.repository = repository or get_memory_repository()

    @property
    def provider(self) -> str:
        return self.repository.provider

    def health(self) -> dict[str, Any]:
        return self.repository.health()

    def create_session(self, request: MemorySessionCreate) -> MemorySession:
        return self.repository.create_session(request)

    def ensure_session(self, request: MemorySessionCreate) -> MemorySession:
        if request.session_id:
            existing = self.repository.get_session(request.session_id)
            if existing is not None:
                return existing
        return self.repository.create_session(request)

    def get_session(self, session_id: str) -> MemorySession:
        session = self.repository.get_session(session_id)
        if session is None:
            raise KeyError(f"Sesión no encontrada: {session_id}")
        return session

    def add_event(self, request: MemoryEventCreate) -> MemoryRecord:
        return self.repository.add_event(request)

    def list_memories(self, session_id: str) -> list[MemoryRecord]:
        self.get_session(session_id)
        return self.repository.list_session_memories(session_id)

    def search(self, request: MemorySearchRequest) -> MemorySearchResponse:
        return MemorySearchResponse(
            query=request.query,
            hits=self.repository.search(request),
            provider=self.repository.provider,
            vector_index_ready=self.repository.vector_index_ready,
        )
