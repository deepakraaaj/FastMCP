from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BaseToolRequest(BaseModel):
    app_id: str = Field(..., description="The application ID (e.g., 'fits')")
    session_id: str | None = None
    actor_id: str | None = None
    idempotency_key: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecuteSQLRequest(BaseToolRequest):
    sql: str
    allow_mutations: bool = False


class RunReportRequest(BaseToolRequest):
    report_name: str


class StartWorkflowRequest(BaseToolRequest):
    workflow_id: str
    values: dict[str, Any] = Field(default_factory=dict)


class ContinueWorkflowRequest(BaseToolRequest):
    values: dict[str, Any] = Field(default_factory=dict)


class SummaryRequest(BaseToolRequest):
    pass


class InvokeCapabilityRequest(BaseToolRequest):
    capability_id: str | None = None
    kind: Literal["tool", "report", "workflow"] | None = None
    tags: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    execution_mode: Literal["auto", "start", "continue"] = "auto"
    allow_platform_tools: bool = False
    channel_id: str | None = None


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str = ""
    tables: list[str] = Field(default_factory=list)
    normalized_sql: str = ""


class SQLResultPayload(BaseModel):
    ran: bool
    query: str
    row_count: int
    rows_preview: list[dict[str, Any]] = Field(default_factory=list)
    policy: PolicyDecision


class ReportResultPayload(BaseModel):
    report_name: str
    query: str
    row_count: int
    rows_preview: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowResultPayload(BaseModel):
    workflow_id: str
    state: Literal["pending", "completed"]
    collected_data: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    next_prompt: str = ""


class SessionPayload(BaseModel):
    session_id: str
    actor_id: str | None = None


class DomainPayload(BaseModel):
    name: str
    description: str
    allowed_tables: list[str] = Field(default_factory=list)
    reports: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)


class ExecutionContractPayload(BaseModel):
    input_schema: str
    output_schema: str
    requires_session: bool = False
    supports_idempotency: bool = False
    validation_owner: Literal["none", "tool", "core", "agent"] = "core"
    execution_owner: Literal["tool", "core", "agent", "manifest"] = "core"
    timeout_seconds: float | None = None
    max_retries: int = 0
    retry_backoff_ms: int = 0
    fallback_capability_id: str | None = None
    circuit_breaker_failure_threshold: int | None = None
    circuit_breaker_reset_seconds: int | None = None
    fallback_hint: str | None = None


class CapabilityPayload(BaseModel):
    capability_id: str
    kind: Literal["tool", "report", "workflow", "formatter"]
    scope: Literal["platform", "app"]
    display_name: str
    description: str
    owner: str
    source: str
    app_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    execution: ExecutionContractPayload


class RegistryServerPayload(BaseModel):
    server_id: str
    display_name: str
    description: str = ""
    version: str
    transport: str
    endpoint: str
    stateless_http: bool = False
    auth_mode: str = "none"
    tags: list[str] = Field(default_factory=list)
    app_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)


class ChannelFormatterPayload(BaseModel):
    formatter_id: str
    request_contract: str
    response_contract: str
    output_modes: list[str] = Field(default_factory=list)
    supports_streaming: bool = False
    supports_actions: bool = False
    supports_approvals: bool = False


class RegistryAgentPayload(BaseModel):
    agent_id: str
    display_name: str
    description: str
    provider: str
    model_name: str
    capability_ids: list[str] = Field(default_factory=list)


class RegistryChannelPayload(BaseModel):
    channel_id: str
    display_name: str
    description: str
    app_ids: list[str] = Field(default_factory=list)
    output_modes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    formatter: ChannelFormatterPayload
    capability_ids: list[str] = Field(default_factory=list)


class RegistryAppPayload(BaseModel):
    app_id: str
    display_name: str
    manifest_path: str
    domain_name: str
    domain_description: str
    allowed_tables: list[str] = Field(default_factory=list)
    protected_tables: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)


class RegistryPayload(BaseModel):
    mcp_servers: list[RegistryServerPayload] = Field(default_factory=list)
    agents: list[RegistryAgentPayload] = Field(default_factory=list)
    channels: list[RegistryChannelPayload] = Field(default_factory=list)
    apps: list[RegistryAppPayload] = Field(default_factory=list)
    capabilities: list[CapabilityPayload] = Field(default_factory=list)


class RoutingPayload(BaseModel):
    selected_capability_id: str
    capability_kind: Literal["tool", "report", "workflow"]
    selection_mode: Literal["capability_id", "tags"]
    selection_reason: str
    channel_id: str | None = None
    formatter_id: str | None = None
    server_id: str | None = None
    downstream_route: str | None = None
    downstream_status: str | None = None
    attempts: int = 0
    fallback_used: bool = False
    fallback_capability_id: str | None = None
    circuit_breaker_state: Literal["closed", "open", "half_open"] | None = None
    warnings: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)


class ResponseEnvelope(BaseModel):
    request_id: str
    route: Literal["SYSTEM", "SQL", "REPORT", "WORKFLOW", "ROUTING"]
    status: Literal["ok", "error", "blocked", "pending"]
    message: str
    session_id: str | None = None
    trace_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    session: SessionPayload | None = None
    sql: SQLResultPayload | None = None
    report: ReportResultPayload | None = None
    workflow: WorkflowResultPayload | None = None
    domain: DomainPayload | None = None
    registry: RegistryPayload | None = None
    routing: RoutingPayload | None = None
