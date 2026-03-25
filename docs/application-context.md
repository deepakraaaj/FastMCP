# TAG FastMCP Application Context

Date: 2026-03-19
Purpose: Canonical fast-start context for this repository.

The default runtime profile is now `simple`. That means the main shipped surface is app-scoped chat plus schema understanding and guarded DB execution. In that default path, fallback chat can now execute safe app-scoped reads and stage writes behind explicit confirmation. Older admin, lifecycle, builder, and external-routing paths are deferred behind the explicit `platform` profile, and the simple startup path no longer needs to construct those platform services.

## What This Project Is

This project is a FastMCP-first rebuild of the TAG assistant runtime.

The target is not a demo MCP server. The target is a smaller and more explicit production architecture where MCP is the public tool surface and a compact internal core owns policy, state, and domain behavior.

Long term, this repository should sit inside a larger platform:

- LangGraph for orchestration and multi-step agent flow
- FastMCP for MCP servers and tool adapters
- Langfuse for AI trace, debug, and eval workflows
- OpenTelemetry plus Grafana, Loki, Tempo, and Prometheus for platform observability
- React Flow for visual topology and execution views
- Valkey for ephemeral shared state
- PostgreSQL for durable control-plane state
- EKS for deployment

## Product Goal

Convert natural-language or tool-driven business requests into trustworthy outcomes while staying:

- safe
- explicit
- domain-aware
- easy to debug

## Core Runtime Responsibilities

The internal core owns:

- capability registry and discovery contracts
- session state
- idempotency
- SQL policy enforcement
- domain/runtime rules
- response contracts
- workflow continuation

The FastMCP surface owns:

- tool exposure
- typed tool schemas
- session-aware tool entry points
- transport/runtime integration
- builder-graph validation tool exposure

The larger platform around this repo should own:

- conversation orchestration
- registry and routing control plane
- execution reliability policies
- cross-service observability
- application and channel formatting

## Active Runtime Paths

### System path

- health
- session start
- domain metadata

### Registry path

- app registry load
- domain config or manifest load
- external MCP server config load
- channel formatter config load
- capability snapshot derivation
- typed registry response envelope

### Routing path

- capability registry lookup
- capability selection by id or tags
- built-in report/workflow execution or external MCP dispatch
- timeout, retry, circuit-breaker, and fallback policy for external MCP execution
- channel formatter attachment
- typed routing response envelope

### SQL path

- request normalize
- session resolve
- idempotency check
- SQL validate
- SQL execute
- response envelope

### Report path

- report lookup
- SQL validate
- SQL execute
- response envelope

### Workflow path

- workflow start
- missing-field detection
- continuation
- response envelope

### Builder preview path

- builder graph validate
- session start
- execute approved tool sequence through FastMCP client calls
- collect preview steps and validation issues

### Understanding capture path

- resolve one configured app context
- generate the base schema intelligence document inside the existing guardrails
- collect bounded sample rows from the allowed tables only
- ask targeted business questions for app purpose, write rules, table meaning, and status semantics
- write YAML and Markdown workbook artifacts for later onboarding and chat-context improvement

### Widget HTTP adapter path

- list configured app scopes for the frontend app picker
- decode widget user context from headers
- resolve widget app_id from `x-app-id` or default settings
- start or reuse a session in the shared session store
- build a planner-side decision inside the request context and policy envelope
- execute a bounded report, workflow, or external tool when a strong approved route exists
- derive a visibility profile and channel response before transport output
- rebuild agent history from session events only when the app-scoped chat agent must answer directly
- stream newline-delimited JSON back to the widget, with optional rich formatter events for newer clients

### Admin HTTP adapter path

- decode trusted admin context from bearer JWT claims, with a development-only `x-admin-context` fallback
- derive `admin_chat` request context and policy envelope before any lifecycle or chat action
- auto-start or reuse an admin chat session in the shared session store
- plan bounded admin-chat execution inside the existing orchestration service
- execute approved report, workflow, or external-tool routes directly when the planner finds a strong match
- pause proposal and approval-required paths in the same durable lifecycle services used by MCP tools
- stream newline-delimited JSON back to the admin client, with optional rich formatter events
- expose approval queue review, approval decision, proposal listing, registration, activation, and resume routes
- reuse the same durable approval and lifecycle services as the MCP admin tool surface
- return typed lifecycle or routing envelopes back to the admin client

## Current Strengths

- explicit runtime ownership boundaries
- typed capability registry for plug-and-play discovery
- config-only app onboarding through `apps.yaml` with optional manifest fallback
- typed request and response contracts
- request-context and policy-envelope enforcement services in the internal core
- bounded agent catalog and agent-selection scaffolding in the internal core
- active admin orchestration runtime in the internal core
- active schema intelligence runtime for app understanding-document generation
- interactive understanding-workbook capture over schema summaries and safe row previews
- deterministic intent planner, plan compiler, and orchestration service in the internal core
- role-aware visibility policy and formatter services in the internal core
- durable control-plane baseline for approvals, proposal drafts, registrations, paused execution, and lifecycle audit events
- deterministic SQL policy validation
- constrained builder-to-runtime bridge
- optional Valkey-backed session and idempotency persistence
- session-bound app scope for widget chat and direct tool execution
- widget chat now routes directly into approved reports, workflows, or external tools before falling back to the clarification agent
- rich widget `block`, `state`, and `action` events are available through an opt-in stream mode
- compatibility HTTP adapter for the existing chatbot widget
- shared admin lifecycle HTTP adapter for dashboard or console integrations
- shared admin chat HTTP adapter layered over the planner, formatter, and lifecycle core
- admin bearer JWT auth baseline for trusted admin HTTP context derivation
- live browser console over widget chat, admin chat, approvals, proposals, and registration activation
- optional demo multi-app bootstrap through `apps.demo.yaml` with auto-seeded SQLite maintenance and dispatch datasets
- bootstrapped development database
- AI handoff docs included from the start

## Current Gaps

- no end-user auth provider yet
- no NL-to-SQL planner yet
- heavy and proposal agent runtimes are still stubbed or gated
- no production-grade auth-backed admin dashboard yet; the current live console still defaults to the development `x-admin-context` path unless a bearer token is supplied
- formatter coverage is still concentrated in widget chat and registry routing, not every direct tool or future admin surface
- single-domain sample only

## Phase 2 Target Contracts

Before more planner or agent work is added, the runtime should adopt these shared contracts:

- `RequestContext`
  - normalized request identity, actor, role, tenant, app, channel, and origin metadata
- `PolicyEnvelope`
  - immutable allowed app, tenant, capability, formatter, and execution limits derived before any reasoning
- `RoutingPlan`
  - deterministic plan output that remains inside the policy envelope

The detailed target for these contracts lives in `docs/enforcement-model.md`.

The current runtime now includes the baseline Phase 2 implementation:

- `src/tag_fastmcp/core/request_context.py`
- `src/tag_fastmcp/core/policy_envelope.py`
- session-bound `bound_app_id` enforcement in the session store
- widget chat, direct tool execution, and registry routing wired through the shared enforcement path

The critical design rule is:

- app chat binds to one approved app before planning
- admin chat widens only from trusted auth context, never from prompt text
- direct tool execution still uses the same enforcement path

## Phase 3 Target Agent Topology

The target agent set for this repository is now defined in `docs/agent-model.md`.

That topology keeps the current rule intact:

- agents reason inside policy
- the internal core still owns validation, scope, and execution safety

The planned agent set is:

- app scoped chat agent
- admin orchestration agent
- schema intelligence agent
- heavy cross-db agent
- agent proposal agent

The current runtime now includes the baseline Phase 3 implementation:

- `src/tag_fastmcp/core/agent_registry.py`
- `src/tag_fastmcp/agent/admin_orchestration_agent.py`
- expanded agent metadata in `describe_capabilities`
- default agent selection for widget chat
- active admin orchestration runtime plus stub classes for the remaining later-phase agents

## Phase 4 Routing and Orchestration

The routing and orchestration target now lives in `docs/routing-orchestration.md`.

That phase defines:

- how natural language becomes bounded planner input
- how capability candidates are ranked
- when the system must clarify, reject, or escalate
- how the planner hands off to the existing deterministic dispatcher

The current runtime now includes the baseline Phase 4 implementation:

- `src/tag_fastmcp/core/intent_planner.py`
- `src/tag_fastmcp/core/plan_compiler.py`
- `src/tag_fastmcp/core/orchestration_service.py`
- `src/tag_fastmcp/core/admin_chat_service.py`
- widget chat routed through the planner before direct agent fallback
- `invoke_capability` upgraded to emit a minimal `OrchestrationDecision` on the direct-tool path
- admin chat routed through the same planner and compiler path before the active admin orchestration runtime executes bounded actions

## Phase 5 Formatter and UX Layer

The formatter and UX target now lives in `docs/formatter-ux.md`.

That phase defines:

- channel response contracts
- role-aware visibility rules
- approval and escalation presentation
- widget streaming evolution beyond plain text only

The current runtime now includes the baseline Phase 5 implementation:

- `src/tag_fastmcp/core/visibility_policy.py`
- `src/tag_fastmcp/core/formatter_service.py`
- `src/tag_fastmcp/models/http_api.py`
- role-aware channel responses attached to widget chat and routed MCP responses
- opt-in rich widget stream events for `block`, `state`, and `action`
- opt-in rich admin chat stream events for `block`, `state`, and `action`

## Phase 6 Approval and Agent Lifecycle

The approval and lifecycle target now lives in `docs/approval-agent-lifecycle.md`.

That phase defines:

- durable approval request records
- draft proposal handling for new agents
- registration versus activation boundaries
- approval queue and audit requirements

The current runtime now includes the baseline Phase 6 implementation:

- `src/tag_fastmcp/core/control_plane_store.py`
- `src/tag_fastmcp/core/approval_service.py`
- `src/tag_fastmcp/core/agent_lifecycle_service.py`
- `src/tag_fastmcp/core/admin_service.py`
- `src/tag_fastmcp/tools/lifecycle_tools.py`
- `src/tag_fastmcp/http_api.py`
- durable local SQL-backed records for approvals, proposal drafts, registrations, paused execution, and lifecycle audit events
- widget chat and `invoke_capability` now pause at approval boundaries instead of executing immediately
- proposal outcomes now create draft records plus separate lifecycle approvals before any registration or activation step
- trusted admin MCP tools now expose approval queue review, decision, proposal listing, registration, activation, and execution resume
- trusted admin HTTP routes now expose the same review, decision, registration, activation, and resume actions via bearer JWT auth, with development header fallback
- activated registrations now refresh back into `describe_capabilities` as dynamic active agents

## Phase 7 Visual Artifacts

The Phase 7 visual artifact target now lives in `docs/visual-artifacts.md`.

That phase defines:

- the topology diagram for the target request path
- the screen blueprint for app chat, admin orchestration, and proposal review
- the React demo states that make enforcement, escalation, and approval visible

The current runtime now includes the Phase 7 live-console baseline:

- `ui/src/App.jsx`
- `ui/src/components/LiveConsole.jsx`
- `ui/vite.config.js`
- the architecture console remains visible as the static design artifact
- the browser can now drive live widget chat, admin chat, approval review, proposal registration, and activation through proxied backend routes

## Phase 8 Codex Implementation Prompts

The Phase 8 prompt pack now lives in `docs/codex-implementation-prompts.md`.

That phase defines:

- one repo-specific Codex-ready prompt per prior phase
- explicit phase boundaries for future implementation work
- the expected verification and doc-sync rules for each phase

## Important Rule

Do not hide critical business policy in FastMCP tool handlers. Keep those rules in the internal core.

For the broader platform shape:

- use Valkey for ephemeral runtime state such as cache, session continuity, idempotency keys, rate limits, short-lived workflow state, and lightweight pub/sub or streams
- use PostgreSQL as the durable source of truth for registry data, tenants, audits, approvals, and durable workflow records
- use LangGraph for orchestration rather than stretching FastMCP into a workflow engine for the whole platform
- split roadmap work into five groups: conversation/orchestration, MCP registry/routing, execution reliability, visual observability, and application output formatting
