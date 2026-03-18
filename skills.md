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
- keep session/idempotency backend selection in the core container, not inside tool code
- treat Valkey as the ephemeral runtime state layer and keep durable records out of it
- do not move orchestration, approvals, or cross-service observability into FastMCP unless the architecture explicitly changes
- make new tool behavior discoverable through the capability registry before orchestration depends on it

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
