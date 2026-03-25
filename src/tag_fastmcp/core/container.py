from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING

from tag_fastmcp.core.app_router import AppRouter
from tag_fastmcp.core.agent_registry import AgentRegistry
from tag_fastmcp.core.chat_service import ChatService
from tag_fastmcp.core.circuit_breaker import CircuitBreakerService
from tag_fastmcp.core.capability_registry import CapabilityRegistry
from tag_fastmcp.core.capability_router import CapabilityRouter
from tag_fastmcp.core.formatter_service import FormatterService
from tag_fastmcp.core.idempotency import (
    IdempotencyService,
    InMemoryIdempotencyStore,
    ValkeyIdempotencyStore,
)
from tag_fastmcp.core.intent_planner import IntentPlanner
from tag_fastmcp.core.orchestration_service import OrchestrationService
from tag_fastmcp.core.plan_compiler import PlanCompiler
from tag_fastmcp.core.policy_envelope import PolicyEnvelopeService
from tag_fastmcp.core.request_context import RequestContextService
from tag_fastmcp.core.response_builder import ResponseBuilder
from tag_fastmcp.core.session_store import (
    InMemorySessionStore,
    SessionStore,
    ValkeySessionStore,
)
from tag_fastmcp.core.visibility_policy import VisibilityPolicyService
from tag_fastmcp.settings import AppSettings, get_settings

if TYPE_CHECKING:
    from tag_fastmcp.core.admin_chat_service import AdminChatService
    from tag_fastmcp.core.admin_service import AdminService
    from tag_fastmcp.core.agent_lifecycle_service import AgentLifecycleService
    from tag_fastmcp.core.approval_service import ApprovalService
    from tag_fastmcp.core.control_plane_store import SqlControlPlaneStore


@dataclass
class AppContainer:
    settings: AppSettings
    session_store: SessionStore
    idempotency: IdempotencyService
    app_router: AppRouter
    agent_registry: AgentRegistry
    capability_registry: CapabilityRegistry
    request_contexts: RequestContextService
    policy_envelopes: PolicyEnvelopeService
    circuit_breakers: CircuitBreakerService
    capability_router: CapabilityRouter
    intent_planner: IntentPlanner
    plan_compiler: PlanCompiler
    orchestration: OrchestrationService
    visibility_policy: VisibilityPolicyService
    formatter_service: FormatterService
    control_plane_store: SqlControlPlaneStore | None
    approvals: ApprovalService | None
    agent_lifecycle: AgentLifecycleService | None
    admin_service: AdminService | None
    admin_chat_service: AdminChatService | None
    chat_service: ChatService
    responses: ResponseBuilder
    mcp_target_overrides: dict[str, object] = field(default_factory=dict)

    async def close(self) -> None:
        await self.session_store.close()
        await self.idempotency.close()
        if self.control_plane_store is not None:
            await self.control_plane_store.close()

    @property
    def builder_runtime(self):  # type: ignore[no-untyped-def]
        if not self.settings.enable_platform_features:
            raise RuntimeError("Builder runtime is unavailable in the simple runtime profile.")
        if len(self.app_router.registry.apps) != 1:
            raise ValueError("builder_runtime is ambiguous when multiple apps are configured. Resolve an app context first.")
        app_id = next(iter(self.app_router.registry.apps))
        builder_runtime = self.app_router.resolve(app_id).builder_runtime
        if builder_runtime is None:
            raise RuntimeError("Builder runtime is unavailable for the resolved application context.")
        return builder_runtime


def _build_session_store(settings: AppSettings) -> SessionStore:
    if settings.session_store_backend in {"valkey", "redis"}:
        return ValkeySessionStore(
            valkey_url=settings.valkey_url,
            key_prefix=settings.valkey_key_prefix,
            session_ttl_seconds=settings.session_ttl_seconds,
        )
    return InMemorySessionStore()


def _build_idempotency(settings: AppSettings) -> IdempotencyService:
    if settings.idempotency_store_backend in {"valkey", "redis"}:
        store = ValkeyIdempotencyStore(
            valkey_url=settings.valkey_url,
            key_prefix=settings.valkey_key_prefix,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        )
    else:
        store = InMemoryIdempotencyStore()
    return IdempotencyService(store)


def build_container(settings: AppSettings | None = None) -> AppContainer:
    resolved_settings = settings or get_settings()
    session_store = _build_session_store(resolved_settings)
    idempotency = _build_idempotency(resolved_settings)
    control_plane_store = None
    if resolved_settings.enable_platform_features:
        from tag_fastmcp.core.control_plane_store import SqlControlPlaneStore

        control_plane_store = SqlControlPlaneStore(
            resolved_settings.control_plane_database_url or resolved_settings.database_url,
        )
    app_router = AppRouter(settings=resolved_settings, session_store=session_store)
    agent_registry = AgentRegistry(
        settings=resolved_settings,
        control_plane_store=control_plane_store,
    )
    capability_registry = CapabilityRegistry(
        settings=resolved_settings,
        apps_registry=app_router.registry,
        agent_registry=agent_registry,
    )
    request_contexts = RequestContextService(settings=resolved_settings, session_store=session_store)
    policy_envelopes = PolicyEnvelopeService(
        settings=resolved_settings,
        app_router=app_router,
        capability_registry=capability_registry,
    )
    circuit_breakers = CircuitBreakerService()
    mcp_target_overrides: dict[str, object] = {}
    capability_router = CapabilityRouter(
        app_router=app_router,
        capability_registry=capability_registry,
        apps_registry=app_router.registry,
        session_store=session_store,
        circuit_breakers=circuit_breakers,
        target_resolver=lambda server_id, endpoint: mcp_target_overrides.get(server_id, endpoint),
    )
    intent_planner = IntentPlanner(
        app_router=app_router,
        capability_registry=capability_registry,
    )
    plan_compiler = PlanCompiler(capability_registry=capability_registry)
    orchestration = OrchestrationService(
        intent_planner=intent_planner,
        plan_compiler=plan_compiler,
        capability_router=capability_router,
    )
    visibility_policy = VisibilityPolicyService()
    formatter_service = FormatterService(
        capability_registry=capability_registry,
        visibility_policy=visibility_policy,
    )
    responses = ResponseBuilder()
    approvals = None
    agent_lifecycle = None
    admin_service = None
    admin_chat_service = None
    if resolved_settings.enable_platform_features:
        from tag_fastmcp.core.admin_chat_service import AdminChatService
        from tag_fastmcp.core.admin_service import AdminService
        from tag_fastmcp.core.agent_lifecycle_service import AgentLifecycleService
        from tag_fastmcp.core.approval_service import ApprovalService

        if control_plane_store is None:
            raise RuntimeError("Platform runtime requires a control-plane store.")
        approvals = ApprovalService(store=control_plane_store)
        agent_lifecycle = AgentLifecycleService(
            store=control_plane_store,
            agent_registry=agent_registry,
        )
        admin_service = AdminService(
            request_contexts=request_contexts,
            policy_envelopes=policy_envelopes,
            session_store=session_store,
            approvals=approvals,
            agent_lifecycle=agent_lifecycle,
            capability_router=capability_router,
            formatter_service=formatter_service,
            control_plane_store=control_plane_store,
            responses=responses,
        )
        admin_chat_service = AdminChatService(
            settings=resolved_settings,
            app_router=app_router,
            session_store=session_store,
            agent_registry=agent_registry,
            orchestration=orchestration,
            formatter_service=formatter_service,
            request_contexts=request_contexts,
            policy_envelopes=policy_envelopes,
            approvals=approvals,
            agent_lifecycle=agent_lifecycle,
        )
    chat_service = ChatService(
        settings=resolved_settings,
        app_router=app_router,
        session_store=session_store,
        agent_registry=agent_registry,
        orchestration=orchestration,
        formatter_service=formatter_service,
        request_contexts=request_contexts,
        policy_envelopes=policy_envelopes,
        approvals=approvals,
        agent_lifecycle=agent_lifecycle,
    )

    return AppContainer(
        settings=resolved_settings,
        session_store=session_store,
        idempotency=idempotency,
        app_router=app_router,
        agent_registry=agent_registry,
        capability_registry=capability_registry,
        request_contexts=request_contexts,
        policy_envelopes=policy_envelopes,
        circuit_breakers=circuit_breakers,
        capability_router=capability_router,
        intent_planner=intent_planner,
        plan_compiler=plan_compiler,
        orchestration=orchestration,
        visibility_policy=visibility_policy,
        formatter_service=formatter_service,
        control_plane_store=control_plane_store,
        approvals=approvals,
        agent_lifecycle=agent_lifecycle,
        admin_service=admin_service,
        admin_chat_service=admin_chat_service,
        chat_service=chat_service,
        mcp_target_overrides=mcp_target_overrides,
        responses=responses,
    )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return build_container()
