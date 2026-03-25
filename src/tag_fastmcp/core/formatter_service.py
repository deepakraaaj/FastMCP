from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from tag_fastmcp.core.capability_registry import CapabilityRegistry
from tag_fastmcp.core.visibility_policy import VisibilityPolicyService
from tag_fastmcp.models.contracts import (
    ChannelAction,
    ChannelResponse,
    FormatterInput,
    OutputBlock,
    PolicyEnvelope,
    RegistryChannelPayload,
    RequestContext,
    ResponseState,
    VisibilityProfile,
)


@dataclass
class RenderedResponse:
    visibility_profile: VisibilityProfile
    formatter_input: FormatterInput
    channel_response: ChannelResponse


@dataclass
class FormatterService:
    capability_registry: CapabilityRegistry
    visibility_policy: VisibilityPolicyService

    def render(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        route: str,
        primary_message: str,
        execution_payload: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        fallback_used: bool = False,
        fallback_capability_id: str | None = None,
        approval_state: str = "none",
        escalation_state: str = "none",
        available_actions: list[str] | None = None,
        trace_id: str | None = None,
        channel_id: str | None = None,
    ) -> RenderedResponse:
        visibility = self.visibility_policy.derive(
            request_context=request_context,
            policy_envelope=policy_envelope,
        )
        resolved_channel_id, channel = self._channel(channel_id, policy_envelope)
        formatter_id = channel.formatter.formatter_id if channel else "text.fallback"
        formatter_input = FormatterInput(
            request_id=request_context.request_id,
            trace_id=trace_id,
            channel_id=resolved_channel_id,
            formatter_id=formatter_id,
            execution_mode=request_context.execution_mode,
            visibility_profile_id=visibility.profile_id,
            route=route,  # type: ignore[arg-type]
            primary_message=primary_message,
            execution_payload=dict(execution_payload or {}),
            warnings=list(warnings or []),
            fallback_used=fallback_used,
            fallback_capability_id=fallback_capability_id,
            approval_state=approval_state,  # type: ignore[arg-type]
            escalation_state=escalation_state,  # type: ignore[arg-type]
            available_actions=list(available_actions or []),
        )
        channel_response = self._format(formatter_input, visibility, channel)
        return RenderedResponse(
            visibility_profile=visibility,
            formatter_input=formatter_input,
            channel_response=channel_response,
        )

    def _format(
        self,
        formatter_input: FormatterInput,
        visibility: VisibilityProfile,
        channel: RegistryChannelPayload | None,
    ) -> ChannelResponse:
        output_modes = list(channel.output_modes) if channel else ["text"]
        primary_mode = self._primary_mode(formatter_input, visibility, output_modes)
        blocks = self._blocks(formatter_input, primary_mode)
        actions = self._actions(formatter_input, visibility)
        state = self._state(formatter_input, visibility)
        diagnostics = self._diagnostics(formatter_input, visibility)

        return ChannelResponse(
            response_id=uuid.uuid4().hex,
            channel_id=formatter_input.channel_id,
            formatter_id=formatter_input.formatter_id,
            primary_mode=primary_mode,  # type: ignore[arg-type]
            blocks=blocks,
            actions=actions,
            state=state,
            diagnostics=diagnostics,
        )

    def _channel(
        self,
        channel_id: str | None,
        policy_envelope: PolicyEnvelope,
    ) -> tuple[str, RegistryChannelPayload | None]:
        registry = self.capability_registry.describe(app_id=policy_envelope.primary_app_id)
        channels = {
            channel.channel_id: channel
            for channel in registry.channels
            if channel.channel_id in policy_envelope.allowed_channel_ids
        }

        resolved_channel_id = channel_id
        if resolved_channel_id is None:
            if "web_chat" in channels:
                resolved_channel_id = "web_chat"
            elif len(channels) == 1:
                resolved_channel_id = next(iter(channels))

        if resolved_channel_id and resolved_channel_id in channels:
            return resolved_channel_id, channels[resolved_channel_id]
        return "text_fallback", None

    @staticmethod
    def _primary_mode(
        formatter_input: FormatterInput,
        visibility: VisibilityProfile,
        output_modes: list[str],
    ) -> str:
        if formatter_input.route in {"escalation", "approval"} and "card" in output_modes:
            return "card"
        if (
            formatter_input.route in {"report", "routing"}
            and visibility.execution_mode == "admin_chat"
            and "dashboard" in output_modes
        ):
            return "dashboard"
        if formatter_input.route in {"report", "workflow", "rejection", "clarification"} and "card" in output_modes:
            return "card"
        if "text" in output_modes:
            return "text"
        return output_modes[0] if output_modes else "text"

    def _blocks(
        self,
        formatter_input: FormatterInput,
        primary_mode: str,
    ) -> list[OutputBlock]:
        blocks = [
            OutputBlock(
                block_id=uuid.uuid4().hex,
                kind="text",
                body=formatter_input.primary_message,
            )
        ]
        payload = formatter_input.execution_payload

        if formatter_input.route == "report" and primary_mode != "text":
            report = payload.get("report") or payload.get("output", {}).get("report")
            if isinstance(report, dict):
                blocks.append(
                    OutputBlock(
                        block_id=uuid.uuid4().hex,
                        kind="table",
                        title=report.get("report_name"),
                        data={
                            "row_count": report.get("row_count"),
                            "rows_preview": report.get("rows_preview") or [],
                        },
                    )
                )

        if formatter_input.route == "routing" and primary_mode != "text":
            sql_result = payload.get("sql_result")
            if isinstance(sql_result, dict):
                blocks.append(
                    OutputBlock(
                        block_id=uuid.uuid4().hex,
                        kind="table",
                        title="Query Result",
                        data={
                            "row_count": sql_result.get("row_count"),
                            "rows_preview": sql_result.get("rows_preview") or [],
                        },
                    )
                )

        if formatter_input.route == "workflow":
            workflow = payload.get("workflow") or payload.get("output", {}).get("workflow")
            if isinstance(workflow, dict):
                blocks.append(
                    OutputBlock(
                        block_id=uuid.uuid4().hex,
                        kind="checklist" if workflow.get("state") == "pending" else "status",
                        title=workflow.get("workflow_id"),
                        data={
                            "state": workflow.get("state"),
                            "missing_fields": workflow.get("missing_fields") or [],
                            "collected_data": workflow.get("collected_data") or {},
                            "next_prompt": workflow.get("next_prompt"),
                        },
                    )
                )

        if formatter_input.route == "rejection":
            blocks.append(
                OutputBlock(
                    block_id=uuid.uuid4().hex,
                    kind="status",
                    title="Blocked",
                    data={"reason": formatter_input.primary_message},
                )
            )

        if formatter_input.route == "escalation":
            blocks.append(
                OutputBlock(
                    block_id=uuid.uuid4().hex,
                    kind="escalation",
                    title="Escalation",
                    data={"state": formatter_input.escalation_state},
                )
            )

        if formatter_input.approval_state != "none":
            blocks.append(
                OutputBlock(
                    block_id=uuid.uuid4().hex,
                    kind="approval",
                    title="Approval",
                    data={"state": formatter_input.approval_state},
                )
            )

        if formatter_input.warnings or formatter_input.fallback_used:
            blocks.append(
                OutputBlock(
                    block_id=uuid.uuid4().hex,
                    kind="status",
                    title="Execution Status",
                    data={
                        "warnings": formatter_input.warnings,
                        "fallback_used": formatter_input.fallback_used,
                        "fallback_capability_id": formatter_input.fallback_capability_id,
                    },
                )
            )

        return blocks

    @staticmethod
    def _actions(
        formatter_input: FormatterInput,
        visibility: VisibilityProfile,
    ) -> list[ChannelAction]:
        if not visibility.show_actions:
            return []

        label_map = {
            "continue_workflow": "Continue Workflow",
            "approve": "Approve",
            "reject": "Reject",
            "retry": "Retry",
            "open_details": "Open Details",
            "open_dashboard": "Open Dashboard",
        }
        actions = [
            ChannelAction(
                action_id=uuid.uuid4().hex,
                kind=action,  # type: ignore[arg-type]
                label=label_map.get(action, action.replace("_", " ").title()),
                enabled=True,
                payload={"request_id": formatter_input.request_id},
            )
            for action in formatter_input.available_actions
        ]
        if not actions and formatter_input.route == "workflow":
            workflow = formatter_input.execution_payload.get("workflow") or formatter_input.execution_payload.get("output", {}).get("workflow")
            if isinstance(workflow, dict) and workflow.get("state") == "pending":
                actions.append(
                    ChannelAction(
                        action_id=uuid.uuid4().hex,
                        kind="continue_workflow",
                        label="Continue Workflow",
                        enabled=True,
                        payload={"request_id": formatter_input.request_id},
                    )
                )
        return actions

    @staticmethod
    def _state(
        formatter_input: FormatterInput,
        visibility: VisibilityProfile,
    ) -> ResponseState:
        status = "ok"
        if formatter_input.approval_state in {"required", "pending"}:
            status = "approval_required"
        elif formatter_input.route == "escalation":
            status = "escalated"
        elif formatter_input.route == "rejection":
            status = "blocked"
        elif formatter_input.fallback_used or formatter_input.warnings:
            status = "degraded"
        elif formatter_input.route == "workflow":
            workflow = formatter_input.execution_payload.get("workflow") or formatter_input.execution_payload.get("output", {}).get("workflow")
            if isinstance(workflow, dict) and workflow.get("state") == "pending":
                status = "pending"

        if visibility.show_raw_errors or visibility.show_sql_text or visibility.show_trace_id:
            detail_level = "diagnostic"
        elif visibility.show_capability_ids or visibility.show_plan_summary:
            detail_level = "standard"
        else:
            detail_level = "minimal"

        return ResponseState(
            status=status,  # type: ignore[arg-type]
            user_visible_reason=formatter_input.primary_message,
            detail_level=detail_level,  # type: ignore[arg-type]
        )

    @staticmethod
    def _diagnostics(
        formatter_input: FormatterInput,
        visibility: VisibilityProfile,
    ) -> dict[str, Any]:
        diagnostics: dict[str, Any] = {}
        payload = formatter_input.execution_payload

        if visibility.show_plan_summary and payload.get("reasoning_summary"):
            diagnostics["plan_summary"] = payload["reasoning_summary"]
        if visibility.show_capability_ids:
            selected = payload.get("selected_capability_id")
            if selected:
                diagnostics["selected_capability_id"] = selected
            selected_capability_ids = payload.get("selected_capability_ids")
            if selected_capability_ids:
                diagnostics["selected_capability_ids"] = list(selected_capability_ids)
        if visibility.show_app_scope and payload.get("allowed_app_ids"):
            diagnostics["allowed_app_ids"] = list(payload["allowed_app_ids"])
        if visibility.show_sql_text:
            sql_text = FormatterService._sql_text(payload)
            if sql_text:
                diagnostics["sql_text"] = sql_text
        if visibility.show_trace_id and formatter_input.trace_id:
            diagnostics["trace_id"] = formatter_input.trace_id
        if visibility.show_retry_and_fallback:
            diagnostics["warnings"] = list(formatter_input.warnings)
            diagnostics["fallback_used"] = formatter_input.fallback_used
            diagnostics["fallback_capability_id"] = formatter_input.fallback_capability_id
        if visibility.show_approval_metadata and formatter_input.approval_state != "none":
            diagnostics["approval_state"] = formatter_input.approval_state
        if visibility.show_escalation_metadata and formatter_input.escalation_state != "none":
            diagnostics["escalation_state"] = formatter_input.escalation_state
        if visibility.show_raw_errors and payload.get("raw_error"):
            diagnostics["raw_error"] = payload["raw_error"]
        return diagnostics

    @staticmethod
    def _sql_text(payload: dict[str, Any]) -> str | None:
        if "query" in payload:
            return str(payload["query"])
        if "proposed_sql" in payload:
            return str(payload["proposed_sql"])
        sql_result = payload.get("sql_result")
        if isinstance(sql_result, dict) and sql_result.get("query"):
            return str(sql_result["query"])
        report = payload.get("report") or payload.get("output", {}).get("report")
        if isinstance(report, dict) and report.get("query"):
            return str(report["query"])
        return None
