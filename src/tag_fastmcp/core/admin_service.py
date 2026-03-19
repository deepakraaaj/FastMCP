from __future__ import annotations

from dataclasses import dataclass

from tag_fastmcp.core.response_builder import ResponseBuilder
from tag_fastmcp.models.contracts import (
    ActivateRegistrationRequest,
    ApprovalDecisionRequest,
    ApprovalQueueRequest,
    BaseAdminToolRequest,
    LifecyclePayload,
    PolicyEnvelope,
    ProposalListRequest,
    RegistrationListRequest,
    RegisterProposalRequest,
    RequestContext,
    ResponseEnvelope,
    ResumeExecutionRequest,
    RoutingPayload,
)

if False:  # pragma: no cover
    from tag_fastmcp.core.agent_lifecycle_service import AgentLifecycleService
    from tag_fastmcp.core.approval_service import ApprovalService
    from tag_fastmcp.core.capability_router import CapabilityRouter
    from tag_fastmcp.core.control_plane_store import ControlPlaneStore
    from tag_fastmcp.core.formatter_service import FormatterService
    from tag_fastmcp.core.policy_envelope import PolicyEnvelopeService
    from tag_fastmcp.core.request_context import RequestContextService
    from tag_fastmcp.core.session_store import SessionStore


def _route_name(last_routing: RoutingPayload | None) -> str:
    if last_routing is None:
        return "routing"
    if last_routing.capability_kind == "report":
        return "report"
    if last_routing.capability_kind == "workflow":
        return "workflow"
    return "routing"


def _message_from_routings(routings: list[RoutingPayload]) -> str:
    messages: list[str] = []
    for index, routing in enumerate(routings, start=1):
        output = routing.output if isinstance(routing.output, dict) else {}
        message = str(output.get("message") or f"Capability '{routing.selected_capability_id}' executed.")
        if len(routings) > 1:
            message = f"Step {index}: {message}"
        messages.append(message)
    return "\n\n".join(messages)


@dataclass
class AdminService:
    request_contexts: RequestContextService
    policy_envelopes: PolicyEnvelopeService
    session_store: SessionStore
    approvals: ApprovalService
    agent_lifecycle: AgentLifecycleService
    capability_router: CapabilityRouter
    formatter_service: FormatterService
    control_plane_store: ControlPlaneStore
    responses: ResponseBuilder

    async def list_approval_queue(
        self,
        request: ApprovalQueueRequest,
        *,
        origin: str = "admin_http",
    ) -> ResponseEnvelope:
        request_context, policy_envelope = await self._enforce(request, origin=origin)
        queue = await self.approvals.list_queue(
            request_context=request_context,
            policy_envelope=policy_envelope,
            status=request.status,
            scope_type=request.scope_type,
        )
        return self.responses.system(
            message="Approval queue loaded.",
            trace_id=request.trace_id,
            lifecycle=LifecyclePayload(approval_queue=queue),
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
                "approval_count": len(queue),
                "scope_type": request.scope_type,
                "status": request.status,
            },
        )

    async def decide_approval(
        self,
        request: ApprovalDecisionRequest,
        *,
        origin: str = "admin_http",
    ) -> ResponseEnvelope:
        request_context, policy_envelope = await self._enforce(request, origin=origin)
        approval, decision = await self.approvals.decide(
            request_context=request_context,
            policy_envelope=policy_envelope,
            approval_id=request.approval_id,
            decision=request.decision,
            comment=request.comment,
        )
        proposal = await self.agent_lifecycle.sync_proposal_from_approval(approval)
        approval_payload = await self.approvals.get_execution_approval_payload(request.approval_id)
        paused_execution = await self.control_plane_store.get_paused_execution_by_approval(request.approval_id)
        audit_events = await self.approvals.list_audit_events(approval_id=request.approval_id)
        return self.responses.system(
            message=f"Approval '{request.approval_id}' is now '{approval.status}'.",
            trace_id=request.trace_id,
            lifecycle=LifecyclePayload(
                approval_request=approval,
                approval_decision=decision,
                execution_approval_payload=approval_payload,
                proposal_draft=proposal,
                paused_execution=paused_execution,
                audit_events=audit_events,
            ),
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
                "approval_id": approval.approval_id,
                "approval_status": approval.status,
                "scope_type": approval.scope_type,
            },
        )

    async def list_agent_proposals(
        self,
        request: ProposalListRequest,
        *,
        origin: str = "admin_http",
    ) -> ResponseEnvelope:
        request_context, policy_envelope = await self._enforce(request, origin=origin)
        proposals = await self.agent_lifecycle.list_visible_proposals(
            request_context=request_context,
            policy_envelope=policy_envelope,
            status=request.status,
        )
        return self.responses.system(
            message="Agent proposals loaded.",
            trace_id=request.trace_id,
            lifecycle=LifecyclePayload(proposal_drafts=proposals),
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
                "proposal_count": len(proposals),
                "status": request.status,
            },
        )

    async def list_agent_registrations(
        self,
        request: RegistrationListRequest,
        *,
        origin: str = "admin_http",
    ) -> ResponseEnvelope:
        request_context, policy_envelope = await self._enforce(request, origin=origin)
        registrations = await self.agent_lifecycle.list_visible_registrations(
            request_context=request_context,
            policy_envelope=policy_envelope,
            proposal_id=request.proposal_id,
            registry_state=request.registry_state,
        )
        return self.responses.system(
            message="Agent registrations loaded.",
            trace_id=request.trace_id,
            lifecycle=LifecyclePayload(registration_records=registrations),
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
                "registration_count": len(registrations),
                "proposal_id": request.proposal_id,
                "registry_state": request.registry_state,
            },
        )

    async def register_agent_proposal(
        self,
        request: RegisterProposalRequest,
        *,
        origin: str = "admin_http",
    ) -> ResponseEnvelope:
        request_context, policy_envelope = await self._enforce(request, origin=origin)
        registration = await self.agent_lifecycle.register_proposal(
            request_context=request_context,
            policy_envelope=policy_envelope,
            proposal_id=request.proposal_id,
            version=request.version,
        )
        proposal = await self.agent_lifecycle.get_proposal_draft(request.proposal_id)
        return self.responses.system(
            message=f"Proposal '{request.proposal_id}' registered as '{registration.agent_id}'.",
            trace_id=request.trace_id,
            lifecycle=LifecyclePayload(
                proposal_draft=proposal,
                registration_record=registration,
            ),
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
                "proposal_id": request.proposal_id,
                "registration_id": registration.registration_id,
                "registry_state": registration.registry_state,
            },
        )

    async def activate_agent_registration(
        self,
        request: ActivateRegistrationRequest,
        *,
        origin: str = "admin_http",
    ) -> ResponseEnvelope:
        request_context, policy_envelope = await self._enforce(request, origin=origin)
        registration = await self.agent_lifecycle.activate_registration(
            request_context=request_context,
            registration_id=request.registration_id,
        )
        proposal = await self.agent_lifecycle.get_proposal_draft(registration.proposal_id)
        return self.responses.system(
            message=f"Registration '{request.registration_id}' is now active.",
            trace_id=request.trace_id,
            lifecycle=LifecyclePayload(
                proposal_draft=proposal,
                registration_record=registration,
            ),
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
                "proposal_id": registration.proposal_id,
                "registration_id": registration.registration_id,
                "agent_id": registration.agent_id,
                "registry_state": registration.registry_state,
            },
        )

    async def resume_approved_execution(
        self,
        request: ResumeExecutionRequest,
        *,
        origin: str = "admin_http",
    ) -> ResponseEnvelope:
        request_context, policy_envelope = await self._enforce(request, origin=origin)
        resumed = await self.approvals.resume_execution(
            request_context=request_context,
            policy_envelope=policy_envelope,
            approval_id=request.approval_id,
        )
        approval = await self.approvals.get_approval_request(request.approval_id)
        approval_payload = await self.approvals.get_execution_approval_payload(request.approval_id)

        routings: list[RoutingPayload] = []
        for execution_request in resumed.execution_requests:
            routings.append(
                await self.capability_router.invoke(
                    execution_request,
                    session_id=resumed.request_context.session_id,
                    request_context=resumed.request_context,
                    policy_envelope=resumed.policy_envelope,
                    routing_plan=resumed.routing_plan,
                )
            )

        last_routing = routings[-1] if routings else None
        message = _message_from_routings(routings) if routings else "Approved execution resumed."
        warnings = [warning for routing in routings for warning in routing.warnings]
        fallback_used = any(routing.fallback_used for routing in routings)
        fallback_capability_id = next(
            (
                routing.fallback_capability_id
                for routing in reversed(routings)
                if routing.fallback_capability_id
            ),
            None,
        )
        rendered = self.formatter_service.render(
            request_context=resumed.request_context,
            policy_envelope=resumed.policy_envelope,
            route=_route_name(last_routing),
            primary_message=message,
            execution_payload={
                **(last_routing.model_dump(mode="json") if last_routing else {}),
                "selected_capability_ids": list(resumed.orchestration_decision.selected_capability_ids),
                "allowed_app_ids": list(resumed.policy_envelope.allowed_app_ids),
                "reasoning_summary": resumed.routing_plan.reasoning_summary,
                "approval": approval.model_dump(mode="json"),
            },
            warnings=warnings,
            fallback_used=fallback_used,
            fallback_capability_id=fallback_capability_id,
            approval_state="approved",
            trace_id=resumed.request_context.trace_id,
            channel_id=resumed.request_context.channel_id,
        )
        routing = last_routing or RoutingPayload(
            request_context_id=resumed.request_context.request_id,
            policy_envelope_id=resumed.policy_envelope.envelope_id,
            routing_plan_id=resumed.routing_plan.plan_id,
            selected_capability_id=resumed.routing_plan.selected_capability_id or "resumed_execution",
            capability_kind="tool",
            selection_mode="capability_id",
            selection_reason=resumed.routing_plan.reasoning_summary,
            formatter_id=resumed.routing_plan.formatter_id,
            downstream_status="ok",
            output={"message": message},
        )
        return self.responses.routing(
            status=routing.downstream_status or "ok",
            message=message,
            routing=routing,
            session_id=resumed.request_context.session_id,
            trace_id=resumed.request_context.trace_id,
            warnings=warnings,
            presentation=rendered.channel_response,
            lifecycle=LifecyclePayload(
                approval_request=approval,
                execution_approval_payload=approval_payload,
                paused_execution=resumed,
            ),
            meta={
                "request_context_id": resumed.request_context.request_id,
                "policy_envelope_id": resumed.policy_envelope.envelope_id,
                "routing_plan_id": resumed.routing_plan.plan_id,
                "approval_id": approval.approval_id,
                "approval_status": approval.status,
                "orchestration_decision_id": resumed.orchestration_decision.decision_id,
                "visibility_profile_id": rendered.visibility_profile.profile_id,
                "presentation_formatter_id": rendered.formatter_input.formatter_id,
                "presentation_channel_id": rendered.formatter_input.channel_id,
                "response_state": rendered.channel_response.state.status,
                "primary_mode": rendered.channel_response.primary_mode,
            },
        )

    async def _enforce(
        self,
        request: BaseAdminToolRequest,
        *,
        origin: str,
    ) -> tuple[RequestContext, PolicyEnvelope]:
        request_context = await self.request_contexts.build(
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
        policy_envelope = self.policy_envelopes.derive(
            request_context,
            allow_platform_tools=True,
        )
        if request.session_id is not None:
            await self.session_store.ensure(request.session_id, actor_id=request_context.actor_id)
            if policy_envelope.primary_app_id is not None:
                await self.session_store.bind_scope(
                    request.session_id,
                    app_id=policy_envelope.primary_app_id,
                    tenant_id=request_context.tenant_id,
                    execution_mode=request_context.execution_mode,
                )
        return request_context, policy_envelope
