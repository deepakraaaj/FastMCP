from __future__ import annotations

from dataclasses import dataclass, field

from tag_fastmcp.core.control_plane_store import ControlPlaneStore
from tag_fastmcp.models.contracts import (
    AgentDefinition,
    AgentProposalDraft,
    AgentRegistrationRecord,
    AgentSelection,
    PolicyEnvelope,
    RegistryAgentPayload,
    RequestContext,
)
from tag_fastmcp.settings import AppSettings


@dataclass(frozen=True)
class _AgentSpec:
    agent_id: str
    agent_kind: str
    display_name: str
    description: str
    provider: str
    model_name: str | None
    default_execution_modes: tuple[str, ...]
    requires_admin: bool = False
    supports_cross_app: bool = False
    requires_envelope_flag: str | None = None
    runtime_state: str = "active"
    capability_ids: tuple[str, ...] = ()


AGENT_SPECS: tuple[_AgentSpec, ...] = (
    _AgentSpec(
        agent_id="agent.app_scoped_chat",
        agent_kind="app_scoped_chat",
        display_name="App Scoped Chat Agent",
        description="Single-app clarification and conversational agent that stays inside one policy envelope.",
        provider="vllm-compatible",
        model_name="runtime-default",
        default_execution_modes=("app_chat", "direct_tool"),
        capability_ids=("tool.agent_chat",),
    ),
    _AgentSpec(
        agent_id="agent.admin_orchestration",
        agent_kind="admin_orchestration",
        display_name="Admin Orchestration Agent",
        description="Privileged cross-app orchestration runtime for approved admin execution.",
        provider="core-runtime",
        model_name=None,
        default_execution_modes=("admin_chat",),
        requires_admin=True,
        supports_cross_app=True,
        runtime_state="active",
        capability_ids=("tool.invoke_capability", "tool.describe_capabilities"),
    ),
    _AgentSpec(
        agent_id="agent.schema_intelligence",
        agent_kind="schema_intelligence",
        display_name="Schema Intelligence Agent",
        description="Schema-pack and understanding-document generation runtime over approved schema discovery output.",
        provider="core-runtime",
        model_name=None,
        default_execution_modes=("admin_chat", "direct_tool"),
        requires_admin=True,
        runtime_state="active",
        capability_ids=("tool.discover_schema", "tool.generate_understanding_doc"),
    ),
    _AgentSpec(
        agent_id="agent.heavy_cross_db",
        agent_kind="heavy_cross_db",
        display_name="Heavy Cross-DB Agent",
        description="Explicit high-cost cross-source execution mode gated by envelope policy.",
        provider="phase-stub",
        model_name=None,
        default_execution_modes=("admin_chat",),
        requires_admin=True,
        supports_cross_app=True,
        requires_envelope_flag="allow_heavy_agent",
        runtime_state="gated",
        capability_ids=(),
    ),
    _AgentSpec(
        agent_id="agent.agent_proposal",
        agent_kind="agent_proposal",
        display_name="Agent Proposal Agent",
        description="Draft-only proposal agent for recurring unmet demand and future capability scaffolding.",
        provider="phase-stub",
        model_name=None,
        default_execution_modes=("admin_chat",),
        requires_admin=True,
        requires_envelope_flag="allow_agent_proposal",
        runtime_state="gated",
        capability_ids=(),
    ),
)


SIMPLE_RUNTIME_AGENT_KINDS = {
    "app_scoped_chat",
    "schema_intelligence",
}


@dataclass
class AgentRegistry:
    settings: AppSettings
    control_plane_store: ControlPlaneStore | None = None
    _dynamic_agents: dict[str, AgentDefinition] = field(default_factory=dict)

    def catalog(self) -> list[RegistryAgentPayload]:
        payloads = [
            self._to_registry_payload(spec)
            for spec in AGENT_SPECS
            if self._spec_allowed_by_profile(spec)
        ]
        payloads.extend(
            RegistryAgentPayload(
                **definition.model_dump(),
                available=definition.runtime_state == "active",
            )
            for definition in self._dynamic_agents.values()
            if self._definition_allowed_by_profile(definition)
        )
        return sorted(payloads, key=lambda item: item.agent_id)

    def available_agents(
        self,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
    ) -> list[AgentDefinition]:
        available: list[AgentDefinition] = []

        for spec in AGENT_SPECS:
            if not self._spec_allowed_by_profile(spec):
                continue
            definition = self._to_definition(spec)
            if self._definition_allowed(definition, request_context, policy_envelope):
                available.append(definition)

        for definition in self._dynamic_agents.values():
            if not self._definition_allowed_by_profile(definition):
                continue
            if self._definition_allowed(definition, request_context, policy_envelope):
                available.append(definition)

        return available

    async def refresh_dynamic_agents(self) -> None:
        if self.control_plane_store is None:
            return
        registrations = await self.control_plane_store.list_registration_records(registry_state="active")
        dynamic_agents: dict[str, AgentDefinition] = {}
        for registration in registrations:
            proposal = await self.control_plane_store.get_proposal_draft(registration.proposal_id)
            definition = self._dynamic_definition(proposal, registration)
            dynamic_agents[definition.agent_id] = definition
        self._dynamic_agents = dynamic_agents

    def activate_dynamic_agent(
        self,
        proposal: AgentProposalDraft,
        registration: AgentRegistrationRecord,
    ) -> AgentDefinition:
        definition = self._dynamic_definition(proposal, registration)
        self._dynamic_agents[definition.agent_id] = definition
        return definition

    def select_agent(
        self,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        *,
        preferred_agent_kind: str | None = None,
    ) -> AgentSelection:
        available = self.available_agents(request_context, policy_envelope)
        if not available:
            raise ValueError(
                f"No agent is available for execution_mode '{request_context.execution_mode}' "
                f"inside the current policy envelope."
            )

        selected = self._select_definition(
            request_context.execution_mode,
            available,
            preferred_agent_kind=preferred_agent_kind,
        )

        reason = (
            f"Selected preferred agent '{selected.agent_kind}' inside execution_mode "
            f"'{request_context.execution_mode}'."
            if preferred_agent_kind
            else f"Selected default agent '{selected.agent_kind}' for execution_mode "
            f"'{request_context.execution_mode}'."
        )
        if selected.runtime_state != "active":
            reason += f" Runtime state is '{selected.runtime_state}', so later phases must supply the concrete implementation."

        return AgentSelection(
            request_id=request_context.request_id,
            execution_mode=request_context.execution_mode,
            agent_id=selected.agent_id,
            agent_kind=selected.agent_kind,
            available_agent_ids=[agent.agent_id for agent in available],
            selection_reason=reason,
            runtime_state=selected.runtime_state,
        )

    def _select_definition(
        self,
        execution_mode: str,
        available: list[AgentDefinition],
        *,
        preferred_agent_kind: str | None,
    ) -> AgentDefinition:
        if preferred_agent_kind is not None:
            for definition in available:
                if definition.agent_kind == preferred_agent_kind:
                    return definition
            raise ValueError(
                f"Agent kind '{preferred_agent_kind}' is not available for execution_mode '{execution_mode}'."
            )

        preferred_order = {
            "app_chat": ["app_scoped_chat"],
            "admin_chat": ["admin_orchestration", "schema_intelligence", "heavy_cross_db", "agent_proposal"],
            "direct_tool": ["app_scoped_chat", "schema_intelligence"],
            "system": [],
        }
        for preferred_kind in preferred_order.get(execution_mode, []):
            matches = [definition for definition in available if definition.agent_kind == preferred_kind]
            if matches:
                return sorted(
                    matches,
                    key=lambda item: (self._runtime_priority(item.runtime_state), item.agent_id),
                )[0]

        return available[0]

    def _to_registry_payload(self, spec: _AgentSpec) -> RegistryAgentPayload:
        definition = self._to_definition(spec)
        return RegistryAgentPayload(
            **definition.model_dump(),
            available=definition.runtime_state == "active",
        )

    def _to_definition(self, spec: _AgentSpec) -> AgentDefinition:
        model_name = self.settings.llm_model if spec.model_name == "runtime-default" else spec.model_name
        return AgentDefinition(
            agent_id=spec.agent_id,
            agent_kind=spec.agent_kind,  # type: ignore[arg-type]
            display_name=spec.display_name,
            description=spec.description,
            provider=spec.provider,
            model_name=model_name,
            default_execution_modes=list(spec.default_execution_modes),  # type: ignore[list-item]
            requires_admin=spec.requires_admin,
            supports_cross_app=spec.supports_cross_app,
            requires_envelope_flag=spec.requires_envelope_flag,
            runtime_state=spec.runtime_state,  # type: ignore[arg-type]
            capability_ids=list(spec.capability_ids),
        )

    def _dynamic_definition(
        self,
        proposal: AgentProposalDraft,
        registration: AgentRegistrationRecord,
    ) -> AgentDefinition:
        agent_kind = self._proposal_kind_to_agent_kind(proposal.proposed_agent_kind)
        default_execution_modes = self._dynamic_execution_modes(agent_kind)
        requires_envelope_flag = {
            "heavy_cross_db": "allow_heavy_agent",
            "agent_proposal": "allow_agent_proposal",
        }.get(agent_kind)
        supports_cross_app = agent_kind in {"admin_orchestration", "heavy_cross_db"} and len(proposal.target_app_ids) > 1
        requires_admin = agent_kind != "app_scoped_chat"
        return AgentDefinition(
            agent_id=registration.agent_id,
            agent_kind=agent_kind,  # type: ignore[arg-type]
            display_name=proposal.display_name,
            description=proposal.justification,
            provider="dynamic-registration",
            model_name=None,
            default_execution_modes=default_execution_modes,  # type: ignore[list-item]
            requires_admin=requires_admin,
            supports_cross_app=supports_cross_app,
            requires_envelope_flag=requires_envelope_flag,
            runtime_state="active",
            capability_ids=list(proposal.proposed_capability_bundle),
        )

    @staticmethod
    def _proposal_kind_to_agent_kind(proposed_kind: str) -> str:
        return {
            "app_chat": "app_scoped_chat",
            "admin_orchestrator": "admin_orchestration",
            "schema_intelligence": "schema_intelligence",
            "heavy_cross_db": "heavy_cross_db",
            "proposal": "agent_proposal",
        }[proposed_kind]

    @staticmethod
    def _dynamic_execution_modes(agent_kind: str) -> list[str]:
        return {
            "app_scoped_chat": ["app_chat", "direct_tool"],
            "admin_orchestration": ["admin_chat"],
            "schema_intelligence": ["admin_chat", "direct_tool"],
            "heavy_cross_db": ["admin_chat"],
            "agent_proposal": ["admin_chat"],
        }[agent_kind]

    def _definition_allowed(
        self,
        definition: AgentDefinition,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
    ) -> bool:
        if request_context.execution_mode not in definition.default_execution_modes:
            return False
        if definition.requires_admin and request_context.role not in {"app_admin", "platform_admin", "service"}:
            return False
        if definition.requires_envelope_flag and not self._envelope_flag(policy_envelope, definition.requires_envelope_flag):
            return False
        if definition.agent_kind == "app_scoped_chat" and "tool.agent_chat" not in policy_envelope.allowed_capability_ids:
            return False
        if definition.agent_kind == "schema_intelligence" and not policy_envelope.allow_schema_discovery:
            return False
        return True

    @staticmethod
    def _envelope_flag(policy_envelope: PolicyEnvelope, name: str) -> bool:
        return bool(getattr(policy_envelope, name, False))

    @staticmethod
    def _runtime_priority(runtime_state: str) -> int:
        return {"active": 0, "stub": 1, "gated": 2}.get(runtime_state, 3)

    def _spec_allowed_by_profile(self, spec: _AgentSpec) -> bool:
        if self.settings.enable_platform_features:
            return True
        return spec.agent_kind in SIMPLE_RUNTIME_AGENT_KINDS

    def _definition_allowed_by_profile(self, definition: AgentDefinition) -> bool:
        if self.settings.enable_platform_features:
            return True
        return definition.agent_kind in SIMPLE_RUNTIME_AGENT_KINDS
