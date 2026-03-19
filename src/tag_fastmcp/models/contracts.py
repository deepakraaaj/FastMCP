from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class BaseToolRequest(BaseModel):
    app_id: str = Field(..., description="The application ID (e.g., 'fits')")
    session_id: str | None = None
    actor_id: str | None = None
    auth_subject: str | None = None
    tenant_id: str | None = None
    role: Literal["end_user", "app_admin", "platform_admin", "service"] | None = None
    auth_scopes: list[str] = Field(default_factory=list)
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


class BaseAdminToolRequest(BaseModel):
    app_id: str | None = None
    session_id: str | None = None
    actor_id: str | None = None
    auth_subject: str | None = None
    tenant_id: str | None = None
    role: Literal["app_admin", "platform_admin", "service"] | None = None
    auth_scopes: list[str] = Field(default_factory=list)
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalQueueRequest(BaseAdminToolRequest):
    status: Literal["pending", "approved", "rejected", "expired", "cancelled"] | None = "pending"
    scope_type: Literal["execution", "agent_lifecycle"] | None = None


class ApprovalDecisionRequest(BaseAdminToolRequest):
    approval_id: str
    decision: Literal["approve", "reject", "cancel", "expire"]
    comment: str | None = None


class ResumeExecutionRequest(BaseAdminToolRequest):
    approval_id: str


class ProposalListRequest(BaseAdminToolRequest):
    status: Literal[
        "draft",
        "pending_review",
        "approved_for_registration",
        "rejected",
        "registered",
        "activated",
        "superseded",
    ] | None = None


class RegistrationListRequest(BaseAdminToolRequest):
    proposal_id: str | None = None
    registry_state: Literal["draft", "registered", "activation_pending", "active", "inactive", "retired"] | None = None


class RegisterProposalRequest(BaseAdminToolRequest):
    proposal_id: str
    version: str = "v1"


class ActivateRegistrationRequest(BaseAdminToolRequest):
    registration_id: str


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str = ""
    tables: list[str] = Field(default_factory=list)
    normalized_sql: str = ""


class RequestContext(BaseModel):
    request_id: str
    trace_id: str | None = None
    session_id: str | None = None
    actor_id: str | None = None
    auth_subject: str | None = None
    tenant_id: str | None = None
    role: Literal["end_user", "app_admin", "platform_admin", "service"]
    origin: Literal["widget_http", "admin_http", "mcp_tool", "builder_preview", "internal"]
    execution_mode: Literal["app_chat", "admin_chat", "direct_tool", "system"]
    requested_app_id: str | None = None
    session_bound_app_id: str | None = None
    channel_id: str | None = None
    auth_scopes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SqlPolicyProfile(BaseModel):
    allowed_tables: list[str] = Field(default_factory=list)
    protected_tables: list[str] = Field(default_factory=list)
    allow_mutations: bool = False
    require_select_where: bool = True


class PolicyEnvelope(BaseModel):
    envelope_id: str
    request_id: str
    execution_mode: Literal["app_chat", "admin_chat", "direct_tool", "system"]
    primary_app_id: str | None = None
    allowed_app_ids: list[str] = Field(default_factory=list)
    allowed_tenant_ids: list[str] = Field(default_factory=list)
    allowed_capability_ids: list[str] = Field(default_factory=list)
    allowed_channel_ids: list[str] = Field(default_factory=list)
    allowed_formatter_ids: list[str] = Field(default_factory=list)
    allow_platform_tools: bool = False
    allow_cross_app: bool = False
    allow_cross_db: bool = False
    allow_sql_execution: bool = False
    allow_external_mcp: bool = False
    allow_schema_discovery: bool = False
    allow_workflow_execution: bool = False
    allow_heavy_agent: bool = False
    allow_agent_proposal: bool = False
    require_approval_for: list[str] = Field(default_factory=list)
    reveal_sql_to_user: bool = False
    reveal_diagnostics: bool = False
    reveal_policy_reasons: bool = False
    sql_profiles_by_app: dict[str, SqlPolicyProfile] = Field(default_factory=dict)


class RoutingPlan(BaseModel):
    plan_id: str
    request_id: str
    intent_type: Literal[
        "answer_from_context",
        "ask_clarification",
        "run_report",
        "run_workflow",
        "execute_sql",
        "invoke_external_tool",
        "escalate_heavy_agent",
        "propose_agent",
        "reject",
    ]
    target_app_ids: list[str] = Field(default_factory=list)
    selected_capability_id: str | None = None
    candidate_capability_ids: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    requires_confirmation: bool = False
    requires_approval: bool = False
    approval_reason: str | None = None
    formatter_id: str | None = None
    audit_tags: list[str] = Field(default_factory=list)
    reasoning_summary: str


class PlanningInput(BaseModel):
    request_id: str
    session_id: str | None = None
    execution_mode: Literal["app_chat", "admin_chat", "direct_tool", "system"]
    actor_role: Literal["end_user", "app_admin", "platform_admin", "service"]
    user_message: str | None = None
    requested_app_ids: list[str] = Field(default_factory=list)
    channel_id: str | None = None
    session_summary: str | None = None
    envelope_ref: str
    candidate_capability_ids: list[str] = Field(default_factory=list)
    available_reports: list[str] = Field(default_factory=list)
    available_workflows: list[str] = Field(default_factory=list)
    available_external_tools: list[str] = Field(default_factory=list)


class IntentAnalysis(BaseModel):
    request_id: str
    intent_family: Literal[
        "answer",
        "clarify",
        "report",
        "workflow",
        "sql",
        "external_tool",
        "multi_app_analysis",
        "agent_gap",
        "reject",
    ]
    business_entities: list[str] = Field(default_factory=list)
    mentioned_apps: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    ambiguity_reasons: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    side_effect_level: Literal["none", "read", "write"] = "none"
    preferred_execution_kind: Literal[
        "answer",
        "report",
        "workflow",
        "sql",
        "external_tool",
        "heavy_agent",
        "proposal",
    ] = "answer"


class CapabilityCandidate(BaseModel):
    capability_id: str
    app_id: str | None = None
    kind: Literal["report", "workflow", "tool"]
    score: int
    match_reason: str
    risk_flags: list[str] = Field(default_factory=list)
    requires_session: bool = False
    requires_confirmation: bool = False
    requires_approval: bool = False


class OrchestrationDecision(BaseModel):
    decision_id: str
    request_id: str
    routing_plan_id: str
    orchestration_mode: Literal[
        "answer_only",
        "single_step",
        "multi_step",
        "heavy_agent",
        "proposal",
        "reject",
    ]
    selected_capability_ids: list[str] = Field(default_factory=list)
    primary_capability_id: str | None = None
    clarification_prompt: str | None = None
    missing_inputs: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    requires_approval: bool = False
    approval_reason: str | None = None
    formatter_id: str | None = None
    audit_tags: list[str] = Field(default_factory=list)
    user_visible_reason: str


class VisibilityProfile(BaseModel):
    profile_id: str
    actor_role: Literal["end_user", "app_admin", "platform_admin", "service"]
    execution_mode: Literal["app_chat", "admin_chat", "direct_tool", "system"]
    show_plan_summary: bool = False
    show_capability_ids: bool = False
    show_app_scope: bool = False
    show_sql_text: bool = False
    show_trace_id: bool = False
    show_retry_and_fallback: bool = False
    show_approval_metadata: bool = False
    show_escalation_metadata: bool = False
    show_raw_errors: bool = False
    show_actions: bool = False


class FormatterInput(BaseModel):
    request_id: str
    trace_id: str | None = None
    channel_id: str
    formatter_id: str
    execution_mode: Literal["app_chat", "admin_chat", "direct_tool", "system"]
    visibility_profile_id: str
    route: Literal[
        "answer",
        "clarification",
        "report",
        "workflow",
        "routing",
        "approval",
        "escalation",
        "rejection",
        "error",
    ]
    primary_message: str
    execution_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_capability_id: str | None = None
    approval_state: Literal["none", "required", "pending", "approved", "rejected"] = "none"
    escalation_state: Literal["none", "requested", "running", "partial", "completed", "failed"] = "none"
    available_actions: list[str] = Field(default_factory=list)


class OutputBlock(BaseModel):
    block_id: str
    kind: Literal["text", "card", "table", "metric_group", "checklist", "status", "approval", "escalation"]
    title: str | None = None
    body: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ChannelAction(BaseModel):
    action_id: str
    kind: Literal["continue_workflow", "approve", "reject", "retry", "open_details", "open_dashboard"]
    label: str
    enabled: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)


class ResponseState(BaseModel):
    status: Literal["ok", "pending", "blocked", "degraded", "approval_required", "escalated", "error"]
    user_visible_reason: str
    detail_level: Literal["minimal", "standard", "diagnostic"] = "minimal"


class ChannelResponse(BaseModel):
    response_id: str
    channel_id: str
    formatter_id: str
    primary_mode: Literal["text", "card", "dashboard"]
    blocks: list[OutputBlock] = Field(default_factory=list)
    actions: list[ChannelAction] = Field(default_factory=list)
    state: ResponseState
    diagnostics: dict[str, Any] = Field(default_factory=dict)


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


class AgentDefinition(BaseModel):
    agent_id: str
    agent_kind: Literal[
        "app_scoped_chat",
        "admin_orchestration",
        "schema_intelligence",
        "heavy_cross_db",
        "agent_proposal",
    ]
    display_name: str
    description: str
    provider: str
    model_name: str | None = None
    default_execution_modes: list[Literal["app_chat", "admin_chat", "direct_tool", "system"]] = Field(
        default_factory=list
    )
    requires_admin: bool = False
    supports_cross_app: bool = False
    requires_envelope_flag: str | None = None
    runtime_state: Literal["active", "stub", "gated"] = "active"
    capability_ids: list[str] = Field(default_factory=list)


class RegistryAgentPayload(AgentDefinition):
    available: bool = True


class AgentSelection(BaseModel):
    request_id: str
    execution_mode: Literal["app_chat", "admin_chat", "direct_tool", "system"]
    agent_id: str
    agent_kind: Literal[
        "app_scoped_chat",
        "admin_orchestration",
        "schema_intelligence",
        "heavy_cross_db",
        "agent_proposal",
    ]
    available_agent_ids: list[str] = Field(default_factory=list)
    selection_reason: str
    runtime_state: Literal["active", "stub", "gated"] = "active"


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
    request_context_id: str | None = None
    policy_envelope_id: str | None = None
    routing_plan_id: str | None = None
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
    presentation: ChannelResponse | None = None
    lifecycle: LifecyclePayload | None = None


class ApprovalRequest(BaseModel):
    approval_id: str
    scope_type: Literal["execution", "agent_lifecycle"]
    status: Literal["pending", "approved", "rejected", "expired", "cancelled"]
    tenant_id: str | None = None
    app_ids: list[str] = Field(default_factory=list)
    requested_by_actor_id: str | None = None
    requested_by_role: Literal["end_user", "app_admin", "platform_admin", "service"]
    approver_actor_id: str | None = None
    approver_role: Literal["app_admin", "platform_admin", "service"] | None = None
    request_reason: str
    approval_reason: str | None = None
    created_at: datetime
    decided_at: datetime | None = None
    expires_at: datetime | None = None
    trace_id: str | None = None
    request_context_ref: str | None = None
    routing_plan_ref: str | None = None
    proposal_draft_ref: str | None = None


class ExecutionApprovalPayload(BaseModel):
    approval_id: str
    orchestration_decision_id: str
    selected_capability_ids: list[str] = Field(default_factory=list)
    primary_capability_id: str | None = None
    side_effect_level: Literal["none", "read", "write"] = "none"
    risk_level: Literal["low", "medium", "high"] = "low"
    user_visible_summary: str
    admin_review_summary: str


class ApprovalDecision(BaseModel):
    approval_id: str
    decision: Literal["approve", "reject", "cancel", "expire"]
    approver_actor_id: str
    approver_role: Literal["app_admin", "platform_admin", "service"]
    comment: str | None = None
    decided_at: datetime
    resulting_status: Literal["pending", "approved", "rejected", "expired", "cancelled"]


class AgentProposalDraft(BaseModel):
    proposal_id: str
    status: Literal[
        "draft",
        "pending_review",
        "approved_for_registration",
        "rejected",
        "registered",
        "activated",
        "superseded",
    ]
    tenant_id: str | None = None
    target_app_ids: list[str] = Field(default_factory=list)
    proposed_agent_kind: Literal[
        "app_chat",
        "admin_orchestrator",
        "schema_intelligence",
        "heavy_cross_db",
        "proposal",
    ]
    display_name: str
    problem_statement: str
    justification: str
    proposed_capability_bundle: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    required_channels: list[str] = Field(default_factory=list)
    draft_spec_payload: dict[str, Any] = Field(default_factory=dict)
    proposed_by_actor_id: str | None = None
    generated_by_system: bool = True
    linked_approval_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentRegistrationRecord(BaseModel):
    registration_id: str
    proposal_id: str
    agent_id: str
    version: str
    registry_state: Literal["draft", "registered", "activation_pending", "active", "inactive", "retired"]
    registered_by_actor_id: str | None = None
    activated_by_actor_id: str | None = None
    created_at: datetime
    activated_at: datetime | None = None


class ApprovalQueueItem(BaseModel):
    approval_id: str
    scope_type: Literal["execution", "agent_lifecycle"]
    status: Literal["pending", "approved", "rejected", "expired", "cancelled"]
    title: str
    summary: str
    requested_by: str | None = None
    target_scope_label: str
    created_at: datetime
    expires_at: datetime | None = None
    severity: Literal["low", "medium", "high"] = "low"


class LifecycleAuditEvent(BaseModel):
    event_id: str
    event_type: Literal[
        "approval_requested",
        "approval_approved",
        "approval_rejected",
        "approval_cancelled",
        "approval_expired",
        "proposal_created",
        "proposal_updated",
        "proposal_registered",
        "proposal_activated",
        "proposal_retired",
    ]
    actor_id: str | None = None
    actor_role: str | None = None
    approval_id: str | None = None
    proposal_id: str | None = None
    registration_id: str | None = None
    trace_id: str | None = None
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class PausedExecutionRecord(BaseModel):
    pause_id: str
    approval_id: str
    status: Literal[
        "pending_approval",
        "approved",
        "rejected",
        "expired",
        "cancelled",
        "resumed",
    ]
    request_id: str
    request_context: RequestContext
    policy_envelope: PolicyEnvelope
    routing_plan: RoutingPlan
    orchestration_decision: OrchestrationDecision
    execution_requests: list[InvokeCapabilityRequest] = Field(default_factory=list)
    created_at: datetime
    resumed_at: datetime | None = None


class LifecyclePayload(BaseModel):
    approval_queue: list[ApprovalQueueItem] = Field(default_factory=list)
    approval_request: ApprovalRequest | None = None
    approval_decision: ApprovalDecision | None = None
    execution_approval_payload: ExecutionApprovalPayload | None = None
    proposal_drafts: list[AgentProposalDraft] = Field(default_factory=list)
    proposal_draft: AgentProposalDraft | None = None
    registration_records: list[AgentRegistrationRecord] = Field(default_factory=list)
    registration_record: AgentRegistrationRecord | None = None
    paused_execution: PausedExecutionRecord | None = None
    audit_events: list[LifecycleAuditEvent] = Field(default_factory=list)
