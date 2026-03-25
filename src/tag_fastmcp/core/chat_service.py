from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tag_fastmcp.agent.clarification_agent import ClarificationAgent
from tag_fastmcp.agent.structured_chat_agent import StructuredChatAgent
from tag_fastmcp.models.contracts import ChatExecutionPlan, RoutingPayload, SQLResultPayload
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
    approvals: ApprovalService | None
    agent_lifecycle: AgentLifecycleService | None
    agent_factory: Callable[[str, str], ClarificationAgent] | None = None
    sql_planner_factory: Callable[[str, str], StructuredChatAgent] | None = None

    @staticmethod
    def _simple_runtime_message(feature_name: str) -> str:
        return (
            f"{feature_name} is unavailable in the simple runtime profile. "
            "Keep this service focused on app-scoped database chat, or switch to the platform profile "
            "if you need approvals, admin flows, or agent lifecycle features."
        )

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

    def _sql_planner(self) -> StructuredChatAgent:
        if self.sql_planner_factory is not None:
            return self.sql_planner_factory(self.settings.llm_base_url, self.settings.llm_model)
        return StructuredChatAgent(
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
    def _pending_sql_action(history: list[dict[str, Any]]) -> dict[str, Any] | None:
        pending: dict[str, Any] | None = None
        for event in history:
            event_type = event.get("type")
            if event_type == "pending_sql_action":
                pending = event
            elif event_type in {"pending_sql_cleared", "pending_sql_executed"}:
                pending = None
        return pending

    @staticmethod
    def _is_confirmation_message(message: str) -> bool:
        normalized = message.strip().lower()
        return normalized in {"confirm", "confirmed", "yes", "yes confirm", "ok", "okay", "proceed"}

    @staticmethod
    def _is_cancellation_message(message: str) -> bool:
        normalized = message.strip().lower()
        return normalized in {"cancel", "no", "stop", "do not", "don't", "dont"}

    @staticmethod
    def _sql_result_message(result: SQLResultPayload, *, intent: str) -> str:
        if intent == "read_query":
            if result.row_count == 0:
                return "I ran the query safely, but it returned no rows."
            preview = ChatService._preview_rows(result.rows_preview)
            base = f"I found {result.row_count} row{'s' if result.row_count != 1 else ''}."
            if preview:
                return f"{base} Preview: {preview}."
            return base
        return (
            f"I executed the {intent.replace('_', ' ')} successfully on "
            f"{', '.join(result.policy.tables)} and affected {result.row_count} row"
            f"{'s' if result.row_count != 1 else ''}."
        )

    async def _execute_sql_plan(
        self,
        *,
        session_id: str,
        app_id: str,
        sql: str,
        allow_mutations: bool,
        intent: str,
    ) -> tuple[str, dict[str, Any]]:
        app_ctx = self.app_router.resolve(app_id)
        policy = app_ctx.sql_policy.validate(
            sql,
            allow_mutations_override=allow_mutations,
        )
        if not policy.allowed:
            return (
                f"I could not run that safely: {policy.reason}",
                {
                    "raw_error": policy.reason,
                    "proposed_sql": sql,
                    "selected_capability_id": "chat.generated_sql",
                    "selected_capability_ids": ["chat.generated_sql"],
                },
            )

        result = await app_ctx.query_engine.execute_sql(sql, policy)
        await self.session_store.set_last_query(session_id, result.query)
        await self.session_store.append_event(
            session_id,
            {
                "type": "sql",
                "query": result.query,
                "row_count": result.row_count,
                "app_id": app_id,
            },
        )
        return (
            self._sql_result_message(result, intent=intent),
            {
                "query": result.query,
                "row_count": result.row_count,
                "rows_preview": result.rows_preview,
                "sql_result": result.model_dump(mode="json"),
                "selected_capability_id": "chat.generated_sql",
                "selected_capability_ids": ["chat.generated_sql"],
            },
        )

    async def _handle_answer_only_plan(
        self,
        *,
        snapshot: Any,
        app_id: str,
        session_id: str,
        message: str,
        render_payload: dict[str, Any],
    ) -> tuple[str, str | None, dict[str, Any], str | None]:
        app_ctx = self.app_router.resolve(app_id)
        history = self._history_for_agent(snapshot.history)
        plan = await self._sql_planner().plan(app_ctx, message, history=history or None)
        render_payload["chat_execution_plan"] = plan.model_dump(mode="json")

        if plan.intent == "read_query" and plan.proposed_sql:
            reply, sql_payload = await self._execute_sql_plan(
                session_id=session_id,
                app_id=app_id,
                sql=plan.proposed_sql,
                allow_mutations=False,
                intent=plan.intent,
            )
            render_payload.update(sql_payload)
            return reply, "routing", render_payload, plan.intent

        if plan.intent in {"insert", "update"} and plan.proposed_sql:
            await self.session_store.append_event(
                session_id,
                {
                    "type": "pending_sql_action",
                    "app_id": app_id,
                    "intent": plan.intent,
                    "sql": plan.proposed_sql,
                    "confirmation_message": plan.confirmation_message,
                },
            )
            render_payload.update(
                {
                    "proposed_sql": plan.proposed_sql,
                    "selected_capability_id": "chat.generated_sql",
                    "selected_capability_ids": ["chat.generated_sql"],
                }
            )
            reply = (
                plan.confirmation_message
                or "I prepared a safe database change. Reply 'confirm' to run it or 'cancel' to stop."
            )
            return reply, "clarification", render_payload, plan.intent

        if plan.intent == "clarify":
            reply = plan.clarification_question or "I need a bit more detail before I can do that safely."
            return reply, "clarification", render_payload, plan.intent

        if plan.intent == "reject":
            reply = plan.answer or "I can't execute that request safely."
            return reply, "rejection", render_payload, plan.intent

        if plan.intent == "manual_answer" and plan.answer:
            return plan.answer, "answer", render_payload, plan.intent

        reply = await self._agent().chat(app_ctx, message, history=history or None)
        return reply, None, render_payload, plan.intent

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
        snapshot = await self.session_store.ensure(session_id, actor_id=request_context.actor_id)
        await self.session_store.bind_scope(
            session_id,
            app_id=app_id,
            tenant_id=request_context.tenant_id,
            execution_mode=request_context.execution_mode,
        )
        agent_selection = self.agent_registry.select_agent(request_context, policy_envelope)
        pending_sql_action = self._pending_sql_action(snapshot.history)
        direct_response_ready = False
        if pending_sql_action is not None:
            if self._is_confirmation_message(message):
                reply, render_payload = await self._execute_sql_plan(
                    session_id=session_id,
                    app_id=app_id,
                    sql=str(pending_sql_action.get("sql") or ""),
                    allow_mutations=True,
                    intent=str(pending_sql_action.get("intent") or "update"),
                )
                await self.session_store.append_event(
                    session_id,
                    {
                        "type": "pending_sql_executed",
                        "app_id": app_id,
                        "sql": pending_sql_action.get("sql"),
                    },
                )
                render_route = "routing"
                chat_plan_intent = str(pending_sql_action.get("intent") or "confirm")
                planning = None
                compiled = None
                all_warnings: list[str] = []
                fallback_used = False
                fallback_capability_id: str | None = None
                last_routing: RoutingPayload | None = None
                approval_state = "none"
                escalation_state = "none"
                approval_id = None
                approval_status = None
                approval_scope_type = None
                proposal_id = None
                proposal_status = None
                render_payload.update(
                    {
                        "confirmed_pending_sql": True,
                    }
                )
                direct_response_ready = True
            elif self._is_cancellation_message(message):
                reply = "Cancelled the pending database change."
                await self.session_store.append_event(
                    session_id,
                    {
                        "type": "pending_sql_cleared",
                        "app_id": app_id,
                        "sql": pending_sql_action.get("sql"),
                    },
                )
                render_route = "clarification"
                render_payload = {
                    "selected_capability_ids": ["chat.generated_sql"],
                    "allowed_app_ids": list(policy_envelope.allowed_app_ids),
                    "cancelled_pending_sql": True,
                }
                planning = None
                compiled = None
                all_warnings = []
                fallback_used = False
                fallback_capability_id = None
                last_routing = None
                approval_state = "none"
                escalation_state = "none"
                approval_id = None
                approval_status = None
                approval_scope_type = None
                proposal_id = None
                proposal_status = None
                chat_plan_intent = "cancel"
                direct_response_ready = True
            else:
                planning, compiled = self.orchestration.plan_message(
                    request_context=request_context,
                    policy_envelope=policy_envelope,
                    user_message=message,
                )
                render_payload = {
                    "selected_capability_ids": list(compiled.orchestration_decision.selected_capability_ids),
                    "allowed_app_ids": list(policy_envelope.allowed_app_ids),
                    "reasoning_summary": compiled.routing_plan.reasoning_summary,
                }
                all_warnings = []
                fallback_used = False
                fallback_capability_id = None
                last_routing = None
                render_route = None
                approval_state = "none"
                escalation_state = "requested" if compiled.orchestration_decision.orchestration_mode == "heavy_agent" else "none"
                approval_id = None
                approval_status = None
                approval_scope_type = None
                proposal_id = None
                proposal_status = None
                chat_plan_intent = None
        else:
            planning, compiled = self.orchestration.plan_message(
                request_context=request_context,
                policy_envelope=policy_envelope,
                user_message=message,
            )
            render_payload = {
                "selected_capability_ids": list(compiled.orchestration_decision.selected_capability_ids),
                "allowed_app_ids": list(policy_envelope.allowed_app_ids),
                "reasoning_summary": compiled.routing_plan.reasoning_summary,
            }
            all_warnings = []
            fallback_used = False
            fallback_capability_id = None
            last_routing = None
            render_route = None
            approval_state = "none"
            escalation_state = "requested" if compiled.orchestration_decision.orchestration_mode == "heavy_agent" else "none"
            approval_id = None
            approval_status = None
            approval_scope_type = None
            proposal_id = None
            proposal_status = None
            chat_plan_intent = None
        if compiled is not None and compiled.orchestration_decision.orchestration_mode == "proposal":
            if self.agent_lifecycle is None:
                reply = self._simple_runtime_message("Agent proposal workflows")
                render_route = "answer"
            else:
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
        elif compiled is not None and compiled.orchestration_decision.requires_approval:
            if self.approvals is None:
                reply = self._simple_runtime_message("Approval workflows")
                render_route = "answer"
            else:
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
        elif compiled is not None and compiled.execution_requests:
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
        elif compiled is not None and compiled.orchestration_decision.clarification_prompt:
            reply = compiled.orchestration_decision.clarification_prompt
        elif compiled is not None and compiled.orchestration_decision.orchestration_mode == "answer_only":
            reply, render_route, render_payload, chat_plan_intent = await self._handle_answer_only_plan(
                snapshot=snapshot,
                app_id=app_id,
                session_id=session_id,
                message=message,
                render_payload=render_payload,
            )
        elif direct_response_ready:
            pass
        elif compiled is not None:
            reply = compiled.orchestration_decision.user_visible_reason
        else:
            reply = "I couldn't continue that request."

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
                compiled_orchestration_mode=compiled.orchestration_decision.orchestration_mode if compiled is not None else "answer_only",
                clarification_prompt=compiled.orchestration_decision.clarification_prompt if compiled is not None else None,
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
                "routing_plan_id": compiled.routing_plan.plan_id if compiled is not None else None,
                "execution_mode": request_context.execution_mode,
                "agent_id": agent_selection.agent_id,
                "agent_kind": agent_selection.agent_kind,
                "planning_request_id": planning.planning_input.request_id if planning is not None else None,
                "intent_family": planning.intent_analysis.intent_family if planning is not None else None,
                "orchestration_decision_id": compiled.orchestration_decision.decision_id if compiled is not None else None,
                "orchestration_mode": compiled.orchestration_decision.orchestration_mode if compiled is not None else "answer_only",
                "selected_capability_ids": list(compiled.orchestration_decision.selected_capability_ids) if compiled is not None else [],
                "primary_capability_id": compiled.orchestration_decision.primary_capability_id if compiled is not None else "chat.generated_sql",
                "approval_id": approval_id,
                "approval_status": approval_status,
                "approval_scope_type": approval_scope_type,
                "proposal_id": proposal_id,
                "proposal_status": proposal_status,
                "chat_plan_intent": chat_plan_intent,
                "visibility_profile_id": rendered.visibility_profile.profile_id,
                "formatter_id": rendered.formatter_input.formatter_id,
                "channel_id": rendered.formatter_input.channel_id,
                "response_state": rendered.channel_response.state.status,
                "primary_mode": rendered.channel_response.primary_mode,
            },
        )
