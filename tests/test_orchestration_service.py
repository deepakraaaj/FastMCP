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
        stateless_http=True,
        root_path=tmp_path,
    )


async def test_planner_prefers_report_for_read_requests(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="app_chat",
        origin="widget_http",
        requested_app_id="maintenance",
        actor_id="worker-1",
        role="end_user",
        channel_id="web_chat",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)

    planning, compiled = container.orchestration.plan_message(
        request_context=request_context,
        policy_envelope=policy_envelope,
        user_message="Show overdue tasks",
    )

    assert planning.intent_analysis.intent_family == "report"
    assert planning.orchestration_decision.orchestration_mode == "single_step"
    assert planning.orchestration_decision.primary_capability_id == "report.maintenance.overdue_tasks"
    assert compiled.routing_plan.intent_type == "run_report"
    assert compiled.execution_requests[0].capability_id == "report.maintenance.overdue_tasks"


async def test_planner_prefers_workflow_and_clarifies_missing_fields(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="app_chat",
        origin="widget_http",
        requested_app_id="maintenance",
        actor_id="worker-1",
        role="end_user",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)

    planning, compiled = container.orchestration.plan_message(
        request_context=request_context,
        policy_envelope=policy_envelope,
        user_message="Create a task",
    )

    assert planning.intent_analysis.intent_family == "workflow"
    assert planning.orchestration_decision.orchestration_mode == "answer_only"
    assert "workflow.maintenance.create_task" in planning.orchestration_decision.clarification_prompt
    assert "title" in planning.orchestration_decision.clarification_prompt
    assert "facility_id" in planning.orchestration_decision.clarification_prompt
    assert "priority" in planning.orchestration_decision.clarification_prompt
    assert compiled.routing_plan.intent_type == "ask_clarification"


async def test_planner_rejects_cross_app_request_from_app_chat(tmp_path: Path) -> None:
    container = build_container(_multi_app_settings(tmp_path))
    request_context = await container.request_contexts.build(
        execution_mode="app_chat",
        origin="widget_http",
        requested_app_id="maintenance",
        actor_id="worker-1",
        role="end_user",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)

    planning, compiled = container.orchestration.plan_message(
        request_context=request_context,
        policy_envelope=policy_envelope,
        user_message="Compare maintenance and dispatch overdue tasks",
    )

    assert planning.orchestration_decision.orchestration_mode == "reject"
    assert compiled.routing_plan.intent_type == "reject"
    assert "cannot access cross-application data" in planning.orchestration_decision.user_visible_reason


async def test_planner_escalates_heavy_cross_app_admin_request(tmp_path: Path) -> None:
    container = build_container(_multi_app_settings(tmp_path))
    request_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin="admin_http",
        requested_app_id=None,
        actor_id="admin-1",
        role="platform_admin",
        auth_scopes=["apps:*"],
        metadata={"allow_heavy_agent": True},
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=True,
    )

    planning, compiled = container.orchestration.plan_message(
        request_context=request_context,
        policy_envelope=policy_envelope,
        user_message="Compare maintenance and dispatch overdue tasks and reconcile the differences.",
    )

    assert planning.intent_analysis.intent_family == "multi_app_analysis"
    assert planning.orchestration_decision.orchestration_mode == "heavy_agent"
    assert compiled.routing_plan.intent_type == "escalate_heavy_agent"


async def test_planner_compiles_multi_step_workflow_when_context_report_exists(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="app_chat",
        origin="widget_http",
        requested_app_id="maintenance",
        actor_id="worker-1",
        role="end_user",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)

    planning, compiled = container.orchestration.plan_message(
        request_context=request_context,
        policy_envelope=policy_envelope,
        user_message=(
            "Create complex task with title facility_id location_id part_id part_quantity priority"
        ),
    )

    assert planning.orchestration_decision.orchestration_mode == "multi_step"
    assert planning.orchestration_decision.selected_capability_ids == [
        "report.maintenance.complex_task_menu",
        "workflow.maintenance.create_complex_task",
    ]
    assert [request.capability_id for request in compiled.execution_requests] == [
        "report.maintenance.complex_task_menu",
        "workflow.maintenance.create_complex_task",
    ]
