from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from tag_fastmcp.models.contracts import ChannelResponse


class WidgetUserContext(BaseModel):
    user_id: str | None = None
    user_name: str | None = None
    company_id: str | None = None
    company_name: str | None = None


class AdminUserContext(BaseModel):
    actor_id: str
    auth_subject: str | None = None
    tenant_id: str | None = None
    role: Literal["app_admin", "platform_admin", "service"]
    auth_scopes: list[str] = Field(default_factory=list)
    allowed_app_ids: list[str] = Field(default_factory=list)


class WidgetSessionStartResponse(BaseModel):
    session_id: str
    app_id: str


class WidgetAppOption(BaseModel):
    app_id: str
    display_name: str
    description: str | None = None
    domain_name: str | None = None
    allowed_tables: list[str] = Field(default_factory=list)


class WidgetAppListResponse(BaseModel):
    apps: list[WidgetAppOption] = Field(default_factory=list)
    default_app_id: str | None = None


class WidgetChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1)
    app_id: str | None = None


class AdminChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1)
    app_id: str | None = None
    channel_id: str | None = None


class AdminScopeParams(BaseModel):
    app_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None


class AdminApprovalQueueParams(AdminScopeParams):
    status: Literal["pending", "approved", "rejected", "expired", "cancelled"] | None = "pending"
    scope_type: Literal["execution", "agent_lifecycle"] | None = None


class AdminApprovalDecisionBody(AdminScopeParams):
    decision: Literal["approve", "reject", "cancel", "expire"]
    comment: str | None = None


class AdminResumeExecutionBody(AdminScopeParams):
    pass


class AdminProposalListParams(AdminScopeParams):
    status: Literal[
        "draft",
        "pending_review",
        "approved_for_registration",
        "rejected",
        "registered",
        "activated",
        "superseded",
    ] | None = None


class AdminRegistrationListParams(AdminScopeParams):
    proposal_id: str | None = None
    registry_state: Literal["draft", "registered", "activation_pending", "active", "inactive", "retired"] | None = None


class AdminRegisterProposalBody(AdminScopeParams):
    version: str = "v1"


class AdminActivateRegistrationBody(AdminScopeParams):
    pass


class WidgetChatResult(BaseModel):
    session_id: str
    app_id: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    channel_response: ChannelResponse | None = None


class AdminChatResult(BaseModel):
    session_id: str
    app_id: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    channel_response: ChannelResponse | None = None


class WidgetStreamEvent(BaseModel):
    type: Literal["token", "result", "error"]
    content: str | None = None
    message: str | None = None
    session_id: str | None = None
    app_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class WidgetStreamEventV2(BaseModel):
    type: Literal["token", "block", "state", "action", "result", "error"]
    content: str | None = None
    message: str | None = None
    session_id: str | None = None
    app_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
