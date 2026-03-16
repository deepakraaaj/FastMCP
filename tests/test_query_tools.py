from __future__ import annotations

from fastmcp import Client


async def test_execute_sql_is_idempotent(test_app) -> None:
    async with Client(test_app) as client:
        session_result = await client.call_tool("start_session", {"actor_id": "tester"})
        session_id = session_result.structured_content["session"]["session_id"]

        payload = {
            "app_id": "maintenance",
            "session_id": session_id,
            "sql": "SELECT id, title, status FROM tasks WHERE status = 'pending'",
            "idempotency_key": "same-request",
        }
        first = await client.call_tool("execute_sql", {"request": payload})
        second = await client.call_tool("execute_sql", {"request": payload})

    assert first.structured_content["status"] == "ok"
    assert second.structured_content["meta"]["idempotent_replay"] is True
    assert second.structured_content["sql"]["row_count"] == first.structured_content["sql"]["row_count"]


async def test_session_state_is_reused_between_calls(test_app) -> None:
    async with Client(test_app) as client:
        await client.call_tool("start_session", {"actor_id": "tester"})
        result = await client.call_tool(
            "execute_sql",
            {
                "request": {
                    "app_id": "maintenance",
                    "sql": "SELECT id, title, status FROM tasks WHERE status = 'pending'",
                }
            },
        )

    assert result.structured_content["status"] == "ok"
    assert result.structured_content["session_id"]


async def test_report_tool_runs_manifest_report(test_app) -> None:
    async with Client(test_app) as client:
        session = await client.call_tool("start_session", {"actor_id": "report-user"})
        session_id = session.structured_content["session"]["session_id"]
        result = await client.call_tool(
            "run_report",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "report_name": "overdue_tasks",
                }
            },
        )

    assert result.structured_content["route"] == "REPORT"
    assert result.structured_content["report"]["report_name"] == "overdue_tasks"
