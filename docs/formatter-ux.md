# Formatter and UX Contract

Date: 2026-03-19
Purpose: Phase 5 target design for channel formatting, visibility rules, and execution-state presentation.

## Why This Exists

The repository already has:

- channel formatter metadata in the registry
- formatter capability ids attached during routing
- a widget HTTP stream that can emit `token`, `result`, and `error`
- a baseline visibility policy and formatter service in the internal core

What it still does not have is the full approval-aware and admin-surface presentation layer for every runtime path.

This document defines that missing layer.

It sits after:

- `RequestContext`
- `PolicyEnvelope`
- planner and orchestration decisions
- guarded execution

The design it depends on is defined in:

- `docs/enforcement-model.md`
- `docs/agent-model.md`
- `docs/routing-orchestration.md`

## Core Rule

Formatters do not decide what the user is allowed to know.

They render what the policy and visibility rules already allow.

The formatter layer must not:

- widen scope
- expose blocked diagnostics
- reveal raw SQL or planner traces by accident
- invent capability actions that were not approved upstream

## Current Runtime Assessment

### Already present

- channel metadata and formatter metadata in the registry
- formatter ids attached to routing results
- widget NDJSON response path
- typed response envelopes from the core
- visibility profiles derived from request context and policy envelope
- formatter-backed `ChannelResponse` models attached to widget and routed MCP outputs
- opt-in rich widget `block`, `state`, and `action` events

### Missing

- durable approval-action execution
- richer admin-dashboard presentation and live admin transport
- formatter integration for every direct tool surface
- full live action handling behind the new response models

## Layer Placement

The target output path should be:

1. execution completes or pauses
2. visibility profile is derived from the envelope and actor role
3. formatter selection resolves the allowed channel formatter
4. formatter converts execution output into channel blocks
5. the transport streams or returns those blocks

The important boundary is:

- planner decides what happened
- execution returns structured results
- formatter decides how approved information is shown

## Non-Negotiable Rules

- use only formatter ids allowed by the `PolicyEnvelope`
- preserve typed core response envelopes beneath the presentation layer
- default to the least revealing safe view
- keep app-chat output concise and operational
- keep admin output richer only when diagnostics are explicitly allowed
- make approval, escalation, rejection, and degraded execution states visible
- degrade to plain text safely when a richer formatter is unavailable

## Visibility Model

Visibility is derived from policy, not from formatter preference.

### `VisibilityProfile`

```text
VisibilityProfile
- profile_id: str
- actor_role: end_user | app_admin | platform_admin | service
- execution_mode: app_chat | admin_chat | direct_tool | system
- show_plan_summary: bool
- show_capability_ids: bool
- show_app_scope: bool
- show_sql_text: bool
- show_trace_id: bool
- show_retry_and_fallback: bool
- show_approval_metadata: bool
- show_escalation_metadata: bool
- show_raw_errors: bool
- show_actions: bool
```

### Default Visibility Rules

#### `end_user` in `app_chat`

- show final answer, clarification prompts, workflow progress, and user-safe warnings
- do not show raw SQL
- do not show planner traces
- do not show internal capability ids
- show approval and escalation only as business-safe state

#### `app_admin`

- may show richer execution state and fallback/degraded notices
- may show selected app scope and capability labels
- still hide raw SQL unless explicitly allowed by policy and channel

#### `platform_admin` in `admin_chat`

- may show plan summaries, selected capabilities, app scope, degraded execution details, approval reasons, and escalation state
- raw SQL remains opt-in through policy and channel, not automatic

## Formatter Contracts

The current registry already stores:

- `request_contract`
- `response_contract`
- `output_modes`
- `supports_streaming`
- `supports_actions`
- `supports_approvals`

Phase 5 turns that metadata into executable contracts.

### `FormatterInput`

```text
FormatterInput
- request_id: str
- trace_id: str | None
- channel_id: str
- formatter_id: str
- execution_mode: app_chat | admin_chat | direct_tool | system
- visibility_profile_id: str
- route: answer | clarification | report | workflow | routing | approval | escalation | rejection | error
- primary_message: str
- execution_payload: dict[str, Any]
- warnings: list[str]
- fallback_used: bool
- fallback_capability_id: str | None
- approval_state: none | required | pending | approved | rejected
- escalation_state: none | requested | running | partial | completed | failed
- available_actions: list[str]
```

### `ChannelResponse`

```text
ChannelResponse
- response_id: str
- channel_id: str
- formatter_id: str
- primary_mode: text | card | dashboard
- blocks: list[OutputBlock]
- actions: list[ChannelAction]
- state: ResponseState
- diagnostics: dict[str, Any]
```

### `OutputBlock`

```text
OutputBlock
- block_id: str
- kind: text | card | table | metric_group | checklist | status | approval | escalation
- title: str | None
- body: str | None
- data: dict[str, Any]
```

### `ChannelAction`

```text
ChannelAction
- action_id: str
- kind: continue_workflow | approve | reject | retry | open_details | open_dashboard
- label: str
- enabled: bool
- payload: dict[str, Any]
```

### `ResponseState`

```text
ResponseState
- status: ok | pending | blocked | degraded | approval_required | escalated | error
- user_visible_reason: str
- detail_level: minimal | standard | diagnostic
```

## Output Mode Rules

The existing `output_modes` remain the top-level presentation choices.

### `text`

Use when:

- the channel is chat-first
- the payload is simple
- the user only needs one direct answer or one clarification question

### `card`

Use when:

- the output contains structured facts
- the response benefits from a title, summary, and small action set
- workflow or approval state should be visually separated from the answer

### `dashboard`

Use when:

- the user is in an admin or analytical view
- the output includes metrics, tables, comparisons, or staged execution state
- the channel explicitly supports richer layout

`dashboard` should not be forced into end-user widget chat unless the channel contract allows it and the UX remains legible.

## State Presentation Rules

### Clarification

Must show:

- what is missing
- one next question
- optional candidate choices if available

Must not:

- pretend execution already happened

### Workflow Pending

Must show:

- current workflow purpose
- fields already collected when safe
- next required field

### Approval Required

Must show:

- the action requiring approval
- why approval is needed
- the current approval state

If the channel supports approvals:

- include explicit approve and reject actions

If the channel does not support approvals:

- show a pending state and fallback plain-text instructions or a reference handle

### Heavy Escalation

Must show:

- that heavier execution was invoked
- why normal routing was insufficient
- current state such as requested, running, partial, completed, or failed

Heavy execution must never be invisible to the user.

### Degraded / Fallback Execution

Must show:

- that the primary path degraded or fell back
- user-safe impact summary

Admin channels may also show:

- fallback capability id
- retry or dependency state

### Rejection / Blocked

Must show:

- explicit blocked state
- a clear reason
- next step if one exists

## Widget Streaming Contract

The current widget stream supports:

- `token`
- `result`
- `error`

Phase 5 should preserve compatibility while allowing richer event types for newer clients.

### `WidgetStreamEventV2`

```text
WidgetStreamEventV2
- type: token | block | state | action | result | error
- content: str | None
- session_id: str | None
- app_id: str | None
- payload: dict[str, Any]
```

Migration rule:

- old clients continue receiving `token`, `result`, and `error`
- new clients may opt into richer `block`, `state`, and `action` events

## Channel Profiles

### `web_chat`

Default behavior:

- prefer `text`
- use `card` for structured lookup results, workflow progress, approval state, and escalation state
- stream concise text first when streaming is enabled
- hide raw diagnostics from standard users

### `admin_dashboard`

Target behavior:

- prefer `dashboard`
- allow richer status, metrics, tables, app-scope summaries, and degraded-execution detail
- support approvals and escalation monitoring when the channel contract allows them

### `mcp_tool`

Target behavior:

- preserve typed machine-readable responses first
- attach formatter metadata or a structured presentation section second
- do not replace typed tool outputs with UI-only prose

## Implementation Status

The current Phase 5 baseline is intentionally narrow and safe:

- widget chat now returns a formatter-backed `ChannelResponse` alongside the plain text message
- `invoke_capability` now attaches presentation to the typed `ResponseEnvelope`
- visibility rules hide plan, capability, SQL, retry, and trace diagnostics from standard end users by default
- new widget clients may opt into richer `block`, `state`, and `action` events without breaking older token/result/error clients

## Formatter Selection Rules

1. use the formatter bound to the requested channel if it is allowed by the envelope
2. if the requested formatter is unavailable, fall back to a safe plain-text formatter
3. preserve one consistent formatter across a multi-step response when possible
4. downgrade from `dashboard` to `card` or `text` when the channel cannot render richer output
5. never choose a formatter that exposes more diagnostics than the visibility profile allows

## Edge Cases

### Channel supports streaming but not actions

- stream text and state updates
- omit action blocks

### Channel supports approvals but actor is not allowed to approve

- show approval state
- do not emit approve or reject actions

### Execution returns partial results

- show explicit partial/degraded state
- distinguish usable result from missing result

### Formatter unavailable

- degrade to plain text
- keep the result usable
- log the formatter fallback separately from execution fallback

### Multiple apps in admin output

- show app labels clearly
- avoid merging multi-app data into ambiguous text blobs

## Implementation Mapping For Later Phases

- `src/tag_fastmcp/models/contracts.py`
  - add or split formatter-side models such as `VisibilityProfile`, `FormatterInput`, and `ChannelResponse`
- `src/tag_fastmcp/models/http_api.py`
  - extend widget result and stream event models for richer block and state output
- `src/tag_fastmcp/core/capability_registry.py`
  - keep channel formatter metadata as the discovery contract
- `src/tag_fastmcp/core/response_builder.py`
  - continue building stable execution envelopes underneath formatter output
- future `src/tag_fastmcp/core/visibility_policy.py`
  - derive role-aware output visibility
- future `src/tag_fastmcp/core/formatter_service.py`
  - execute formatter selection and block rendering
- future `src/tag_fastmcp/formatters/`
  - channel-specific formatter implementations
- `src/tag_fastmcp/http_api.py`
  - stream formatter blocks and state updates once richer widget transport is added

## Phase 5 Acceptance Checklist

- formatter execution is defined as a layer after planning and execution
- visibility rules are explicit
- channel response contracts are defined
- approval and escalation states have visible UX rules
- widget streaming migration is defined
- formatter fallback is separated from execution fallback

## Phase 6 Handoff

The detailed Phase 6 approval and lifecycle contract is now defined in `docs/approval-agent-lifecycle.md`.
