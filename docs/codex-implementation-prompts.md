# Phase 8 Codex Implementation Prompts

Date: 2026-03-19
Purpose: Provide one repo-specific Codex-ready prompt per phase so implementation can proceed in bounded steps without collapsing into one large request.

## How To Use This Pack

- use the prompts in order
- do not skip phase boundaries unless the repository has already implemented and verified the earlier phase
- each prompt assumes the earlier phase outputs are already present
- each prompt is written for this repository, not as a generic template
- each prompt expects code, tests, and doc updates unless the phase is explicitly docs-only

## Shared Repo Rules For Every Prompt

Every prompt below assumes the implementation agent will:

1. read `docs/application-context.md`, `docs/architecture.md`, `README.md`, `docs/request-routing.md`, and `docs/continuation-guide.md` first
2. keep MCP tool handlers thin and keep policy, state, and guardrails in the internal core
3. preserve typed contracts and SQL policy enforcement
4. add or update tests for meaningful behavior changes
5. update `docs/application-context.md`, `docs/architecture.md`, `docs/continuation-guide.md`, and `skills.md` when boundaries or workflows change
6. avoid implementing later phases early

## Prompt 1: Phase 1 Architecture Validation And Target Design

Use this when the repository needs a fresh architecture validation pass before any phased implementation work starts.

```text
Review the current TAG FastMCP repository and produce a deterministic Phase 1 architecture validation and target design.

Read first:
- docs/application-context.md
- docs/architecture.md
- README.md
- docs/request-routing.md
- docs/continuation-guide.md

Then inspect the current runtime and produce:
1. executive verdict
2. strengths already implemented
3. goal alignment against strict app isolation, safe admin access, natural-language routing, agent escalation, and approval-based agent creation
4. concrete architectural gaps
5. target architecture by layer
6. recommended agent set
7. acceptance checklist for Phase 1
8. Phase 2 handoff notes

Constraints:
- do not write runtime code
- do not propose prompt-only safety
- app chat must never widen beyond its own application
- admin-wide access must be explicit and auditable
- no LLM may receive raw database power
- new agent creation must be draft-first and approval-gated

Deliverables:
- update docs with the current-state assessment and target architecture
- keep the result repo-specific, not generic
- state clearly what is already strong and what is missing
```

## Prompt 2: Phase 2 Enforcement Model And Routing Contract

Use this after Phase 1 is accepted and before agent or planner work is implemented.

```text
Implement Phase 2 in the TAG FastMCP repository: request normalization, policy envelopes, execution-mode separation, and routing-plan contracts.

Read first:
- docs/application-context.md
- docs/architecture.md
- README.md
- docs/request-routing.md
- docs/continuation-guide.md
- docs/enforcement-model.md

Goal:
Introduce the shared contracts that force scope before reasoning:
- RequestContext
- PolicyEnvelope
- RoutingPlan

Implementation expectations:
- add typed models for the new contracts
- add core services for request normalization and policy-envelope derivation
- separate execution modes into app_chat, admin_chat, direct_tool, and system
- bind widget chat sessions to trusted app scope before any LLM call
- ensure direct tool paths also create request context and envelope records
- thread the new enforcement path into the current chat and routing flows without weakening existing SQL guardrails

Suggested files to add or update:
- src/tag_fastmcp/models/contracts.py or a dedicated typed model module if cleaner
- src/tag_fastmcp/core/request_context.py
- src/tag_fastmcp/core/policy_envelope.py
- src/tag_fastmcp/core/chat_service.py
- src/tag_fastmcp/http_api.py
- src/tag_fastmcp/core/container.py
- tests covering scope binding and rejection behavior

Do not implement yet:
- full natural-language planner logic
- heavy-agent execution
- approval persistence
- formatter execution

Required behavior:
- app_chat rejects missing or conflicting app context before planning
- prompt text cannot expand app, tenant, or admin scope
- app sessions cannot silently switch bound app_id
- selected capabilities must remain a strict subset of the envelope

Verification:
- add tests for app binding, denied cross-app access, admin scope derivation, and direct-tool enforcement
- run the relevant test suite

Update docs after implementation.
```

## Prompt 3: Phase 3 Agent Model

Use this after Phase 2 contracts exist and enforcement is already in place.

```text
Implement Phase 3 in the TAG FastMCP repository: the bounded agent model and agent-selection scaffolding.

Read first:
- docs/application-context.md
- docs/architecture.md
- README.md
- docs/request-routing.md
- docs/continuation-guide.md
- docs/enforcement-model.md
- docs/agent-model.md

Goal:
Represent the approved agent topology in code without moving permission or safety out of the internal core.

Implementation expectations:
- add typed agent-class metadata and selection rules for:
  - app scoped chat agent
  - admin orchestration agent
  - schema intelligence agent
  - heavy cross-db agent
  - agent proposal agent
- make agent choice depend on RequestContext and PolicyEnvelope
- extend capability or agent registry metadata so later planner work can ask which agent classes are available
- keep the current clarification agent as the concrete baseline for the app-scoped path
- add stubs or interfaces for the other agent classes if they are not fully executable yet

Suggested files to add or update:
- src/tag_fastmcp/core/agent_registry.py or equivalent core module
- src/tag_fastmcp/core/container.py
- src/tag_fastmcp/core/capability_registry.py
- src/tag_fastmcp/agent/
- tests for agent selection and forbidden transitions

Do not implement yet:
- full NL planner execution
- heavy-agent orchestration logic
- approval workflow persistence
- formatter service

Required behavior:
- agents never widen scope
- app chat can only select the app-scoped chat agent
- admin agent selection requires trusted admin scope
- heavy and proposal agents remain explicitly disabled unless the envelope allows them

Verification:
- add tests for agent selection by execution mode and policy envelope
- run the relevant test suite

Update docs after implementation.
```

## Prompt 4: Phase 4 Routing And Orchestration

Use this after Phases 2 and 3 are implemented and verified.

```text
Implement Phase 4 in the TAG FastMCP repository: natural-language planning, capability ranking, bounded orchestration decisions, and compilation into the existing deterministic router.

Read first:
- docs/application-context.md
- docs/architecture.md
- README.md
- docs/request-routing.md
- docs/continuation-guide.md
- docs/enforcement-model.md
- docs/agent-model.md
- docs/routing-orchestration.md

Goal:
Turn user language into a bounded OrchestrationDecision and RoutingPlan without letting the planner bypass policy.

Implementation expectations:
- add typed planner-side models such as PlanningInput, IntentAnalysis, CapabilityCandidate, and OrchestrationDecision
- implement intent analysis and candidate generation from the envelope-filtered registry
- implement ranking rules that prefer reports and workflows over speculative SQL
- compile approved decisions into the existing CapabilityRouter inputs
- add explicit planner outcomes for clarification, rejection, single-step execution, multi-step execution, heavy escalation, and proposal
- keep direct-tool mode on the minimal audited path without NL classification

Suggested files to add or update:
- src/tag_fastmcp/core/intent_planner.py
- src/tag_fastmcp/core/plan_compiler.py
- src/tag_fastmcp/core/capability_router.py
- src/tag_fastmcp/core/chat_service.py
- src/tag_fastmcp/models/contracts.py or adjacent planner model module
- tests for candidate ranking, clarification thresholds, rejection, and heavy escalation thresholds

Do not implement yet:
- durable approval records
- final formatter execution service
- live UI wiring beyond what current transports need

Required behavior:
- planner cannot widen the PolicyEnvelope
- clarification is chosen over guessing
- blocked scope requests become explicit rejections
- heavy escalation is driven by execution structure, not broad wording alone
- the dispatcher remains the execution owner

Verification:
- add tests for report preference, workflow preference, blocked cross-app requests, and heavy-agent thresholds
- run the relevant test suite

Update docs after implementation.
```

## Prompt 5: Phase 5 Formatter And UX Layer

Use this after planner outcomes exist and execution paths return structured results.

```text
Implement Phase 5 in the TAG FastMCP repository: visibility profiles, formatter execution, channel response models, and explicit presentation for approval, escalation, rejection, and degraded states.

Read first:
- docs/application-context.md
- docs/architecture.md
- README.md
- docs/request-routing.md
- docs/continuation-guide.md
- docs/enforcement-model.md
- docs/routing-orchestration.md
- docs/formatter-ux.md

Goal:
Convert structured execution results into safe, role-aware channel output without allowing the formatter layer to decide data scope.

Implementation expectations:
- add typed models for VisibilityProfile, FormatterInput, ChannelResponse, OutputBlock, ChannelAction, and ResponseState
- implement visibility-policy derivation from PolicyEnvelope and actor role
- implement a formatter service that resolves allowed formatter ids and safely degrades to text when a richer formatter is unavailable
- evolve widget response handling toward richer stateful events while preserving compatibility where possible
- make approval-required, escalated, rejected, and degraded states visible in the response model

Suggested files to add or update:
- src/tag_fastmcp/core/visibility_policy.py
- src/tag_fastmcp/core/formatter_service.py
- src/tag_fastmcp/models/contracts.py
- src/tag_fastmcp/models/http_api.py
- src/tag_fastmcp/http_api.py
- tests for visibility rules and formatter fallback behavior

Do not implement yet:
- durable approval queue persistence
- real agent registration or activation
- full live admin UI integration

Required behavior:
- app users do not see raw SQL or planner traces by default
- admin users only see richer diagnostics when policy allows it
- formatter ids must come from the envelope
- presentation fallback does not change execution behavior

Verification:
- add tests for end-user versus admin visibility and formatter fallback
- run the relevant test suite

Update docs after implementation.
```

## Prompt 6: Phase 6 Approval And Agent Creation Workflow

Use this after the planner and formatter can surface approval-required and proposal-required states.

```text
Implement Phase 6 in the TAG FastMCP repository: durable approval records, proposal drafts, registration-versus-activation boundaries, and pause/resume control flow.

Read first:
- docs/application-context.md
- docs/architecture.md
- README.md
- docs/request-routing.md
- docs/continuation-guide.md
- docs/enforcement-model.md
- docs/routing-orchestration.md
- docs/formatter-ux.md
- docs/approval-agent-lifecycle.md

Goal:
Turn approval-required execution and agent proposals into durable, auditable control-plane workflows.

Implementation expectations:
- add typed models and persistence-facing interfaces for:
  - ApprovalRequest
  - ApprovalDecision
  - ExecutionApprovalPayload
  - AgentProposalDraft
  - AgentRegistrationRecord
- add approval and agent-lifecycle services in the internal core
- pause runtime execution at approval boundaries and resume only from recorded state
- keep registration separate from activation
- support draft-only proposal creation for new agents
- make the implementation ready for durable PostgreSQL-backed control-plane storage even if a local baseline store is used first

Suggested files to add or update:
- src/tag_fastmcp/core/approval_service.py
- src/tag_fastmcp/core/agent_lifecycle_service.py
- src/tag_fastmcp/models/contracts.py or a dedicated lifecycle model module
- src/tag_fastmcp/core/container.py
- planner and formatter integration points
- tests for approval state transitions and draft proposal lifecycle

Do not implement yet:
- silent auto-approval
- automatic agent activation
- broad UI redesign outside the contract needed for lifecycle state

Required behavior:
- no approval decision lives only in chat history or session memory
- execution approval and agent lifecycle approval remain separate scopes
- approved proposals may become registered without becoming active
- rejected proposals remain rejected and auditable

Verification:
- add tests for approval creation, approval rejection, proposal drafting, registration, and activation gating
- run the relevant test suite

Update docs after implementation.
```

## Prompt 7: Phase 7 Visual Artifacts

Use this when the backend contracts for earlier phases are documented or partially implemented and the UI needs to show the system shape clearly.

```text
Implement or refine Phase 7 in the TAG FastMCP repository: diagrams, screen blueprint, and a working React demo that makes policy, escalation, approval, and lifecycle state visible.

Read first:
- docs/application-context.md
- docs/architecture.md
- README.md
- docs/request-routing.md
- docs/continuation-guide.md
- docs/formatter-ux.md
- docs/approval-agent-lifecycle.md
- docs/visual-artifacts.md

Goal:
Replace any generic node-builder demo with an architecture console that accurately reflects the system designed in Phases 2 through 6.

Implementation expectations:
- keep a fixed topology for the target request path
- show at least these scenarios:
  - app-scoped chat
  - admin cross-app orchestration
  - draft-only agent proposal
- show policy envelope state, active agents, approval queue state, user-facing transcript examples, and formatter-facing output blocks
- keep the UI obviously demonstrative rather than pretending to be fully live if the backend is not wired yet

Suggested files to add or update:
- ui/src/App.jsx
- ui/src/index.css
- ui/src/nodes/
- docs/visual-artifacts.md

Do not implement yet:
- full live backend integration unless earlier phases are already complete
- fake approval logic that implies persistence exists when it does not
- a generic drag-and-drop builder unrelated to the approved architecture

Required behavior:
- app chat and admin chat must read as distinct operating modes
- heavy-agent invocation must be visibly explicit
- new-agent creation must appear as draft-first and approval-gated
- the UI must separate user-visible output from audit and control state

Verification:
- build the UI successfully
- confirm the documented scenarios are represented

Update docs after implementation.
```

## Prompt Pack Acceptance Criteria

This Phase 8 pack is complete when:

- every earlier phase has a prompt that is repo-specific
- every prompt states what should not be implemented yet
- prompts preserve the policy-first, guarded-core architecture
- prompts instruct future implementers to add tests and sync docs
- no prompt allows app chat to widen scope or grants raw DB power to an LLM

## Recommended Execution Order

1. Phase 1 validation prompt if the repository needs a fresh design review
2. Phase 2 implementation prompt
3. Phase 3 implementation prompt
4. Phase 4 implementation prompt
5. Phase 5 implementation prompt
6. Phase 6 implementation prompt
7. Phase 7 implementation prompt

Phase 8 is this prompt pack itself.
