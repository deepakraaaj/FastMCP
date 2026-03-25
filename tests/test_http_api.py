from __future__ import annotations

import base64
import json
from pathlib import Path

import jwt
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from tag_fastmcp.core.container import build_container
from tag_fastmcp.http_api import create_http_app
from tag_fastmcp.models.contracts import InvokeCapabilityRequest
from tag_fastmcp.settings import AppSettings


ADMIN_JWT_SECRET = "test-admin-secret"


def _context_header(payload: dict[str, object]) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def _admin_bearer_headers(payload: dict[str, object], *, secret: str = ADMIN_JWT_SECRET) -> dict[str, str]:
    claims = {
        "sub": payload.get("auth_subject") or payload.get("actor_id") or "admin-user",
        "role": payload.get("role", "platform_admin"),
    }
    if payload.get("actor_id") is not None:
        claims["actor_id"] = payload["actor_id"]
    if payload.get("tenant_id") is not None:
        claims["tenant_id"] = payload["tenant_id"]
    if payload.get("auth_scopes") is not None:
        claims["scope"] = payload["auth_scopes"]
    if payload.get("allowed_app_ids") is not None:
        claims["allowed_app_ids"] = payload["allowed_app_ids"]
    token = jwt.encode(claims, secret, algorithm="HS256")
    return {"authorization": f"Bearer {token}"}


async def _bootstrap_widget_database(container) -> None:  # type: ignore[no-untyped-def]
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
      response_contract: "ChannelResponse[text|card|dashboard]"
      output_modes:
        - text
        - card
        - dashboard
      supports_streaming: true
      supports_actions: true
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


async def test_widget_session_start_returns_session_and_app(app_settings) -> None:
    container = build_container(app_settings)
    app = create_http_app(settings=app_settings, container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/session/start",
            headers={
                "x-app-id": "maintenance",
                "x-user-context": _context_header(
                    {
                        "user_id": "u-123",
                        "user_name": "Deepak",
                        "company_id": "c-42",
                        "company_name": "Kriti",
                    }
                ),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["app_id"] == "maintenance"
    assert isinstance(payload["session_id"], str)
    assert payload["session_id"]
    snapshot = await container.session_store.get(payload["session_id"])
    assert snapshot.bound_app_id == "maintenance"
    assert snapshot.execution_mode == "app_chat"


async def test_apps_endpoint_lists_available_apps(app_settings) -> None:
    container = build_container(app_settings)
    app = create_http_app(settings=app_settings, container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/apps")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_app_id"] == "maintenance"
    assert payload["apps"][0]["app_id"] == "maintenance"
    assert payload["apps"][0]["display_name"] == "Maintenance Test"
    assert payload["apps"][0]["domain_name"] == "maintenance"
    assert payload["apps"][0]["allowed_tables"] == [
        "tasks",
        "facilities",
        "locations",
        "parts",
        "task_parts",
        "audit_logs",
    ]


async def test_widget_chat_routes_report_without_llm(monkeypatch, app_settings) -> None:
    async def fail_chat(*args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        raise AssertionError("The clarification agent should not run for a direct report route.")

    monkeypatch.setattr(
        "tag_fastmcp.agent.clarification_agent.ClarificationAgent.chat",
        fail_chat,
    )

    container = build_container(app_settings)
    await _bootstrap_widget_database(container)
    app = create_http_app(settings=app_settings, container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        start_response = await client.post(
            "/session/start",
            headers={
                "x-app-id": "maintenance",
                "x-user-context": _context_header(
                    {
                        "user_id": "u-321",
                        "user_name": "Deepak",
                    }
                ),
            },
        )
        session_id = start_response.json()["session_id"]

        chat_response = await client.post(
            "/chat?stream=false",
            json={
                "session_id": session_id,
                "message": "Show overdue tasks",
            },
            headers={
                "x-app-id": "maintenance",
                "x-user-context": _context_header(
                    {
                        "user_id": "u-321",
                        "user_name": "Deepak",
                    }
                ),
            },
        )

    assert chat_response.status_code == 200
    events = [json.loads(line) for line in chat_response.text.splitlines() if line.strip()]
    assert events[-1]["type"] == "result"
    assert events[-1]["orchestration_mode"] == "single_step"
    assert events[-1]["primary_capability_id"] == "report.maintenance.overdue_tasks"
    assert "I ran report 'overdue_tasks'" in events[-1]["message"]


async def test_widget_chat_can_emit_rich_formatter_events(monkeypatch, app_settings) -> None:
    async def fail_chat(*args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        raise AssertionError("The clarification agent should not run for a direct report route.")

    monkeypatch.setattr(
        "tag_fastmcp.agent.clarification_agent.ClarificationAgent.chat",
        fail_chat,
    )

    container = build_container(app_settings)
    await _bootstrap_widget_database(container)
    app = create_http_app(settings=app_settings, container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        start_response = await client.post(
            "/session/start",
            headers={
                "x-app-id": "maintenance",
                "x-user-context": _context_header(
                    {
                        "user_id": "u-654",
                        "user_name": "Deepak",
                    }
                ),
            },
        )
        session_id = start_response.json()["session_id"]

        chat_response = await client.post(
            "/chat?stream=false&rich=true",
            json={
                "session_id": session_id,
                "message": "Show overdue tasks",
            },
            headers={
                "x-app-id": "maintenance",
                "x-user-context": _context_header(
                    {
                        "user_id": "u-654",
                        "user_name": "Deepak",
                    }
                ),
            },
        )

    assert chat_response.status_code == 200
    events = [json.loads(line) for line in chat_response.text.splitlines() if line.strip()]
    event_types = [event["type"] for event in events]
    assert event_types[0] == "token"
    assert event_types.count("block") >= 2
    assert "state" in event_types
    assert events[-1]["type"] == "result"
    assert events[-1]["channel_response"]["primary_mode"] == "card"
    assert events[-1]["channel_response"]["state"]["status"] == "ok"


async def test_widget_http_api_handles_cors_preflight(app_settings) -> None:
    app = create_http_app(settings=app_settings, container=build_container(app_settings))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.options(
            "/session/start",
            headers={
                "origin": "http://localhost:5173",
                "access-control-request-method": "POST",
                "access-control-request-headers": "content-type,x-app-id,x-user-context",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST" in response.headers["access-control-allow-methods"]


async def test_widget_chat_streams_token_and_result(monkeypatch, app_settings) -> None:
    async def fake_chat(self, app_ctx, user_message: str, history=None) -> str:  # type: ignore[no-untyped-def]
        assert app_ctx.app_id == "maintenance"
        assert user_message == "Hello there"
        assert history and history[0]["role"] == "system"
        return "Here are the open tasks."

    monkeypatch.setattr(
        "tag_fastmcp.agent.clarification_agent.ClarificationAgent.chat",
        fake_chat,
    )

    container = build_container(app_settings)
    app = create_http_app(settings=app_settings, container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        start_response = await client.post(
            "/session/start",
            headers={
                "x-app-id": "maintenance",
                "x-user-context": _context_header(
                    {
                        "user_id": "u-123",
                        "user_name": "Deepak",
                    }
                ),
            },
        )
        session_id = start_response.json()["session_id"]

        chat_response = await client.post(
            "/chat?stream=false",
            json={
                "session_id": session_id,
                "message": "Hello there",
            },
            headers={
                "x-app-id": "maintenance",
                "x-user-context": _context_header(
                    {
                        "user_id": "u-123",
                        "user_name": "Deepak",
                    }
                ),
            },
        )

    assert chat_response.status_code == 200
    events = [json.loads(line) for line in chat_response.text.splitlines() if line.strip()]
    assert events[0]["type"] == "token"
    assert events[0]["content"] == "Here are the open tasks."
    assert events[-1]["type"] == "result"
    assert events[-1]["message"] == "Here are the open tasks."
    assert events[-1]["app_id"] == "maintenance"
    assert events[-1]["request_context_id"]
    assert events[-1]["policy_envelope_id"]
    assert events[-1]["routing_plan_id"]
    assert events[-1]["agent_id"] == "agent.app_scoped_chat"
    assert events[-1]["agent_kind"] == "app_scoped_chat"

    snapshot = await container.session_store.get(session_id)
    assert [event["type"] for event in snapshot.history] == [
        "chat_context",
        "chat_message",
        "chat_message",
    ]
    assert snapshot.bound_app_id == "maintenance"


async def test_widget_chat_streams_development_error_detail(monkeypatch, app_settings) -> None:
    async def fail_chat(*args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        raise RuntimeError("database connection failed")

    monkeypatch.setattr(
        "tag_fastmcp.core.chat_service.ChatService.chat",
        fail_chat,
    )

    container = build_container(app_settings)
    app = create_http_app(settings=app_settings, container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        chat_response = await client.post(
            "/chat?rich=true",
            json={
                "session_id": "session-dev-error",
                "message": "Hello there",
            },
            headers={
                "x-app-id": "maintenance",
            },
        )

    assert chat_response.status_code == 200
    events = [json.loads(line) for line in chat_response.text.splitlines() if line.strip()]
    assert events[-1]["type"] == "error"
    assert events[-1]["message"] == "database connection failed"


async def test_admin_http_requires_trusted_admin_context(app_settings) -> None:
    app = create_http_app(settings=app_settings, container=build_container(app_settings))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/admin/approvals")

    assert response.status_code == 401
    assert "x-admin-context" in response.json()["error"]


async def test_admin_http_requires_bearer_token_in_production(app_settings) -> None:
    settings = app_settings.model_copy(
        update={
            "environment": "production",
            "admin_auth_jwt_secret": ADMIN_JWT_SECRET,
        }
    )
    app = create_http_app(settings=settings, container=build_container(settings))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/admin/approvals")

    assert response.status_code == 401
    assert "Authorization: Bearer" in response.json()["error"]


async def test_admin_http_rejects_dev_header_in_production(app_settings) -> None:
    settings = app_settings.model_copy(
        update={
            "environment": "production",
            "admin_auth_jwt_secret": ADMIN_JWT_SECRET,
        }
    )
    app = create_http_app(settings=settings, container=build_container(settings))
    admin_header = _context_header(
        {
            "actor_id": "reviewer-admin",
            "role": "app_admin",
            "allowed_app_ids": ["maintenance"],
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            "/admin/approvals",
            headers={"x-admin-context": admin_header},
        )

    assert response.status_code == 401
    assert "development mode" in response.json()["error"]


async def test_admin_http_can_review_and_resume_execution(app_settings) -> None:
    container = build_container(app_settings)
    await _bootstrap_widget_database(container)
    app = create_http_app(settings=app_settings, container=container)

    session = await container.session_store.start_session(actor_id="requester-admin")
    request = InvokeCapabilityRequest(
        app_id="maintenance",
        session_id=session.session_id,
        kind="report",
        tags=["overdue_tasks"],
        channel_id="web_chat",
        actor_id="requester-admin",
        role="app_admin",
        metadata={"require_approval_for": ["manual_review"]},
    )
    request_context = await container.request_contexts.build_from_tool_request(
        request,
        session_id=session.session_id,
        origin="internal",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)
    compiled = container.orchestration.plan_direct_request(
        request=request,
        request_context=request_context,
        policy_envelope=policy_envelope,
    )
    pending = await container.approvals.request_execution_approval(
        request_context=request_context,
        policy_envelope=policy_envelope,
        routing_plan=compiled.routing_plan,
        orchestration_decision=compiled.orchestration_decision,
        execution_requests=compiled.execution_requests,
    )
    approval_id = pending.approval_request.approval_id
    admin_header = _context_header(
        {
            "actor_id": "reviewer-admin",
            "role": "app_admin",
            "allowed_app_ids": ["maintenance"],
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        queue = await client.get(
            "/admin/approvals",
            params={"app_id": "maintenance"},
            headers={"x-admin-context": admin_header},
        )
        decision = await client.post(
            f"/admin/approvals/{approval_id}/decision",
            json={"app_id": "maintenance", "decision": "approve"},
            headers={"x-admin-context": admin_header},
        )
        resumed = await client.post(
            f"/admin/approvals/{approval_id}/resume",
            json={"app_id": "maintenance"},
            headers={"x-admin-context": admin_header},
        )

    assert queue.status_code == 200
    assert queue.json()["lifecycle"]["approval_queue"][0]["approval_id"] == approval_id
    assert decision.status_code == 200
    assert decision.json()["lifecycle"]["approval_request"]["status"] == "approved"
    assert resumed.status_code == 200
    payload = resumed.json()
    assert payload["route"] == "ROUTING"
    assert payload["status"] == "ok"
    assert payload["meta"]["approval_id"] == approval_id
    assert payload["routing"]["downstream_route"] == "REPORT"
    assert payload["routing"]["output"]["report"]["report_name"] == "overdue_tasks"
    assert payload["lifecycle"]["paused_execution"]["status"] == "resumed"


async def test_admin_http_can_register_and_activate_agent_proposal(app_settings) -> None:
    container = build_container(app_settings)
    app = create_http_app(settings=app_settings, container=container)

    request_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin="admin_http",
        requested_app_id="maintenance",
        actor_id="platform-admin",
        role="platform_admin",
        auth_scopes=["apps:*"],
        metadata={
            "allow_agent_proposal": True,
            "allowed_app_ids": ["maintenance"],
        },
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=True,
    )
    planning, compiled = container.orchestration.plan_message(
        request_context=request_context,
        policy_envelope=policy_envelope,
        user_message="Create a dedicated maintenance orchestration agent.",
    )
    pending = await container.agent_lifecycle.create_proposal_draft(
        request_context=request_context,
        policy_envelope=policy_envelope,
        planning=planning,
        compiled=compiled,
        user_message="Create a dedicated maintenance orchestration agent.",
    )
    admin_header = _context_header(
        {
            "actor_id": "platform-admin",
            "role": "platform_admin",
            "auth_scopes": ["apps:*"],
            "allowed_app_ids": ["maintenance"],
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        proposals = await client.get(
            "/admin/agents/proposals",
            params={"app_id": "maintenance"},
            headers={"x-admin-context": admin_header},
        )
        decision = await client.post(
            f"/admin/approvals/{pending.approval_request.approval_id}/decision",
            json={"app_id": "maintenance", "decision": "approve"},
            headers={"x-admin-context": admin_header},
        )
        registration = await client.post(
            f"/admin/agents/proposals/{pending.proposal_draft.proposal_id}/register",
            json={"app_id": "maintenance"},
            headers={"x-admin-context": admin_header},
        )
        registration_id = registration.json()["lifecycle"]["registration_record"]["registration_id"]
        activation = await client.post(
            f"/admin/agents/registrations/{registration_id}/activate",
            json={"app_id": "maintenance"},
            headers={"x-admin-context": admin_header},
        )
        registrations = await client.get(
            "/admin/agents/registrations",
            params={"app_id": "maintenance"},
            headers={"x-admin-context": admin_header},
        )

    assert proposals.status_code == 200
    assert proposals.json()["lifecycle"]["proposal_drafts"][0]["proposal_id"] == pending.proposal_draft.proposal_id
    assert decision.status_code == 200
    assert decision.json()["lifecycle"]["proposal_draft"]["status"] == "approved_for_registration"
    assert registration.status_code == 200
    assert registration.json()["lifecycle"]["registration_record"]["registry_state"] == "registered"
    assert activation.status_code == 200
    assert activation.json()["lifecycle"]["registration_record"]["registry_state"] == "active"
    records = registrations.json()["lifecycle"]["registration_records"]
    assert any(record["registration_id"] == registration_id and record["registry_state"] == "active" for record in records)


async def test_admin_chat_requires_trusted_admin_context(app_settings) -> None:
    app = create_http_app(settings=app_settings, container=build_container(app_settings))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/admin/chat", json={"message": "Show overdue tasks"})

    assert response.status_code == 401
    assert "x-admin-context" in response.json()["error"]


async def test_admin_chat_accepts_bearer_jwt_in_production(monkeypatch, app_settings) -> None:
    async def fail_chat(*args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        raise AssertionError("The clarification agent should not run for a direct admin report route.")

    monkeypatch.setattr(
        "tag_fastmcp.agent.clarification_agent.ClarificationAgent.chat",
        fail_chat,
    )

    settings = app_settings.model_copy(
        update={
            "environment": "production",
            "admin_auth_jwt_secret": ADMIN_JWT_SECRET,
        }
    )
    container = build_container(settings)
    await _bootstrap_widget_database(container)
    app = create_http_app(settings=settings, container=container)
    admin_headers = _admin_bearer_headers(
        {
            "actor_id": "reviewer-admin",
            "role": "app_admin",
            "allowed_app_ids": ["maintenance"],
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/admin/chat?rich=true",
            json={
                "message": "Show overdue tasks",
                "app_id": "maintenance",
                "channel_id": "web_chat",
            },
            headers=admin_headers,
        )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    result = events[-1]
    assert result["type"] == "result"
    assert result["orchestration_mode"] == "single_step"
    assert result["primary_capability_id"] == "report.maintenance.overdue_tasks"
    assert result["agent_kind"] == "admin_orchestration"


async def test_admin_chat_routes_report_without_llm(monkeypatch, app_settings) -> None:
    async def fail_chat(*args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        raise AssertionError("The clarification agent should not run for a direct admin report route.")

    monkeypatch.setattr(
        "tag_fastmcp.agent.clarification_agent.ClarificationAgent.chat",
        fail_chat,
    )

    container = build_container(app_settings)
    await _bootstrap_widget_database(container)
    app = create_http_app(settings=app_settings, container=container)
    admin_header = _context_header(
        {
            "actor_id": "reviewer-admin",
            "role": "app_admin",
            "allowed_app_ids": ["maintenance"],
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/admin/chat?rich=true",
            json={
                "message": "Show overdue tasks",
                "app_id": "maintenance",
                "channel_id": "web_chat",
            },
            headers={"x-admin-context": admin_header},
        )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    result = events[-1]
    assert result["type"] == "result"
    assert result["orchestration_mode"] == "single_step"
    assert result["primary_capability_id"] == "report.maintenance.overdue_tasks"
    assert result["agent_kind"] == "admin_orchestration"
    assert result["agent_runtime_state"] == "active"
    assert result["response_state"] == "ok"
    assert result["session_id"]
    snapshot = await container.session_store.get(result["session_id"])
    assert snapshot.execution_mode == "admin_chat"
    assert snapshot.bound_app_id is None


async def test_admin_chat_clarifies_missing_app_target_for_multi_app_scope(tmp_path: Path) -> None:
    settings = _multi_app_settings(tmp_path)
    app = create_http_app(settings=settings, container=build_container(settings))
    admin_header = _context_header(
        {
            "actor_id": "platform-admin",
            "role": "platform_admin",
            "auth_scopes": ["apps:*"],
            "allowed_app_ids": ["maintenance", "dispatch"],
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/admin/chat",
            json={
                "message": "Show overdue tasks",
                "channel_id": "web_chat",
            },
            headers={"x-admin-context": admin_header},
        )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    result = events[-1]
    assert result["type"] == "result"
    assert result["intent_family"] == "clarify"
    assert "Select which application to use" in result["message"]
    assert "dispatch" in result["message"]
    assert "maintenance" in result["message"]


async def test_admin_chat_requests_heavy_escalation_for_cross_app_scope(tmp_path: Path) -> None:
    settings = _multi_app_settings(tmp_path)
    app = create_http_app(settings=settings, container=build_container(settings))
    admin_header = _context_header(
        {
            "actor_id": "platform-admin",
            "role": "platform_admin",
            "auth_scopes": ["apps:*"],
            "allowed_app_ids": ["maintenance", "dispatch"],
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/admin/chat?rich=true",
            json={
                "message": "Compare maintenance and dispatch overdue tasks and reconcile the differences.",
                "channel_id": "web_chat",
            },
            headers={"x-admin-context": admin_header},
        )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    result = events[-1]
    assert result["type"] == "result"
    assert result["orchestration_mode"] == "heavy_agent"
    assert result["intent_family"] == "multi_app_analysis"
    assert set(result["allowed_app_ids"]) == {"maintenance", "dispatch"}
    assert result["response_state"] == "approval_required"
    assert result["approval_id"]
    assert result["channel_response"]["state"]["status"] == "approval_required"
