from __future__ import annotations

from tag_fastmcp.models.contracts import (
    BaseAdminToolRequest,
    BaseToolRequest,
    PolicyEnvelope,
    RequestContext,
)

if False:  # pragma: no cover
    from tag_fastmcp.core.container import AppContainer


async def apply_tool_enforcement(
    container: AppContainer,
    request: BaseToolRequest,
    *,
    session_id: str | None,
    allow_platform_tools: bool = False,
) -> tuple[RequestContext, PolicyEnvelope]:
    request_context = await container.request_contexts.build_from_tool_request(
        request,
        session_id=session_id,
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=allow_platform_tools,
    )

    if session_id is not None:
        await container.session_store.ensure(session_id, actor_id=request_context.actor_id)
        if policy_envelope.primary_app_id is not None:
            await container.session_store.bind_scope(
                session_id,
                app_id=policy_envelope.primary_app_id,
                tenant_id=request_context.tenant_id,
                execution_mode=request_context.execution_mode,
            )

    return request_context, policy_envelope


async def apply_admin_enforcement(
    container: AppContainer,
    request: BaseAdminToolRequest,
    *,
    origin: str = "mcp_tool",
) -> tuple[RequestContext, PolicyEnvelope]:
    request_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin=origin,
        requested_app_id=request.app_id,
        session_id=request.session_id,
        actor_id=request.actor_id,
        auth_subject=request.auth_subject,
        tenant_id=request.tenant_id,
        role=request.role,
        auth_scopes=request.auth_scopes,
        trace_id=request.trace_id,
        metadata=request.metadata,
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=True,
    )

    if request.session_id is not None:
        await container.session_store.ensure(request.session_id, actor_id=request_context.actor_id)
        if policy_envelope.primary_app_id is not None:
            await container.session_store.bind_scope(
                request.session_id,
                app_id=policy_envelope.primary_app_id,
                tenant_id=request_context.tenant_id,
                execution_mode=request_context.execution_mode,
            )

    return request_context, policy_envelope
