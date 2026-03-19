# Routing and Orchestration Contract

Date: 2026-03-19
Purpose: Phase 4 target design for converting natural language into safe, bounded capability execution.

## Why This Exists

The repository already has a useful deterministic dispatcher:

- `CapabilityRouter` can execute reports, workflows, and external MCP tools
- it applies timeout, retry, circuit-breaker, and fallback logic
- it returns typed routing output

The repository now has a baseline orchestration layer for single-turn routing, but it still needs richer admin, approval, and formatter integration.

This document defines that missing layer.

It sits after `RequestContext` and `PolicyEnvelope`, and before the existing execution router.

The enforcement and agent boundaries it depends on are defined in:

- `docs/enforcement-model.md`
- `docs/agent-model.md`

## Current Runtime Assessment

### Already strong

- deterministic capability dispatch by `capability_id` or `kind + tags`
- typed registry discovery
- app-scoped workflow continuation
- explicit external dependency reliability handling
- app-scoped widget chat entry point
- deterministic natural-language planner for report, workflow, external-tool, rejection, proposal, and heavy-escalation decisions
- planner/compiler split that keeps `CapabilityRouter` as the execution owner

### Missing

- no NL-to-SQL compilation path yet
- no exposed admin-chat transport yet
- no durable approval pause/resume flow yet
- no formatter execution layer yet
- multi-step orchestration is still intentionally small and deterministic

## Non-Negotiable Rules

- orchestration cannot widen the `PolicyEnvelope`
- planner outputs must be deterministic enough to audit
- clarification is preferred over speculative execution
- reports and workflows are preferred over ad hoc SQL when they satisfy the request
- the dispatcher remains responsible for execution and reliability
- heavy-agent escalation is explicit and visible
- direct tool calls bypass language classification, not policy or audit

## Target Routing Stages

1. build `RequestContext`
2. derive `PolicyEnvelope`
3. choose the allowed agent class
4. analyze user intent
5. generate capability candidates from the envelope-filtered registry
6. rank candidates and choose orchestration mode
7. ask for clarification, confirmation, or approval when required
8. compile the decision into one or more execution requests
9. dispatch through the existing guarded core
10. format output and emit audit events

The key boundary is:

- planner decides what should happen
- router executes what is allowed to happen

## Planning Contracts

Phase 2 defined the boundary contracts `RequestContext`, `PolicyEnvelope`, and `RoutingPlan`.

Phase 4 refines the orchestration internals with three planning objects.

### `PlanningInput`

```text
PlanningInput
- request_id: str
- session_id: str | None
- execution_mode: app_chat | admin_chat | direct_tool | system
- actor_role: str
- user_message: str | None
- requested_app_ids: list[str]
- channel_id: str | None
- session_summary: str | None
- envelope_ref: str
- candidate_capability_ids: list[str]
- available_reports: list[str]
- available_workflows: list[str]
- available_external_tools: list[str]
```

### `IntentAnalysis`

```text
IntentAnalysis
- request_id: str
- intent_family: answer | clarify | report | workflow | sql | external_tool | multi_app_analysis | agent_gap | reject
- business_entities: list[str]
- mentioned_apps: list[str]
- missing_inputs: list[str]
- ambiguity_reasons: list[str]
- risk_level: low | medium | high
- side_effect_level: none | read | write
- preferred_execution_kind: answer | report | workflow | sql | external_tool | heavy_agent | proposal
```

### `CapabilityCandidate`

```text
CapabilityCandidate
- capability_id: str
- app_id: str | None
- kind: report | workflow | tool
- score: int
- match_reason: str
- risk_flags: list[str]
- requires_session: bool
- requires_confirmation: bool
- requires_approval: bool
```

### `OrchestrationDecision`

```text
OrchestrationDecision
- decision_id: str
- request_id: str
- routing_plan_id: str
- orchestration_mode: answer_only | single_step | multi_step | heavy_agent | proposal | reject
- selected_capability_ids: list[str]
- primary_capability_id: str | None
- clarification_prompt: str | None
- missing_inputs: list[str]
- requires_confirmation: bool
- requires_approval: bool
- approval_reason: str | None
- formatter_id: str | None
- audit_tags: list[str]
- user_visible_reason: str
```

The external persisted boundary remains `RoutingPlan`. `OrchestrationDecision` is the planner-side object that compiles into one or more actual execution requests.

## Candidate Ranking Rules

Ranking should follow these rules in order:

1. drop every capability outside the `PolicyEnvelope`
2. prefer exact app-scoped matches over broader platform-scoped matches
3. prefer manifest-backed reports over ad hoc SQL for read questions
4. prefer manifest-backed workflows over inferred write plans
5. prefer lower-risk, lower-cost execution when outcomes are equivalent
6. prefer a single-step plan over a multi-step plan when the result is materially the same
7. prefer internal guarded capability over external MCP when both can satisfy the request
8. if top candidates remain tied or under-specified, ask for clarification instead of guessing

## Clarification Rules

The planner must choose clarification instead of execution when any of these are true:

- required workflow fields are missing
- the user refers to a business entity that cannot be uniquely resolved
- more than one candidate capability has the same top ranking
- the app target is missing or ambiguous
- the user intent mixes multiple unrelated actions in one turn
- the route would require assumptions about write intent, approval, or cross-app scope

Clarification responses should be specific and execution-oriented:

- say what is missing
- say why execution cannot continue yet
- ask the smallest next question that unblocks routing

## Rejection Rules

The planner must reject instead of clarify when:

- the request is outside the `PolicyEnvelope`
- app chat requests cross-app or cross-tenant data
- the requested action is blocked by policy regardless of user clarification
- no approved capability type may satisfy the request
- the user requests direct privilege expansion from prompt text alone

Rejection should be explicit and auditable. It should not degrade into vague assistant prose.

## Lightweight Orchestration Rules

`single_step` mode is appropriate when one capability execution is sufficient.

`multi_step` mode is appropriate only when all of these are true:

- every step stays inside the current `PolicyEnvelope`
- the sequence is short and deterministic
- each step has a clear dependency on earlier bounded results
- the expected latency still fits normal chat interaction
- the workflow does not require heavy reconciliation or partial-failure management

Examples:

- resolve an entity with a report, then continue a workflow using the selected identifier
- ask one clarification question, then run the chosen report

`multi_step` should not become a hidden general workflow engine. Once the sequence becomes long-running, cross-source, or failure-sensitive, it must escalate.

## Heavy-Agent Invocation Thresholds

The planner should escalate to `heavy_agent` when one or more of these are true:

- more than one approved app must be queried and the results must be reconciled
- the execution requires cross-database reasoning with intermediate state
- the expected execution is long-running relative to normal chat
- partial-failure handling is part of the normal plan, not an exception
- the request needs staged progress reporting or resumability

The planner should not escalate merely because a request is phrased broadly. Heavy execution must be driven by execution structure, not by dramatic wording.

## Direct Tool Path

`direct_tool` mode still builds:

- `RequestContext`
- `PolicyEnvelope`
- a minimal `RoutingPlan`
- a minimal `OrchestrationDecision`

It skips natural-language intent analysis because the caller already named the capability target.

This preserves:

- auditability
- confirmation and approval checks
- scope enforcement

## Compilation to Execution

After the planner emits `OrchestrationDecision`, the compiler should generate:

- zero execution requests for `answer_only`, `reject`, or pure clarification
- one `InvokeCapabilityRequest` for `single_step`
- a bounded ordered list of execution requests for `multi_step`
- one explicit escalation event for `heavy_agent`
- one draft-generation event for `proposal`

The existing dispatcher should remain the execution surface for:

- reports
- workflows
- external MCP tools
- future bounded SQL execution plans

## Formatter Selection Rules

Formatter selection must happen after planning, but before the final user response is emitted.

Rules:

- choose only from formatter ids allowed by the envelope
- preserve channel consistency across a multi-step plan
- allow admin diagnostics only when visibility rules permit them
- never expose raw planner traces or SQL by default to standard app chat users

## Edge Cases

### No candidate capability found

- choose `reject` if the request is out of scope
- choose `propose_agent` only if the unmet pattern is structurally recurring and proposal is allowed
- otherwise choose clarification or unsupported-response path

### Candidate found but app is missing

- `app_chat`: reject
- `admin_chat`: clarify target app unless the request is a safe platform discovery action

### Workflow and report both match

- prefer workflow for write or guided action intent
- prefer report for read-only lookup intent

### External tool and internal report both match

- prefer the internal guarded report unless the external tool adds unique approved capability

### Session-bound app mismatch

- reject before compilation

### Circuit-breaker fallback after planning

- keep planner decision and execution fallback separate in audit
- do not treat runtime fallback as if it were the original intent choice

## Implementation Mapping

- `src/tag_fastmcp/models/contracts.py`
  - now carries `PlanningInput`, `IntentAnalysis`, `CapabilityCandidate`, and `OrchestrationDecision`
- `src/tag_fastmcp/core/capability_router.py`
  - remains the deterministic dispatcher, not the planner
- `src/tag_fastmcp/core/chat_service.py`
  - now routes widget chat through the planner before agent fallback
- `src/tag_fastmcp/core/intent_planner.py`
  - performs deterministic intent analysis and candidate ranking
- `src/tag_fastmcp/core/plan_compiler.py`
  - compiles orchestration decisions into executable requests
- `src/tag_fastmcp/core/orchestration_service.py`
  - coordinates planner, compiler, and dispatcher integration

## Implementation Status

The current Phase 4 baseline is intentionally bounded:

- app chat can directly route strong read and write requests into approved reports or workflows
- app chat falls back to the clarification agent when no strong bounded route exists
- direct tool routing now emits a minimal `OrchestrationDecision` for audit continuity
- heavy-agent and proposal outcomes are explicit, but their concrete runtimes still belong to later phases

## Phase 4 Acceptance Checklist

- a planner-side contract exists between envelope and dispatcher
- candidate ranking rules are documented
- clarification and rejection thresholds are documented
- heavy-agent escalation criteria are explicit
- direct-tool routing remains enforced and auditable
- the dispatcher boundary stays separate from planner behavior

## Phase 5 Handoff

The detailed Phase 5 formatter and UX contract is now defined in `docs/formatter-ux.md`.
