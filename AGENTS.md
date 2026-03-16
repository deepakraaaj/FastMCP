# Repository Instructions

## Startup Context

For any new request in this repository, read these files first before exploring the codebase:

1. `docs/application-context.md`
2. `docs/architecture.md`
3. `README.md`
4. `docs/request-routing.md`
5. `docs/continuation-guide.md`

These are the canonical fast-start files for understanding the project.

## Request Prefix Routing

If the user begins a request with one of these prefixes, treat it as the task selector for the turn:

- `/feature`
- `/bugfix`
- `/bug fix`
- `/review`
- `/investigate`
- `/docs`

## Task-Specific Rules

### Feature work

Before coding:

- identify the runtime path
- identify which core service owns the behavior
- describe whether the change belongs in the FastMCP surface or the internal core
- preserve typed response contracts
- preserve SQL policy enforcement

### Bugfix work

Before patching:

- reproduce or trace the failure
- identify whether the failure is in tools, core services, or manifest config
- prefer the smallest fix that preserves current contracts

### Review work

Primary focus:

- bugs
- regressions
- policy bypasses
- missing tests
- typed contract drift

## Runtime Ownership Rules

Keep these responsibilities in the internal core unless the request explicitly changes architecture:

- session state
- idempotency
- SQL validation and mutation policy
- domain/runtime rules
- final response envelopes
- builder graph validation and compilation rules

Keep MCP tool handlers thin.

## Working Rules

- Do not mirror the full API surface automatically.
- Prefer curated tool design over transport-driven code generation.
- Keep behavior deterministic before adding more LLM logic.
- Do not weaken SQL guardrails.
- If behavior spans multiple tools, consider whether it belongs in a shared core service first.
- Update docs when architecture or runtime boundaries change.

## Contributor Deliverables

When making meaningful changes, update the relevant docs:

- `docs/application-context.md`
- `docs/architecture.md`
- `docs/continuation-guide.md`
- `skills.md`
