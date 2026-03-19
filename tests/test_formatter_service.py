from __future__ import annotations

from tag_fastmcp.core.container import build_container


async def test_visibility_profile_hides_diagnostics_for_end_user_app_chat(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="app_chat",
        origin="widget_http",
        requested_app_id="maintenance",
        actor_id="worker-1",
        role="end_user",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)

    profile = container.visibility_policy.derive(
        request_context=request_context,
        policy_envelope=policy_envelope,
    )

    assert profile.show_plan_summary is False
    assert profile.show_capability_ids is False
    assert profile.show_app_scope is False
    assert profile.show_sql_text is False
    assert profile.show_trace_id is False
    assert profile.show_retry_and_fallback is False
    assert profile.show_actions is False


async def test_visibility_profile_allows_richer_admin_diagnostics(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="admin_chat",
        origin="admin_http",
        requested_app_id="maintenance",
        actor_id="admin-1",
        role="platform_admin",
        auth_scopes=["apps:*"],
        metadata={"reveal_sql_to_user": True},
    )
    policy_envelope = container.policy_envelopes.derive(
        request_context,
        allow_platform_tools=True,
    )

    profile = container.visibility_policy.derive(
        request_context=request_context,
        policy_envelope=policy_envelope,
    )

    assert profile.show_plan_summary is True
    assert profile.show_capability_ids is True
    assert profile.show_app_scope is True
    assert profile.show_sql_text is True
    assert profile.show_trace_id is True
    assert profile.show_retry_and_fallback is True
    assert profile.show_approval_metadata is True
    assert profile.show_escalation_metadata is True


async def test_formatter_service_falls_back_to_text_when_channel_is_unavailable(app_settings) -> None:
    container = build_container(app_settings)
    request_context = await container.request_contexts.build(
        execution_mode="app_chat",
        origin="widget_http",
        requested_app_id="maintenance",
        actor_id="worker-1",
        role="end_user",
    )
    policy_envelope = container.policy_envelopes.derive(request_context)

    rendered = container.formatter_service.render(
        request_context=request_context,
        policy_envelope=policy_envelope,
        route="report",
        primary_message="I ran the overdue task report.",
        execution_payload={
            "report": {
                "report_name": "overdue_tasks",
                "row_count": 1,
                "rows_preview": [{"title": "Replace pump"}],
                "query": "SELECT * FROM tasks",
            },
            "selected_capability_ids": ["report.maintenance.overdue_tasks"],
        },
        channel_id="missing_channel",
    )

    assert rendered.channel_response.channel_id == "text_fallback"
    assert rendered.channel_response.formatter_id == "text.fallback"
    assert rendered.channel_response.primary_mode == "text"
    assert rendered.channel_response.state.status == "ok"
    assert rendered.channel_response.diagnostics == {}
