from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from tag_fastmcp.core.control_plane_store import ControlPlaneStore, utcnow
from tag_fastmcp.core.intent_planner import PlanningArtifacts
from tag_fastmcp.core.plan_compiler import CompiledOrchestration
from tag_fastmcp.models.contracts import (
    AgentProposalDraft,
    AgentRegistrationRecord,
    ApprovalRequest,
    LifecycleAuditEvent,
    PolicyEnvelope,
    RequestContext,
)

if False:  # pragma: no cover
    from tag_fastmcp.core.agent_registry import AgentRegistry


@dataclass
class PendingAgentProposal:
    proposal_draft: AgentProposalDraft
    approval_request: ApprovalRequest
    user_visible_message: str


@dataclass
class AgentLifecycleService:
    store: ControlPlaneStore
    agent_registry: AgentRegistry | None = None

    async def create_proposal_draft(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        planning: PlanningArtifacts,
        compiled: CompiledOrchestration,
        user_message: str,
    ) -> PendingAgentProposal:
        proposal_id = self._identifier("prp")
        proposed_kind = self._proposed_agent_kind(
            request_context=request_context,
            policy_envelope=policy_envelope,
            user_message=user_message,
        )
        draft = AgentProposalDraft(
            proposal_id=proposal_id,
            status="pending_review",
            tenant_id=request_context.tenant_id,
            target_app_ids=list(policy_envelope.allowed_app_ids),
            proposed_agent_kind=proposed_kind,
            display_name=self._display_name(proposed_kind, policy_envelope),
            problem_statement=user_message.strip() or compiled.orchestration_decision.user_visible_reason,
            justification=compiled.orchestration_decision.user_visible_reason,
            proposed_capability_bundle=self._capability_bundle(planning, compiled),
            required_permissions=list(policy_envelope.require_approval_for),
            required_channels=[request_context.channel_id] if request_context.channel_id else [],
            draft_spec_payload={
                "request_context_ref": request_context.request_id,
                "routing_plan_ref": compiled.routing_plan.plan_id,
                "planning_request_id": planning.planning_input.request_id,
                "candidate_capability_ids": list(planning.planning_input.candidate_capability_ids),
                "execution_mode": request_context.execution_mode,
                "allowed_app_ids": list(policy_envelope.allowed_app_ids),
                "intent_family": planning.intent_analysis.intent_family,
            },
            proposed_by_actor_id=request_context.actor_id,
            generated_by_system=True,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        await self.store.put_proposal_draft(draft)
        await self.store.append_audit_event(
            LifecycleAuditEvent(
                event_id=self._identifier("evt"),
                event_type="proposal_created",
                actor_id=request_context.actor_id,
                actor_role=request_context.role,
                proposal_id=proposal_id,
                trace_id=request_context.trace_id,
                timestamp=utcnow(),
                payload={
                    "proposed_agent_kind": proposed_kind,
                    "target_app_ids": list(policy_envelope.allowed_app_ids),
                    "generated_by_system": True,
                },
            )
        )
        approval_request = ApprovalRequest(
            approval_id=self._identifier("apr"),
            scope_type="agent_lifecycle",
            status="pending",
            tenant_id=request_context.tenant_id,
            app_ids=list(policy_envelope.allowed_app_ids),
            requested_by_actor_id=request_context.actor_id,
            requested_by_role=request_context.role,
            request_reason=compiled.orchestration_decision.user_visible_reason,
            approval_reason="agent_lifecycle",
            created_at=utcnow(),
            trace_id=request_context.trace_id,
            request_context_ref=request_context.request_id,
            routing_plan_ref=compiled.routing_plan.plan_id,
            proposal_draft_ref=proposal_id,
        )
        draft = draft.model_copy(
            update={
                "linked_approval_id": approval_request.approval_id,
                "updated_at": utcnow(),
            }
        )
        await self.store.put_proposal_draft(draft)
        await self.store.put_approval_request(approval_request)
        await self.store.append_audit_event(
            LifecycleAuditEvent(
                event_id=self._identifier("evt"),
                event_type="approval_requested",
                actor_id=request_context.actor_id,
                actor_role=request_context.role,
                approval_id=approval_request.approval_id,
                proposal_id=proposal_id,
                trace_id=request_context.trace_id,
                timestamp=utcnow(),
                payload={
                    "scope_type": "agent_lifecycle",
                    "proposal_id": proposal_id,
                },
            )
        )
        return PendingAgentProposal(
            proposal_draft=draft,
            approval_request=approval_request,
            user_visible_message=(
                f"I created proposal draft '{proposal_id}' for review. "
                f"It is waiting on lifecycle approval '{approval_request.approval_id}'."
            ),
        )

    async def sync_proposal_from_approval(self, approval: ApprovalRequest) -> AgentProposalDraft | None:
        if approval.scope_type != "agent_lifecycle" or approval.proposal_draft_ref is None:
            return None
        draft = await self.store.get_proposal_draft(approval.proposal_draft_ref)
        next_status = draft.status
        if approval.status == "approved":
            next_status = "approved_for_registration"
        elif approval.status == "rejected":
            next_status = "rejected"
        updated = draft.model_copy(
            update={
                "status": next_status,
                "updated_at": utcnow(),
            }
        )
        await self.store.put_proposal_draft(updated)
        await self.store.append_audit_event(
            LifecycleAuditEvent(
                event_id=self._identifier("evt"),
                event_type="proposal_updated",
                proposal_id=updated.proposal_id,
                approval_id=approval.approval_id,
                timestamp=utcnow(),
                payload={
                    "status": updated.status,
                    "approval_status": approval.status,
                },
            )
        )
        return updated

    async def register_proposal(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        proposal_id: str,
        version: str = "v1",
    ) -> AgentRegistrationRecord:
        self._ensure_platform_operator(request_context)
        proposal = await self.store.get_proposal_draft(proposal_id)
        if proposal.status != "approved_for_registration":
            raise ValueError("Only approved proposals can be registered.")
        if not set(proposal.target_app_ids).issubset(set(policy_envelope.allowed_app_ids)):
            raise ValueError("The current scope cannot register this proposal.")

        registration = AgentRegistrationRecord(
            registration_id=self._identifier("reg"),
            proposal_id=proposal_id,
            agent_id=self._agent_id(proposal),
            version=version,
            registry_state="registered",
            registered_by_actor_id=request_context.actor_id,
            created_at=utcnow(),
        )
        await self.store.put_registration_record(registration)
        await self.store.put_proposal_draft(
            proposal.model_copy(update={"status": "registered", "updated_at": utcnow()})
        )
        await self.store.append_audit_event(
            LifecycleAuditEvent(
                event_id=self._identifier("evt"),
                event_type="proposal_registered",
                actor_id=request_context.actor_id,
                actor_role=request_context.role,
                proposal_id=proposal_id,
                registration_id=registration.registration_id,
                trace_id=request_context.trace_id,
                timestamp=utcnow(),
                payload={
                    "agent_id": registration.agent_id,
                    "version": registration.version,
                    "registry_state": registration.registry_state,
                },
            )
        )
        return registration

    async def activate_registration(
        self,
        *,
        request_context: RequestContext,
        registration_id: str,
    ) -> AgentRegistrationRecord:
        self._ensure_platform_operator(request_context)
        record = await self.store.get_registration_record(registration_id)
        if record.registry_state not in {"registered", "activation_pending"}:
            raise ValueError("Only registered proposals can be activated.")
        activated = record.model_copy(
            update={
                "registry_state": "active",
                "activated_by_actor_id": request_context.actor_id,
                "activated_at": utcnow(),
            }
        )
        await self.store.put_registration_record(activated)
        proposal = await self.store.get_proposal_draft(record.proposal_id)
        updated_proposal = proposal.model_copy(update={"status": "activated", "updated_at": utcnow()})
        await self.store.put_proposal_draft(updated_proposal)
        if self.agent_registry is not None:
            self.agent_registry.activate_dynamic_agent(updated_proposal, activated)
        await self.store.append_audit_event(
            LifecycleAuditEvent(
                event_id=self._identifier("evt"),
                event_type="proposal_activated",
                actor_id=request_context.actor_id,
                actor_role=request_context.role,
                proposal_id=record.proposal_id,
                registration_id=registration_id,
                trace_id=request_context.trace_id,
                timestamp=utcnow(),
                payload={
                    "agent_id": activated.agent_id,
                    "registry_state": activated.registry_state,
                },
            )
        )
        return activated

    async def list_visible_proposals(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        status: str | None = None,
    ) -> list[AgentProposalDraft]:
        proposals = await self.store.list_proposal_drafts(status=status)
        if request_context.role in {"platform_admin", "service"}:
            return proposals
        return [
            proposal
            for proposal in proposals
            if set(proposal.target_app_ids).issubset(set(policy_envelope.allowed_app_ids))
        ]

    async def list_visible_registrations(
        self,
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        proposal_id: str | None = None,
        registry_state: str | None = None,
    ) -> list[AgentRegistrationRecord]:
        registrations = await self.store.list_registration_records(
            proposal_id=proposal_id,
            registry_state=registry_state,
        )
        if request_context.role in {"platform_admin", "service"}:
            return registrations

        visible: list[AgentRegistrationRecord] = []
        for registration in registrations:
            proposal = await self.store.get_proposal_draft(registration.proposal_id)
            if set(proposal.target_app_ids).issubset(set(policy_envelope.allowed_app_ids)):
                visible.append(registration)
        return visible

    async def get_proposal_draft(self, proposal_id: str) -> AgentProposalDraft:
        return await self.store.get_proposal_draft(proposal_id)

    async def list_proposal_drafts(self, *, status: str | None = None) -> list[AgentProposalDraft]:
        return await self.store.list_proposal_drafts(status=status)

    async def list_registration_records(
        self,
        *,
        proposal_id: str | None = None,
        registry_state: str | None = None,
    ) -> list[AgentRegistrationRecord]:
        return await self.store.list_registration_records(
            proposal_id=proposal_id,
            registry_state=registry_state,
        )

    @staticmethod
    def _identifier(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _proposed_agent_kind(
        *,
        request_context: RequestContext,
        policy_envelope: PolicyEnvelope,
        user_message: str,
    ) -> str:
        lowered = user_message.lower()
        if "schema" in lowered or "metadata" in lowered:
            return "schema_intelligence"
        if len(policy_envelope.allowed_app_ids) > 1 or policy_envelope.allow_cross_app:
            return "heavy_cross_db"
        if request_context.execution_mode == "admin_chat":
            return "admin_orchestrator"
        return "app_chat"

    @staticmethod
    def _display_name(proposed_kind: str, policy_envelope: PolicyEnvelope) -> str:
        scope = ", ".join(policy_envelope.allowed_app_ids) if policy_envelope.allowed_app_ids else "platform"
        return f"Proposed {proposed_kind.replace('_', ' ')} for {scope}"

    @staticmethod
    def _capability_bundle(
        planning: PlanningArtifacts,
        compiled: CompiledOrchestration,
    ) -> list[str]:
        if compiled.orchestration_decision.selected_capability_ids:
            return list(compiled.orchestration_decision.selected_capability_ids)
        if planning.capability_candidates:
            return [candidate.capability_id for candidate in planning.capability_candidates[:3]]
        return []

    @staticmethod
    def _ensure_platform_operator(request_context: RequestContext) -> None:
        if request_context.role not in {"platform_admin", "service"}:
            raise ValueError("Only platform-level operators may register or activate agent proposals.")

    @staticmethod
    def _agent_id(proposal: AgentProposalDraft) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", proposal.display_name.lower()).strip("_")
        return f"agent.dynamic.{slug or proposal.proposal_id}"
