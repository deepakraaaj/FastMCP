from __future__ import annotations

import anyio
from pathlib import Path

import pytest
from fastmcp import FastMCP

from tag_fastmcp.app import create_app
from tag_fastmcp.core.container import build_container
from tag_fastmcp.settings import AppSettings


@pytest.fixture
def app_settings(tmp_path: Path) -> AppSettings:
    # Create a mock apps.yaml
    apps_yaml = tmp_path / "apps.yaml"
    manifest_path = Path(__file__).resolve().parents[1] / "domains" / "maintenance.yaml"
    db_path = tmp_path / "test.sqlite3"
    
    with apps_yaml.open("w") as f:
        f.write(f"""
apps:
  maintenance:
    display_name: "Maintenance Test"
    database_url: "sqlite+aiosqlite:///{db_path}"
    manifest: "{manifest_path}"
mcp_servers:
  github:
    display_name: "GitHub MCP"
    description: "External GitHub integration server."
    transport: "streamable-http"
    endpoint: "http://github-mcp.local/mcp"
    auth_mode: "bearer"
    app_ids:
      - maintenance
    tags:
      - github
      - scm
    tools:
      search_issues:
        display_name: "Search Issues"
        description: "Search GitHub issues for one repository."
        input_schema: "GitHubIssueSearchRequest"
        output_schema: "GitHubIssueSearchResponse"
        timeout_seconds: 0.01
        max_retries: 1
        retry_backoff_ms: 0
        fallback_capability_id: "report.maintenance.overdue_tasks"
        tags:
          - issues
          - search
        supports_idempotency: true
    circuit_breaker_failure_threshold: 2
    circuit_breaker_reset_seconds: 60
channels:
  web_chat:
    display_name: "Web Chat"
    description: "Primary browser chat surface."
    app_ids:
      - maintenance
    tags:
      - web
      - realtime
    formatter:
      formatter_id: "web_chat.default"
      request_contract: "ChannelRequest[web_chat]"
      response_contract: "ChannelResponse[text|card|dashboard]"
      output_modes:
        - text
        - card
        - dashboard
      supports_streaming: true
      supports_actions: true
""")

    return AppSettings(
        apps_config_path=apps_yaml,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_profile="platform",
        stateless_http=True,
        root_path=tmp_path
    )


async def _bootstrap_database(container) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    app_ctx = container.app_router.resolve("maintenance")
    async with app_ctx.query_engine._engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                facility_id INTEGER,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (facility_id) REFERENCES facilities (id)
            );
        """))
        await conn.execute(text("INSERT INTO facilities (name) VALUES ('Test Facility')"))
        await conn.execute(text("INSERT INTO tasks (title, status) VALUES ('Initial Task', 'pending')"))


@pytest.fixture
async def test_app(app_settings):
    container = build_container(app_settings)
    app = create_app(settings=app_settings, container=container)
    await _bootstrap_database(container)
    return app


@pytest.fixture
def external_github_app():
    app = FastMCP(name="GitHub MCP", version="0.1.0")
    attempts = {"transient failure": 0, "always fail": 0, "slow call": 0}

    @app.tool
    async def search_issues(repository: str, query: str) -> dict:
        if query == "transient failure":
            attempts[query] += 1
            if attempts[query] == 1:
                return {
                    "status": "error",
                    "route": "TOOL",
                    "message": "Transient upstream failure.",
                }
        if query == "always fail":
            attempts[query] += 1
            return {
                "status": "error",
                "route": "TOOL",
                "message": "Persistent upstream failure.",
            }
        if query == "slow call":
            attempts[query] += 1
            await anyio.sleep(0.05)

        return {
            "status": "ok",
            "route": "TOOL",
            "message": f"Found issues for '{query}'.",
            "issues": [
                {"repository": repository, "title": "Hydraulic pump fault", "number": 42},
            ],
        }

    return app


@pytest.fixture
async def routed_test_app(app_settings, external_github_app):
    container = build_container(app_settings)
    container.mcp_target_overrides["github"] = external_github_app
    app = create_app(settings=app_settings, container=container)
    await _bootstrap_database(container)
    return app
