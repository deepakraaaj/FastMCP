from __future__ import annotations

from fastmcp import Client

from tag_fastmcp.app import create_app
from tag_fastmcp.core.container import build_container
from tag_fastmcp.models.contracts import InvokeCapabilityRequest


async def test_invoke_capability_creates_pending_execution_approval(app_settings) -> None:
    container = build_container(app_settings)
    app = create_app(settings=app_settings, container=container)

    async with Client(app) as client:
        result = await client.call_tool(
            "invoke_capability",
            {
                "request": {
                    "app_id": "maintenance",
                    "kind": "report",
                    "tags": ["overdue_tasks"],
                    "channel_id": "web_chat",
                    "actor_id": "requester-1",
                    "role": "app_admin",
                    "metadata": {
                        "require_approval_for": ["manual_review"],
                    },
                }
            },
        )

    payload = result.structured_content
    approval_id = payload["meta"]["approval_id"]
    assert payload["status"] == "pending"
    assert payload["meta"]["approval_scope_type"] == "execution"
    assert payload["routing"]["downstream_status"] == "pending"
    assert payload["presentation"]["state"]["status"] == "approval_required"

    approval = await container.approvals.get_approval_request(approval_id)
    paused = await container.control_plane_store.get_paused_execution_by_approval(approval_id)
    assert approval.status == "pending"
    assert paused is not None
    assert paused.status == "pending_approval"
    assert paused.routing_plan.selected_capability_id == "report.maintenance.overdue_tasks"


async def test_execution_approval_rejection_updates_paused_state(app_settings) -> None:
    container = build_container(app_settings)
    request = InvokeCapabilityRequest(
        app_id="maintenance",
        capability_id="report.maintenance.overdue_tasks",
        actor_id="requester-2",
        role="app_admin",
        metadata={"require_approval_for": ["manual_review"]},
    )
    request_context = await container.request_contexts.build_from_tool_request(
        request,
        session_id=None,
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=True,
    )
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

    reviewer_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin="admin_http",
        requested_app_id="maintenance",
        actor_id="reviewer-1",
        role="app_admin",
        metadata={"allowed_app_ids": ["maintenance"]},
    )
    reviewer_envelope = container.policy_envelopes.derive(
        reviewer_context,
        allow_platform_tools=True,
    )
    approval, decision = await container.approvals.decide(
        request_context=reviewer_context,
        policy_envelope=reviewer_envelope,
        approval_id=pending.approval_request.approval_id,
        decision="reject",
        comment="Rejected for validation.",
    )

    paused = await container.control_plane_store.get_paused_execution_by_approval(approval.approval_id)
    audits = await container.approvals.list_audit_events(approval_id=approval.approval_id)

    assert approval.status == "rejected"
    assert decision.resulting_status == "rejected"
    assert paused is not None
    assert paused.status == "rejected"
    assert [event.event_type for event in audits] == [
        "approval_requested",
        "approval_rejected",
    ]


async def test_execution_approval_can_resume_after_approval(app_settings) -> None:
    container = build_container(app_settings)
    request = InvokeCapabilityRequest(
        app_id="maintenance",
        capability_id="report.maintenance.overdue_tasks",
        actor_id="requester-3",
        role="app_admin",
        metadata={"require_approval_for": ["manual_review"]},
    )
    request_context = await container.request_contexts.build_from_tool_request(
        request,
        session_id=None,
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=True,
    )
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

    reviewer_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin="admin_http",
        requested_app_id="maintenance",
        actor_id="reviewer-2",
        role="app_admin",
        metadata={"allowed_app_ids": ["maintenance"]},
    )
    reviewer_envelope = container.policy_envelopes.derive(
        reviewer_context,
        allow_platform_tools=True,
    )
    approval, _ = await container.approvals.decide(
        request_context=reviewer_context,
        policy_envelope=reviewer_envelope,
        approval_id=pending.approval_request.approval_id,
        decision="approve",
    )
    resumed = await container.approvals.resume_execution(
        request_context=reviewer_context,
        policy_envelope=reviewer_envelope,
        approval_id=approval.approval_id,
    )

    assert approval.status == "approved"
    assert resumed.status == "resumed"
    assert resumed.execution_requests[0].capability_id == "report.maintenance.overdue_tasks"


async def test_agent_proposal_requires_approval_then_registration(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin="admin_http",
        requested_app_id="maintenance",
        actor_id="platform-admin-1",
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
        user_message="Create a dedicated agent for maintenance approval triage.",
    )
    pending = await container.agent_lifecycle.create_proposal_draft(
        request_context=request_context,
        policy_envelope=policy_envelope,
        planning=planning,
        compiled=compiled,
        user_message="Create a dedicated agent for maintenance approval triage.",
    )

    assert compiled.orchestration_decision.orchestration_mode == "proposal"
    assert compiled.orchestration_decision.requires_approval is True
    assert pending.proposal_draft.status == "pending_review"
    assert pending.approval_request.scope_type == "agent_lifecycle"

    approval, _ = await container.approvals.decide(
        request_context=request_context,
        policy_envelope=policy_envelope,
        approval_id=pending.approval_request.approval_id,
        decision="approve",
    )
    updated_proposal = await container.agent_lifecycle.sync_proposal_from_approval(approval)
    registration = await container.agent_lifecycle.register_proposal(
        request_context=request_context,
        policy_envelope=policy_envelope,
        proposal_id=pending.proposal_draft.proposal_id,
    )
    refreshed_proposal = await container.agent_lifecycle.get_proposal_draft(
        pending.proposal_draft.proposal_id
    )

    assert updated_proposal is not None
    assert updated_proposal.status == "approved_for_registration"
    assert registration.registry_state == "registered"
    assert refreshed_proposal.status == "registered"


async def test_agent_registration_activation_is_explicit(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin="admin_http",
        requested_app_id="maintenance",
        actor_id="platform-admin-2",
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
        user_message="Create a new maintenance workflow agent.",
    )
    pending = await container.agent_lifecycle.create_proposal_draft(
        request_context=request_context,
        policy_envelope=policy_envelope,
        planning=planning,
        compiled=compiled,
        user_message="Create a new maintenance workflow agent.",
    )
    approval, _ = await container.approvals.decide(
        request_context=request_context,
        policy_envelope=policy_envelope,
        approval_id=pending.approval_request.approval_id,
        decision="approve",
    )
    await container.agent_lifecycle.sync_proposal_from_approval(approval)
    registration = await container.agent_lifecycle.register_proposal(
        request_context=request_context,
        policy_envelope=policy_envelope,
        proposal_id=pending.proposal_draft.proposal_id,
    )

    assert registration.registry_state == "registered"

    activated = await container.agent_lifecycle.activate_registration(
        request_context=request_context,
        registration_id=registration.registration_id,
    )
    proposal = await container.agent_lifecycle.get_proposal_draft(
        pending.proposal_draft.proposal_id
    )

    assert activated.registry_state == "active"
    assert proposal.status == "activated"
