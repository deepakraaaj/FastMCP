# Approval and Agent Lifecycle Contract

Date: 2026-03-19
Purpose: Phase 6 target design for approval workflows, draft agent proposals, registration, and activation.

## Why This Exists

The prior phases established:

- trusted request and policy envelopes
- bounded agent roles
- planner-side orchestration
- formatter and UX rules for approval and escalation state

What is still missing is the durable lifecycle that turns:

- approval-required execution
- repeated unmet demand
- draft agent proposals

into explicit, auditable control-plane records.

This document defines that lifecycle.

It depends on:

- `docs/enforcement-model.md`
- `docs/agent-model.md`
- `docs/routing-orchestration.md`
- `docs/formatter-ux.md`

## Core Rule

No approval decision is prompt-only.

Approval and lifecycle state must live in durable control-plane records, not in:

- chat history alone
- temporary session memory
- formatter metadata
- implicit tool state

Valkey may help with ephemeral coordination, but PostgreSQL is the source of truth for:

- approval requests
- proposal drafts
- approval decisions
- registration records
- activation state
- audit history

## Current Runtime Assessment

### Already present

- channel metadata advertises `supports_approvals`
- planner and formatter designs already carry approval-related fields
- the architecture already reserves PostgreSQL for approvals and durable records
- the runtime now has a local SQL-backed baseline store for lifecycle state
- the runtime now has core approval and agent-lifecycle services
- widget chat and `invoke_capability` now pause and create durable approval records instead of executing through approval boundaries
- trusted admin lifecycle MCP tools now expose queue, decision, proposal listing, registration, activation, and execution resume
- activated registrations now refresh into `describe_capabilities`

### Missing

- dedicated PostgreSQL control-plane deployment instead of the local baseline store
- real admin dashboard experience layered over the existing HTTP and MCP lifecycle transport
- richer admin UX layered over the current lifecycle records

## Approval Scope Types

Phase 6 recognizes two distinct approval scopes.

### 1. Execution Approval

Use when an otherwise valid plan requires explicit human approval before execution.

Examples:

- elevated admin-wide operations
- risky write actions
- high-impact multi-app operations

### 2. Agent Lifecycle Approval

Use when the system proposes a new reusable agent or agent bundle.

Examples:

- repeated unmet demand suggests a dedicated agent
- a new app-specific orchestrator is needed
- a schema or cross-db assistant should be added to the registry

These scopes must not be conflated. Approving one execution does not approve a new agent. Approving a draft agent does not mean it is active yet.

## Lifecycle Principles

- draft first, approve second, register third, activate last
- approval actors must be explicit and role-validated
- approval decisions must be reversible through versioned state, not silent mutation
- proposal drafts may be AI-generated, but approval records must clearly separate system suggestions from human decisions
- runtime execution must pause at approval boundaries and resume from recorded state
- registration and activation are separate lifecycle transitions

## Durable Record Types

### `ApprovalRequest`

```text
ApprovalRequest
- approval_id: str
- scope_type: execution | agent_lifecycle
- status: pending | approved | rejected | expired | cancelled
- tenant_id: str | None
- app_ids: list[str]
- requested_by_actor_id: str | None
- requested_by_role: str
- approver_actor_id: str | None
- approver_role: str | None
- request_reason: str
- approval_reason: str | None
- created_at: datetime
- decided_at: datetime | None
- expires_at: datetime | None
- trace_id: str | None
- request_context_ref: str | None
- routing_plan_ref: str | None
- proposal_draft_ref: str | None
```

### `ExecutionApprovalPayload`

```text
ExecutionApprovalPayload
- approval_id: str
- orchestration_decision_id: str
- selected_capability_ids: list[str]
- primary_capability_id: str | None
- side_effect_level: none | read | write
- risk_level: low | medium | high
- user_visible_summary: str
- admin_review_summary: str
```

### `AgentProposalDraft`

```text
AgentProposalDraft
- proposal_id: str
- status: draft | pending_review | approved_for_registration | rejected | registered | activated | superseded
- tenant_id: str | None
- target_app_ids: list[str]
- proposed_agent_kind: app_chat | admin_orchestrator | schema_intelligence | heavy_cross_db | proposal
- display_name: str
- problem_statement: str
- justification: str
- proposed_capability_bundle: list[str]
- required_permissions: list[str]
- required_channels: list[str]
- draft_spec_payload: dict[str, Any]
- proposed_by_actor_id: str | None
- generated_by_system: bool
- linked_approval_id: str | None
- created_at: datetime
- updated_at: datetime
```

### `AgentRegistrationRecord`

```text
AgentRegistrationRecord
- registration_id: str
- proposal_id: str
- agent_id: str
- version: str
- registry_state: draft | registered | activation_pending | active | inactive | retired
- registered_by_actor_id: str | None
- activated_by_actor_id: str | None
- created_at: datetime
- activated_at: datetime | None
```

## Approval Decision Model

### `ApprovalDecision`

```text
ApprovalDecision
- approval_id: str
- decision: approve | reject | cancel | expire
- approver_actor_id: str
- approver_role: str
- comment: str | None
- decided_at: datetime
- resulting_status: pending | approved | rejected | expired | cancelled
```

Rules:

- only approved reviewer roles may decide
- the reviewer role must satisfy scope-specific approval policy
- comments are optional, but rejection reasons should be strongly encouraged
- approval expiration must be recorded, not inferred

## Runtime State Transitions

### Execution Approval Flow

1. planner marks `requires_approval = true`
2. formatter shows approval-required state
3. control plane writes `ApprovalRequest(scope_type=execution)`
4. runtime pauses execution at the decision boundary
5. approver reviews and approves or rejects
6. if approved, the orchestration resumes from the recorded plan boundary
7. if rejected, the runtime returns a rejected state and does not execute the pending plan

### Agent Proposal Flow

1. planner or proposal agent identifies a recurring unmet pattern
2. system creates `AgentProposalDraft(status=draft or pending_review)`
3. formatter/admin UX presents the draft and its justification
4. control plane writes `ApprovalRequest(scope_type=agent_lifecycle)`
5. approver approves or rejects the draft
6. if approved, the draft moves to `approved_for_registration`
7. registry registration creates `AgentRegistrationRecord(registry_state=registered)`
8. activation remains a separate transition to `activation_pending` and then `active`

Approving a proposal does not mean the runtime can immediately execute it.

## Registration Versus Activation

This separation is non-negotiable.

### Registration

Registration means:

- the draft is accepted into controlled metadata
- the future agent has an `agent_id`
- the registry can track its version and status

Registration does not mean:

- it is callable in production
- it is visible to all channels
- it has been rollout-approved

### Activation

Activation means:

- the registered agent is enabled for approved scopes and channels
- the runtime may expose it through the capability registry

Activation should require:

- successful registration
- any implementation or config validation required by the platform
- an explicit activating actor or deployment step

## Queue and Review UX

The UI or admin channel should expose an approval queue with enough context to decide safely.

### `ApprovalQueueItem`

```text
ApprovalQueueItem
- approval_id: str
- scope_type: execution | agent_lifecycle
- status: pending | approved | rejected | expired | cancelled
- title: str
- summary: str
- requested_by: str | None
- target_scope_label: str
- created_at: datetime
- expires_at: datetime | None
- severity: low | medium | high
```

### Review Requirements

Execution approvals should show:

- what action will run
- affected apps and tenant scope
- risk and side-effect level
- the user-visible reason for approval

Agent proposal reviews should show:

- the business gap
- why existing capabilities are insufficient
- the proposed capability bundle
- the proposed scope and channels
- whether the draft was system-generated

## Channel Behavior

### Channels with `supports_approvals = true`

May render:

- explicit approve and reject actions
- approval state blocks
- proposal draft cards

### Channels without `supports_approvals = true`

Must render:

- pending approval status
- a reference id or queue handle
- no inline approve or reject actions

### App Chat

May show:

- that an action needs approval
- that the request is pending, approved, or rejected

Must not show:

- admin-only review notes
- proposal-internal diagnostic detail

### Admin Chat / Admin Dashboard

May show:

- richer review context
- proposal draft details
- queue state
- registration and activation progress

## Audit Requirements

Every lifecycle step must emit durable audit events.

### `LifecycleAuditEvent`

```text
LifecycleAuditEvent
- event_id: str
- event_type: approval_requested | approval_approved | approval_rejected | proposal_created | proposal_updated | proposal_registered | proposal_activated | proposal_retired
- actor_id: str | None
- actor_role: str | None
- approval_id: str | None
- proposal_id: str | None
- registration_id: str | None
- trace_id: str | None
- timestamp: datetime
- payload: dict[str, Any]
```

Audit rules:

- execution fallback is not an approval decision
- proposal generation is not approval
- registration is not activation
- every transition must be attributable to a system action or human actor

## Policy and Role Rules

- end users may request actions that later require approval, but may not approve them
- app admins may approve only within their authorized tenant and app scope
- platform admins may approve broader platform-level lifecycle changes
- approval authority must be validated from trusted auth, never from prompt text

## Expiration and Rejection Rules

- approvals may expire based on policy or business time window
- expired approvals must not auto-resume execution
- rejected execution approvals terminate the paused path
- rejected agent proposals remain historical drafts and may be superseded by later versions

## Edge Cases

### Duplicate proposal drafts

- deduplicate by problem pattern and active draft state where possible
- preserve historical records instead of destructive overwrite

### Approval arrives after context has changed

- revalidate the stored plan or draft against current policy before resume or activation
- if scope no longer matches, require a new approval request

### Activation fails after registration

- keep the record in `registered` or `activation_pending`
- emit activation failure audit
- do not silently mark active

### Proposal approved but implementation missing

- keep the lifecycle at `approved_for_registration` or `registered`
- show explicit pending implementation state

## Implementation Status

- `src/tag_fastmcp/models/contracts.py`
  - now includes lifecycle-side models such as `ApprovalRequest`, `ApprovalDecision`, `AgentProposalDraft`, and `AgentRegistrationRecord`
- `src/tag_fastmcp/models/app_config.py`
  - keep channel approval support as a presentation capability, not as the approval source of truth
- `src/tag_fastmcp/core/approval_service.py`
  - create, store, decide, resume, and audit approval requests
- `src/tag_fastmcp/core/agent_lifecycle_service.py`
  - manage proposal drafts, approval sync, registration, activation, and lifecycle audit transitions
- `src/tag_fastmcp/core/control_plane_store.py`
  - local durable SQL-backed records for approvals and lifecycle state, ready to move to PostgreSQL later
- `src/tag_fastmcp/tools/lifecycle_tools.py`
  - trusted admin lifecycle tool surface for review, decision, registration, activation, and resume
- `src/tag_fastmcp/core/admin_service.py` and `src/tag_fastmcp/http_api.py`
  - shared admin lifecycle HTTP transport with trusted bearer JWT scope derivation and development header fallback
- `src/tag_fastmcp/core/agent_registry.py` and `src/tag_fastmcp/tools/system_tools.py`
  - active registrations now refresh into `describe_capabilities`; drafts and non-activated registrations remain hidden

## Phase 6 Acceptance Checklist

- execution approval and agent lifecycle approval are separate scopes
- durable record types are defined
- registration and activation are separate transitions
- queue and review UX requirements are explicit
- audit requirements are explicit
- no approval or activation path relies on prompt-only state

## Phase 7 Handoff

Phase 7 should define visual artifacts and working demonstration assets.

That next phase should specify:

- architecture diagrams
- UX mockups
- approval queue screens
- escalation and lifecycle views
- demo-ready visual flows
