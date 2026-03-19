from __future__ import annotations

from pathlib import Path

import pytest

from tag_fastmcp.core.container import build_container
from tag_fastmcp.models.contracts import InvokeCapabilityRequest
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
    tags:
      - web
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
        stateless_http=True,
        root_path=tmp_path,
    )


async def test_chat_service_requires_app_in_multi_app_widget_mode(tmp_path: Path) -> None:
    settings = _multi_app_settings(tmp_path)
    container = build_container(settings)

    with pytest.raises(ValueError, match="app_id is required when multiple applications are configured"):
        await container.chat_service.start_session(requested_app_id=None, user_context=None)


async def test_chat_service_binds_session_scope_and_reuses_it(monkeypatch, tmp_path: Path) -> None:
    settings = _multi_app_settings(tmp_path)
    container = build_container(settings)

    async def fake_chat(self, app_ctx, user_message: str, history=None) -> str:  # type: ignore[no-untyped-def]
        assert app_ctx.app_id == "maintenance"
        assert user_message == "Hello there"
        return "Bound to maintenance."

    monkeypatch.setattr(
        "tag_fastmcp.agent.clarification_agent.ClarificationAgent.chat",
        fake_chat,
    )

    session_id, app_id = await container.chat_service.start_session(
        requested_app_id="maintenance",
        user_context=None,
    )
    snapshot = await container.session_store.get(session_id)

    assert app_id == "maintenance"
    assert snapshot.bound_app_id == "maintenance"
    assert snapshot.execution_mode == "app_chat"

    result = await container.chat_service.chat(
        session_id=session_id,
        message="Hello there",
        requested_app_id=None,
        user_context=None,
    )

    assert result.app_id == "maintenance"
    assert result.metadata["request_context_id"]
    assert result.metadata["policy_envelope_id"]
    assert result.metadata["routing_plan_id"]

    with pytest.raises(ValueError, match="already bound to app 'maintenance'"):
        await container.chat_service.chat(
            session_id=session_id,
            message="Switch apps",
            requested_app_id="dispatch",
            user_context=None,
        )


async def test_policy_envelope_derives_admin_scope_from_trusted_scopes(tmp_path: Path) -> None:
    settings = _multi_app_settings(tmp_path)
    container = build_container(settings)

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

    assert set(policy_envelope.allowed_app_ids) == {"maintenance", "dispatch"}
    assert policy_envelope.primary_app_id == "dispatch"
    assert policy_envelope.allow_cross_app is True
    assert policy_envelope.allow_cross_db is True
    assert policy_envelope.allow_heavy_agent is True
    assert policy_envelope.allow_agent_proposal is True
    assert "tool.describe_capabilities" in policy_envelope.allowed_capability_ids


async def test_direct_tool_scope_rejects_bound_session_app_switch(tmp_path: Path) -> None:
    settings = _multi_app_settings(tmp_path)
    container = build_container(settings)

    session = await container.session_store.start_session(actor_id="worker-1")
    await container.session_store.bind_scope(
        session.session_id,
        app_id="maintenance",
        execution_mode="direct_tool",
    )

    request = InvokeCapabilityRequest(
        app_id="dispatch",
        capability_id="report.dispatch.overdue_tasks",
        session_id=session.session_id,
    )
    request_context = await container.request_contexts.build_from_tool_request(
        request,
        session_id=session.session_id,
    )

    with pytest.raises(ValueError, match="already bound to app 'maintenance'"):
        container.policy_envelopes.derive(request_context)
