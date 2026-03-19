from __future__ import annotations

from dataclasses import dataclass

from tag_fastmcp.core.capability_registry import CapabilityRegistry
from tag_fastmcp.models.contracts import (
    CapabilityCandidate,
    IntentAnalysis,
    InvokeCapabilityRequest,
    OrchestrationDecision,
    PlanningInput,
    PolicyEnvelope,
    RequestContext,
    RoutingPlan,
)


@dataclass
class CompiledOrchestration:
    orchestration_decision: OrchestrationDecision
    routing_plan: RoutingPlan
    execution_requests: list[InvokeCapabilityRequest]


@dataclass
class PlanCompiler:
    capability_registry: CapabilityRegistry

    def compile_message(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        planning_input: PlanningInput,
        intent_analysis: IntentAnalysis,
        capability_candidates: list[CapabilityCandidate],
        orchestration_decision: OrchestrationDecision,
    ) -> CompiledOrchestration:
        candidate_map = {candidate.capability_id: candidate for candidate in capability_candidates}
        formatter_id = self._formatter_id(request_context, policy_envelope)

        if orchestration_decision.orchestration_mode == "single_step":
            selected = self._candidate(candidate_map, orchestration_decision.primary_capability_id)
            routing_plan = RoutingPlan(
                plan_id=orchestration_decision.routing_plan_id,
                request_id=request_context.request_id,
                intent_type=self._intent_type(selected.kind),
                target_app_ids=list(policy_envelope.allowed_app_ids),
                selected_capability_id=selected.capability_id,
                candidate_capability_ids=[candidate.capability_id for candidate in capability_candidates],
                requires_confirmation=orchestration_decision.requires_confirmation,
                requires_approval=orchestration_decision.requires_approval,
                approval_reason=orchestration_decision.approval_reason,
                formatter_id=formatter_id,
                audit_tags=[*orchestration_decision.audit_tags, request_context.execution_mode],
                reasoning_summary=orchestration_decision.user_visible_reason,
            )
            return CompiledOrchestration(
                orchestration_decision=orchestration_decision.model_copy(update={"formatter_id": formatter_id}),
                routing_plan=routing_plan,
                execution_requests=[
                    self._invoke_request(
                        request_context=request_context,
                        candidate=selected,
                        channel_id=request_context.channel_id,
                    )
                ],
            )

        if orchestration_decision.orchestration_mode == "multi_step":
            selected_candidates = [
                self._candidate(candidate_map, capability_id)
                for capability_id in orchestration_decision.selected_capability_ids
            ]
            routing_plan = RoutingPlan(
                plan_id=orchestration_decision.routing_plan_id,
                request_id=request_context.request_id,
                intent_type="run_workflow",
                target_app_ids=list(policy_envelope.allowed_app_ids),
                selected_capability_id=orchestration_decision.primary_capability_id,
                candidate_capability_ids=list(orchestration_decision.selected_capability_ids),
                requires_confirmation=orchestration_decision.requires_confirmation,
                requires_approval=orchestration_decision.requires_approval,
                approval_reason=orchestration_decision.approval_reason,
                formatter_id=formatter_id,
                audit_tags=[*orchestration_decision.audit_tags, request_context.execution_mode],
                reasoning_summary=orchestration_decision.user_visible_reason,
            )
            return CompiledOrchestration(
                orchestration_decision=orchestration_decision.model_copy(update={"formatter_id": formatter_id}),
                routing_plan=routing_plan,
                execution_requests=[
                    self._invoke_request(
                        request_context=request_context,
                        candidate=candidate,
                        channel_id=request_context.channel_id,
                    )
                    for candidate in selected_candidates
                ],
            )

        if orchestration_decision.orchestration_mode == "heavy_agent":
            intent_type = "escalate_heavy_agent"
        elif orchestration_decision.orchestration_mode == "proposal":
            intent_type = "propose_agent"
        elif orchestration_decision.orchestration_mode == "reject":
            intent_type = "reject"
        else:
            intent_type = "ask_clarification" if orchestration_decision.clarification_prompt else "answer_from_context"

        routing_plan = RoutingPlan(
            plan_id=orchestration_decision.routing_plan_id,
            request_id=request_context.request_id,
            intent_type=intent_type,  # type: ignore[arg-type]
            target_app_ids=list(policy_envelope.allowed_app_ids),
            selected_capability_id=orchestration_decision.primary_capability_id,
            candidate_capability_ids=[candidate.capability_id for candidate in capability_candidates],
            requires_clarification=orchestration_decision.clarification_prompt is not None,
            requires_confirmation=orchestration_decision.requires_confirmation,
            requires_approval=orchestration_decision.requires_approval,
            approval_reason=orchestration_decision.approval_reason,
            formatter_id=formatter_id,
            audit_tags=[*orchestration_decision.audit_tags, request_context.execution_mode],
            reasoning_summary=orchestration_decision.user_visible_reason,
        )
        return CompiledOrchestration(
            orchestration_decision=orchestration_decision.model_copy(update={"formatter_id": formatter_id}),
            routing_plan=routing_plan,
            execution_requests=[],
        )

    def compile_direct_request(
        self,
        *,
        request: InvokeCapabilityRequest,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        routing_plan: RoutingPlan,
    ) -> CompiledOrchestration:
        decision = OrchestrationDecision(
            decision_id=f"direct_{request_context.request_id}",
            request_id=request_context.request_id,
            routing_plan_id=routing_plan.plan_id,
            orchestration_mode="single_step",
            selected_capability_ids=[routing_plan.selected_capability_id] if routing_plan.selected_capability_id else [],
            primary_capability_id=routing_plan.selected_capability_id,
            requires_confirmation=routing_plan.requires_confirmation,
            requires_approval=routing_plan.requires_approval,
            approval_reason=routing_plan.approval_reason,
            formatter_id=routing_plan.formatter_id,
            audit_tags=["planner", "direct_tool", request_context.execution_mode],
            user_visible_reason=routing_plan.reasoning_summary,
        )
        return CompiledOrchestration(
            orchestration_decision=decision,
            routing_plan=routing_plan,
            execution_requests=[request],
        )

    @staticmethod
    def _intent_type(kind: str) -> str:
        if kind == "report":
            return "run_report"
        if kind == "workflow":
            return "run_workflow"
        return "invoke_external_tool"

    @staticmethod
    def _candidate(
        candidate_map: dict[str, CapabilityCandidate],
        capability_id: str | None,
    ) -> CapabilityCandidate:
        if capability_id is None or capability_id not in candidate_map:
            raise ValueError("A selected capability is required before compilation.")
        return candidate_map[capability_id]

    @staticmethod
    def _invoke_request(
        *,
        request_context: RequestContext,
        candidate: CapabilityCandidate,
        channel_id: str | None,
    ) -> InvokeCapabilityRequest:
        app_id = candidate.app_id or request_context.requested_app_id or request_context.session_bound_app_id
        if app_id is None:
            raise ValueError("A compiled execution step requires a resolved app_id.")
        return InvokeCapabilityRequest(
            app_id=app_id,
            session_id=request_context.session_id,
            actor_id=request_context.actor_id,
            auth_subject=request_context.auth_subject,
            tenant_id=request_context.tenant_id,
            role=request_context.role,
            auth_scopes=list(request_context.auth_scopes),
            trace_id=request_context.trace_id,
            metadata=dict(request_context.metadata),
            capability_id=candidate.capability_id,
            channel_id=channel_id,
        )

    def _formatter_id(
        self,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
    ) -> str | None:
        if request_context.channel_id is None:
            return None
        registry = self.capability_registry.describe(app_id=policy_envelope.primary_app_id)
        for channel in registry.channels:
            if channel.channel_id != request_context.channel_id:
                continue
            if channel.channel_id not in policy_envelope.allowed_channel_ids:
                continue
            if channel.formatter.formatter_id not in policy_envelope.allowed_formatter_ids:
                continue
            return channel.formatter.formatter_id
        return None
