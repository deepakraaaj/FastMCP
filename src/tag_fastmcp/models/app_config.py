from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExternalToolConfig(BaseModel):
    display_name: str
    description: str
    input_schema: str
    output_schema: str
    argument_style: Literal["flat", "request"] = "flat"
    tags: list[str] = Field(default_factory=list)
    requires_session: bool = False
    supports_idempotency: bool = False
    timeout_seconds: float = 10.0
    max_retries: int = 0
    retry_backoff_ms: int = 0
    fallback_capability_id: str | None = None
    fallback_hint: str | None = None


class MCPServerConfig(BaseModel):
    display_name: str
    description: str
    transport: Literal["streamable-http", "http", "sse", "stdio"]
    endpoint: str
    auth_mode: Literal["none", "bearer", "oidc", "apikey", "session"] = "none"
    enabled: bool = True
    app_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_reset_seconds: int = 30
    tools: dict[str, ExternalToolConfig] = Field(default_factory=dict)


class FormatterContractConfig(BaseModel):
    formatter_id: str
    request_contract: str
    response_contract: str
    output_modes: list[str] = Field(default_factory=list)
    supports_streaming: bool = False
    supports_actions: bool = False
    supports_approvals: bool = False


class ChannelConfig(BaseModel):
    display_name: str
    description: str
    app_ids: list[str] = Field(default_factory=list)
    formatter: FormatterContractConfig
    tags: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    display_name: str
    database_url: str
    manifest: str


class AppsRegistry(BaseModel):
    apps: dict[str, AppConfig] = Field(default_factory=dict)
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    channels: dict[str, ChannelConfig] = Field(default_factory=dict)
