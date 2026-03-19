from __future__ import annotations

from fastmcp import Client


async def test_invoke_capability_routes_report_by_tags(routed_test_app) -> None:
    async with Client(routed_test_app) as client:
        session = await client.call_tool("start_session", {"actor_id": "router-user"})
        session_id = session.structured_content["session"]["session_id"]
        result = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "kind": "report",
                    "tags": ["overdue_tasks"],
                    "channel_id": "web_chat",
                }
            },
        )

    payload = result.structured_content
    assert payload["route"] == "ROUTING"
    assert payload["status"] == "ok"
    assert payload["meta"]["request_context_id"]
    assert payload["meta"]["policy_envelope_id"]
    assert payload["meta"]["routing_plan_id"]
    assert payload["meta"]["orchestration_decision_id"]
    assert payload["meta"]["orchestration_mode"] == "single_step"
    assert payload["meta"]["response_state"] == "ok"
    assert payload["meta"]["primary_mode"] == "card"
    assert payload["routing"]["selected_capability_id"] == "report.maintenance.overdue_tasks"
    assert payload["routing"]["request_context_id"] == payload["meta"]["request_context_id"]
    assert payload["routing"]["policy_envelope_id"] == payload["meta"]["policy_envelope_id"]
    assert payload["routing"]["routing_plan_id"] == payload["meta"]["routing_plan_id"]
    assert payload["routing"]["selection_mode"] == "tags"
    assert payload["routing"]["formatter_id"] == "web_chat.default"
    assert payload["routing"]["downstream_route"] == "REPORT"
    assert payload["routing"]["output"]["report"]["report_name"] == "overdue_tasks"
    assert payload["presentation"]["primary_mode"] == "card"
    assert payload["presentation"]["state"]["status"] == "ok"


async def test_invoke_capability_dispatches_registered_external_mcp_tool(routed_test_app) -> None:
    async with Client(routed_test_app) as client:
        result = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "capability_id": "tool.github.search_issues",
                    "arguments": {
                        "repository": "kriti/fits",
                        "query": "hydraulic pump",
                    },
                }
            },
        )

    payload = result.structured_content
    assert payload["route"] == "ROUTING"
    assert payload["status"] == "ok"
    assert payload["routing"]["selected_capability_id"] == "tool.github.search_issues"
    assert payload["routing"]["server_id"] == "github"
    assert payload["routing"]["downstream_route"] == "TOOL"
    assert payload["routing"]["attempts"] == 1
    assert payload["routing"]["circuit_breaker_state"] == "closed"
    assert payload["routing"]["output"]["issues"][0]["repository"] == "kriti/fits"


async def test_invoke_capability_retries_transient_external_failure(routed_test_app) -> None:
    async with Client(routed_test_app) as client:
        result = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "capability_id": "tool.github.search_issues",
                    "arguments": {
                        "repository": "kriti/fits",
                        "query": "transient failure",
                    },
                }
            },
        )

    payload = result.structured_content
    assert payload["status"] == "ok"
    assert payload["routing"]["attempts"] == 2
    assert payload["routing"]["fallback_used"] is False
    assert payload["routing"]["circuit_breaker_state"] == "closed"
    assert payload["routing"]["output"]["message"] == "Found issues for 'transient failure'."


async def test_invoke_capability_falls_back_when_external_mcp_fails(routed_test_app) -> None:
    async with Client(routed_test_app) as client:
        session = await client.call_tool("start_session", {"actor_id": "router-user"})
        session_id = session.structured_content["session"]["session_id"]
        result = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "capability_id": "tool.github.search_issues",
                    "channel_id": "web_chat",
                    "arguments": {
                        "repository": "kriti/fits",
                        "query": "always fail",
                    },
                }
            },
        )

    payload = result.structured_content
    assert payload["status"] == "ok"
    assert payload["routing"]["selected_capability_id"] == "report.maintenance.overdue_tasks"
    assert payload["routing"]["fallback_used"] is True
    assert payload["routing"]["fallback_capability_id"] == "report.maintenance.overdue_tasks"
    assert payload["routing"]["attempts"] == 3
    assert payload["routing"]["circuit_breaker_state"] == "closed"
    assert payload["routing"]["downstream_route"] == "REPORT"
    assert payload["routing"]["formatter_id"] == "web_chat.default"
    assert "Falling back" in payload["warnings"][0]


async def test_invoke_capability_opens_circuit_breaker_after_repeated_failures(routed_test_app) -> None:
    async with Client(routed_test_app) as client:
        session = await client.call_tool("start_session", {"actor_id": "router-user"})
        session_id = session.structured_content["session"]["session_id"]

        first = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "capability_id": "tool.github.search_issues",
                    "arguments": {
                        "repository": "kriti/fits",
                        "query": "slow call",
                    },
                }
            },
        )
        second = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "capability_id": "tool.github.search_issues",
                    "arguments": {
                        "repository": "kriti/fits",
                        "query": "slow call",
                    },
                }
            },
        )
        third = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "capability_id": "tool.github.search_issues",
                    "arguments": {
                        "repository": "kriti/fits",
                        "query": "slow call",
                    },
                }
            },
        )

    first_payload = first.structured_content
    second_payload = second.structured_content
    third_payload = third.structured_content

    assert first_payload["routing"]["circuit_breaker_state"] == "closed"
    assert second_payload["routing"]["circuit_breaker_state"] == "open"
    assert third_payload["routing"]["circuit_breaker_state"] == "open"
    assert third_payload["routing"]["attempts"] == 1
    assert third_payload["routing"]["fallback_used"] is True
    assert third_payload["routing"]["downstream_route"] == "REPORT"
