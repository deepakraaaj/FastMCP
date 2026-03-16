from __future__ import annotations

from fastmcp import Client


async def test_workflow_collects_missing_fields(test_app) -> None:
    async with Client(test_app) as client:
        session = await client.call_tool("start_session", {"actor_id": "workflow-user"})
        session_id = session.structured_content["session"]["session_id"]
        start = await client.call_tool(
            "start_workflow",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "workflow_id": "create_task",
                    "values": {"title": "Inspect gearbox"},
                }
            },
        )
        continue_result = await client.call_tool(
            "continue_workflow",
            {
                "request": {
                    "app_id": "maintenance",
                    "values": {"facility_id": 1, "priority": "high"},
                }
            },
        )

    assert start.structured_content["status"] == "pending"
    assert "facility_id" in start.structured_content["workflow"]["missing_fields"]
    assert continue_result.structured_content["status"] == "ok"
    assert continue_result.structured_content["workflow"]["state"] == "completed"
