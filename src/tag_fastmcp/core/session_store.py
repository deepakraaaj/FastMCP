from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import valkey.asyncio as valkey


@dataclass
class WorkflowState:
    workflow_id: str
    collected_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "collected_data": dict(self.collected_data),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WorkflowState:
        return cls(
            workflow_id=payload["workflow_id"],
            collected_data=dict(payload.get("collected_data") or {}),
        )


@dataclass
class SessionSnapshot:
    session_id: str
    actor_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    last_query: str | None = None
    active_workflow: WorkflowState | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "actor_id": self.actor_id,
            "history": list(self.history),
            "last_query": self.last_query,
            "active_workflow": self.active_workflow.to_dict() if self.active_workflow else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SessionSnapshot:
        workflow_payload = payload.get("active_workflow")
        return cls(
            session_id=payload["session_id"],
            actor_id=payload.get("actor_id"),
            history=list(payload.get("history") or []),
            last_query=payload.get("last_query"),
            active_workflow=WorkflowState.from_dict(workflow_payload) if workflow_payload else None,
        )


class SessionStore(Protocol):
    async def start_session(self, actor_id: str | None = None) -> SessionSnapshot: ...

    async def get(self, session_id: str) -> SessionSnapshot: ...

    async def ensure(self, session_id: str, actor_id: str | None = None) -> SessionSnapshot: ...

    async def append_event(self, session_id: str, event: dict[str, Any]) -> None: ...

    async def set_last_query(self, session_id: str, sql: str) -> None: ...

    async def set_workflow(self, session_id: str, workflow: WorkflowState | None) -> None: ...

    async def close(self) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionSnapshot] = {}

    async def start_session(self, actor_id: str | None = None) -> SessionSnapshot:
        session = SessionSnapshot(session_id=str(uuid.uuid4()), actor_id=actor_id)
        self._sessions[session.session_id] = session
        return session

    async def get(self, session_id: str) -> SessionSnapshot:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session '{session_id}'.") from exc

    async def ensure(self, session_id: str, actor_id: str | None = None) -> SessionSnapshot:
        if session_id in self._sessions:
            snapshot = self._sessions[session_id]
            if actor_id and not snapshot.actor_id:
                snapshot.actor_id = actor_id
            return snapshot
        snapshot = SessionSnapshot(session_id=session_id, actor_id=actor_id)
        self._sessions[session_id] = snapshot
        return snapshot

    async def append_event(self, session_id: str, event: dict[str, Any]) -> None:
        snapshot = await self.get(session_id)
        snapshot.history.append(event)

    async def set_last_query(self, session_id: str, sql: str) -> None:
        snapshot = await self.get(session_id)
        snapshot.last_query = sql

    async def set_workflow(self, session_id: str, workflow: WorkflowState | None) -> None:
        snapshot = await self.get(session_id)
        snapshot.active_workflow = workflow

    async def close(self) -> None:
        return None


class ValkeySessionStore:
    def __init__(
        self,
        valkey_url: str | None = None,
        *,
        key_prefix: str = "tag_fastmcp",
        session_ttl_seconds: int = 86_400,
        client: Any | None = None,
    ) -> None:
        if client is None and valkey_url is None:
            raise ValueError("valkey_url is required when no Valkey client is provided.")
        self._client = client or valkey.Valkey.from_url(valkey_url, decode_responses=True)
        self._key_prefix = key_prefix
        self._session_ttl_seconds = session_ttl_seconds

    def _session_key(self, session_id: str) -> str:
        return f"{self._key_prefix}:session:{session_id}"

    def _ttl(self) -> int | None:
        return self._session_ttl_seconds if self._session_ttl_seconds > 0 else None

    async def _persist(self, snapshot: SessionSnapshot) -> None:
        await self._client.set(
            self._session_key(snapshot.session_id),
            json.dumps(snapshot.to_dict(), sort_keys=True, default=str),
            ex=self._ttl(),
        )

    async def _touch(self, session_id: str) -> None:
        ttl = self._ttl()
        if ttl is not None:
            await self._client.expire(self._session_key(session_id), ttl)

    async def start_session(self, actor_id: str | None = None) -> SessionSnapshot:
        snapshot = SessionSnapshot(session_id=str(uuid.uuid4()), actor_id=actor_id)
        await self._persist(snapshot)
        return snapshot

    async def get(self, session_id: str) -> SessionSnapshot:
        payload = await self._client.get(self._session_key(session_id))
        if payload is None:
            raise KeyError(f"Unknown session '{session_id}'.")
        await self._touch(session_id)
        return SessionSnapshot.from_dict(json.loads(payload))

    async def ensure(self, session_id: str, actor_id: str | None = None) -> SessionSnapshot:
        try:
            snapshot = await self.get(session_id)
        except KeyError:
            snapshot = SessionSnapshot(session_id=session_id, actor_id=actor_id)
            await self._persist(snapshot)
            return snapshot

        if actor_id and not snapshot.actor_id:
            snapshot.actor_id = actor_id
            await self._persist(snapshot)
        return snapshot

    async def append_event(self, session_id: str, event: dict[str, Any]) -> None:
        snapshot = await self.get(session_id)
        snapshot.history.append(event)
        await self._persist(snapshot)

    async def set_last_query(self, session_id: str, sql: str) -> None:
        snapshot = await self.get(session_id)
        snapshot.last_query = sql
        await self._persist(snapshot)

    async def set_workflow(self, session_id: str, workflow: WorkflowState | None) -> None:
        snapshot = await self.get(session_id)
        snapshot.active_workflow = workflow
        await self._persist(snapshot)

    async def close(self) -> None:
        await self._client.aclose()
