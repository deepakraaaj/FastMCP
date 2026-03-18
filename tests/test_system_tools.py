from __future__ import annotations

from fastmcp import Client


async def test_describe_capabilities_returns_registry_snapshot(test_app) -> None:
    async with Client(test_app) as client:
        result = await client.call_tool("describe_capabilities", {})

    payload = result.structured_content
    assert payload["route"] == "SYSTEM"
    assert payload["status"] == "ok"
    assert payload["meta"]["app_count"] == 1
    assert payload["meta"]["agent_count"] == 1
    assert payload["meta"]["mcp_server_count"] == 2

    registry = payload["registry"]
    assert registry["apps"][0]["app_id"] == "maintenance"
    capability_ids = {item["capability_id"] for item in registry["capabilities"]}
    assert "tool.execute_sql" in capability_ids
    assert "tool.describe_capabilities" in capability_ids
    assert "report.maintenance.overdue_tasks" in capability_ids
    assert "workflow.maintenance.create_task" in capability_ids
    assert "tool.github.search_issues" in capability_ids
    assert "formatter.web_chat.default" in capability_ids

    server_ids = {item["server_id"] for item in registry["mcp_servers"]}
    assert "mcp.tag_fastmcp" in server_ids
    assert "github" in server_ids

    channels = {item["channel_id"]: item for item in registry["channels"]}
    assert "web_chat" in channels
    assert channels["web_chat"]["formatter"]["response_contract"] == "ChannelResponse[text|card|dashboard]"
    assert channels["web_chat"]["formatter"]["supports_streaming"] is True


async def test_describe_capabilities_can_filter_one_app(test_app) -> None:
    async with Client(test_app) as client:
        result = await client.call_tool("describe_capabilities", {"app_id": "maintenance"})

    registry = result.structured_content["registry"]
    assert len(registry["apps"]) == 1
    assert registry["apps"][0]["app_id"] == "maintenance"
    assert len(registry["channels"]) == 1
    servers = {item["server_id"]: item for item in registry["mcp_servers"]}
    assert servers["github"]["app_ids"] == ["maintenance"]
