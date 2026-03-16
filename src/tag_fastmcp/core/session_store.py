from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowState:
    workflow_id: str
    collected_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionSnapshot:
    session_id: str
    actor_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    last_query: str | None = None
    active_workflow: WorkflowState | None = None


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionSnapshot] = {}

    def start_session(self, actor_id: str | None = None) -> SessionSnapshot:
        session = SessionSnapshot(session_id=str(uuid.uuid4()), actor_id=actor_id)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> SessionSnapshot:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session '{session_id}'.") from exc

    def ensure(self, session_id: str, actor_id: str | None = None) -> SessionSnapshot:
        if session_id in self._sessions:
            snapshot = self._sessions[session_id]
            if actor_id and not snapshot.actor_id:
                snapshot.actor_id = actor_id
            return snapshot
        snapshot = SessionSnapshot(session_id=session_id, actor_id=actor_id)
        self._sessions[session_id] = snapshot
        return snapshot

    def append_event(self, session_id: str, event: dict[str, Any]) -> None:
        self.get(session_id).history.append(event)

    def set_last_query(self, session_id: str, sql: str) -> None:
        self.get(session_id).last_query = sql

    def set_workflow(self, session_id: str, workflow: WorkflowState | None) -> None:
        self.get(session_id).active_workflow = workflow
