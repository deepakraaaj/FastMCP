from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tag_fastmcp.agent.clarification_agent import ClarificationAgent
from tag_fastmcp.models.contracts import RoutingPayload
from tag_fastmcp.models.http_api import WidgetChatResult, WidgetUserContext

if False:  # pragma: no cover
    from tag_fastmcp.core.agent_lifecycle_service import AgentLifecycleService
    from tag_fastmcp.core.agent_registry import AgentRegistry
    from tag_fastmcp.core.approval_service import ApprovalService
    from tag_fastmcp.core.app_router import AppRouter
    from tag_fastmcp.core.formatter_service import FormatterService
    from tag_fastmcp.core.orchestration_service import OrchestrationService
    from tag_fastmcp.core.policy_envelope import PolicyEnvelopeService
    from tag_fastmcp.core.request_context import RequestContextService
    from tag_fastmcp.core.session_store import SessionStore
    from tag_fastmcp.settings import AppSettings


@dataclass
class ChatService:
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
    def _actor_id(user_context: WidgetUserContext | None) -> str | None:
        if user_context is None:
            return None
        return (
            user_context.user_id
            or user_context.user_name
            or user_context.company_id
            or user_context.company_name
        )

    @staticmethod
    def _tenant_id(user_context: WidgetUserContext | None) -> str | None:
        if user_context is None:
            return None
        return user_context.company_id or None

    @staticmethod
    def _context_message(user_context: WidgetUserContext) -> str:
        payload = {
            "user_id": user_context.user_id,
            "user_name": user_context.user_name,
            "company_id": user_context.company_id,
            "company_name": user_context.company_name,
        }
        return f"Current widget user context: {json.dumps(payload, sort_keys=True)}"

    @staticmethod
    def _request_metadata(user_context: WidgetUserContext | None) -> dict[str, Any]:
        if user_context is None:
            return {}
        return {
            "user_id": user_context.user_id,
            "user_name": user_context.user_name,
            "company_id": user_context.company_id,
            "company_name": user_context.company_name,
        }

    def _agent(self) -> ClarificationAgent:
        if self.agent_factory is not None:
            return self.agent_factory(self.settings.llm_base_url, self.settings.llm_model)
        return ClarificationAgent(
            base_url=self.settings.llm_base_url,
            model_name=self.settings.llm_model,
        )

    def _history_for_agent(
        self,
        history: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for event in history:
            event_type = event.get("type")
            if event_type == "chat_context":
                content = str(event.get("content") or "").strip()
                if content:
                    messages.append({"role": "system", "content": content})
                continue
            if event_type != "chat_message":
                continue
            role = str(event.get("role") or "").strip()
            content = str(event.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        return messages

    @staticmethod
    def _preview_rows(rows: list[dict[str, Any]]) -> str:
        previews: list[str] = []
        for row in rows[:2]:
            cells = ", ".join(f"{key}={value}" for key, value in row.items())
            if cells:
                previews.append(cells)
        return " | ".join(previews)

    def _message_from_routings(self, routings: list[RoutingPayload]) -> str:
        step_messages: list[str] = []
        for index, routing in enumerate(routings, start=1):
            output = routing.output if isinstance(routing.output, dict) else {}
            if "report" in output:
                report = output["report"]
                base = (
                    f"I ran report '{report['report_name']}' and found {report['row_count']} rows."
                )
                preview = self._preview_rows(report.get("rows_preview") or [])
                if preview:
                    base = f"{base} Preview: {preview}."
            elif "workflow" in output:
                workflow = output["workflow"]
                base = str(output.get("message") or f"Workflow '{workflow['workflow_id']}' updated.")
                missing = workflow.get("missing_fields") or []
                if missing and "need" not in base.lower():
                    base = f"{base} Still needed: {', '.join(missing)}."
            else:
                base = str(output.get("message") or f"Capability '{routing.selected_capability_id}' executed.")
            if len(routings) > 1:
                base = f"Step {index}: {base}"
            step_messages.append(base)
        return "\n\n".join(step_messages)

    @staticmethod
    def _route_name(
        *,
        compiled_orchestration_mode: str,
        clarification_prompt: str | None,
        last_routing: RoutingPayload | None,
    ) -> str:
        if clarification_prompt:
            return "clarification"
        if compiled_orchestration_mode == "reject":
            return "rejection"
        if compiled_orchestration_mode == "heavy_agent":
            return "escalation"
        if last_routing is None:
            return "answer"
        if last_routing.capability_kind == "report":
            return "report"
        if last_routing.capability_kind == "workflow":
            return "workflow"
        return "routing"

    async def start_session(
        self,
        *,
        requested_app_id: str | None,
        user_context: WidgetUserContext | None,
    ) -> tuple[str, str]:
        request_context = await self.request_contexts.build(
            execution_mode="app_chat",
            origin="widget_http",
            requested_app_id=requested_app_id,
            actor_id=self._actor_id(user_context),
            auth_subject=self._actor_id(user_context),
            tenant_id=self._tenant_id(user_context),
            role="end_user",
            metadata=self._request_metadata(user_context),
        )
        policy_envelope = self.policy_envelopes.derive(request_context)
        app_id = policy_envelope.primary_app_id
        if app_id is None:
            raise ValueError("A widget session requires one resolved application scope.")

        session = await self.session_store.start_session(actor_id=request_context.actor_id)
        await self.session_store.bind_scope(
            session.session_id,
            app_id=app_id,
            tenant_id=request_context.tenant_id,
            execution_mode=request_context.execution_mode,
        )
        if user_context is not None:
            await self.session_store.append_event(
                session.session_id,
                {
                    "type": "chat_context",
                    "content": self._context_message(user_context),
                    "app_id": app_id,
                },
            )
        return session.session_id, app_id

    async def chat(
        self,
        *,
        session_id: str,
        message: str,
        requested_app_id: str | None,
        user_context: WidgetUserContext | None,
    ) -> WidgetChatResult:
        request_context = await self.request_contexts.build(
            execution_mode="app_chat",
            origin="widget_http",
            requested_app_id=requested_app_id,
            session_id=session_id,
            actor_id=self._actor_id(user_context),
            auth_subject=self._actor_id(user_context),
            tenant_id=self._tenant_id(user_context),
            role="end_user",
            metadata=self._request_metadata(user_context),
        )
        policy_envelope = self.policy_envelopes.derive(request_context)
        app_id = policy_envelope.primary_app_id
        if app_id is None:
            raise ValueError("A widget chat request requires one resolved application scope.")
        agent_selection = self.agent_registry.select_agent(request_context, policy_envelope)
        planning, compiled = self.orchestration.plan_message(
            request_context=request_context,
            policy_envelope=policy_envelope,
            user_message=message,
        )

        snapshot = await self.session_store.ensure(session_id, actor_id=request_context.actor_id)
        await self.session_store.bind_scope(
            session_id,
            app_id=app_id,
            tenant_id=request_context.tenant_id,
            execution_mode=request_context.execution_mode,
        )
        all_warnings: list[str] = []
        fallback_used = False
        fallback_capability_id: str | None = None
        last_routing: RoutingPayload | None = None
        render_route: str | None = None
        render_payload: dict[str, Any] = {
            "selected_capability_ids": list(compiled.orchestration_decision.selected_capability_ids),
            "allowed_app_ids": list(policy_envelope.allowed_app_ids),
            "reasoning_summary": compiled.routing_plan.reasoning_summary,
        }
        approval_state = "none"
        escalation_state = "requested" if compiled.orchestration_decision.orchestration_mode == "heavy_agent" else "none"
        approval_id: str | None = None
        approval_status: str | None = None
        approval_scope_type: str | None = None
        proposal_id: str | None = None
        proposal_status: str | None = None
        if compiled.orchestration_decision.orchestration_mode == "proposal":
            pending_proposal = await self.agent_lifecycle.create_proposal_draft(
                request_context=request_context,
                policy_envelope=policy_envelope,
                planning=planning,
                compiled=compiled,
                user_message=message,
            )
            reply = pending_proposal.user_visible_message
            render_route = "approval"
            approval_state = "pending"
            approval_id = pending_proposal.approval_request.approval_id
            approval_status = pending_proposal.approval_request.status
            approval_scope_type = pending_proposal.approval_request.scope_type
            proposal_id = pending_proposal.proposal_draft.proposal_id
            proposal_status = pending_proposal.proposal_draft.status
            render_payload.update(
                {
                    "approval": pending_proposal.approval_request.model_dump(mode="json"),
                    "proposal": pending_proposal.proposal_draft.model_dump(mode="json"),
                }
            )
        elif compiled.orchestration_decision.requires_approval:
            pending_execution = await self.approvals.request_execution_approval(
                request_context=request_context,
                policy_envelope=policy_envelope,
                routing_plan=compiled.routing_plan,
                orchestration_decision=compiled.orchestration_decision,
                execution_requests=compiled.execution_requests,
            )
            reply = pending_execution.user_visible_message
            render_route = "approval"
            approval_state = "pending"
            approval_id = pending_execution.approval_request.approval_id
            approval_status = pending_execution.approval_request.status
            approval_scope_type = pending_execution.approval_request.scope_type
            render_payload.update(
                {
                    "approval": pending_execution.approval_request.model_dump(mode="json"),
                    "approval_payload": pending_execution.approval_payload.model_dump(mode="json"),
                    "paused_execution": pending_execution.paused_execution.model_dump(mode="json"),
                }
            )
        elif compiled.execution_requests:
            routings: list[RoutingPayload] = []
            for execution_request in compiled.execution_requests:
                routings.append(
                    await self.orchestration.capability_router.invoke(
                        execution_request,
                        session_id=session_id,
                        request_context=request_context,
                        policy_envelope=policy_envelope,
                        routing_plan=compiled.routing_plan,
                    )
            )
            all_warnings = [warning for routing in routings for warning in routing.warnings]
            fallback_used = any(routing.fallback_used for routing in routings)
            fallback_capability_id = next(
                (routing.fallback_capability_id for routing in reversed(routings) if routing.fallback_capability_id),
                None,
            )
            last_routing = routings[-1]
            reply = self._message_from_routings(routings)
            render_payload.update(last_routing.model_dump(mode="json"))
        elif compiled.orchestration_decision.clarification_prompt:
            reply = compiled.orchestration_decision.clarification_prompt
        elif compiled.orchestration_decision.orchestration_mode == "answer_only":
            history = self._history_for_agent(snapshot.history)
            app_ctx = self.app_router.resolve(app_id)
            reply = await self._agent().chat(app_ctx, message, history=history or None)
        else:
            reply = compiled.orchestration_decision.user_visible_reason

        await self.session_store.append_event(
            session_id,
            {
                "type": "chat_message",
                "role": "user",
                "content": message,
                "app_id": app_id,
            },
        )
        await self.session_store.append_event(
            session_id,
            {
                "type": "chat_message",
                "role": "assistant",
                "content": reply,
                "app_id": app_id,
            },
        )
        rendered = self.formatter_service.render(
            request_context=request_context,
            policy_envelope=policy_envelope,
            route=render_route
            or self._route_name(
                compiled_orchestration_mode=compiled.orchestration_decision.orchestration_mode,
                clarification_prompt=compiled.orchestration_decision.clarification_prompt,
                last_routing=last_routing,
            ),
            primary_message=reply,
            execution_payload=render_payload,
            warnings=all_warnings,
            fallback_used=fallback_used,
            fallback_capability_id=fallback_capability_id,
            approval_state=approval_state,
            escalation_state=escalation_state,
            trace_id=request_context.trace_id,
        )

        return WidgetChatResult(
            session_id=session_id,
            app_id=app_id,
            message=reply,
            channel_response=rendered.channel_response,
            metadata={
                "app_id": app_id,
                "session_id": session_id,
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
                "routing_plan_id": compiled.routing_plan.plan_id,
                "execution_mode": request_context.execution_mode,
                "agent_id": agent_selection.agent_id,
                "agent_kind": agent_selection.agent_kind,
                "planning_request_id": planning.planning_input.request_id,
                "intent_family": planning.intent_analysis.intent_family,
                "orchestration_decision_id": compiled.orchestration_decision.decision_id,
                "orchestration_mode": compiled.orchestration_decision.orchestration_mode,
                "selected_capability_ids": list(compiled.orchestration_decision.selected_capability_ids),
                "primary_capability_id": compiled.orchestration_decision.primary_capability_id,
                "approval_id": approval_id,
                "approval_status": approval_status,
                "approval_scope_type": approval_scope_type,
                "proposal_id": proposal_id,
                "proposal_status": proposal_status,
                "visibility_profile_id": rendered.visibility_profile.profile_id,
                "formatter_id": rendered.formatter_input.formatter_id,
                "channel_id": rendered.formatter_input.channel_id,
                "response_state": rendered.channel_response.state.status,
                "primary_mode": rendered.channel_response.primary_mode,
            },
        )
