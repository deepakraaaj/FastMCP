from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import InvokeCapabilityRequest, RoutingPayload


async def _resolved_session_id(request_session_id: str | None, ctx: Context) -> str | None:
    return request_session_id or await ctx.get_state("active_session_id")


def _capability_kind(intent_type: str) -> str:
    if intent_type == "run_report":
        return "report"
    if intent_type == "run_workflow":
        return "workflow"
    return "tool"


def register_routing_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def invoke_capability(request: InvokeCapabilityRequest, ctx: Context) -> dict:
        session_id = await _resolved_session_id(request.session_id, ctx)
        request_context = await container.request_contexts.build_from_tool_request(
            request,
            session_id=session_id,
        )
        policy_envelope = container.policy_envelopes.derive(
            request_context,
            allow_platform_tools=request.allow_platform_tools,
        )
        compiled = container.orchestration.plan_direct_request(
            request=request,
            request_context=request_context,
            policy_envelope=policy_envelope,
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

        if compiled.orchestration_decision.requires_approval:
            pending_execution = await container.approvals.request_execution_approval(
                request_context=request_context,
                policy_envelope=policy_envelope,
                routing_plan=compiled.routing_plan,
                orchestration_decision=compiled.orchestration_decision,
                execution_requests=compiled.execution_requests,
            )
            routing = RoutingPayload(
                request_context_id=request_context.request_id,
                policy_envelope_id=policy_envelope.envelope_id,
                routing_plan_id=compiled.routing_plan.plan_id,
                selected_capability_id=compiled.routing_plan.selected_capability_id or "approval_pending",
                capability_kind=_capability_kind(compiled.routing_plan.intent_type),  # type: ignore[arg-type]
                selection_mode="capability_id" if request.capability_id else "tags",
                selection_reason=compiled.routing_plan.reasoning_summary,
                channel_id=request.channel_id,
                formatter_id=compiled.routing_plan.formatter_id,
                downstream_status="pending",
                output={
                    "message": pending_execution.user_visible_message,
                    "approval": pending_execution.approval_request.model_dump(mode="json"),
                    "approval_payload": pending_execution.approval_payload.model_dump(mode="json"),
                },
            )
            rendered = container.formatter_service.render(
                request_context=request_context,
                policy_envelope=policy_envelope,
                route="approval",
                primary_message=pending_execution.user_visible_message,
                execution_payload={
                    **routing.model_dump(mode="json"),
                    "selected_capability_ids": list(compiled.orchestration_decision.selected_capability_ids),
                    "allowed_app_ids": list(policy_envelope.allowed_app_ids),
                    "reasoning_summary": compiled.routing_plan.reasoning_summary,
                    "paused_execution": pending_execution.paused_execution.model_dump(mode="json"),
                },
                approval_state="pending",
                trace_id=request.trace_id,
                channel_id=request.channel_id,
            )
            return container.responses.routing(
                status="pending",
                message=pending_execution.user_visible_message,
                routing=routing,
                session_id=session_id,
                trace_id=request.trace_id,
                presentation=rendered.channel_response,
                meta={
                    "selection_mode": routing.selection_mode,
                    "selected_capability_id": routing.selected_capability_id,
                    "formatter_id": routing.formatter_id,
                    "request_context_id": request_context.request_id,
                    "policy_envelope_id": policy_envelope.envelope_id,
                    "routing_plan_id": compiled.routing_plan.plan_id,
                    "execution_mode": request_context.execution_mode,
                    "orchestration_decision_id": compiled.orchestration_decision.decision_id,
                    "orchestration_mode": compiled.orchestration_decision.orchestration_mode,
                    "approval_id": pending_execution.approval_request.approval_id,
                    "approval_status": pending_execution.approval_request.status,
                    "approval_scope_type": pending_execution.approval_request.scope_type,
                    "visibility_profile_id": rendered.visibility_profile.profile_id,
                    "presentation_formatter_id": rendered.formatter_input.formatter_id,
                    "presentation_channel_id": rendered.formatter_input.channel_id,
                    "response_state": rendered.channel_response.state.status,
                    "primary_mode": rendered.channel_response.primary_mode,
                },
            ).model_dump(mode="json")

        routing = await container.capability_router.invoke(
            request,
            session_id=session_id,
            request_context=request_context,
            policy_envelope=policy_envelope,
            routing_plan=compiled.routing_plan,
        )
        if session_id is not None:
            await ctx.set_state("active_session_id", session_id)

        status = routing.downstream_status or "ok"
        message = routing.output.get("message") if isinstance(routing.output, dict) else None
        primary_message = str(message or f"Capability '{routing.selected_capability_id}' executed.")
        route_name = "routing"
        if compiled.orchestration_decision.orchestration_mode == "reject":
            route_name = "rejection"
        elif routing.capability_kind == "report":
            route_name = "report"
        elif routing.capability_kind == "workflow":
            route_name = "workflow"
        rendered = container.formatter_service.render(
            request_context=request_context,
            policy_envelope=policy_envelope,
            route=route_name,
            primary_message=primary_message,
            execution_payload={
                **routing.model_dump(mode="json"),
                "selected_capability_ids": list(compiled.orchestration_decision.selected_capability_ids),
                "allowed_app_ids": list(policy_envelope.allowed_app_ids),
                "reasoning_summary": compiled.routing_plan.reasoning_summary,
            },
            warnings=routing.warnings,
            fallback_used=routing.fallback_used,
            fallback_capability_id=routing.fallback_capability_id,
            approval_state="required" if compiled.orchestration_decision.requires_approval else "none",
            trace_id=request.trace_id,
            channel_id=request.channel_id,
        )
        return container.responses.routing(
            status=status,
            message=primary_message,
            routing=routing,
            session_id=session_id,
            trace_id=request.trace_id,
            warnings=routing.warnings,
            presentation=rendered.channel_response,
            meta={
                "selection_mode": routing.selection_mode,
                "selected_capability_id": routing.selected_capability_id,
                "formatter_id": routing.formatter_id,
                "server_id": routing.server_id,
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
                "routing_plan_id": compiled.routing_plan.plan_id,
                "execution_mode": request_context.execution_mode,
                "orchestration_decision_id": compiled.orchestration_decision.decision_id,
                "orchestration_mode": compiled.orchestration_decision.orchestration_mode,
                "primary_capability_id": compiled.orchestration_decision.primary_capability_id,
                "visibility_profile_id": rendered.visibility_profile.profile_id,
                "presentation_formatter_id": rendered.formatter_input.formatter_id,
                "presentation_channel_id": rendered.formatter_input.channel_id,
                "response_state": rendered.channel_response.state.status,
                "primary_mode": rendered.channel_response.primary_mode,
            },
        ).model_dump(mode="json")
