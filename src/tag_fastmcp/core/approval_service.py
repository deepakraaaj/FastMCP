from __future__ import annotations

import uuid
from dataclasses import dataclass

from tag_fastmcp.core.control_plane_store import ControlPlaneStore, utcnow
from tag_fastmcp.models.contracts import (
    ApprovalDecision,
    ApprovalQueueItem,
    ApprovalRequest,
    ExecutionApprovalPayload,
    InvokeCapabilityRequest,
    LifecycleAuditEvent,
    OrchestrationDecision,
    PausedExecutionRecord,
    PolicyEnvelope,
    RequestContext,
    RoutingPlan,
)


@dataclass
class PendingExecutionApproval:
    approval_request: ApprovalRequest
    approval_payload: ExecutionApprovalPayload
    paused_execution: PausedExecutionRecord
    user_visible_message: str


@dataclass
class ApprovalService:
    store: ControlPlaneStore

    async def request_execution_approval(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        routing_plan: RoutingPlan,
        orchestration_decision: OrchestrationDecision,
        execution_requests: list[InvokeCapabilityRequest],
    ) -> PendingExecutionApproval:
        approval_id = self._identifier("apr")
        approval_reason = orchestration_decision.approval_reason or self._first_reason(policy_envelope)
        approval_request = ApprovalRequest(
            approval_id=approval_id,
            scope_type="execution",
            status="pending",
            tenant_id=request_context.tenant_id,
            app_ids=list(policy_envelope.allowed_app_ids),
            requested_by_actor_id=request_context.actor_id,
            requested_by_role=request_context.role,
            request_reason=orchestration_decision.user_visible_reason,
            approval_reason=approval_reason,
            created_at=utcnow(),
            trace_id=request_context.trace_id,
            request_context_ref=request_context.request_id,
            routing_plan_ref=routing_plan.plan_id,
        )
        approval_payload = ExecutionApprovalPayload(
            approval_id=approval_id,
            orchestration_decision_id=orchestration_decision.decision_id,
            selected_capability_ids=list(orchestration_decision.selected_capability_ids),
            primary_capability_id=orchestration_decision.primary_capability_id,
            side_effect_level=self._side_effect_level(routing_plan),
            risk_level=self._risk_level(policy_envelope, routing_plan, orchestration_decision),
            user_visible_summary=orchestration_decision.user_visible_reason,
            admin_review_summary=self._admin_review_summary(policy_envelope, routing_plan, orchestration_decision),
        )
        paused_execution = PausedExecutionRecord(
            pause_id=self._identifier("pex"),
            approval_id=approval_id,
            status="pending_approval",
            request_id=request_context.request_id,
            request_context=request_context,
            policy_envelope=policy_envelope,
            routing_plan=routing_plan,
            orchestration_decision=orchestration_decision,
            execution_requests=list(execution_requests),
            created_at=utcnow(),
        )
        await self.store.put_approval_request(approval_request)
        await self.store.put_execution_approval_payload(approval_payload)
        await self.store.put_paused_execution(paused_execution)
        await self.store.append_audit_event(
            LifecycleAuditEvent(
                event_id=self._identifier("evt"),
                event_type="approval_requested",
                actor_id=request_context.actor_id,
                actor_role=request_context.role,
                approval_id=approval_id,
                trace_id=request_context.trace_id,
                timestamp=utcnow(),
                payload={
                    "scope_type": "execution",
                    "request_context_ref": request_context.request_id,
                    "routing_plan_ref": routing_plan.plan_id,
                    "selected_capability_ids": list(orchestration_decision.selected_capability_ids),
                    "approval_reason": approval_reason,
                },
            )
        )
        return PendingExecutionApproval(
            approval_request=approval_request,
            approval_payload=approval_payload,
            paused_execution=paused_execution,
            user_visible_message=(
                f"This request is paused for approval under '{approval_id}'. "
                "It will not execute until an authorized reviewer approves it."
            ),
        )

    async def decide(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        approval_id: str,
        decision: str,
        comment: str | None = None,
    ) -> tuple[ApprovalRequest, ApprovalDecision]:
        approval = await self.store.get_approval_request(approval_id)
        self._validate_decider(request_context, policy_envelope, approval)

        resulting_status = self._resulting_status(decision)
        updated_approval = approval.model_copy(
            update={
                "status": resulting_status,
                "approver_actor_id": request_context.actor_id,
                "approver_role": request_context.role,
                "approval_reason": comment or approval.approval_reason,
                "decided_at": utcnow(),
            }
        )
        approval_decision = ApprovalDecision(
            approval_id=approval_id,
            decision=decision,  # type: ignore[arg-type]
            approver_actor_id=request_context.actor_id or "unknown",
            approver_role=request_context.role if request_context.role != "end_user" else "service",
            comment=comment,
            decided_at=updated_approval.decided_at or utcnow(),
            resulting_status=resulting_status,  # type: ignore[arg-type]
        )
        await self.store.put_approval_request(updated_approval)

        paused_execution = await self.store.get_paused_execution_by_approval(approval_id)
        if paused_execution is not None:
            paused_status = {
                "approved": "approved",
                "rejected": "rejected",
                "cancelled": "cancelled",
                "expired": "expired",
            }.get(resulting_status, paused_execution.status)
            await self.store.put_paused_execution(
                paused_execution.model_copy(update={"status": paused_status})
            )

        await self.store.append_audit_event(
            LifecycleAuditEvent(
                event_id=self._identifier("evt"),
                event_type=self._event_type_for_status(resulting_status),
                actor_id=request_context.actor_id,
                actor_role=request_context.role,
                approval_id=approval_id,
                trace_id=request_context.trace_id,
                timestamp=approval_decision.decided_at,
                payload={
                    "decision": decision,
                    "comment": comment,
                    "resulting_status": resulting_status,
                },
            )
        )
        return updated_approval, approval_decision

    async def resume_execution(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        approval_id: str,
    ) -> PausedExecutionRecord:
        approval = await self.store.get_approval_request(approval_id)
        if approval.status != "approved":
            raise ValueError(f"Approval '{approval_id}' is not approved.")

        paused_execution = await self.store.get_paused_execution_by_approval(approval_id)
        if paused_execution is None:
            raise ValueError(f"Approval '{approval_id}' does not reference a paused execution.")
        if paused_execution.status == "resumed":
            return paused_execution

        self._validate_resume_scope(policy_envelope, paused_execution)
        resumed = paused_execution.model_copy(
            update={
                "status": "resumed",
                "resumed_at": utcnow(),
            }
        )
        await self.store.put_paused_execution(resumed)
        return resumed

    async def list_queue(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        status: str | None = "pending",
        scope_type: str | None = None,
    ) -> list[ApprovalQueueItem]:
        self._ensure_reviewer(request_context)
        approvals = await self.store.list_approval_requests(status=status, scope_type=scope_type)
        visible = [approval for approval in approvals if self._visible_to_scope(approval, request_context, policy_envelope)]
        queue: list[ApprovalQueueItem] = []
        for approval in visible:
            payload = await self.store.get_execution_approval_payload(approval.approval_id)
            severity = payload.risk_level if payload is not None else "medium"
            title = "Execution approval"
            summary = approval.request_reason
            if approval.scope_type == "agent_lifecycle" and approval.proposal_draft_ref:
                proposal = await self.store.get_proposal_draft(approval.proposal_draft_ref)
                title = proposal.display_name
                summary = proposal.justification
                severity = "medium"
            elif payload is not None:
                title = payload.primary_capability_id or "Execution approval"
                summary = payload.user_visible_summary
            queue.append(
                ApprovalQueueItem(
                    approval_id=approval.approval_id,
                    scope_type=approval.scope_type,
                    status=approval.status,
                    title=title,
                    summary=summary,
                    requested_by=approval.requested_by_actor_id,
                    target_scope_label=", ".join(approval.app_ids) if approval.app_ids else "platform",
                    created_at=approval.created_at,
                    expires_at=approval.expires_at,
                    severity=severity,  # type: ignore[arg-type]
                )
            )
        return queue

    async def get_execution_approval_payload(self, approval_id: str) -> ExecutionApprovalPayload | None:
        return await self.store.get_execution_approval_payload(approval_id)

    async def get_approval_request(self, approval_id: str) -> ApprovalRequest:
        return await self.store.get_approval_request(approval_id)

    async def list_audit_events(self, *, approval_id: str | None = None) -> list[LifecycleAuditEvent]:
        return await self.store.list_audit_events(approval_id=approval_id)

    @staticmethod
    def _identifier(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _first_reason(policy_envelope: PolicyEnvelope) -> str | None:
        return policy_envelope.require_approval_for[0] if policy_envelope.require_approval_for else None

    @staticmethod
    def _side_effect_level(routing_plan: RoutingPlan) -> str:
        if routing_plan.intent_type == "run_workflow":
            return "write"
        if routing_plan.intent_type in {"run_report", "invoke_external_tool", "execute_sql", "escalate_heavy_agent"}:
            return "read"
        return "none"

    @staticmethod
    def _risk_level(
        policy_envelope: PolicyEnvelope,
        routing_plan: RoutingPlan,
        orchestration_decision: OrchestrationDecision,
    ) -> str:
        if policy_envelope.allow_cross_app or orchestration_decision.orchestration_mode == "heavy_agent":
            return "high"
        if routing_plan.intent_type == "run_workflow" or len(orchestration_decision.selected_capability_ids) > 1:
            return "medium"
        return "low"

    @staticmethod
    def _admin_review_summary(
        policy_envelope: PolicyEnvelope,
        routing_plan: RoutingPlan,
        orchestration_decision: OrchestrationDecision,
    ) -> str:
        target_scope = ", ".join(policy_envelope.allowed_app_ids) if policy_envelope.allowed_app_ids else "platform"
        selected = ", ".join(orchestration_decision.selected_capability_ids) or "none"
        return (
            f"Mode={orchestration_decision.orchestration_mode}; "
            f"intent={routing_plan.intent_type}; "
            f"apps={target_scope}; "
            f"capabilities={selected}."
        )

    @staticmethod
    def _resulting_status(decision: str) -> str:
        return {
            "approve": "approved",
            "reject": "rejected",
            "cancel": "cancelled",
            "expire": "expired",
        }[decision]

    @staticmethod
    def _event_type_for_status(status: str) -> str:
        return {
            "approved": "approval_approved",
            "rejected": "approval_rejected",
            "cancelled": "approval_cancelled",
            "expired": "approval_expired",
        }[status]

    def _validate_decider(
        self,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        approval: ApprovalRequest,
    ) -> None:
        self._ensure_reviewer(request_context)
        if request_context.role == "app_admin" and not set(approval.app_ids).issubset(set(policy_envelope.allowed_app_ids)):
            raise ValueError("The current app-admin scope cannot decide this approval.")
        if approval.tenant_id and request_context.role == "app_admin" and approval.tenant_id not in policy_envelope.allowed_tenant_ids:
            raise ValueError("The current app-admin tenant scope cannot decide this approval.")

    @staticmethod
    def _ensure_reviewer(request_context: RequestContext) -> None:
        if request_context.role not in {"app_admin", "platform_admin", "service"}:
            raise ValueError("Only explicit reviewer roles may decide approvals.")

    @staticmethod
    def _visible_to_scope(
        approval: ApprovalRequest,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
    ) -> bool:
        if request_context.role in {"platform_admin", "service"}:
            return True
        return set(approval.app_ids).issubset(set(policy_envelope.allowed_app_ids))

    @staticmethod
    def _validate_resume_scope(
        policy_envelope: PolicyEnvelope,
        paused_execution: PausedExecutionRecord,
    ) -> None:
        paused_apps = set(paused_execution.routing_plan.target_app_ids or paused_execution.policy_envelope.allowed_app_ids)
        current_apps = set(policy_envelope.allowed_app_ids)
        if not paused_apps.issubset(current_apps):
            raise ValueError("The current policy envelope no longer covers the approved execution scope.")
        paused_tenants = set(paused_execution.policy_envelope.allowed_tenant_ids)
        current_tenants = set(policy_envelope.allowed_tenant_ids)
        if paused_tenants and not paused_tenants.issubset(current_tenants):
            raise ValueError("The current policy envelope no longer covers the approved tenant scope.")
