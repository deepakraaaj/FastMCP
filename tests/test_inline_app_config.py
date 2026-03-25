from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client
from sqlalchemy import text

from tag_fastmcp.app import create_app
from tag_fastmcp.core.container import build_container
from tag_fastmcp.settings import AppSettings


def _inline_settings(tmp_path: Path) -> AppSettings:
    apps_yaml = tmp_path / "apps.yaml"
    db_path = tmp_path / "maintenance.sqlite3"
    apps_yaml.write_text(
        f"""
apps:
  maintenance:
    display_name: "Maintenance"
    database_url: "sqlite+aiosqlite:///{db_path}"
    description: "Maintenance domain with inline config-only onboarding."
    allow_mutations: true
    allowed_tables:
      - tasks
      - facilities
    protected_tables:
      - schema_migrations
    reports:
      overdue_tasks:
        description: "Show overdue maintenance tasks with facility info."
        sql: >
          SELECT t.id, t.title, t.status, f.name AS facility
          FROM tasks t
          JOIN facilities f ON f.id = t.facility_id
          WHERE t.status = 'overdue'
    workflows:
      create_task:
        description: "Collect the minimum fields for task creation."
        required_fields:
          - title
          - facility_id
channels:
  web_chat:
    display_name: "Web Chat"
    description: "Primary browser chat surface."
    app_ids:
      - maintenance
    formatter:
      formatter_id: "web_chat.default"
      request_contract: "ChannelRequest[web_chat]"
      response_contract: "ChannelResponse[text]"
      output_modes:
        - text
      supports_streaming: true
""",
        encoding="utf-8",
    )

    return AppSettings(
        apps_config_path=apps_yaml,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_profile="platform",
        stateless_http=True,
        root_path=tmp_path,
    )


async def _bootstrap_inline_database(container) -> None:  # type: ignore[no-untyped-def]
    app_ctx = container.app_router.resolve("maintenance")
    async with app_ctx.query_engine._engine.begin() as conn:
        await conn.execute(text("CREATE TABLE IF NOT EXISTS facilities (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"))
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "facility_id INTEGER, "
                "title TEXT NOT NULL, "
                "status TEXT DEFAULT 'pending', "
                "FOREIGN KEY (facility_id) REFERENCES facilities (id)"
                ")"
            )
        )
        await conn.execute(text("INSERT INTO facilities (name) VALUES ('Plant Alpha')"))
        await conn.execute(
            text(
                "INSERT INTO tasks (facility_id, title, status) "
                "VALUES (1, 'Replace pump', 'overdue')"
            )
        )


async def test_inline_app_config_describes_domain_and_capabilities(tmp_path: Path) -> None:
    settings = _inline_settings(tmp_path)
    container = build_container(settings)
    app = create_app(settings=settings, container=container)
    await _bootstrap_inline_database(container)

    async with Client(app) as client:
        capabilities = await client.call_tool("describe_capabilities", {})
        domain = await client.call_tool("describe_domain", {"app_id": "maintenance"})

    registry = capabilities.structured_content["registry"]
    app_payload = registry["apps"][0]
    capability_ids = {item["capability_id"] for item in registry["capabilities"]}

    assert app_payload["app_id"] == "maintenance"
    assert app_payload["manifest_path"] == "config:apps.maintenance"
    assert app_payload["allowed_tables"] == ["tasks", "facilities"]
    assert "report.maintenance.overdue_tasks" in capability_ids
    assert "workflow.maintenance.create_task" in capability_ids

    domain_payload = domain.structured_content["domain"]
    assert domain_payload["name"] == "maintenance"
    assert domain_payload["description"] == "Maintenance domain with inline config-only onboarding."
    assert domain_payload["allowed_tables"] == ["tasks", "facilities"]
    assert domain_payload["reports"] == ["overdue_tasks"]
    assert domain_payload["workflows"] == ["create_task"]
    assert container.app_router.resolve("maintenance").sql_policy.allow_mutations is True


async def test_inline_app_config_runs_report_and_workflow(tmp_path: Path) -> None:
    settings = _inline_settings(tmp_path)
    container = build_container(settings)
    app = create_app(settings=settings, container=container)
    await _bootstrap_inline_database(container)

    async with Client(app) as client:
        session = await client.call_tool("start_session", {"actor_id": "inline-user"})
        session_id = session.structured_content["session"]["session_id"]
        report = await client.call_tool(
            "run_report",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "report_name": "overdue_tasks",
                }
            },
        )
        workflow = await client.call_tool(
            "start_workflow",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "workflow_id": "create_task",
                    "values": {"title": "Inspect compressor"},
                }
            },
        )

    assert report.structured_content["route"] == "REPORT"
    assert report.structured_content["report"]["report_name"] == "overdue_tasks"
    assert report.structured_content["report"]["row_count"] == 1
    assert workflow.structured_content["status"] == "pending"
    assert workflow.structured_content["workflow"]["missing_fields"] == ["facility_id"]


async def test_inline_app_config_requires_allowed_tables_without_manifest(tmp_path: Path) -> None:
    apps_yaml = tmp_path / "apps.yaml"
    db_path = tmp_path / "maintenance.sqlite3"
    apps_yaml.write_text(
        f"""
apps:
  maintenance:
    display_name: "Maintenance"
    database_url: "sqlite+aiosqlite:///{db_path}"
""",
        encoding="utf-8",
    )
    settings = AppSettings(
        apps_config_path=apps_yaml,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_profile="platform",
        stateless_http=True,
        root_path=tmp_path,
    )
    container = build_container(settings)

    with pytest.raises(ValueError, match="inline allowed_tables"):
        container.app_router.resolve("maintenance")
