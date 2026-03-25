from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from tag_fastmcp.core.container import build_container
from tag_fastmcp.http_api import create_http_app
from tag_fastmcp.settings import AppSettings


def _simple_settings(tmp_path: Path) -> AppSettings:
    apps_yaml = tmp_path / "apps.yaml"
    manifest_path = Path(__file__).resolve().parents[1] / "domains" / "maintenance.yaml"
    db_path = tmp_path / "simple.sqlite3"
    apps_yaml.write_text(
        f"""
apps:
  maintenance:
    display_name: "Maintenance"
    database_url: "sqlite+aiosqlite:///{db_path}"
    manifest: "{manifest_path}"
""",
        encoding="utf-8",
    )
    return AppSettings(
        apps_config_path=apps_yaml,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        runtime_profile="simple",
        stateless_http=True,
        root_path=tmp_path,
    )


def test_simple_runtime_profile_hides_platform_capabilities(tmp_path: Path) -> None:
    container = build_container(_simple_settings(tmp_path))

    registry = container.capability_registry.describe(app_id="maintenance")
    capability_ids = {item.capability_id for item in registry.capabilities}
    agent_ids = {item.agent_id for item in registry.agents}
    server_ids = {item.server_id for item in registry.mcp_servers}

    assert "tool.invoke_capability" not in capability_ids
    assert "tool.list_approval_queue" not in capability_ids
    assert "tool.preview_builder_graph" not in capability_ids
    assert agent_ids == {"agent.app_scoped_chat", "agent.schema_intelligence"}
    assert server_ids == {"mcp.tag_fastmcp"}
    assert container.control_plane_store is None
    assert container.approvals is None
    assert container.agent_lifecycle is None
    assert container.admin_service is None
    assert container.admin_chat_service is None
    assert container.app_router.resolve("maintenance").builder_runtime is None
    with pytest.raises(RuntimeError, match="Builder runtime is unavailable"):
        _ = container.builder_runtime


async def test_simple_runtime_profile_omits_admin_http_routes(tmp_path: Path) -> None:
    settings = _simple_settings(tmp_path)
    container = build_container(settings)
    app = create_http_app(settings=settings, container=container)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post("/admin/chat", json={"message": "hello"})
    finally:
        await container.close()

    assert response.status_code == 404


async def test_simple_runtime_profile_degrades_platform_only_chat_paths(tmp_path: Path) -> None:
    container = build_container(_simple_settings(tmp_path))

    try:
        session_id, _ = await container.chat_service.start_session(
            requested_app_id="maintenance",
            user_context=None,
        )
        result = await container.chat_service.chat(
            session_id=session_id,
            message="create agent for this app",
            requested_app_id="maintenance",
            user_context=None,
        )
    finally:
        await container.close()

    assert (
        "unavailable in the simple runtime profile" in result.message
        or "not allowed in the current scope" in result.message
    )
