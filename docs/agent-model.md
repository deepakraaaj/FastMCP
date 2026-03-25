# Agent Model

Date: 2026-03-19
Purpose: Phase 3 target design for agent topology, boundaries, and escalation rules.

## Why This Exists

The repository currently exposes one useful agent surface:

- `ClarificationAgent`
  - prompt-driven, app-scoped, schema-aware, and text-only

That is not yet the final agent model.

Phase 3 defines the agents this platform should eventually expose without moving policy, state, SQL guardrails, or response contracts out of the internal core.

## Implementation Status

The baseline Phase 3 implementation now exists in the runtime:

- `src/tag_fastmcp/core/agent_registry.py`
- `src/tag_fastmcp/agent/admin_orchestration_agent.py`
- `src/tag_fastmcp/agent/schema_intelligence_agent.py`
- `src/tag_fastmcp/agent/stubs.py`

That baseline currently provides:

- a typed catalog for all five approved agent classes
- selection rules driven by `RequestContext` and `PolicyEnvelope`
- registry metadata that distinguishes active, stub, and gated agent runtime states

The app-scoped clarification agent, the admin orchestration agent, and the schema intelligence agent are concretely executable today. The heavy and proposal agents remain bounded stubs or gated later-phase runtimes.

## Core Rule

Agents do not own permission.

The internal core still owns:

- request normalization
- policy envelope derivation
- session binding
- capability allow-lists
- SQL validation
- response envelopes
- audit and approval records

Agents reason inside those boundaries. They do not widen them.

## Current Runtime Assessment

### Already present

- one app-scoped clarification agent over schema and manifest context
- one bounded admin orchestration runtime over the planner, formatter, and approval services
- one bounded schema intelligence runtime for understanding-doc generation over approved schema and manifest context
- schema discovery as a reusable core primitive
- manifest-backed reports and workflows
- registry-driven capability execution
- session and idempotency primitives

### Not yet present

- heavy cross-db execution agent
- agent proposal and approval workflow
- agent registry metadata and runtime beyond the active app/admin/schema agents

## Agent Topology

### 1. App Scoped Chat Agent

Primary role:

- default conversational agent for widget chat and single-app assistant flows

Allowed inputs:

- `RequestContext` in `app_chat` mode
- `PolicyEnvelope` with exactly one allowed app
- app-scoped schema metadata
- app-scoped reports, workflows, and allowed capabilities
- session history already bound to the same app

Allowed actions:

- answer from existing context when no execution is needed
- ask clarifying questions
- propose a bounded plan
- invoke app-allowed report, workflow, SQL, or external MCP capabilities through the guarded core

Forbidden behavior:

- cross-app access
- cross-tenant access
- self-authorized capability expansion
- raw database access
- hidden escalation to heavy execution

When to use:

- the user is operating inside one application
- the task fits a normal response, clarification loop, report, workflow, or bounded single-app query

### 2. Admin Orchestration Agent

Primary role:

- privileged planner for admin dashboard chat across approved applications

Allowed inputs:

- `RequestContext` in `admin_chat` mode
- `PolicyEnvelope` with trusted admin scope
- multi-app capability inventory
- prior admin session context

Allowed actions:

- compare and coordinate work across approved apps
- choose app-specific capabilities across more than one app
- request formatter modes with richer diagnostics when allowed
- escalate to heavy execution when plan complexity exceeds the lightweight path

Forbidden behavior:

- bypassing policy envelope checks
- implicit global access without explicit admin scope
- direct unvalidated cross-db SQL
- activating new agents without approval

When to use:

- the requester is an approved admin
- the question spans more than one application or requires platform-level visibility

### 3. Schema Intelligence Agent

Primary role:

- offline or background metadata generation for better planning and safer execution

Allowed inputs:

- approved database configs
- manifest metadata
- schema discovery output

Allowed actions:

- generate schema packs
- create table summaries, join hints, glossary terms, and safe-query examples
- flag schema drift against prior metadata snapshots

Forbidden behavior:

- acting as an end-user business chat agent
- executing operational business changes
- bypassing manifest or policy review

When to use:

- onboarding a new app
- refreshing metadata after schema changes
- improving planner context without giving the runtime raw schema dumps every turn

### 4. Heavy Cross-DB Agent

Primary role:

- explicit high-cost execution mode for staged, cross-source reasoning

Allowed inputs:

- `RequestContext` and `PolicyEnvelope` with heavy execution enabled
- approved multi-app target set
- bounded intermediate results returned from guarded tools

Allowed actions:

- decompose long-running or multi-step analysis
- reconcile data from multiple approved sources
- return staged progress, partial results, or escalation summaries

Forbidden behavior:

- silent background execution from normal app chat
- unrestricted database exploration
- bypassing per-app SQL policy profiles
- auto-running without visible escalation state

When to use:

- the task requires cross-db reconciliation
- the plan needs multiple dependent capability calls with high latency or partial-failure handling
- the normal planner would exceed latency or complexity limits

### 5. Agent Proposal Agent

Primary role:

- detect repeated unmet demand and prepare draft agent specifications

Allowed inputs:

- audit history
- repeated rejected or escalated intents
- capability gaps and registry metadata

Allowed actions:

- draft agent specifications
- suggest capability bundles
- propose onboarding metadata or code/config scaffolds for review

Forbidden behavior:

- self-registration
- self-activation
- production execution of unapproved agent logic

When to use:

- the same unmet pattern appears often enough to justify a dedicated agent
- existing reports, workflows, and orchestrators are no longer sufficient

## Agent Handoff Model

The target handoff sequence is:

1. build `RequestContext`
2. derive `PolicyEnvelope`
3. choose the allowed agent class for the execution mode
4. create a bounded plan
5. validate the plan against allowed capabilities
6. execute through the existing guarded core
7. format output by channel and visibility
8. emit audit, escalation, and approval events

This means:

- the app chat agent is the default, not the only agent
- the admin orchestration agent decides when heavier execution is needed
- the heavy agent is an execution mode, not a replacement for the core router
- the proposal agent drafts future capability, not live behavior

## Escalation Rules

Use the app scoped chat agent when:

- one app is in scope
- the request can be satisfied with a single bounded plan
- the answer can come from context, one report, one workflow, one SQL path, or a small number of tool calls

Escalate from app scoped chat to clarification when:

- key business entities are missing
- the workflow requires additional fields
- capability selection is ambiguous within the same app

Escalate from admin orchestration to heavy execution when:

- more than one approved app must be queried and reconciled
- one or more sources may be slow or partially unavailable
- the task needs staged execution with visible progress

The detailed thresholds and planner behavior for this escalation are defined in `docs/routing-orchestration.md`.

Escalate from repeated failures to agent proposal when:

- there is no adequate capability bundle
- the same pattern repeats across sessions
- the problem is structural, not a one-off routing miss

## Registry Direction

The future registry should represent agents as first-class platform metadata with fields such as:

- `agent_id`
- `agent_kind`
- `execution_modes`
- `allowed_scope`
- `allowed_capability_ids`
- `supports_escalation`
- `requires_approval`
- `visibility_level`

The registry should not treat all agents as interchangeable chat models. Each agent must advertise boundary and approval metadata, not just provider and model name.

The detailed proposal, registration, approval, and activation lifecycle for these agents is defined in `docs/approval-agent-lifecycle.md`.

## Phase 3 Acceptance Checklist

- the final agent set is explicitly named
- each agent has clear allowed inputs and forbidden behavior
- app chat and admin orchestration are separate modes
- heavy execution is explicit, not hidden
- agent proposal is draft-first and approval-gated
- no agent is allowed to bypass the core policy and SQL layers

## Phase 4 Handoff

Phase 4 should convert natural language plus policy envelope into safe orchestration.

That next phase should define:

- planner contracts
- intent classification outputs
- capability ranking rules
- clarification versus execution thresholds
- heavy-agent invocation thresholds
- rejection behavior for blocked cross-app requests
