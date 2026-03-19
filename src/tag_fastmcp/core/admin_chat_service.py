from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tag_fastmcp.agent.admin_orchestration_agent import AdminOrchestrationAgent
from tag_fastmcp.agent.clarification_agent import ClarificationAgent
from tag_fastmcp.models.http_api import AdminChatResult, AdminUserContext

if False:  # pragma: no cover
    from tag_fastmcp.core.agent_lifecycle_service import AgentLifecycleService
    from tag_fastmcp.core.agent_registry import AgentRegistry
    from tag_fastmcp.core.approval_service import ApprovalService
    from tag_fastmcp.core.app_router import AppRouter
    from tag_fastmcp.core.formatter_service import FormatterService
    from tag_fastmcp.core.orchestration_service import OrchestrationService
    from tag_fastmcp.core.policy_envelope import PolicyEnvelopeService
    from tag_fastmcp.core.request_context import RequestContextService
    from tag_fastmcp.core.session_store import SessionStore, SessionSnapshot
    from tag_fastmcp.settings import AppSettings


@dataclass
class AdminChatService:
    settings: AppSettings
    app_router: AppRouter
    session_store: SessionStore
    agent_registry: AgentRegistry
    orchestration: OrchestrationService
    formatter_service: FormatterService
    request_contexts: RequestContextService
    policy_envelopes: PolicyEnvelopeService
    approvals: ApprovalService
    agent_lifecycle: AgentLifecycleService
    agent_factory: Callable[[str, str], ClarificationAgent] | None = None

    @staticmethod
    def _request_metadata(admin_context: AdminUserContext) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "allowed_app_ids": list(admin_context.allowed_app_ids),
        }
        if admin_context.role in {"platform_admin", "service"}:
            metadata["allow_heavy_agent"] = True
            metadata["allow_agent_proposal"] = True
        return metadata

    @staticmethod
    def _context_message(admin_context: AdminUserContext) -> str:
        payload = {
            "actor_id": admin_context.actor_id,
            "auth_subject": admin_context.auth_subject,
            "tenant_id": admin_context.tenant_id,
            "role": admin_context.role,
            "auth_scopes": list(admin_context.auth_scopes),
            "allowed_app_ids": list(admin_context.allowed_app_ids),
        }
        return f"Current admin context: {json.dumps(payload, sort_keys=True)}"

    def _agent(self) -> ClarificationAgent:
        if self.agent_factory is not None:
            return self.agent_factory(self.settings.llm_base_url, self.settings.llm_model)
        return ClarificationAgent(
            base_url=self.settings.llm_base_url,
            model_name=self.settings.llm_model,
        )

    async def _ensure_session(
        self,
        *,
        session_id: str | None,
        actor_id: str,
        tenant_id: str | None,
    ) -> tuple[str, SessionSnapshot, bool]:
        if session_id is None:
            session = await self.session_store.start_session(actor_id=actor_id)
            await self.session_store.bind_scope(
                session.session_id,
                tenant_id=tenant_id,
                execution_mode="admin_chat",
            )
            return session.session_id, session, True

        snapshot = await self.session_store.ensure(session_id, actor_id=actor_id)
        await self.session_store.bind_scope(
            session_id,
            tenant_id=tenant_id,
            execution_mode="admin_chat",
        )
        return session_id, snapshot, False

    async def chat(
        self,
        *,
        session_id: str | None,
        message: str,
        requested_app_id: str | None,
        channel_id: str | None,
        admin_context: AdminUserContext,
    ) -> AdminChatResult:
        session_id, _snapshot, started_session = await self._ensure_session(
            session_id=session_id,
            actor_id=admin_context.actor_id,
            tenant_id=admin_context.tenant_id,
        )
        request_context = await self.request_contexts.build(
            execution_mode="admin_chat",
            origin="admin_http",
            requested_app_id=requested_app_id,
            session_id=session_id,
            actor_id=admin_context.actor_id,
            auth_subject=admin_context.auth_subject or admin_context.actor_id,
            tenant_id=admin_context.tenant_id,
            role=admin_context.role,
            channel_id=channel_id,
            auth_scopes=admin_context.auth_scopes,
            metadata=self._request_metadata(admin_context),
        )
        policy_envelope = self.policy_envelopes.derive(
            request_context,
            allow_platform_tools=True,
        )
        agent_selection = self.agent_registry.select_agent(request_context, policy_envelope)
        if agent_selection.agent_kind != "admin_orchestration":
            raise ValueError(
                "Admin chat currently requires the admin_orchestration runtime inside admin_chat mode."
            )
        runtime = AdminOrchestrationAgent(
            settings=self.settings,
            app_router=self.app_router,
            session_store=self.session_store,
            orchestration=self.orchestration,
            formatter_service=self.formatter_service,
            approvals=self.approvals,
            agent_lifecycle=self.agent_lifecycle,
            agent_factory=self.agent_factory,
        )
        return await runtime.run(
            session_id=session_id,
            started_session=started_session,
            context_message=self._context_message(admin_context),
            message=message,
            request_context=request_context,
            policy_envelope=policy_envelope,
            agent_selection=agent_selection,
        )
