from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


BuilderNodeType = Literal[
    "start",
    "execute_sql",
    "run_report",
    "start_workflow",
    "continue_workflow",
    "respond",
]


class BuilderNode(BaseModel):
    id: str
    type: BuilderNodeType
    label: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class BuilderEdge(BaseModel):
    source: str
    target: str


class BuilderGraph(BaseModel):
    name: str
    description: str = ""
    actor_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    nodes: list[BuilderNode] = Field(default_factory=list)
    edges: list[BuilderEdge] = Field(default_factory=list)


class BuilderValidationIssue(BaseModel):
    level: Literal["error", "warning"]
    message: str
    node_id: str | None = None


class BuilderValidationResult(BaseModel):
    valid: bool
    ordered_node_ids: list[str] = Field(default_factory=list)
    issues: list[BuilderValidationIssue] = Field(default_factory=list)


class BuilderPreviewStep(BaseModel):
    node_id: str
    node_type: BuilderNodeType
    tool_name: str | None = None
    status: Literal["ok", "error", "skipped"]
    message: str
    output: dict[str, Any] = Field(default_factory=dict)


class BuilderPreviewResult(BaseModel):
    valid: bool
    session_id: str | None = None
    ordered_node_ids: list[str] = Field(default_factory=list)
    issues: list[BuilderValidationIssue] = Field(default_factory=list)
    steps: list[BuilderPreviewStep] = Field(default_factory=list)
