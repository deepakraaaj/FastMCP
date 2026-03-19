from __future__ import annotations

from dataclasses import dataclass

from tag_fastmcp.core.capability_router import CapabilityRouter
from tag_fastmcp.core.intent_planner import IntentPlanner, PlanningArtifacts
from tag_fastmcp.core.plan_compiler import CompiledOrchestration, PlanCompiler
from tag_fastmcp.models.contracts import InvokeCapabilityRequest, PolicyEnvelope, RequestContext


@dataclass
class OrchestrationService:
    intent_planner: IntentPlanner
    plan_compiler: PlanCompiler
    capability_router: CapabilityRouter

    def plan_message(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        user_message: str,
    ) -> tuple[PlanningArtifacts, CompiledOrchestration]:
        planning = self.intent_planner.plan_message(
            request_context=request_context,
            policy_envelope=policy_envelope,
            user_message=user_message,
        )
        compiled = self.plan_compiler.compile_message(
            request_context=request_context,
            policy_envelope=policy_envelope,
            planning_input=planning.planning_input,
            intent_analysis=planning.intent_analysis,
            capability_candidates=planning.capability_candidates,
            orchestration_decision=planning.orchestration_decision,
        )
        return planning, compiled

    def plan_direct_request(
        self,
        *,
        request: InvokeCapabilityRequest,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
    ) -> CompiledOrchestration:
        routing_plan = self.capability_router.build_routing_plan(
            request,
            request_context=request_context,
            policy_envelope=policy_envelope,
        )
        return self.plan_compiler.compile_direct_request(
            request=request,
            request_context=request_context,
            policy_envelope=policy_envelope,
            routing_plan=routing_plan,
        )
