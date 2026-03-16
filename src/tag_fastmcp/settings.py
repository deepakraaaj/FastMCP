from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
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
    database_url: str = "sqlite+aiosqlite:///data/tag_fastmcp.sqlite3"
    apps_config_path: Path = PROJECT_ROOT / "apps.yaml"
    llm_base_url: str = "http://192.168.15.112:8000/v1"
    llm_model: str = "default"
    root_path: Path = PROJECT_ROOT


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
