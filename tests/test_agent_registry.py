from __future__ import annotations

from pathlib import Path

from tag_fastmcp.core.container import build_container
from tag_fastmcp.settings import AppSettings


def _multi_app_settings(tmp_path: Path) -> AppSettings:
    apps_yaml = tmp_path / "apps.yaml"
    manifest_path = Path(__file__).resolve().parents[1] / "domains" / "maintenance.yaml"
    maintenance_db = tmp_path / "maintenance.sqlite3"
    dispatch_db = tmp_path / "dispatch.sqlite3"

    apps_yaml.write_text(
        f"""
apps:
  maintenance:
    display_name: "Maintenance"
    database_url: "sqlite+aiosqlite:///{maintenance_db}"
    manifest: "{manifest_path}"
  dispatch:
    display_name: "Dispatch"
    database_url: "sqlite+aiosqlite:///{dispatch_db}"
    manifest: "{manifest_path}"
channels:
  web_chat:
    display_name: "Web Chat"
    description: "Primary browser chat surface."
    app_ids:
      - maintenance
      - dispatch
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
        database_url=f"sqlite+aiosqlite:///{maintenance_db}",
        runtime_profile="platform",
        stateless_http=True,
        root_path=tmp_path,
    )


async def test_agent_registry_selects_app_scoped_chat_for_widget_mode(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="app_chat",
        origin="widget_http",
        requested_app_id="maintenance",
        actor_id="worker-1",
        role="end_user",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)

    available = container.agent_registry.available_agents(request_context, policy_envelope)
    selection = container.agent_registry.select_agent(request_context, policy_envelope)

    assert [agent.agent_kind for agent in available] == ["app_scoped_chat"]
    assert selection.agent_kind == "app_scoped_chat"
    assert selection.runtime_state == "active"


async def test_agent_registry_exposes_admin_agents_only_when_scope_allows(tmp_path: Path) -> None:
    container = build_container(_multi_app_settings(tmp_path))
    request_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin="admin_http",
        requested_app_id="dispatch",
        actor_id="admin-1",
        role="platform_admin",
        auth_scopes=["apps:*"],
        metadata={
            "allow_heavy_agent": True,
            "allow_agent_proposal": True,
        },
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=True,
    )

    available = container.agent_registry.available_agents(request_context, policy_envelope)
    selection = container.agent_registry.select_agent(request_context, policy_envelope)
    available_kinds = [agent.agent_kind for agent in available]

    assert available_kinds == [
        "admin_orchestration",
        "schema_intelligence",
        "heavy_cross_db",
        "agent_proposal",
    ]
    assert selection.agent_kind == "admin_orchestration"
    assert selection.runtime_state == "active"


async def test_agent_registry_rejects_forbidden_agent_kind_in_app_mode(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="app_chat",
        origin="widget_http",
        requested_app_id="maintenance",
        actor_id="worker-1",
        role="end_user",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)

    try:
        container.agent_registry.select_agent(
            request_context,
            policy_envelope,
            preferred_agent_kind="heavy_cross_db",
        )
    except ValueError as exc:
        assert "not available" in str(exc)
    else:
        raise AssertionError("Expected forbidden heavy agent selection to be rejected.")


async def test_agent_registry_allows_schema_intelligence_for_direct_tool_service_role(
    app_settings,
) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="direct_tool",
        origin="mcp_tool",
        requested_app_id="maintenance",
        actor_id="service-worker",
        role="service",
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=True,
    )

    selection = container.agent_registry.select_agent(
        request_context,
        policy_envelope,
        preferred_agent_kind="schema_intelligence",
    )

    assert selection.agent_kind == "schema_intelligence"
    assert selection.runtime_state == "active"


def test_capability_registry_exposes_understanding_doc_tool_and_schema_agent(app_settings) -> None:
    container = build_container(app_settings)
    registry = container.capability_registry.describe(app_id="maintenance")

    capability_ids = {item.capability_id for item in registry.capabilities}
    agents = {item.agent_id: item for item in registry.agents}

    assert "tool.generate_understanding_doc" in capability_ids
    assert agents["agent.schema_intelligence"].runtime_state == "active"
    assert "tool.generate_understanding_doc" in agents["agent.schema_intelligence"].capability_ids
