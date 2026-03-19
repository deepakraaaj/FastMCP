from __future__ import annotations

import uuid
from dataclasses import dataclass

from tag_fastmcp.models.contracts import PolicyEnvelope, RequestContext, VisibilityProfile


@dataclass
class VisibilityPolicyService:
    def derive(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
    ) -> VisibilityProfile:
        role = request_context.role
        execution_mode = request_context.execution_mode
        diagnostics = policy_envelope.reveal_diagnostics
        show_actions = role != "end_user" and execution_mode != "direct_tool"

        if role == "end_user" and execution_mode == "app_chat":
            return VisibilityProfile(
                profile_id=uuid.uuid4().hex,
                actor_role=role,
                execution_mode=execution_mode,
                show_plan_summary=False,
                show_capability_ids=False,
                show_app_scope=False,
                show_sql_text=False,
                show_trace_id=False,
                show_retry_and_fallback=False,
                show_approval_metadata=False,
                show_escalation_metadata=False,
                show_raw_errors=False,
                show_actions=False,
            )

        show_capability_ids = role in {"app_admin", "platform_admin", "service"}
        show_app_scope = role in {"app_admin", "platform_admin", "service"}
        show_plan_summary = role in {"app_admin", "platform_admin", "service"} and (
            policy_envelope.reveal_policy_reasons or execution_mode != "app_chat"
        )
        show_sql_text = policy_envelope.reveal_sql_to_user and role in {"app_admin", "platform_admin", "service"}
        show_trace_id = diagnostics or execution_mode in {"admin_chat", "direct_tool"}
        show_retry_and_fallback = diagnostics or role in {"platform_admin", "service"}
        show_approval_metadata = role in {"app_admin", "platform_admin", "service"}
        show_escalation_metadata = role in {"app_admin", "platform_admin", "service"}
        show_raw_errors = diagnostics and role in {"platform_admin", "service"}

        return VisibilityProfile(
            profile_id=uuid.uuid4().hex,
            actor_role=role,
            execution_mode=execution_mode,
            show_plan_summary=show_plan_summary,
            show_capability_ids=show_capability_ids,
            show_app_scope=show_app_scope,
            show_sql_text=show_sql_text,
            show_trace_id=show_trace_id,
            show_retry_and_fallback=show_retry_and_fallback,
            show_approval_metadata=show_approval_metadata,
            show_escalation_metadata=show_escalation_metadata,
            show_raw_errors=show_raw_errors,
            show_actions=show_actions,
        )
