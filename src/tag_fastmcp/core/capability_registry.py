from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tag_fastmcp.core.domain_registry import DomainRegistry
from tag_fastmcp.models.app_config import AppConfig, AppsRegistry
from tag_fastmcp.models.contracts import (
    CapabilityPayload,
    ChannelFormatterPayload,
    ExecutionContractPayload,
    RegistryAgentPayload,
    RegistryAppPayload,
    RegistryChannelPayload,
    RegistryPayload,
    RegistryServerPayload,
)

if TYPE_CHECKING:
    from tag_fastmcp.settings import AppSettings


@dataclass(frozen=True)
class _ToolCapabilitySpec:
    tool_name: str
    display_name: str
    description: str
    tags: tuple[str, ...]
    input_schema: str
    output_schema: str
    requires_session: bool = False
    supports_idempotency: bool = False
    validation_owner: str = "core"
    execution_owner: str = "core"
    fallback_hint: str | None = None


BUILT_IN_TOOL_CAPABILITIES: tuple[_ToolCapabilitySpec, ...] = (
    _ToolCapabilitySpec(
        tool_name="health_check",
        display_name="Health Check",
        description="Return the runtime health status for the current MCP server.",
        tags=("system", "health"),
        input_schema="health_check()",
        output_schema="ResponseEnvelope[system]",
        validation_owner="none",
    ),
    _ToolCapabilitySpec(
        tool_name="start_session",
        display_name="Start Session",
        description="Create a new session and bind it to the active MCP context.",
        tags=("system", "session"),
        input_schema="start_session(actor_id?: str, trace_id?: str)",
        output_schema="ResponseEnvelope[session]",
        validation_owner="none",
    ),
    _ToolCapabilitySpec(
        tool_name="describe_domain",
        display_name="Describe Domain",
        description="Describe the manifest-backed domain for a specific application.",
        tags=("system", "discovery", "domain"),
        input_schema="describe_domain(app_id: str, trace_id?: str)",
        output_schema="ResponseEnvelope[domain]",
        validation_owner="none",
    ),
    _ToolCapabilitySpec(
        tool_name="describe_capabilities",
        display_name="Describe Capabilities",
        description="Return the plug-and-play registry snapshot for the platform or one application.",
        tags=("system", "discovery", "registry"),
        input_schema="describe_capabilities(app_id?: str, trace_id?: str)",
        output_schema="ResponseEnvelope[registry]",
        validation_owner="none",
    ),
    _ToolCapabilitySpec(
        tool_name="execute_sql",
        display_name="Execute SQL",
        description="Run validated SQL against the selected application context.",
        tags=("sql", "query"),
        input_schema="ExecuteSQLRequest",
        output_schema="ResponseEnvelope[sql]",
        requires_session=True,
        supports_idempotency=True,
        fallback_hint="Use run_report when a canned report exists.",
    ),
    _ToolCapabilitySpec(
        tool_name="summarize_last_query",
        display_name="Summarize Last Query",
        description="Re-run the last session query and summarize its current result size.",
        tags=("sql", "summary"),
        input_schema="SummaryRequest",
        output_schema="ResponseEnvelope[sql]",
        requires_session=True,
    ),
    _ToolCapabilitySpec(
        tool_name="run_report",
        display_name="Run Report",
        description="Execute a manifest-defined report for the selected application.",
        tags=("report", "manifest"),
        input_schema="RunReportRequest",
        output_schema="ResponseEnvelope[report]",
        requires_session=True,
    ),
    _ToolCapabilitySpec(
        tool_name="start_workflow",
        display_name="Start Workflow",
        description="Start a manifest-defined workflow and collect required fields.",
        tags=("workflow", "manifest"),
        input_schema="StartWorkflowRequest",
        output_schema="ResponseEnvelope[workflow]",
        requires_session=True,
    ),
    _ToolCapabilitySpec(
        tool_name="continue_workflow",
        display_name="Continue Workflow",
        description="Continue the active workflow for the current session.",
        tags=("workflow", "continuation"),
        input_schema="ContinueWorkflowRequest",
        output_schema="ResponseEnvelope[workflow]",
        requires_session=True,
    ),
    _ToolCapabilitySpec(
        tool_name="discover_schema",
        display_name="Discover Schema",
        description="Introspect the database schema for the selected application.",
        tags=("schema", "discovery"),
        input_schema="DiscoverSchemaRequest",
        output_schema="DatabaseSchema",
        validation_owner="none",
    ),
    _ToolCapabilitySpec(
        tool_name="agent_chat",
        display_name="Clarification Agent Chat",
        description="Run the clarification agent against one application context.",
        tags=("agent", "clarification"),
        input_schema="AgentChatRequest",
        output_schema="AgentChatResponse",
        execution_owner="agent",
        fallback_hint="Fall back to explicit workflow or report tools when agent routing is unavailable.",
    ),
    _ToolCapabilitySpec(
        tool_name="invoke_capability",
        display_name="Invoke Capability",
        description="Select a capability from registry metadata and execute it through the appropriate adapter.",
        tags=("routing", "registry", "execution"),
        input_schema="InvokeCapabilityRequest",
        output_schema="ResponseEnvelope[routing]",
        execution_owner="core",
        fallback_hint="Use describe_capabilities first when capability selection is ambiguous.",
    ),
    _ToolCapabilitySpec(
        tool_name="validate_builder_graph",
        display_name="Validate Builder Graph",
        description="Validate a constrained builder graph before preview execution.",
        tags=("builder", "validation"),
        input_schema="BuilderGraph",
        output_schema="BuilderValidationResult",
        validation_owner="none",
    ),
    _ToolCapabilitySpec(
        tool_name="preview_builder_graph",
        display_name="Preview Builder Graph",
        description="Preview a constrained builder graph through real MCP tool calls.",
        tags=("builder", "preview"),
        input_schema="BuilderGraph",
        output_schema="BuilderPreviewResult",
        validation_owner="none",
    ),
)


class CapabilityRegistry:
    def __init__(self, settings: AppSettings, apps_registry: AppsRegistry):
        self.settings = settings
        self.apps_registry = apps_registry

    def describe(self, app_id: str | None = None) -> RegistryPayload:
        selected_apps = self._selected_apps(app_id)
        built_in_capabilities = [self._tool_capability(spec) for spec in BUILT_IN_TOOL_CAPABILITIES]
        capabilities = list(built_in_capabilities)
        apps: list[RegistryAppPayload] = []
        channels: list[RegistryChannelPayload] = []

        for selected_app_id, config in selected_apps:
            domain_registry = DomainRegistry(self._resolve_manifest_path(config))
            app_capabilities = self._app_capabilities(selected_app_id, config, domain_registry)
            apps.append(
                RegistryAppPayload(
                    app_id=selected_app_id,
                    display_name=config.display_name,
                    manifest_path=str(self._resolve_manifest_path(config)),
                    domain_name=domain_registry.manifest.name,
                    domain_description=domain_registry.manifest.description,
                    allowed_tables=list(domain_registry.manifest.allowed_tables),
                    protected_tables=list(domain_registry.manifest.protected_tables),
                    capability_ids=[cap.capability_id for cap in app_capabilities],
                )
            )
            capabilities.extend(app_capabilities)

        external_servers, external_capabilities = self._external_mcp_servers(app_id)
        channels, channel_capabilities = self._channels(app_id)
        capabilities.extend(external_capabilities)
        capabilities.extend(channel_capabilities)
        capabilities = sorted(capabilities, key=lambda item: item.capability_id)
        built_in_server_capability_ids = [
            item.capability_id
            for item in capabilities
            if item.kind != "formatter" and not item.owner.startswith("mcp_server:")
        ]

        return RegistryPayload(
            mcp_servers=[
                RegistryServerPayload(
                    server_id="mcp.tag_fastmcp",
                    display_name=self.settings.app_name,
                    description="Built-in FastMCP runtime that exposes core system, query, report, workflow, schema, agent, and builder tools.",
                    version=self.settings.app_version,
                    transport=self.settings.transport,
                    endpoint=self.settings.path,
                    stateless_http=self.settings.stateless_http,
                    auth_mode="none",
                    tags=["core", "fastmcp"],
                    capability_ids=built_in_server_capability_ids,
                )
            ]
            + external_servers,
            agents=[
                RegistryAgentPayload(
                    agent_id="agent.clarification",
                    display_name="Clarification Agent",
                    description="vLLM-backed clarification agent exposed through the MCP surface.",
                    provider="vllm-compatible",
                    model_name=self.settings.llm_model,
                    capability_ids=["tool.agent_chat"],
                )
            ],
            channels=channels,
            apps=sorted(apps, key=lambda item: item.app_id),
            capabilities=capabilities,
        )

    def _selected_apps(self, app_id: str | None) -> list[tuple[str, AppConfig]]:
        if app_id is None:
            return sorted(self.apps_registry.apps.items(), key=lambda item: item[0])
        try:
            return [(app_id, self.apps_registry.apps[app_id])]
        except KeyError as exc:
            raise KeyError(f"Unknown application ID: {app_id}") from exc

    def _resolve_manifest_path(self, config: AppConfig) -> Path:
        path = Path(config.manifest)
        if path.is_absolute():
            return path
        return self.settings.root_path / path

    @staticmethod
    def _is_visible(app_filter: str | None, app_ids: list[str]) -> bool:
        if app_filter is None:
            return True
        return not app_ids or app_filter in app_ids

    @staticmethod
    def _tool_capability(spec: _ToolCapabilitySpec) -> CapabilityPayload:
        return CapabilityPayload(
            capability_id=f"tool.{spec.tool_name}",
            kind="tool",
            scope="platform",
            display_name=spec.display_name,
            description=spec.description,
            owner="fastmcp",
            source="runtime:tools",
            tags=list(spec.tags),
            execution=ExecutionContractPayload(
                input_schema=spec.input_schema,
                output_schema=spec.output_schema,
                requires_session=spec.requires_session,
                supports_idempotency=spec.supports_idempotency,
                validation_owner=spec.validation_owner,  # type: ignore[arg-type]
                execution_owner=spec.execution_owner,  # type: ignore[arg-type]
                fallback_hint=spec.fallback_hint,
            ),
        )

    def _app_capabilities(
        self,
        app_id: str,
        config: AppConfig,
        domain_registry: DomainRegistry,
    ) -> list[CapabilityPayload]:
        capabilities: list[CapabilityPayload] = []

        for report_name, report in sorted(domain_registry.manifest.reports.items()):
            capabilities.append(
                CapabilityPayload(
                    capability_id=f"report.{app_id}.{report_name}",
                    kind="report",
                    scope="app",
                    display_name=report_name,
                    description=report.description,
                    owner="domain_manifest",
                    source=str(self._resolve_manifest_path(config)),
                        app_id=app_id,
                        tags=["report", "manifest", app_id, report_name],
                        execution=ExecutionContractPayload(
                        input_schema="RunReportRequest",
                        output_schema="ResponseEnvelope[report]",
                        requires_session=True,
                        supports_idempotency=False,
                        validation_owner="core",
                        execution_owner="core",
                        fallback_hint="Use execute_sql only when a report contract does not exist.",
                    ),
                )
            )

        for workflow_id, workflow in sorted(domain_registry.manifest.workflows.items()):
            capabilities.append(
                CapabilityPayload(
                    capability_id=f"workflow.{app_id}.{workflow_id}",
                    kind="workflow",
                    scope="app",
                    display_name=workflow_id,
                    description=workflow.description,
                    owner="domain_manifest",
                    source=str(self._resolve_manifest_path(config)),
                        app_id=app_id,
                        tags=["workflow", "manifest", app_id, workflow_id],
                    execution=ExecutionContractPayload(
                        input_schema="StartWorkflowRequest / ContinueWorkflowRequest",
                        output_schema="ResponseEnvelope[workflow]",
                        requires_session=True,
                        supports_idempotency=False,
                        validation_owner="core",
                        execution_owner="core",
                        fallback_hint="Escalate to the clarification agent when required fields remain ambiguous.",
                    ),
                )
            )

        return capabilities

    def _external_mcp_servers(self, app_id: str | None) -> tuple[list[RegistryServerPayload], list[CapabilityPayload]]:
        servers: list[RegistryServerPayload] = []
        capabilities: list[CapabilityPayload] = []

        for server_id, server in sorted(self.apps_registry.mcp_servers.items()):
            if not server.enabled or not self._is_visible(app_id, server.app_ids):
                continue

            server_capability_ids: list[str] = []
            for tool_name, tool in sorted(server.tools.items()):
                capability_id = f"tool.{server_id}.{tool_name}"
                server_capability_ids.append(capability_id)
                capabilities.append(
                    CapabilityPayload(
                        capability_id=capability_id,
                        kind="tool",
                        scope="app" if server.app_ids else "platform",
                        display_name=tool.display_name,
                        description=tool.description,
                        owner=f"mcp_server:{server_id}",
                        source=server.endpoint,
                        app_id=app_id if app_id in server.app_ids else None,
                        tags=list(dict.fromkeys([*server.tags, *tool.tags, tool_name])),
                        execution=ExecutionContractPayload(
                            input_schema=tool.input_schema,
                            output_schema=tool.output_schema,
                            requires_session=tool.requires_session,
                            supports_idempotency=tool.supports_idempotency,
                            validation_owner="tool",
                            execution_owner="tool",
                            timeout_seconds=tool.timeout_seconds,
                            max_retries=tool.max_retries,
                            retry_backoff_ms=tool.retry_backoff_ms,
                            fallback_capability_id=tool.fallback_capability_id,
                            circuit_breaker_failure_threshold=server.circuit_breaker_failure_threshold,
                            circuit_breaker_reset_seconds=server.circuit_breaker_reset_seconds,
                            fallback_hint=tool.fallback_hint,
                        ),
                    )
                )

            servers.append(
                RegistryServerPayload(
                    server_id=server_id,
                    display_name=server.display_name,
                    description=server.description,
                    version="external",
                    transport=server.transport,
                    endpoint=server.endpoint,
                    stateless_http=server.transport in {"http", "streamable-http"},
                    auth_mode=server.auth_mode,
                    tags=list(server.tags),
                    app_ids=list(server.app_ids),
                    capability_ids=server_capability_ids,
                )
            )

        return servers, capabilities

    def _channels(self, app_id: str | None) -> tuple[list[RegistryChannelPayload], list[CapabilityPayload]]:
        channels: list[RegistryChannelPayload] = []
        capabilities: list[CapabilityPayload] = []

        for channel_id, channel in sorted(self.apps_registry.channels.items()):
            if not self._is_visible(app_id, channel.app_ids):
                continue

            formatter_capability_id = f"formatter.{channel.formatter.formatter_id}"
            channels.append(
                RegistryChannelPayload(
                    channel_id=channel_id,
                    display_name=channel.display_name,
                    description=channel.description,
                    app_ids=list(channel.app_ids),
                    output_modes=list(channel.formatter.output_modes),
                    tags=list(channel.tags),
                    formatter=ChannelFormatterPayload(
                        formatter_id=channel.formatter.formatter_id,
                        request_contract=channel.formatter.request_contract,
                        response_contract=channel.formatter.response_contract,
                        output_modes=list(channel.formatter.output_modes),
                        supports_streaming=channel.formatter.supports_streaming,
                        supports_actions=channel.formatter.supports_actions,
                        supports_approvals=channel.formatter.supports_approvals,
                    ),
                    capability_ids=[formatter_capability_id],
                )
            )
            capabilities.append(
                CapabilityPayload(
                    capability_id=formatter_capability_id,
                    kind="formatter",
                    scope="app" if channel.app_ids else "platform",
                    display_name=channel.display_name,
                    description=f"Formatter contract for channel '{channel_id}'.",
                    owner=f"channel:{channel_id}",
                    source="config:channels",
                    app_id=app_id if app_id in channel.app_ids else None,
                    tags=list(dict.fromkeys([*channel.tags, *channel.formatter.output_modes, channel_id, channel.formatter.formatter_id])),
                    execution=ExecutionContractPayload(
                        input_schema=channel.formatter.request_contract,
                        output_schema=channel.formatter.response_contract,
                        requires_session=False,
                        supports_idempotency=False,
                        validation_owner="core",
                        execution_owner="core",
                        fallback_hint="Fall back to plain text formatting when the richer formatter is unavailable.",
                    ),
                )
            )

        return channels, capabilities
