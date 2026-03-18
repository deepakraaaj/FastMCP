from __future__ import annotations

from collections import Counter
from typing import Any

from fastmcp import Client, FastMCP

from tag_fastmcp.core.domain_registry import DomainRegistry
from tag_fastmcp.core.sql_policy import SQLPolicyValidator
from tag_fastmcp.models.builder import (
    BuilderGraph,
    BuilderNode,
    BuilderPreviewResult,
    BuilderPreviewStep,
    BuilderValidationIssue,
    BuilderValidationResult,
)


class BuilderRuntimeBridge:
    """
    Validates a constrained builder graph and can preview it by calling
    FastMCP tools through a real FastMCP client session.
    """

    def __init__(self, *, app_id: str, domain_registry: DomainRegistry, sql_policy: SQLPolicyValidator):
        self.app_id = app_id
        self.domain_registry = domain_registry
        self.sql_policy = sql_policy

    def validate(self, graph: BuilderGraph) -> BuilderValidationResult:
        issues: list[BuilderValidationIssue] = []
        node_ids = [node.id for node in graph.nodes]
        duplicates = [node_id for node_id, count in Counter(node_ids).items() if count > 1]
        for node_id in duplicates:
            issues.append(BuilderValidationIssue(level="error", message="Duplicate node id.", node_id=node_id))

        node_map = {node.id: node for node in graph.nodes}
        outgoing: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
        incoming: dict[str, list[str]] = {node.id: [] for node in graph.nodes}

        if not graph.nodes:
            issues.append(BuilderValidationIssue(level="error", message="Graph has no nodes."))
            return BuilderValidationResult(valid=False, issues=issues)

        for edge in graph.edges:
            if edge.source not in node_map:
                issues.append(BuilderValidationIssue(level="error", message="Edge source does not exist.", node_id=edge.source))
                continue
            if edge.target not in node_map:
                issues.append(BuilderValidationIssue(level="error", message="Edge target does not exist.", node_id=edge.target))
                continue
            outgoing[edge.source].append(edge.target)
            incoming[edge.target].append(edge.source)

        start_nodes = [node for node in graph.nodes if node.type == "start"]
        if len(start_nodes) != 1:
            issues.append(BuilderValidationIssue(level="error", message="Graph must contain exactly one start node."))

        for node in graph.nodes:
            next_nodes = outgoing.get(node.id, [])
            if len(next_nodes) > 1:
                issues.append(
                    BuilderValidationIssue(
                        level="error",
                        message="Branching is not supported yet. Each node may have at most one outgoing edge.",
                        node_id=node.id,
                    )
                )

            if node.type == "start" and incoming.get(node.id):
                issues.append(BuilderValidationIssue(level="error", message="Start node cannot have incoming edges.", node_id=node.id))

            if node.type == "start" and len(next_nodes) != 1:
                issues.append(BuilderValidationIssue(level="error", message="Start node must have exactly one outgoing edge.", node_id=node.id))

            if node.type == "respond" and next_nodes:
                issues.append(BuilderValidationIssue(level="error", message="Respond node must be terminal.", node_id=node.id))

            self._validate_node_config(node, issues)

        ordered_node_ids = self._ordered_path(start_nodes[0].id, outgoing) if len(start_nodes) == 1 else []
        if ordered_node_ids:
            reachable = set(ordered_node_ids)
            unreachable = [node.id for node in graph.nodes if node.id not in reachable]
            for node_id in unreachable:
                issues.append(BuilderValidationIssue(level="error", message="Node is unreachable from start.", node_id=node_id))

            terminal_node = node_map[ordered_node_ids[-1]]
            if terminal_node.type != "respond":
                issues.append(BuilderValidationIssue(level="error", message="Graph must end with a respond node.", node_id=terminal_node.id))

            if self._has_cycle(start_nodes[0].id, outgoing):
                issues.append(BuilderValidationIssue(level="error", message="Graph contains a cycle."))

        valid = not any(issue.level == "error" for issue in issues)
        return BuilderValidationResult(valid=valid, ordered_node_ids=ordered_node_ids if valid else [], issues=issues)

    def _validate_node_config(self, node: BuilderNode, issues: list[BuilderValidationIssue]) -> None:
        cfg = dict(node.config or {})
        if node.type == "execute_sql":
            sql = str(cfg.get("sql", "")).strip()
            if not sql:
                issues.append(BuilderValidationIssue(level="error", message="execute_sql node requires sql.", node_id=node.id))
                return
            decision = self.sql_policy.validate(sql, allow_mutations_override=bool(cfg.get("allow_mutations", False)))
            if not decision.allowed:
                issues.append(BuilderValidationIssue(level="error", message=f"SQL blocked: {decision.reason}", node_id=node.id))
        elif node.type == "run_report":
            report_name = str(cfg.get("report_name", "")).strip()
            if not report_name:
                issues.append(BuilderValidationIssue(level="error", message="run_report node requires report_name.", node_id=node.id))
                return
            try:
                self.domain_registry.get_report(report_name)
            except KeyError as exc:
                issues.append(BuilderValidationIssue(level="error", message=str(exc), node_id=node.id))
        elif node.type == "start_workflow":
            workflow_id = str(cfg.get("workflow_id", "")).strip()
            if not workflow_id:
                issues.append(BuilderValidationIssue(level="error", message="start_workflow node requires workflow_id.", node_id=node.id))
                return
            try:
                self.domain_registry.get_workflow(workflow_id)
            except KeyError as exc:
                issues.append(BuilderValidationIssue(level="error", message=str(exc), node_id=node.id))
        elif node.type == "continue_workflow":
            if not isinstance(cfg.get("values", {}), dict):
                issues.append(BuilderValidationIssue(level="error", message="continue_workflow values must be an object.", node_id=node.id))
        elif node.type == "respond":
            if not str(cfg.get("message", "")).strip():
                issues.append(BuilderValidationIssue(level="warning", message="respond node has no message.", node_id=node.id))

    @staticmethod
    def _ordered_path(start_id: str, outgoing: dict[str, list[str]]) -> list[str]:
        ordered: list[str] = []
        current = start_id
        visited: set[str] = set()
        while current not in visited:
            ordered.append(current)
            visited.add(current)
            next_nodes = outgoing.get(current, [])
            if not next_nodes:
                break
            current = next_nodes[0]
        return ordered

    @staticmethod
    def _has_cycle(start_id: str, outgoing: dict[str, list[str]]) -> bool:
        visited: set[str] = set()
        stack: set[str] = set()

        def walk(node_id: str) -> bool:
            if node_id in stack:
                return True
            if node_id in visited:
                return False
            visited.add(node_id)
            stack.add(node_id)
            for child in outgoing.get(node_id, []):
                if walk(child):
                    return True
            stack.remove(node_id)
            return False

        return walk(start_id)

    async def preview(self, graph: BuilderGraph, mcp_target: FastMCP | str) -> BuilderPreviewResult:
        validation = self.validate(graph)
        if not validation.valid:
            return BuilderPreviewResult(
                valid=False,
                ordered_node_ids=validation.ordered_node_ids,
                issues=validation.issues,
            )

        node_map = {node.id: node for node in graph.nodes}
        steps: list[BuilderPreviewStep] = []
        async with Client(mcp_target) as client:
            session_result = await client.call_tool(
                "start_session",
                {"actor_id": graph.actor_id or "builder-preview"},
                raise_on_error=False,
            )
            session_payload = session_result.structured_content or session_result.data or {}
            session = dict(session_payload.get("session") or {})
            session_id = str(session.get("session_id", "")).strip() or None
            if session_result.is_error or session_id is None:
                message = self._result_message(session_result)
                steps.append(
                    BuilderPreviewStep(
                        node_id=validation.ordered_node_ids[0],
                        node_type="start",
                        tool_name="start_session",
                        status="error",
                        message=message,
                        output=session_payload,
                    )
                )
                return BuilderPreviewResult(
                    valid=False,
                    session_id=session_id,
                    ordered_node_ids=validation.ordered_node_ids,
                    issues=validation.issues,
                    steps=steps,
                )

            steps.append(
                BuilderPreviewStep(
                    node_id=validation.ordered_node_ids[0],
                    node_type="start",
                    tool_name="start_session",
                    status="ok",
                    message="Preview session started.",
                    output=session_payload,
                )
            )

            for node_id in validation.ordered_node_ids[1:]:
                node = node_map[node_id]
                if node.type == "respond":
                    message = str(node.config.get("message", "")).strip() or "Preview finished."
                    steps.append(
                        BuilderPreviewStep(
                            node_id=node.id,
                            node_type=node.type,
                            tool_name=None,
                            status="ok",
                            message=message,
                            output={"message": message},
                        )
                    )
                    continue

                tool_name, arguments = self._tool_call(node=node, session_id=session_id)
                result = await client.call_tool(tool_name, arguments, raise_on_error=False)
                payload = result.structured_content or result.data or {}
                message = self._result_message(result)
                status = "error" if result.is_error else "ok"
                steps.append(
                    BuilderPreviewStep(
                        node_id=node.id,
                        node_type=node.type,
                        tool_name=tool_name,
                        status=status,
                        message=message,
                        output=payload if isinstance(payload, dict) else {"data": payload},
                    )
                )
                if result.is_error:
                    return BuilderPreviewResult(
                        valid=False,
                        session_id=session_id,
                        ordered_node_ids=validation.ordered_node_ids,
                        issues=validation.issues,
                        steps=steps,
                    )

        return BuilderPreviewResult(
            valid=True,
            session_id=session_id,
            ordered_node_ids=validation.ordered_node_ids,
            issues=validation.issues,
            steps=steps,
        )

    def _tool_call(self, *, node: BuilderNode, session_id: str) -> tuple[str, dict[str, Any]]:
        cfg = dict(node.config or {})
        if node.type == "execute_sql":
            return (
                "execute_sql",
                {
                    "request": {
                        "app_id": self.app_id,
                        "session_id": session_id,
                        "sql": str(cfg.get("sql", "")),
                        "allow_mutations": bool(cfg.get("allow_mutations", False)),
                        "idempotency_key": cfg.get("idempotency_key"),
                    }
                },
            )
        if node.type == "run_report":
            return (
                "run_report",
                {
                    "request": {
                        "app_id": self.app_id,
                        "session_id": session_id,
                        "report_name": str(cfg.get("report_name", "")),
                    }
                },
            )
        if node.type == "start_workflow":
            return (
                "start_workflow",
                {
                    "request": {
                        "app_id": self.app_id,
                        "session_id": session_id,
                        "workflow_id": str(cfg.get("workflow_id", "")),
                        "values": dict(cfg.get("values") or {}),
                    }
                },
            )
        if node.type == "continue_workflow":
            return (
                "continue_workflow",
                {
                    "request": {
                        "app_id": self.app_id,
                        "session_id": session_id,
                        "values": dict(cfg.get("values") or {}),
                    }
                },
            )
        raise ValueError(f"Unsupported node type for tool execution: {node.type}")

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
