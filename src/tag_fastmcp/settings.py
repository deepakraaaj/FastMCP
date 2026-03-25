from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TAG_FASTMCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    runtime_profile: Literal["simple", "platform"] = "simple"
    app_name: str = "TAG FastMCP"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8001
    transport: Literal["http", "streamable-http", "sse"] = "streamable-http"
    path: str = "/mcp"
    stateless_http: bool = True
    allow_mutations: bool = False
    require_select_where: bool = True
    default_row_limit: int = Field(default=50, ge=1, le=500)
    session_store_backend: Literal["memory", "valkey", "redis"] = "memory"
    idempotency_store_backend: Literal["memory", "valkey", "redis"] = "memory"
    valkey_url: str = Field(
        default="valkey://127.0.0.1:6379/0",
        validation_alias=AliasChoices("valkey_url", "redis_url"),
    )
    valkey_key_prefix: str = Field(
        default="tag_fastmcp",
        validation_alias=AliasChoices("valkey_key_prefix", "redis_key_prefix"),
    )
    session_ttl_seconds: int = Field(default=86_400, ge=0)
    idempotency_ttl_seconds: int = Field(default=86_400, ge=0)
    database_url: str = "sqlite+aiosqlite:///data/tag_fastmcp.sqlite3"
    control_plane_database_url: str | None = None
    apps_config_path: Path = PROJECT_ROOT / "apps.yaml"
    default_chat_app_id: str | None = None
    enable_demo_seed: bool = False
    admin_auth_mode: Literal["auto", "jwt", "dev_header"] = "auto"
    admin_auth_jwt_secret: str | None = None
    admin_auth_jwt_public_key: str | None = None
    admin_auth_jwt_algorithms: list[str] = Field(default_factory=lambda: ["HS256"])
    admin_auth_jwt_issuer: str | None = None
    admin_auth_jwt_audience: str | None = None
    admin_auth_subject_claim: str = "sub"
    admin_auth_actor_id_claim: str = "actor_id"
    admin_auth_role_claim: str = "role"
    admin_auth_scopes_claim: str = "scope"
    admin_auth_allowed_app_ids_claim: str = "allowed_app_ids"
    admin_auth_tenant_id_claim: str = "tenant_id"
    llm_base_url: str = "http://127.0.0.1:8000/v1"
    llm_model: str = "Qwen-Opt-v1.5"
    root_path: Path = PROJECT_ROOT

    @field_validator("admin_auth_jwt_algorithms", mode="before")
    @classmethod
    def _normalize_admin_auth_jwt_algorithms(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def enable_platform_features(self) -> bool:
        return self.runtime_profile == "platform"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
