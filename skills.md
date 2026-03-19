# Project Skills

This file is not a framework-level skill registry. It is the project-local skill guide for future AI contributors.

## Read First

Before using any skill below, read:

1. `docs/application-context.md`
2. `docs/architecture.md`
3. `docs/continuation-guide.md`

## Available Project Skills

### `fastmcp-runtime`

Use when:

- adding or changing MCP tools
- adjusting transports
- changing context/session usage
- adding auth or middleware
- exposing new capability types through the runtime registry
- exposing new registry-driven execution paths

Focus areas:

- keep tool handlers thin
- prefer typed outputs
- keep session behavior explicit
- keep non-MCP compatibility endpoints thin and push chat/session logic into the core service layer
- keep session/idempotency backend selection in the core container, not inside tool code
- treat Valkey as the ephemeral runtime state layer and keep durable records out of it
- do not move orchestration, approvals, or cross-service observability into FastMCP unless the architecture explicitly changes
- make new tool behavior discoverable through the capability registry before orchestration depends on it
- reuse `core/admin_service.py`, `core/admin_chat_service.py`, `agent/admin_orchestration_agent.py`, and `tools/lifecycle_tools.py` for trusted admin lifecycle or chat operations instead of duplicating planning, approval, or registration logic in transport handlers

### `platform-boundaries`

Use when:

- deciding whether behavior belongs in LangGraph, FastMCP, the control plane, or the UI
- splitting implementation work into services or phases
- reviewing architecture drift

Focus areas:

- LangGraph owns orchestration and multi-step agent state
- FastMCP owns typed MCP and tool exposure
- Langfuse owns AI tracing and eval workflows
- OTel plus Grafana, Loki, Tempo, and Prometheus own platform observability
- React Flow owns visual topology and execution graph experiences
- Valkey is for ephemeral shared state
- PostgreSQL is for durable control-plane state

### `policy-envelope`

Use when:

- adding auth-derived request context
- defining or changing app chat versus admin chat scope
- adding tenant, role, or approval-aware routing behavior
- reviewing possible cross-app or cross-tenant leakage

Focus areas:

- derive scope before reasoning
- reuse the existing `RequestContext` and `PolicyEnvelope` core services before adding new entry-point logic
- keep app chat single-app by hard contract
- treat admin-wide access as an explicit privileged mode
- never let prompt text expand privileges
- make routing decisions auditable and deterministic
- keep heavy-agent and agent-proposal flows explicit and approval-gated

### `agent-topology`

Use when:

- defining or changing agent roles
- deciding whether behavior belongs in app chat, admin orchestration, schema intelligence, heavy execution, or proposal workflow
- reviewing agent sprawl or architecture drift

Focus areas:

- reuse the existing `core/agent_registry.py` catalog and selection rules before inventing new agent metadata paths
- reuse `agent/admin_orchestration_agent.py` before inventing a second admin-chat runtime path
- agents do bounded reasoning, not policy enforcement
- app chat stays single-app
- admin orchestration stays privilege-based and explicit
- schema intelligence remains metadata-oriented, not business chat
- heavy execution is visible and auditable
- proposal agents draft future capability but never self-activate

### `routing-orchestration`

Use when:

- defining or changing planner behavior
- deciding between clarification, direct execution, multi-step orchestration, rejection, or heavy escalation
- changing capability ranking rules or intent outputs
- reviewing planner drift into the execution layer

Focus areas:

- reuse the existing `core/intent_planner.py`, `core/plan_compiler.py`, and `core/orchestration_service.py` before adding planner logic to tool wrappers or chat handlers
- reuse `core/admin_chat_service.py` and `agent/admin_orchestration_agent.py` for admin planning and execution instead of duplicating behavior in `http_api.py`
- keep intent planning separate from dispatch
- prefer reports and workflows over speculative SQL
- clarify instead of guessing when candidates are ambiguous
- keep rejection explicit for blocked scope violations
- escalate to heavy execution only for structural complexity
- preserve auditability from planner decision through execution fallback

### `formatter-ux`

Use when:

- defining or changing channel response shapes
- deciding what end users versus admins can see
- adding approval, escalation, degraded, or blocked execution presentation
- changing streaming event structure for chat channels

Focus areas:

- reuse the existing `core/visibility_policy.py` and `core/formatter_service.py` before adding ad hoc presentation logic to chat, routing, or transport code
- formatter execution happens after policy and execution, not before
- preserve typed execution envelopes under the UI layer
- default to least-revealing safe output
- keep approval and heavy-escalation states visible
- separate formatter fallback from execution fallback
- maintain compatibility for existing widget clients while evolving richer events

### `visual-artifacts`

Use when:

- changing the React demo or architecture console
- designing diagrams, screen blueprints, or execution visualizations
- reviewing whether the UI still matches the policy, planner, formatter, and lifecycle contracts

Focus areas:

- show app chat and admin chat as different operating modes
- make escalation and approval visible instead of implied
- keep the topology fixed to the target architecture, not a generic node builder
- separate user-facing output blocks from internal audit state
- treat the UI as a projection of backend truth, not the enforcement source
- reuse `ui/src/components/LiveConsole.jsx` and the proxied backend routes before creating a second browser interaction path

### `phase-prompts`

Use when:

- resuming implementation from the phase documents
- turning approved architecture into bounded Codex execution requests
- checking whether a future task is trying to skip phase boundaries

Focus areas:

- use `docs/codex-implementation-prompts.md` as the starting pack
- keep each prompt repo-specific and phase-bounded
- make later phases assume earlier phase acceptance rather than redoing architecture
- state clearly what should not be implemented yet
- preserve tests and docs as part of each phase prompt

### `approval-lifecycle`

Use when:

- defining approval workflows
- designing new-agent proposal, registration, or activation state
- deciding who can approve what and when paused execution may resume
- reviewing auditability of lifecycle transitions

Focus areas:

- reuse the existing `core/control_plane_store.py`, `core/approval_service.py`, and `core/agent_lifecycle_service.py` before inventing new lifecycle state paths
- reuse `core/admin_service.py`, `tools/lifecycle_tools.py`, `http_api.py`, and `core/agent_registry.py` before inventing a second admin review or activation path
- durable control-plane records, not prompt-only state
- execution approval and agent lifecycle approval are separate scopes
- registration and activation are separate transitions
- approval authority comes from trusted roles, never prompt text
- every lifecycle transition is auditable and attributable
- drafts may be AI-generated, activation may not be implicit
- only activated registrations become discoverable runtime agents

### `execution-reliability`

Use when:

- adding retry, timeout, fallback, or circuit-breaker behavior
- changing external MCP dependency handling
- reviewing degraded-mode execution

Focus areas:

- keep reliability policy in the internal core, not in MCP tool wrappers
- use deterministic fallback targets where possible
- preserve typed routing results and surface degraded execution clearly
- do not weaken SQL or workflow contracts while adding failure handling

### `sql-policy`

Use when:

- changing SQL validation rules
- allowing mutations
- adding table-level restrictions
- changing summary or execution behavior

Focus areas:

- never weaken policy by accident
- keep validation deterministic
- add regression tests

### `workflow-state`

Use when:

- adding guided flows
- changing continuation behavior
- storing workflow progress

Focus areas:

- keep workflow state explicit
- preserve session continuity
- keep workflow persistence store-agnostic and async-safe
- do not bury workflow rules inside tool wrappers

### `builder-bridge`

Use when:

- changing builder graph schemas
- adding node types
- changing preview execution
- connecting a future visual builder UI

Focus areas:

- keep builder graphs constrained and debuggable
- validate before previewing
- route preview execution through real FastMCP tool calls

### `domain-runtime`

Use when:

- changing manifest structure
- adding reports
- adding workflows
- extending domain metadata
- extending config-only onboarding metadata for external MCP servers or channel formatters

Focus areas:

- domain rules should remain config-driven where possible
- new reports and workflows should automatically appear through capability discovery
- keep localhost-only demo credentials in ignored override files such as `apps.local.yaml`, not in the shared `apps.yaml`
- document manifest changes
- update examples and tests

### `docs-sync`

Use when:

- adding features
- changing architecture
- changing contributor workflow

Focus areas:

- keep docs in sync with runtime reality
- update handoff notes
- note unfinished work clearly
