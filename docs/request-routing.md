# Request Routing

Purpose: Help future agents choose the correct workflow before changing code.

## Prefix Map

### `/feature`

Use for:

- new tool
- new report
- new workflow
- new domain capability
- auth integration

Read first:

1. `docs/application-context.md`
2. `docs/architecture.md`
3. `skills.md`

Execution expectation:

- identify whether change belongs in a tool or the core
- update tests
- update docs

### `/bugfix` or `/bug fix`

Use for:

- broken tool behavior
- invalid SQL policy result
- session continuity issues
- idempotency regressions

Read first:

1. `docs/application-context.md`
2. `docs/architecture.md`
3. `docs/continuation-guide.md`

Execution expectation:

- reproduce or trace
- fix smallest correct layer
- add regression coverage

### `/review`

Use for:

- code review
- design review
- risk review

Focus on:

- policy bypass risk
- contract drift
- missing tests
- architecture erosion

### `/investigate`

Use for:

- tracing unexpected behavior
- understanding runtime flow before coding

### `/docs`

Use for:

- architecture updates
- contributor docs
- handoff docs

## Default Rule

If no prefix is provided, infer the task type from the request and use the smallest workflow that still protects the architecture.
