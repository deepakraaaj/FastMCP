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


class ResponseEnvelope(BaseModel):
    request_id: str
    route: Literal["SYSTEM", "SQL", "REPORT", "WORKFLOW"]
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
