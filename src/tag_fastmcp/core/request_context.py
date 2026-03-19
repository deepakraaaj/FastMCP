from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from tag_fastmcp.core.session_store import SessionSnapshot, SessionStore
from tag_fastmcp.models.contracts import BaseToolRequest, RequestContext
from tag_fastmcp.settings import AppSettings


@dataclass
class RequestContextService:
    settings: AppSettings
    session_store: SessionStore

    async def build(
        self,
        *,
        execution_mode: str,
        origin: str,
        requested_app_id: str | None,
        session_id: str | None = None,
        actor_id: str | None = None,
        auth_subject: str | None = None,
        tenant_id: str | None = None,
        role: str | None = None,
        channel_id: str | None = None,
        auth_scopes: Iterable[str] | str | None = None,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RequestContext:
        snapshot = await self._snapshot(session_id)
        payload = dict(metadata or {})
        payload.setdefault("settings_default_chat_app_id", self.settings.default_chat_app_id)

        return RequestContext(
            request_id=uuid.uuid4().hex,
            trace_id=trace_id,
            session_id=session_id,
            actor_id=actor_id or self._text(payload.get("actor_id")) or (snapshot.actor_id if snapshot else None),
            auth_subject=auth_subject or self._text(payload.get("auth_subject")),
            tenant_id=tenant_id or self._text(payload.get("tenant_id")) or (snapshot.tenant_id if snapshot else None),
            role=self._role(role or self._text(payload.get("role")), execution_mode),
            origin=origin,  # type: ignore[arg-type]
            execution_mode=execution_mode,  # type: ignore[arg-type]
            requested_app_id=self._text(requested_app_id),
            session_bound_app_id=snapshot.bound_app_id if snapshot else None,
            channel_id=channel_id,
            auth_scopes=self._scopes(auth_scopes or payload.get("auth_scopes")),
            metadata=payload,
        )

    async def build_from_tool_request(
        self,
        request: BaseToolRequest,
        *,
        session_id: str | None,
        origin: str = "mcp_tool",
    ) -> RequestContext:
        channel_id = self._text(getattr(request, "channel_id", None))
        return await self.build(
            execution_mode="direct_tool",
            origin=origin,
            requested_app_id=request.app_id,
            session_id=session_id,
            actor_id=request.actor_id,
            auth_subject=request.auth_subject,
            tenant_id=request.tenant_id,
            role=request.role,
            channel_id=channel_id,
            auth_scopes=request.auth_scopes,
            trace_id=request.trace_id,
            metadata=request.metadata,
        )

    async def _snapshot(self, session_id: str | None) -> SessionSnapshot | None:
        if not session_id:
            return None
        try:
            return await self.session_store.get(session_id)
        except KeyError:
            return None

    @staticmethod
    def _role(value: str | None, execution_mode: str) -> str:
        if value in {"end_user", "app_admin", "platform_admin", "service"}:
            return value
        return "end_user" if execution_mode == "app_chat" else "service"

    @staticmethod
    def _scopes(raw_value: Iterable[str] | str | None) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            normalized = raw_value.strip()
            return [normalized] if normalized else []
        return [scope.strip() for scope in raw_value if isinstance(scope, str) and scope.strip()]

    @staticmethod
    def _text(value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None
