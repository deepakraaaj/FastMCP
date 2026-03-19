from __future__ import annotations

from fastmcp import Client

from tag_fastmcp.app import create_app
from tag_fastmcp.core.container import build_container


async def test_admin_lifecycle_tools_can_review_and_resume_execution(test_app) -> None:
    async with Client(test_app) as client:
        session = await client.call_tool("start_session", {"actor_id": "requester-admin"})
        session_id = session.structured_content["session"]["session_id"]

        invoke = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "session_id": session_id,
                    "kind": "report",
                    "tags": ["overdue_tasks"],
                    "channel_id": "web_chat",
                    "actor_id": "requester-admin",
                    "role": "app_admin",
                    "metadata": {
                        "require_approval_for": ["manual_review"],
                    },
                }
            },
        )
        approval_id = invoke.structured_content["meta"]["approval_id"]

        queue = await client.call_tool(
            "list_approval_queue",
            {
                "request": {
                    "app_id": "maintenance",
                    "actor_id": "reviewer-admin",
                    "role": "app_admin",
                    "metadata": {
                        "allowed_app_ids": ["maintenance"],
                    },
                }
            },
        )
        queue_payload = queue.structured_content
        assert queue_payload["lifecycle"]["approval_queue"][0]["approval_id"] == approval_id

        decision = await client.call_tool(
            "decide_approval",
            {
                "request": {
                    "app_id": "maintenance",
                    "actor_id": "reviewer-admin",
                    "role": "app_admin",
                    "approval_id": approval_id,
                    "decision": "approve",
                    "metadata": {
                        "allowed_app_ids": ["maintenance"],
                    },
                }
            },
        )
        decision_payload = decision.structured_content
        assert decision_payload["lifecycle"]["approval_request"]["status"] == "approved"

        resumed = await client.call_tool(
            "resume_approved_execution",
            {
                "request": {
                    "app_id": "maintenance",
                    "actor_id": "reviewer-admin",
                    "role": "app_admin",
                    "approval_id": approval_id,
                    "metadata": {
                        "allowed_app_ids": ["maintenance"],
                    },
                }
            },
        )

    payload = resumed.structured_content
    assert payload["route"] == "ROUTING"
    assert payload["status"] == "ok"
    assert payload["meta"]["approval_id"] == approval_id
    assert payload["routing"]["downstream_route"] == "REPORT"
    assert payload["routing"]["output"]["report"]["report_name"] == "overdue_tasks"
    assert payload["lifecycle"]["paused_execution"]["status"] == "resumed"


async def test_activated_dynamic_agent_is_exposed_in_registry(app_settings) -> None:
    container = build_container(app_settings)
    app = create_app(settings=app_settings, container=container)

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

    async with Client(app) as client:
        decision = await client.call_tool(
            "decide_approval",
            {
                "request": {
                    "app_id": "maintenance",
                    "actor_id": "platform-admin",
                    "role": "platform_admin",
                    "approval_id": pending.approval_request.approval_id,
                    "decision": "approve",
                    "auth_scopes": ["apps:*"],
                    "metadata": {
                        "allowed_app_ids": ["maintenance"],
                    },
                }
            },
        )
        assert decision.structured_content["lifecycle"]["proposal_draft"]["status"] == "approved_for_registration"

        registration = await client.call_tool(
            "register_agent_proposal",
            {
                "request": {
                    "app_id": "maintenance",
                    "actor_id": "platform-admin",
                    "role": "platform_admin",
                    "proposal_id": pending.proposal_draft.proposal_id,
                    "auth_scopes": ["apps:*"],
                    "metadata": {
                        "allowed_app_ids": ["maintenance"],
                    },
                }
            },
        )
        registration_id = registration.structured_content["lifecycle"]["registration_record"]["registration_id"]

        activation = await client.call_tool(
            "activate_agent_registration",
            {
                "request": {
                    "app_id": "maintenance",
                    "actor_id": "platform-admin",
                    "role": "platform_admin",
                    "registration_id": registration_id,
                    "auth_scopes": ["apps:*"],
                    "metadata": {
                        "allowed_app_ids": ["maintenance"],
                    },
                }
            },
        )
        assert activation.structured_content["lifecycle"]["registration_record"]["registry_state"] == "active"

        registry_result = await client.call_tool("describe_capabilities", {"app_id": "maintenance"})

    agents = {agent["agent_id"]: agent for agent in registry_result.structured_content["registry"]["agents"]}
    dynamic_agent_id = activation.structured_content["lifecycle"]["registration_record"]["agent_id"]
    assert dynamic_agent_id in agents
    assert agents[dynamic_agent_id]["runtime_state"] == "active"
    assert agents[dynamic_agent_id]["provider"] == "dynamic-registration"
