from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from fastmcp import Client, FastMCP

from tag_fastmcp.core.circuit_breaker import CircuitBreakerService
from tag_fastmcp.models.app_config import AppsRegistry
from tag_fastmcp.models.contracts import (
    CapabilityPayload,
    InvokeCapabilityRequest,
    RoutingPayload,
)

if False:  # pragma: no cover
    from tag_fastmcp.core.app_router import AppRouter
    from tag_fastmcp.core.capability_registry import CapabilityRegistry
    from tag_fastmcp.core.session_store import SessionStore


@dataclass
class _SelectionResult:
    capability: CapabilityPayload
    selection_mode: str
    selection_reason: str


class CapabilityRouter:
    def __init__(
        self,
        *,
        app_router: AppRouter,
        capability_registry: CapabilityRegistry,
        apps_registry: AppsRegistry,
        session_store: SessionStore,
        circuit_breakers: CircuitBreakerService,
        target_resolver: Callable[[str, str], FastMCP | str],
    ) -> None:
        self.app_router = app_router
        self.capability_registry = capability_registry
        self.apps_registry = apps_registry
        self.session_store = session_store
        self.circuit_breakers = circuit_breakers
        self.target_resolver = target_resolver

    async def invoke(self, request: InvokeCapabilityRequest, session_id: str | None) -> RoutingPayload:
        return await self._invoke(request, session_id=session_id, attempted_fallbacks=set())

    async def _invoke(
        self,
        request: InvokeCapabilityRequest,
        *,
        session_id: str | None,
        attempted_fallbacks: set[str],
    ) -> RoutingPayload:
        registry = self.capability_registry.describe(app_id=request.app_id)
        selection = self._select(registry.capabilities, request)
        formatter_id = self._formatter_id(registry.channels, request.channel_id)

        if selection.capability.execution.requires_session and session_id is None:
            raise ValueError("session_id is required for the selected capability.")

        if selection.capability.kind == "report":
            if session_id is None:
                raise ValueError("session_id is required for report execution.")
            output = await self._run_report(selection.capability, request, session_id)
            return RoutingPayload(
                selected_capability_id=selection.capability.capability_id,
                capability_kind=selection.capability.kind,
                selection_mode=selection.selection_mode,  # type: ignore[arg-type]
                selection_reason=selection.selection_reason,
                channel_id=request.channel_id,
                formatter_id=formatter_id,
                downstream_route=output.get("route"),
                downstream_status=output.get("status"),
                attempts=1,
                output=output,
            )

        if selection.capability.kind == "workflow":
            if session_id is None:
                raise ValueError("session_id is required for workflow execution.")
            output = await self._run_workflow(selection.capability, request, session_id)
            return RoutingPayload(
                selected_capability_id=selection.capability.capability_id,
                capability_kind=selection.capability.kind,
                selection_mode=selection.selection_mode,  # type: ignore[arg-type]
                selection_reason=selection.selection_reason,
                channel_id=request.channel_id,
                formatter_id=formatter_id,
                downstream_route=output.get("route"),
                downstream_status=output.get("status"),
                attempts=1,
                output=output,
            )

        server_id, tool_name = self._external_tool_parts(selection.capability.capability_id)
        output, attempts, circuit_state = await self._run_external_tool(server_id, tool_name, request)
        warnings: list[str] = []
        fallback_used = False
        fallback_capability_id = None

        if output.get("status") != "ok":
            fallback_capability_id = selection.capability.execution.fallback_capability_id
            if fallback_capability_id and fallback_capability_id not in attempted_fallbacks:
                warnings.append(
                    f"Primary capability '{selection.capability.capability_id}' failed. Falling back to '{fallback_capability_id}'."
                )
                fallback_request = request.model_copy(update={"capability_id": fallback_capability_id, "tags": [], "kind": None})
                fallback_result = await self._invoke(
                    fallback_request,
                    session_id=session_id,
                    attempted_fallbacks={*attempted_fallbacks, selection.capability.capability_id},
                )
                fallback_result.fallback_used = True
                fallback_result.fallback_capability_id = fallback_capability_id
                fallback_result.circuit_breaker_state = circuit_state
                fallback_result.attempts += attempts
                fallback_result.warnings = [*warnings, *fallback_result.warnings]
                return fallback_result

        return RoutingPayload(
            selected_capability_id=selection.capability.capability_id,
            capability_kind=selection.capability.kind,
            selection_mode=selection.selection_mode,  # type: ignore[arg-type]
            selection_reason=selection.selection_reason,
            channel_id=request.channel_id,
            formatter_id=formatter_id,
            server_id=server_id,
            downstream_route=output.get("route"),
            downstream_status=output.get("status"),
            attempts=attempts,
            fallback_used=fallback_used,
            fallback_capability_id=fallback_capability_id,
            circuit_breaker_state=circuit_state,  # type: ignore[arg-type]
            warnings=warnings,
            output=output,
        )

    @staticmethod
    def _select(candidates: list[CapabilityPayload], request: InvokeCapabilityRequest) -> _SelectionResult:
        executable = [cap for cap in candidates if cap.kind in {"tool", "report", "workflow"}]

        if request.capability_id:
            for capability in executable:
                if capability.capability_id == request.capability_id:
                    if capability.scope == "platform" and capability.kind == "tool" and not request.allow_platform_tools:
                        raise ValueError("Platform tool execution requires allow_platform_tools=true.")
                    return _SelectionResult(
                        capability=capability,
                        selection_mode="capability_id",
                        selection_reason=f"Selected exact capability_id '{request.capability_id}'.",
                    )
            raise ValueError(f"Unknown capability_id '{request.capability_id}'.")

        requested_tags = {tag.lower() for tag in request.tags}
        if request.kind is None or not requested_tags:
            raise ValueError("Either capability_id or both kind and tags are required for routing.")

        filtered: list[tuple[int, CapabilityPayload]] = []
        for capability in executable:
            if capability.kind != request.kind:
                continue
            if capability.scope == "platform" and capability.kind == "tool" and not request.allow_platform_tools:
                continue
            capability_tags = {tag.lower() for tag in capability.tags}
            if not requested_tags.issubset(capability_tags):
                continue
            score = len(requested_tags) + (1 if capability.scope == "app" else 0)
            filtered.append((score, capability))

        if not filtered:
            raise ValueError("No capability matched the requested kind and tags.")

        filtered.sort(key=lambda item: (-item[0], item[1].capability_id))
        top_score = filtered[0][0]
        top_matches = [capability for score, capability in filtered if score == top_score]
        if len(top_matches) > 1:
            candidate_ids = ", ".join(item.capability_id for item in top_matches[:5])
            raise ValueError(f"Ambiguous capability selection. Top matches: {candidate_ids}")

        chosen = top_matches[0]
        return _SelectionResult(
            capability=chosen,
            selection_mode="tags",
            selection_reason=f"Selected {chosen.capability_id} by kind '{request.kind}' and tags {sorted(requested_tags)}.",
        )

    @staticmethod
    def _formatter_id(channels: list[Any], channel_id: str | None) -> str | None:
        if channel_id is None:
            return None
        for channel in channels:
            if channel.channel_id == channel_id:
                return channel.formatter.formatter_id
        raise ValueError(f"Unknown channel_id '{channel_id}'.")

    async def _run_report(
        self,
        capability: CapabilityPayload,
        request: InvokeCapabilityRequest,
        session_id: str,
    ) -> dict[str, Any]:
        app_ctx = self.app_router.resolve(request.app_id)
        _, _, report_name = capability.capability_id.split(".", 2)
        await self.session_store.ensure(session_id, actor_id=request.actor_id)
        report = app_ctx.domain_registry.get_report(report_name)
        policy = app_ctx.sql_policy.validate(report.sql, allow_mutations_override=False)
        if not policy.allowed:
            return {
                "route": "REPORT",
                "status": "blocked",
                "message": policy.reason,
                "session_id": session_id,
            }

        result = await app_ctx.query_engine.run_report(report_name, report.sql)
        await self.session_store.append_event(
            session_id,
            {"type": "report", "report_name": report_name, "row_count": result.row_count},
        )
        return {
            "route": "REPORT",
            "status": "ok",
            "message": f"Report '{report_name}' executed.",
            "session_id": session_id,
            "report": result.model_dump(mode="json"),
        }

    async def _run_workflow(
        self,
        capability: CapabilityPayload,
        request: InvokeCapabilityRequest,
        session_id: str,
    ) -> dict[str, Any]:
        app_ctx = self.app_router.resolve(request.app_id)
        _, _, workflow_id = capability.capability_id.split(".", 2)
        await self.session_store.ensure(session_id, actor_id=request.actor_id)
        execution_mode = request.execution_mode
        if execution_mode == "auto":
            try:
                snapshot = await self.session_store.get(session_id)
            except KeyError:
                snapshot = None
            execution_mode = (
                "continue"
                if snapshot and snapshot.active_workflow and snapshot.active_workflow.workflow_id == workflow_id
                else "start"
            )

        if execution_mode == "continue":
            result = await app_ctx.workflow_engine.continue_workflow(session_id, request.arguments)
        else:
            result = await app_ctx.workflow_engine.start(session_id, workflow_id, request.arguments)

        return {
            "route": "WORKFLOW",
            "status": "ok" if result.state == "completed" else "pending",
            "message": result.next_prompt if result.state == "pending" else "Workflow collected all required fields.",
            "session_id": session_id,
            "workflow": result.model_dump(mode="json"),
        }

    async def _run_external_tool(
        self,
        server_id: str,
        tool_name: str,
        request: InvokeCapabilityRequest,
    ) -> tuple[dict[str, Any], int, str]:
        server = self.apps_registry.mcp_servers[server_id]
        tool = server.tools[tool_name]
        target = self.target_resolver(server_id, server.endpoint)
        arguments = dict(request.arguments)
        if tool.argument_style == "request":
            arguments = {"request": arguments}

        breaker_id = f"mcp:{server_id}"
        breaker_state = self.circuit_breakers.before_call(breaker_id)
        if breaker_state == "open":
            return (
                {
                    "status": "error",
                    "route": "TOOL",
                    "message": f"Circuit breaker is open for MCP server '{server_id}'.",
                },
                0,
                breaker_state,
            )

        attempts = 0
        last_error_payload: dict[str, Any] | None = None
        total_attempts = max(tool.max_retries, 0) + 1

        for attempt in range(1, total_attempts + 1):
            attempts = attempt
            try:
                async with Client(target) as client:
                    result = await asyncio.wait_for(
                        client.call_tool(tool_name, arguments, raise_on_error=False),
                        timeout=tool.timeout_seconds,
                    )
            except TimeoutError:
                last_error_payload = {
                    "status": "error",
                    "route": "TOOL",
                    "message": f"Tool '{tool_name}' timed out after {tool.timeout_seconds} seconds.",
                }
            except Exception as exc:
                last_error_payload = {
                    "status": "error",
                    "route": "TOOL",
                    "message": f"Tool '{tool_name}' failed: {exc}",
                }
            else:
                payload = result.structured_content or result.data or {}
                if isinstance(payload, dict):
                    if "status" not in payload:
                        payload = {
                            "status": "ok" if not result.is_error else "error",
                            "route": payload.get("route", "TOOL"),
                            "message": self._result_message(result),
                            "data": payload,
                        }
                else:
                    payload = {
                        "status": "ok" if not result.is_error else "error",
                        "route": "TOOL",
                        "message": self._result_message(result),
                        "data": payload,
                    }

                if payload.get("status") == "ok":
                    breaker_state = self.circuit_breakers.record_success(breaker_id)
                    return payload, attempts, breaker_state
                last_error_payload = payload

            if attempt < total_attempts and tool.retry_backoff_ms > 0:
                await asyncio.sleep(tool.retry_backoff_ms / 1000)

        breaker_state = self.circuit_breakers.record_failure(
            breaker_id,
            threshold=server.circuit_breaker_failure_threshold,
            reset_seconds=server.circuit_breaker_reset_seconds,
        )
        return last_error_payload or {
            "status": "error",
            "route": "TOOL",
            "message": f"Tool '{tool_name}' failed without a structured response.",
        }, attempts, breaker_state

    @staticmethod
    def _external_tool_parts(capability_id: str) -> tuple[str, str]:
        parts = capability_id.split(".")
        if len(parts) < 3:
            raise ValueError(f"Capability '{capability_id}' is not an external tool capability.")
        return parts[1], ".".join(parts[2:])

    @staticmethod
    def _result_message(result: Any) -> str:
        payload = result.structured_content or result.data or {}
        if isinstance(payload, dict) and str(payload.get("message", "")).strip():
            return str(payload["message"])
        content = getattr(result, "content", None) or []
        if content:
            first = content[0]
            text = getattr(first, "text", "") or str(first)
            return str(text)
        return "Tool execution finished."
