from __future__ import annotations

from pathlib import Path

from tag_fastmcp.core.container import build_container
from tag_fastmcp.models.contracts import ChatExecutionPlan
from tag_fastmcp.settings import AppSettings


def _sql_chat_settings(tmp_path: Path, *, allow_mutations: bool) -> AppSettings:
    apps_yaml = tmp_path / "apps.yaml"
    db_path = tmp_path / "ops.sqlite3"
    apps_yaml.write_text(
        f"""
apps:
  ops:
    display_name: "Ops"
    database_url: "sqlite+aiosqlite:///{db_path}"
    description: "Operations database"
    allow_mutations: {str(allow_mutations).lower()}
    require_select_where: true
    allowed_tables:
      - tasks
      - facilities
    protected_tables:
      - schema_migrations
channels:
  web_chat:
    display_name: "Web Chat"
    description: "Primary browser chat surface."
    app_ids:
      - ops
    formatter:
      formatter_id: "web_chat.default"
      request_contract: "ChannelRequest[web_chat]"
      response_contract: "ChannelResponse[text|card|dashboard]"
      output_modes:
        - text
        - card
      supports_streaming: true
      supports_actions: true
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


async def test_answer_only_chat_can_execute_safe_read_sql(monkeypatch, tmp_path: Path) -> None:
    async def fake_plan(self, app_ctx, user_message, history=None):  # type: ignore[no-untyped-def]
        return ChatExecutionPlan(
            intent="read_query",
            proposed_sql="SELECT id, title, status FROM tasks WHERE status = 'pending'",
        )

    async def fail_chat(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Clarification fallback should not run for a generated read query.")

    async def fake_execute(self, *, session_id, app_id, sql, allow_mutations, intent):  # type: ignore[no-untyped-def]
        await self.session_store.set_last_query(session_id, sql)
        await self.session_store.append_event(
            session_id,
            {
                "type": "sql",
                "query": sql,
                "row_count": 1,
                "app_id": app_id,
            },
        )
        return (
            "I found 1 row. Preview: id=1, title=Inspect pump, status=pending.",
            {
                "query": sql,
                "row_count": 1,
                "rows_preview": [{"id": 1, "title": "Inspect pump", "status": "pending"}],
                "sql_result": {
                    "ran": True,
                    "query": sql,
                    "row_count": 1,
                    "rows_preview": [{"id": 1, "title": "Inspect pump", "status": "pending"}],
                    "policy": {
                        "allowed": True,
                        "reason": "SQL allowed.",
                        "tables": ["tasks"],
                        "normalized_sql": sql,
                    },
                },
                "selected_capability_id": "chat.generated_sql",
                "selected_capability_ids": ["chat.generated_sql"],
            },
        )

    monkeypatch.setattr("tag_fastmcp.agent.structured_chat_agent.StructuredChatAgent.plan", fake_plan)
    monkeypatch.setattr("tag_fastmcp.agent.clarification_agent.ClarificationAgent.chat", fail_chat)
    monkeypatch.setattr("tag_fastmcp.core.chat_service.ChatService._execute_sql_plan", fake_execute)

    settings = _sql_chat_settings(tmp_path, allow_mutations=False)
    container = build_container(settings)

    try:
        session_id, _ = await container.chat_service.start_session(
            requested_app_id="ops",
            user_context=None,
        )
        result = await container.chat_service.chat(
            session_id=session_id,
            message="show my pending tasks",
            requested_app_id="ops",
            user_context=None,
        )
    finally:
        await container.close()

    assert result.metadata["chat_plan_intent"] == "read_query"
    assert "I found 1 row" in result.message


async def test_answer_only_chat_requires_confirmation_for_safe_write(monkeypatch, tmp_path: Path) -> None:
    async def fake_plan(self, app_ctx, user_message, history=None):  # type: ignore[no-untyped-def]
        return ChatExecutionPlan(
            intent="insert",
            proposed_sql=(
                "INSERT INTO tasks (facility_id, title, status) "
                "VALUES (1, 'Inspect valve', 'pending')"
            ),
            confirmation_message="I can create the task 'Inspect valve'. Reply 'confirm' to run it or 'cancel' to stop.",
        )

    async def fake_execute(self, *, session_id, app_id, sql, allow_mutations, intent):  # type: ignore[no-untyped-def]
        await self.session_store.set_last_query(session_id, sql)
        await self.session_store.append_event(
            session_id,
            {
                "type": "sql",
                "query": sql,
                "row_count": 1,
                "app_id": app_id,
            },
        )
        return (
            "I executed the insert successfully on tasks and affected 1 row.",
            {
                "query": sql,
                "row_count": 1,
                "rows_preview": [],
                "sql_result": {
                    "ran": True,
                    "query": sql,
                    "row_count": 1,
                    "rows_preview": [],
                    "policy": {
                        "allowed": True,
                        "reason": "SQL allowed.",
                        "tables": ["tasks"],
                        "normalized_sql": sql,
                    },
                },
                "selected_capability_id": "chat.generated_sql",
                "selected_capability_ids": ["chat.generated_sql"],
            },
        )

    monkeypatch.setattr("tag_fastmcp.agent.structured_chat_agent.StructuredChatAgent.plan", fake_plan)
    monkeypatch.setattr("tag_fastmcp.core.chat_service.ChatService._execute_sql_plan", fake_execute)

    settings = _sql_chat_settings(tmp_path, allow_mutations=True)
    container = build_container(settings)

    try:
        session_id, _ = await container.chat_service.start_session(
            requested_app_id="ops",
            user_context=None,
        )
        staged = await container.chat_service.chat(
            session_id=session_id,
            message="create a task called Inspect valve",
            requested_app_id="ops",
            user_context=None,
        )
        confirmed = await container.chat_service.chat(
            session_id=session_id,
            message="confirm",
            requested_app_id="ops",
            user_context=None,
        )
        snapshot = await container.session_store.get(session_id)
    finally:
        await container.close()

    assert staged.metadata["chat_plan_intent"] == "insert"
    assert "Reply 'confirm'" in staged.message
    assert confirmed.metadata["chat_plan_intent"] == "insert"
    assert "executed the insert successfully" in confirmed.message
    assert snapshot.last_query and snapshot.last_query.startswith("INSERT INTO tasks")
