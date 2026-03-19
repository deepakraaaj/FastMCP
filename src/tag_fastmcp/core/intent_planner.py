from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from tag_fastmcp.core.app_router import AppRouter
from tag_fastmcp.core.capability_registry import CapabilityRegistry
from tag_fastmcp.models.contracts import (
    CapabilityCandidate,
    CapabilityPayload,
    IntentAnalysis,
    OrchestrationDecision,
    PlanningInput,
    PolicyEnvelope,
    RequestContext,
)


_READ_HINTS = {
    "find",
    "list",
    "lookup",
    "show",
    "status",
    "view",
    "what",
    "which",
}
_WRITE_HINTS = {
    "assign",
    "cancel",
    "close",
    "complete",
    "continue",
    "create",
    "open",
    "start",
    "submit",
    "update",
}
_COMPARE_HINTS = {"across", "compare", "combined", "reconcile", "versus", "vs"}
_PROPOSAL_HINTS = {
    "agent proposal",
    "create agent",
    "custom agent",
    "dedicated agent",
    "new agent",
}
_REPORT_SUPPORT_HINTS = {"available", "lookup", "menu", "option", "options"}
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "me",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "with",
}


@dataclass
class PlanningArtifacts:
    planning_input: PlanningInput
    intent_analysis: IntentAnalysis
    capability_candidates: list[CapabilityCandidate]
    orchestration_decision: OrchestrationDecision


@dataclass
class IntentPlanner:
    app_router: AppRouter
    capability_registry: CapabilityRegistry

    def plan_message(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        user_message: str,
    ) -> PlanningArtifacts:
        capabilities = self._candidate_capabilities(policy_envelope)
        planning_input = self._planning_input(
            request_context=request_context,
            policy_envelope=policy_envelope,
            user_message=user_message,
            capabilities=capabilities,
        )
        intent_analysis = self._analyze_intent(
            request_context=request_context,
            policy_envelope=policy_envelope,
            planning_input=planning_input,
        )
        capability_candidates = self._rank_capabilities(
            request_context=request_context,
            planning_input=planning_input,
            intent_analysis=intent_analysis,
            capabilities=capabilities,
            policy_envelope=policy_envelope,
        )
        orchestration_decision = self._decide(
            request_context=request_context,
            policy_envelope=policy_envelope,
            planning_input=planning_input,
            intent_analysis=intent_analysis,
            capability_candidates=capability_candidates,
            capabilities=capabilities,
        )
        return PlanningArtifacts(
            planning_input=planning_input,
            intent_analysis=intent_analysis,
            capability_candidates=capability_candidates,
            orchestration_decision=orchestration_decision,
        )

    def _planning_input(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        user_message: str,
        capabilities: list[CapabilityPayload],
    ) -> PlanningInput:
        return PlanningInput(
            request_id=request_context.request_id,
            session_id=request_context.session_id,
            execution_mode=request_context.execution_mode,
            actor_role=request_context.role,
            user_message=user_message,
            requested_app_ids=list(policy_envelope.allowed_app_ids),
            channel_id=request_context.channel_id,
            session_summary=None,
            envelope_ref=policy_envelope.envelope_id,
            candidate_capability_ids=[capability.capability_id for capability in capabilities],
            available_reports=[
                capability.capability_id for capability in capabilities if capability.kind == "report"
            ],
            available_workflows=[
                capability.capability_id for capability in capabilities if capability.kind == "workflow"
            ],
            available_external_tools=[
                capability.capability_id
                for capability in capabilities
                if capability.kind == "tool" and capability.owner.startswith("mcp_server:")
            ],
        )

    def _analyze_intent(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        planning_input: PlanningInput,
    ) -> IntentAnalysis:
        message = planning_input.user_message or ""
        message_lower = message.lower()
        message_tokens = self._tokens(message)
        mentioned_apps = [
            app_id
            for app_id in sorted(self.app_router.registry.apps.keys())
            if app_id.lower() in message_lower
        ]
        if request_context.requested_app_id and request_context.requested_app_id not in mentioned_apps:
            mentioned_apps = [*mentioned_apps, request_context.requested_app_id]
        business_entities = self._quoted_entities(message)
        ambiguity_reasons: list[str] = []
        missing_inputs: list[str] = []
        risk_level = "low"
        side_effect_level = "none"
        intent_family = "answer"
        preferred_execution_kind = "answer"

        requested_cross_app = self._requests_cross_app(message_lower, mentioned_apps)
        disallowed_cross_app = request_context.execution_mode == "app_chat" and requested_cross_app
        if disallowed_cross_app:
            return IntentAnalysis(
                request_id=request_context.request_id,
                intent_family="reject",
                business_entities=business_entities,
                mentioned_apps=mentioned_apps,
                ambiguity_reasons=["cross_app_blocked"],
                risk_level="high",
                side_effect_level="read",
                preferred_execution_kind="heavy_agent",
            )

        if any(hint in message_lower for hint in _PROPOSAL_HINTS):
            intent_family = "agent_gap"
            preferred_execution_kind = "proposal"
            risk_level = "medium"
        elif requested_cross_app:
            intent_family = "multi_app_analysis"
            preferred_execution_kind = "heavy_agent"
            risk_level = "high"
            side_effect_level = "read"
        elif message_tokens & _WRITE_HINTS:
            intent_family = "workflow"
            preferred_execution_kind = "workflow"
            risk_level = "medium"
            side_effect_level = "write"
        elif message_tokens & _READ_HINTS or message.strip().endswith("?"):
            intent_family = "report"
            preferred_execution_kind = "report"
            side_effect_level = "read"

        if (
            request_context.execution_mode == "admin_chat"
            and len(policy_envelope.allowed_app_ids) > 1
            and intent_family in {"report", "workflow", "external_tool", "answer"}
            and not requested_cross_app
            and not mentioned_apps
        ):
            ambiguity_reasons.append("missing_app_target")
            intent_family = "clarify"

        return IntentAnalysis(
            request_id=request_context.request_id,
            intent_family=intent_family,  # type: ignore[arg-type]
            business_entities=business_entities,
            mentioned_apps=mentioned_apps,
            missing_inputs=missing_inputs,
            ambiguity_reasons=ambiguity_reasons,
            risk_level=risk_level,  # type: ignore[arg-type]
            side_effect_level=side_effect_level,  # type: ignore[arg-type]
            preferred_execution_kind=preferred_execution_kind,  # type: ignore[arg-type]
        )

    def _rank_capabilities(
        self,
        *,
        request_context: RequestContext,
        planning_input: PlanningInput,
        intent_analysis: IntentAnalysis,
        capabilities: list[CapabilityPayload],
        policy_envelope: PolicyEnvelope,
    ) -> list[CapabilityCandidate]:
        message_tokens = self._tokens(planning_input.user_message or "")
        message_lower = (planning_input.user_message or "").lower()
        candidates: list[CapabilityCandidate] = []

        for capability in capabilities:
            capability_tokens = self._capability_tokens(capability)
            overlap = sorted(message_tokens & capability_tokens)
            exact_name_match = self._display_phrase(capability.display_name) in message_lower
            exact_id_match = self._display_phrase(capability.capability_id) in message_lower
            if not overlap and not exact_name_match and not exact_id_match:
                continue

            score = len(overlap) * 12
            if exact_name_match:
                score += 10
            if exact_id_match:
                score += 8
            if capability.scope == "app":
                score += 3
            if capability.app_id and capability.app_id in intent_analysis.mentioned_apps:
                score += 10
            if capability.app_id and capability.app_id == policy_envelope.primary_app_id:
                score += 4
            if intent_analysis.preferred_execution_kind == "report" and capability.kind == "report":
                score += 9
            if intent_analysis.preferred_execution_kind == "workflow" and capability.kind == "workflow":
                score += 11
            if intent_analysis.preferred_execution_kind == "external_tool" and capability.kind == "tool":
                score += 7
            if capability.kind in {"report", "workflow"}:
                score += 2
            if capability.kind == "tool" and capability.owner.startswith("mcp_server:"):
                score -= 1
            if capability.kind == "workflow" and capability.app_id is not None:
                workflow_id = capability.capability_id.split(".", 2)[2]
                workflow = self.app_router.resolve(capability.app_id).domain_registry.get_workflow(workflow_id)
                score -= len(workflow.required_fields)

            risk_flags: list[str] = []
            if capability.kind == "workflow":
                risk_flags.append("write_path")
            if capability.kind == "tool" and capability.owner.startswith("mcp_server:"):
                risk_flags.append("external_tool")
            if len(policy_envelope.allowed_app_ids) > 1 and capability.app_id in policy_envelope.allowed_app_ids:
                risk_flags.append("multi_app_scope")

            requires_approval = "cross_app" in policy_envelope.require_approval_for and len(policy_envelope.allowed_app_ids) > 1
            candidates.append(
                CapabilityCandidate(
                    capability_id=capability.capability_id,
                    app_id=capability.app_id,
                    kind=capability.kind,  # type: ignore[arg-type]
                    score=score,
                    match_reason=self._match_reason(capability.capability_id, overlap, exact_name_match or exact_id_match),
                    risk_flags=risk_flags,
                    requires_session=capability.execution.requires_session,
                    requires_confirmation=False,
                    requires_approval=requires_approval,
                )
            )

        candidates.sort(key=lambda item: (-item.score, item.capability_id))
        return candidates

    def _decide(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        planning_input: PlanningInput,
        intent_analysis: IntentAnalysis,
        capability_candidates: list[CapabilityCandidate],
        capabilities: list[CapabilityPayload],
    ) -> OrchestrationDecision:
        routing_plan_id = f"route_{request_context.request_id}"
        message = planning_input.user_message or ""
        approval_reason = policy_envelope.require_approval_for[0] if policy_envelope.require_approval_for else None
        requires_approval = approval_reason is not None
        if intent_analysis.intent_family == "reject":
            current_app = policy_envelope.primary_app_id or "the current application"
            return self._decision(
                request_context=request_context,
                routing_plan_id=routing_plan_id,
                orchestration_mode="reject",
                audit_tags=["planner", "reject", "cross_app_blocked"],
                user_visible_reason=(
                    f"This chat session is limited to '{current_app}' and cannot access cross-application data."
                ),
            )

        if intent_analysis.intent_family == "multi_app_analysis":
            if not policy_envelope.allow_cross_app:
                return self._decision(
                    request_context=request_context,
                    routing_plan_id=routing_plan_id,
                    orchestration_mode="reject",
                    audit_tags=["planner", "reject", "cross_app_not_allowed"],
                    user_visible_reason="This request needs cross-application access that is not allowed in the current scope.",
                )
            if not policy_envelope.allow_heavy_agent:
                return self._decision(
                    request_context=request_context,
                    routing_plan_id=routing_plan_id,
                    orchestration_mode="reject",
                    audit_tags=["planner", "reject", "heavy_agent_not_allowed"],
                    user_visible_reason="This cross-application analysis requires the heavy execution path, and that path is not enabled in the current envelope.",
                )
            return self._decision(
                request_context=request_context,
                routing_plan_id=routing_plan_id,
                orchestration_mode="heavy_agent",
                audit_tags=["planner", "heavy_agent", *sorted(policy_envelope.allowed_app_ids)],
                user_visible_reason="This request requires explicit heavy cross-application execution.",
                requires_approval="cross_app" in policy_envelope.require_approval_for,
                approval_reason="cross_app" if "cross_app" in policy_envelope.require_approval_for else None,
            )

        if intent_analysis.intent_family == "agent_gap":
            if not policy_envelope.allow_agent_proposal:
                return self._decision(
                    request_context=request_context,
                    routing_plan_id=routing_plan_id,
                    orchestration_mode="reject",
                    audit_tags=["planner", "reject", "proposal_not_allowed"],
                    user_visible_reason="Creating or proposing a new agent is not allowed in the current scope.",
                )
            return self._decision(
                request_context=request_context,
                routing_plan_id=routing_plan_id,
                orchestration_mode="proposal",
                requires_approval=True,
                approval_reason="agent_lifecycle",
                audit_tags=["planner", "proposal"],
                user_visible_reason="This looks like a recurring unmet pattern and should be reviewed as an agent proposal draft.",
            )

        if "missing_app_target" in intent_analysis.ambiguity_reasons:
            app_list = ", ".join(policy_envelope.allowed_app_ids)
            return self._decision(
                request_context=request_context,
                routing_plan_id=routing_plan_id,
                orchestration_mode="answer_only",
                clarification_prompt=f"Select which application to use before I route this request: {app_list}.",
                audit_tags=["planner", "clarify", "missing_app_target"],
                user_visible_reason="An application target is required before execution can continue.",
            )

        if not capability_candidates or capability_candidates[0].score < 12:
            return self._decision(
                request_context=request_context,
                routing_plan_id=routing_plan_id,
                orchestration_mode="answer_only",
                audit_tags=["planner", "answer_only"],
                user_visible_reason="No approved capability matched strongly enough, so the app-scoped chat agent will answer directly.",
            )

        top_score = capability_candidates[0].score
        top_candidates = [candidate for candidate in capability_candidates if candidate.score == top_score]
        if len(top_candidates) > 1:
            options = ", ".join(candidate.capability_id for candidate in top_candidates[:3])
            return self._decision(
                request_context=request_context,
                routing_plan_id=routing_plan_id,
                orchestration_mode="answer_only",
                clarification_prompt=f"I found multiple approved routes for this request. Choose one: {options}.",
                audit_tags=["planner", "clarify", "ambiguous_route"],
                user_visible_reason="Routing stayed ambiguous, so clarification is required before execution.",
            )

        selected = top_candidates[0]
        selected_capability = next(
            capability for capability in capabilities if capability.capability_id == selected.capability_id
        )

        if selected.kind == "workflow":
            missing_inputs = self._missing_workflow_inputs(selected_capability, message)
            if missing_inputs:
                prompt = self._workflow_clarification_prompt(selected.capability_id, missing_inputs)
                return self._decision(
                    request_context=request_context,
                    routing_plan_id=routing_plan_id,
                    orchestration_mode="answer_only",
                    clarification_prompt=prompt,
                    missing_inputs=missing_inputs,
                    audit_tags=["planner", "clarify", "workflow_inputs"],
                    user_visible_reason="The workflow route is valid, but it is missing required inputs.",
                )

            supporting_report = self._supporting_report(selected, capability_candidates, capabilities)
            if supporting_report is not None:
                return self._decision(
                    request_context=request_context,
                    routing_plan_id=routing_plan_id,
                    orchestration_mode="multi_step",
                    selected_capability_ids=[supporting_report.capability_id, selected.capability_id],
                    primary_capability_id=selected.capability_id,
                    requires_approval=requires_approval,
                    approval_reason=approval_reason,
                    audit_tags=["planner", "multi_step", "workflow"],
                    user_visible_reason="A short bounded sequence will gather supporting context before continuing the workflow.",
                )

        return self._decision(
            request_context=request_context,
            routing_plan_id=routing_plan_id,
            orchestration_mode="single_step",
            selected_capability_ids=[selected.capability_id],
            primary_capability_id=selected.capability_id,
            requires_approval=selected.requires_approval or requires_approval,
            approval_reason="cross_app" if selected.requires_approval else approval_reason,
            audit_tags=["planner", "single_step", selected.kind],
            user_visible_reason=f"Selected '{selected.capability_id}' as the bounded execution route.",
        )

    def _candidate_capabilities(self, policy_envelope: PolicyEnvelope) -> list[CapabilityPayload]:
        registry = self.capability_registry.describe()
        capabilities: list[CapabilityPayload] = []
        for capability in registry.capabilities:
            if capability.capability_id not in policy_envelope.allowed_capability_ids:
                continue
            if capability.kind == "formatter":
                continue
            if capability.kind in {"report", "workflow"}:
                capabilities.append(capability)
                continue
            if capability.kind == "tool" and capability.owner.startswith("mcp_server:"):
                capabilities.append(capability)
        return sorted(capabilities, key=lambda item: item.capability_id)

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9_]+", text.lower().replace("-", " "))
            if token and token not in _STOP_WORDS
        }

    def _capability_tokens(self, capability: CapabilityPayload) -> set[str]:
        token_source = " ".join(
            [
                capability.capability_id.replace(".", " "),
                capability.display_name.replace("_", " "),
                capability.description,
                " ".join(capability.tags),
            ]
        )
        return self._tokens(token_source)

    @staticmethod
    def _display_phrase(value: str) -> str:
        return value.lower().replace("_", " ").replace(".", " ")

    @staticmethod
    def _match_reason(capability_id: str, overlap: list[str], exact_match: bool) -> str:
        details = f"matched terms {', '.join(overlap[:4])}" if overlap else "matched by phrase"
        if exact_match:
            details = f"{details}; exact phrase match"
        return f"{capability_id} {details}"

    @staticmethod
    def _quoted_entities(message: str) -> list[str]:
        return [match.strip() for match in re.findall(r'"([^"]+)"', message) if match.strip()]

    @staticmethod
    def _requests_cross_app(message_lower: str, mentioned_apps: list[str]) -> bool:
        if len(set(mentioned_apps)) > 1:
            return True
        if "all apps" in message_lower or "all applications" in message_lower:
            return True
        return any(hint in message_lower for hint in _COMPARE_HINTS) and "app" in message_lower

    def _missing_workflow_inputs(self, capability: CapabilityPayload, message: str) -> list[str]:
        if capability.app_id is None:
            return []
        _, _, workflow_id = capability.capability_id.split(".", 2)
        workflow = self.app_router.resolve(capability.app_id).domain_registry.get_workflow(workflow_id)
        message_tokens = self._tokens(message)
        missing: list[str] = []
        for field in workflow.required_fields:
            if field.lower() in message_tokens:
                continue
            field_tokens = self._tokens(field.replace("_", " "))
            if field_tokens and field_tokens.issubset(message_tokens):
                continue
            missing.append(field)
        return missing

    @staticmethod
    def _workflow_clarification_prompt(capability_id: str, missing_inputs: list[str]) -> str:
        missing_text = ", ".join(missing_inputs)
        return f"I can route this through '{capability_id}', but I still need: {missing_text}."

    def _supporting_report(
        self,
        selected: CapabilityCandidate,
        capability_candidates: list[CapabilityCandidate],
        capabilities: list[CapabilityPayload],
    ) -> CapabilityCandidate | None:
        if selected.app_id is None:
            return None
        selected_tokens = self._tokens(selected.capability_id.replace(".", " ").replace("_", " "))
        capability_map = {capability.capability_id: capability for capability in capabilities}
        for candidate in capability_candidates:
            if candidate.kind != "report" or candidate.app_id != selected.app_id:
                continue
            report = capability_map.get(candidate.capability_id)
            if report is None:
                continue
            report_tokens = self._capability_tokens(report)
            if not selected_tokens & report_tokens:
                continue
            if not report_tokens & _REPORT_SUPPORT_HINTS:
                continue
            return candidate
        return None

    @staticmethod
    def _decision(
        *,
        request_context: RequestContext,
        routing_plan_id: str,
        orchestration_mode: str,
        user_visible_reason: str,
        selected_capability_ids: list[str] | None = None,
        primary_capability_id: str | None = None,
        clarification_prompt: str | None = None,
        missing_inputs: list[str] | None = None,
        requires_approval: bool = False,
        approval_reason: str | None = None,
        audit_tags: list[str] | None = None,
    ) -> OrchestrationDecision:
        return OrchestrationDecision(
            decision_id=uuid.uuid4().hex,
            request_id=request_context.request_id,
            routing_plan_id=routing_plan_id,
            orchestration_mode=orchestration_mode,  # type: ignore[arg-type]
            selected_capability_ids=list(selected_capability_ids or []),
            primary_capability_id=primary_capability_id,
            clarification_prompt=clarification_prompt,
            missing_inputs=list(missing_inputs or []),
            requires_approval=requires_approval,
            approval_reason=approval_reason,
            formatter_id=request_context.channel_id,
            audit_tags=list(audit_tags or []),
            user_visible_reason=user_visible_reason,
        )
