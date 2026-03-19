from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from tag_fastmcp.core.app_router import AppRouter
from tag_fastmcp.core.capability_registry import CapabilityRegistry
from tag_fastmcp.models.contracts import (
    CapabilityPayload,
    PolicyEnvelope,
    RegistryChannelPayload,
    RequestContext,
    SqlPolicyProfile,
)
from tag_fastmcp.settings import AppSettings


@dataclass
class PolicyEnvelopeService:
    settings: AppSettings
    app_router: AppRouter
    capability_registry: CapabilityRegistry

    def derive(
        self,
        request_context: RequestContext,
        *,
        allow_platform_tools: bool = False,
    ) -> PolicyEnvelope:
        all_app_ids = sorted(self.app_router.registry.apps.keys())
        primary_app_id = self._resolve_primary_app(request_context, all_app_ids)
        allowed_app_ids = self._allowed_app_ids(request_context, all_app_ids, primary_app_id)
        registry_snapshots = [self.capability_registry.describe(app_id=app_id) for app_id in allowed_app_ids]

        channels = self._unique_channels(registry_snapshots)
        allowed_channel_ids = [channel.channel_id for channel in channels]
        allowed_formatter_ids = [channel.formatter.formatter_id for channel in channels]

        if request_context.channel_id and request_context.channel_id not in allowed_channel_ids:
            raise ValueError(f"Channel '{request_context.channel_id}' is not allowed for the current scope.")

        capabilities = self._unique_capabilities(registry_snapshots)
        platform_allowlist = self._platform_allowlist(
            request_context.execution_mode,
            allow_platform_tools=allow_platform_tools,
        )
        allowed_capability_ids = sorted(
            capability.capability_id
            for capability in capabilities
            if self._capability_allowed(capability, allowed_app_ids, platform_allowlist)
        )

        allow_cross_app = request_context.execution_mode == "admin_chat" and len(allowed_app_ids) > 1
        require_approval_for = self._require_approval_for(request_context, allow_cross_app=allow_cross_app)

        return PolicyEnvelope(
            envelope_id=uuid.uuid4().hex,
            request_id=request_context.request_id,
            execution_mode=request_context.execution_mode,
            primary_app_id=primary_app_id,
            allowed_app_ids=allowed_app_ids,
            allowed_tenant_ids=[request_context.tenant_id] if request_context.tenant_id else [],
            allowed_capability_ids=allowed_capability_ids,
            allowed_channel_ids=allowed_channel_ids,
            allowed_formatter_ids=allowed_formatter_ids,
            allow_platform_tools=bool(platform_allowlist),
            allow_cross_app=allow_cross_app,
            allow_cross_db=allow_cross_app,
            allow_sql_execution="tool.execute_sql" in allowed_capability_ids,
            allow_external_mcp=any(capability.owner.startswith("mcp_server:") for capability in capabilities),
            allow_schema_discovery="tool.discover_schema" in allowed_capability_ids,
            allow_workflow_execution=any(
                capability.kind == "workflow" or capability.capability_id.startswith("tool.start_workflow")
                for capability in capabilities
                if capability.capability_id in allowed_capability_ids
            ),
            allow_heavy_agent=self._admin_flag(request_context, "allow_heavy_agent"),
            allow_agent_proposal=self._admin_flag(request_context, "allow_agent_proposal"),
            require_approval_for=require_approval_for,
            reveal_sql_to_user=self._reveal_sql(request_context),
            reveal_diagnostics=request_context.role in {"app_admin", "platform_admin", "service"},
            reveal_policy_reasons=request_context.role != "end_user",
            sql_profiles_by_app=self._sql_profiles(allowed_app_ids),
        )

    def _resolve_primary_app(self, request_context: RequestContext, all_app_ids: list[str]) -> str | None:
        requested_app_id = request_context.requested_app_id
        session_bound_app_id = request_context.session_bound_app_id

        if requested_app_id and session_bound_app_id and requested_app_id != session_bound_app_id:
            raise ValueError(
                f"Session '{request_context.session_id}' is already bound to app '{session_bound_app_id}' "
                f"and cannot switch to '{requested_app_id}'."
            )

        if request_context.execution_mode in {"app_chat", "direct_tool"}:
            candidate = requested_app_id or session_bound_app_id
            if candidate:
                self.app_router.resolve(candidate)
                return candidate

            if request_context.execution_mode == "app_chat":
                if self.settings.default_chat_app_id:
                    self.app_router.resolve(self.settings.default_chat_app_id)
                    return self.settings.default_chat_app_id
                if len(all_app_ids) == 1:
                    self.app_router.resolve(all_app_ids[0])
                    return all_app_ids[0]
                raise ValueError(
                    "app_id is required when multiple applications are configured. "
                    "Pass x-app-id from the widget or set TAG_FASTMCP_DEFAULT_CHAT_APP_ID."
                )

            raise ValueError("app_id is required for direct tool execution.")

        if request_context.execution_mode == "admin_chat":
            candidate = requested_app_id or session_bound_app_id
            if candidate:
                self.app_router.resolve(candidate)
                return candidate
            return None

        if requested_app_id:
            self.app_router.resolve(requested_app_id)
            return requested_app_id
        return session_bound_app_id

    def _allowed_app_ids(
        self,
        request_context: RequestContext,
        all_app_ids: list[str],
        primary_app_id: str | None,
    ) -> list[str]:
        if request_context.execution_mode in {"app_chat", "direct_tool"}:
            if primary_app_id is None:
                raise ValueError("A primary app must be resolved before execution.")
            return [primary_app_id]

        if request_context.execution_mode == "admin_chat":
            if request_context.role not in {"app_admin", "platform_admin"}:
                raise ValueError("admin_chat requires an explicit admin role from trusted context.")

            scoped_app_ids = self._scoped_admin_app_ids(request_context, all_app_ids)
            if primary_app_id and primary_app_id not in scoped_app_ids:
                raise ValueError(f"App '{primary_app_id}' is not allowed for the current admin scope.")
            return scoped_app_ids

        return [primary_app_id] if primary_app_id else []

    def _scoped_admin_app_ids(self, request_context: RequestContext, all_app_ids: list[str]) -> list[str]:
        allowed_app_ids = {
            app_id
            for app_id in self._normalized_app_ids(request_context.metadata.get("allowed_app_ids"))
            if app_id in self.app_router.registry.apps
        }
        for scope in request_context.auth_scopes:
            if scope in {"apps:*", "app:*", "platform:*"}:
                return list(all_app_ids)
            if ":" not in scope:
                continue
            prefix, _, value = scope.partition(":")
            if prefix in {"app", "apps"} and value in self.app_router.registry.apps:
                allowed_app_ids.add(value)

        if not allowed_app_ids:
            if request_context.role == "platform_admin":
                return list(all_app_ids)
            if request_context.role == "app_admin":
                candidate = request_context.requested_app_id or request_context.session_bound_app_id
                if candidate:
                    return [candidate]

        if not allowed_app_ids:
            raise ValueError("No admin app scope could be derived from trusted context.")

        return sorted(allowed_app_ids)

    @staticmethod
    def _normalized_app_ids(raw_value: Any) -> list[str]:
        if isinstance(raw_value, str):
            normalized = raw_value.strip()
            return [normalized] if normalized else []
        if isinstance(raw_value, list):
            return [str(item).strip() for item in raw_value if str(item).strip()]
        return []

    @staticmethod
    def _unique_channels(registry_snapshots: list[Any]) -> list[RegistryChannelPayload]:
        channels: dict[str, RegistryChannelPayload] = {}
        for snapshot in registry_snapshots:
            for channel in snapshot.channels:
                channels[channel.channel_id] = channel
        return sorted(channels.values(), key=lambda item: item.channel_id)

    @staticmethod
    def _unique_capabilities(registry_snapshots: list[Any]) -> list[CapabilityPayload]:
        capabilities: dict[str, CapabilityPayload] = {}
        for snapshot in registry_snapshots:
            for capability in snapshot.capabilities:
                if capability.kind == "formatter":
                    continue
                existing = capabilities.get(capability.capability_id)
                if existing is None or existing.app_id is None:
                    capabilities[capability.capability_id] = capability
        return sorted(capabilities.values(), key=lambda item: item.capability_id)

    @staticmethod
    def _platform_allowlist(execution_mode: str, *, allow_platform_tools: bool) -> set[str]:
        if execution_mode == "system":
            return {
                "tool.health_check",
                "tool.start_session",
                "tool.describe_domain",
                "tool.describe_capabilities",
            }
        if execution_mode == "app_chat":
            return {
                "tool.agent_chat",
                "tool.execute_sql",
                "tool.summarize_last_query",
                "tool.run_report",
                "tool.start_workflow",
                "tool.continue_workflow",
                "tool.invoke_capability",
            }
        if execution_mode == "admin_chat":
            return {
                "tool.agent_chat",
                "tool.list_approval_queue",
                "tool.decide_approval",
                "tool.resume_approved_execution",
                "tool.list_agent_proposals",
                "tool.list_agent_registrations",
                "tool.register_agent_proposal",
                "tool.activate_agent_registration",
                "tool.execute_sql",
                "tool.summarize_last_query",
                "tool.run_report",
                "tool.start_workflow",
                "tool.continue_workflow",
                "tool.invoke_capability",
                "tool.discover_schema",
                "tool.describe_domain",
                "tool.describe_capabilities",
            }
        if execution_mode == "direct_tool" and allow_platform_tools:
            return {
                "tool.health_check",
                "tool.start_session",
                "tool.describe_domain",
                "tool.describe_capabilities",
                "tool.list_approval_queue",
                "tool.decide_approval",
                "tool.resume_approved_execution",
                "tool.list_agent_proposals",
                "tool.list_agent_registrations",
                "tool.register_agent_proposal",
                "tool.activate_agent_registration",
                "tool.execute_sql",
                "tool.summarize_last_query",
                "tool.run_report",
                "tool.start_workflow",
                "tool.continue_workflow",
                "tool.discover_schema",
                "tool.agent_chat",
                "tool.invoke_capability",
            }
        return set()

    @staticmethod
    def _capability_allowed(
        capability: CapabilityPayload,
        allowed_app_ids: list[str],
        platform_allowlist: set[str],
    ) -> bool:
        if capability.scope == "app":
            return capability.app_id in allowed_app_ids
        return capability.capability_id in platform_allowlist

    def _sql_profiles(self, allowed_app_ids: list[str]) -> dict[str, SqlPolicyProfile]:
        profiles: dict[str, SqlPolicyProfile] = {}
        for app_id in allowed_app_ids:
            app_ctx = self.app_router.resolve(app_id)
            manifest = app_ctx.domain_registry.manifest
            profiles[app_id] = SqlPolicyProfile(
                allowed_tables=list(manifest.allowed_tables),
                protected_tables=list(manifest.protected_tables),
                allow_mutations=self.settings.allow_mutations,
                require_select_where=self.settings.require_select_where,
            )
        return profiles

    @staticmethod
    def _admin_flag(request_context: RequestContext, key: str) -> bool:
        if request_context.execution_mode != "admin_chat":
            return False
        if request_context.role not in {"app_admin", "platform_admin"}:
            return False
        return PolicyEnvelopeService._bool_flag(request_context.metadata.get(key))

    @staticmethod
    def _reveal_sql(request_context: RequestContext) -> bool:
        if request_context.role not in {"app_admin", "platform_admin", "service"}:
            return False
        return PolicyEnvelopeService._bool_flag(request_context.metadata.get("reveal_sql_to_user"))

    @staticmethod
    def _require_approval_for(request_context: RequestContext, *, allow_cross_app: bool) -> list[str]:
        reasons = set()
        raw_reasons = request_context.metadata.get("require_approval_for")
        if isinstance(raw_reasons, list):
            reasons.update(str(item).strip() for item in raw_reasons if str(item).strip())
        if allow_cross_app:
            reasons.add("cross_app")
        return sorted(reasons)

    @staticmethod
    def _bool_flag(raw_value: Any) -> bool:
        if isinstance(raw_value, bool):
            return raw_value
        if raw_value is None:
            return False
        return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}
