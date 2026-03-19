# Enforcement Model and Routing Contract

Date: 2026-03-19
Purpose: Phase 2 target design for request normalization, policy envelopes, and routing decisions.

## Why This Exists

The repository already has:

- app-scoped execution contexts
- deterministic SQL policy enforcement
- typed capability discovery
- registry-driven execution for reports, workflows, and external MCP tools
- session and idempotency primitives

What it does not yet have is the control contract for safe multi-app and future multi-tenant chat. This document defines that contract before planner, admin orchestration, or agent-lifecycle work is implemented.

The concrete agent classes that operate inside this contract are defined in `docs/agent-model.md`.

## Implementation Status

The baseline Phase 2 implementation now exists in the runtime:

- `src/tag_fastmcp/core/request_context.py`
- `src/tag_fastmcp/core/policy_envelope.py`
- `src/tag_fastmcp/core/session_store.py`

That baseline currently enforces:

- trusted request normalization for widget chat and direct tool execution
- immutable policy-envelope derivation before chat or registry routing
- session-bound `app_id` checks that prevent silent cross-app switching
- minimal `RoutingPlan` creation for widget chat and registry routing paths

## Non-Negotiable Rules

- app chat never widens beyond one approved application
- tenant and role scope come from trusted context, never from prompt text
- the LLM never receives raw database power or an unbounded tool list
- every routed request passes through `RequestContext -> PolicyEnvelope -> RoutingPlan`
- session binding prevents silent scope changes during a conversation
- heavy-agent execution and new-agent creation are explicit, auditable modes

## Execution Modes

### `app_chat`

Use for widget or embedded chat inside one application.

- must bind to exactly one `app_id`
- must bind to one tenant scope when tenancy is enabled
- cannot request cross-app or cross-database execution
- can only see capabilities whitelisted for that app and channel

### `admin_chat`

Use for privileged dashboard chat.

- requires explicit admin role from trusted auth
- may operate on one app, a selected subset of apps, or all authorized apps
- may request cross-app reasoning only when the envelope allows it
- may escalate to heavy execution only when the envelope allows it

### `direct_tool`

Use for MCP clients that call tools directly.

- still requires trusted actor context and an enforcement envelope
- bypasses natural-language intent classification
- does not bypass policy, scope, or audit requirements

### `system`

Use for health, discovery, bootstrap, and controlled internal flows.

- limited to non-business operations unless explicitly extended

## Request Context Contract

Every request must first normalize into a trusted request object.

```text
RequestContext
- request_id: str
- trace_id: str | None
- session_id: str | None
- actor_id: str | None
- auth_subject: str | None
- tenant_id: str | None
- role: end_user | app_admin | platform_admin | service
- origin: widget_http | admin_http | mcp_tool | builder_preview | internal
- execution_mode: app_chat | admin_chat | direct_tool | system
- requested_app_id: str | None
- session_bound_app_id: str | None
- channel_id: str | None
- auth_scopes: list[str]
- metadata: dict[str, Any]
```

### Request Context Rules

- `app_chat` requires a resolved app before any LLM or routing step
- `app_chat` must reject the request if `tenant_id` is required but missing
- the session binding may narrow scope but never widen it
- a new request may not switch a bound app-chat session to another app
- `requested_app_id` is advisory until validated against auth and session binding
- builder preview and direct MCP tools still create a request context, even if no LLM call occurs

## Policy Envelope Contract

The policy envelope is the immutable execution boundary derived from the request context plus trusted auth, registry metadata, and app policy.

```text
PolicyEnvelope
- envelope_id: str
- request_id: str
- execution_mode: app_chat | admin_chat | direct_tool | system
- primary_app_id: str | None
- allowed_app_ids: list[str]
- allowed_tenant_ids: list[str]
- allowed_capability_ids: list[str]
- allowed_channel_ids: list[str]
- allowed_formatter_ids: list[str]
- allow_platform_tools: bool
- allow_cross_app: bool
- allow_cross_db: bool
- allow_sql_execution: bool
- allow_external_mcp: bool
- allow_schema_discovery: bool
- allow_workflow_execution: bool
- allow_heavy_agent: bool
- allow_agent_proposal: bool
- require_approval_for: list[str]
- reveal_sql_to_user: bool
- reveal_diagnostics: bool
- reveal_policy_reasons: bool
- sql_profiles_by_app: dict[str, SqlPolicyProfile]
```

`SqlPolicyProfile` is derived per app from manifest and runtime settings. It preserves current safeguards such as allowed tables, protected tables, mutation rules, and required `WHERE` filters.

### Policy Envelope Rules

- app chat sets `allowed_app_ids` to exactly one app
- app chat forces `allow_cross_app = false`
- admin chat may only widen `allowed_app_ids` from trusted auth, not user wording
- capability selection must be a strict subset of `allowed_capability_ids`
- formatter selection must come from `allowed_formatter_ids`
- heavy agents are disabled unless the envelope explicitly enables them
- agent proposal may draft metadata, but activation always remains outside the envelope and inside approval workflow

`allow_heavy_agent` and `allow_agent_proposal` control whether the heavy cross-db agent or agent proposal agent from `docs/agent-model.md` may be selected at all.

## Routing Plan Contract

The planner does not execute tools directly. It produces a routing plan that is validated against the envelope.

The detailed planner-side orchestration contract that leads into this plan is defined in `docs/routing-orchestration.md`.

```text
RoutingPlan
- plan_id: str
- request_id: str
- intent_type: answer_from_context | ask_clarification | run_report | run_workflow | execute_sql | invoke_external_tool | escalate_heavy_agent | propose_agent | reject
- target_app_ids: list[str]
- selected_capability_id: str | None
- candidate_capability_ids: list[str]
- requires_clarification: bool
- requires_confirmation: bool
- requires_approval: bool
- approval_reason: str | None
- formatter_id: str | None
- audit_tags: list[str]
- reasoning_summary: str
```

### Routing Rules

- no plan may reference a capability outside the envelope
- `execute_sql` is allowed only for scoped, validated SQL paths
- `ask_clarification` is preferred over speculative tool execution
- `escalate_heavy_agent` is a first-class plan type, not an internal retry
- `propose_agent` is allowed only when no existing bounded capability is sufficient
- direct tool requests may create a minimal routing plan for audit even when no classifier is used

## Deterministic Decision Matrix

| Condition | Required outcome |
| --- | --- |
| `app_chat` and no resolvable app context | Reject before planner or LLM execution |
| `app_chat` requests another app or all apps | Reject as policy violation |
| `app_chat` asks for a known report or workflow and routing is unambiguous | Produce `run_report` or `run_workflow` |
| Request is missing key entity details or required workflow fields | Produce `ask_clarification` |
| Direct MCP tool call names an allowed capability | Produce a validated direct execution plan |
| Admin request spans multiple apps but stays within approved app set and bounded capabilities | Produce a multi-app routing plan |
| Admin request requires staged cross-database reasoning or long-running analysis | Produce `escalate_heavy_agent` |
| No existing capability can satisfy a repeated approved use case | Produce `propose_agent` draft, never activation |

## Edge-Case Handling

### Missing app context

- `app_chat`: reject immediately
- `admin_chat`: request clarification or explicit app selection unless the task is a safe platform-level discovery action

### Missing tenant context

- reject if the route requires tenant-bound data access
- allow only non-business system discovery routes when tenant context is unnecessary

### Cross-app request from app chat

- block before intent planning completes
- surface a clear rejection reason
- log the denied scope-expansion attempt

### Schema drift

- fail closed for unsafe execution
- allow a schema refresh workflow in a later phase through the schema intelligence agent

### One database unavailable during cross-app work

- record partial-failure state in the plan and audit log
- allow degraded response only if the envelope and plan permit partial results

### Long-running work

- convert to explicit heavy-agent or asynchronous execution mode
- do not hide long-running execution behind normal app chat responses

### Approval delays or rejection

- leave draft proposals in `pending` or `rejected`
- never silently auto-activate

### Idempotent retries

- preserve the current idempotency behavior for tool execution
- include plan identity and envelope identity in future replay-safe keys where appropriate

## Implementation Mapping For Later Phases

These are the repository touchpoints for implementation, not a request to code them yet.

- `src/tag_fastmcp/models/http_api.py`
  - extend widget context with role and tenant fields
- `src/tag_fastmcp/models/contracts.py`
  - add or split out `RequestContext`, `PolicyEnvelope`, and `RoutingPlan`
- `src/tag_fastmcp/core/chat_service.py`
  - bind app-chat sessions to approved app and future tenant scope
- `src/tag_fastmcp/core/session_store.py`
  - persist session bindings, not just conversation history
- `src/tag_fastmcp/core/capability_registry.py`
  - support envelope-filtered capability views
- `src/tag_fastmcp/core/capability_router.py`
  - accept validated routing plans instead of raw user intent
- future `core/request_context.py`
  - normalize trusted request metadata
- future `core/policy_envelope.py`
  - derive immutable execution boundaries
- future `core/intent_planner.py`
  - convert natural language into a bounded routing plan

## Phase 2 Acceptance Checklist

- a concrete `RequestContext` contract exists
- a concrete `PolicyEnvelope` contract exists
- app chat and admin chat are distinct execution modes
- session binding rules are documented
- routing outcomes are deterministic and auditable
- cross-app execution is impossible from app chat by contract
- heavy-agent execution is explicit and bounded
- new-agent creation is draft-first and approval-gated
