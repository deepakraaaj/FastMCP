# Continuation Guide

Date: 2026-03-19

This file is for the next AI or engineer who takes over.

The repo now defaults to the `simple` runtime profile. Treat app-scoped chat, schema understanding, onboarding capture, workflows, and guarded DB execution as the active product path. The chat fallback path now supports safe generated reads plus staged write confirmation. The older admin, lifecycle, builder, and external-routing surfaces are still present only as deferred `platform` features, and simple-mode startup should avoid constructing those platform services at all.

## Strategic Direction

Do not turn FastMCP into the whole platform.

Use these long-term ownership boundaries:

- `LangGraph` for orchestration, clarification loops, and multi-step agent flow
- `FastMCP` for MCP servers and tool adapters
- `Langfuse` for AI trace, debug, and eval workflows
- `OpenTelemetry + Grafana + Loki + Tempo + Prometheus` for service observability
- `React Flow` for visual topology and execution graphs
- `Valkey` for ephemeral shared state
- `PostgreSQL` for durable control-plane records
- `EKS` for deployment

## What Is Already Built

- FastMCP app factory and server entrypoint
- typed capability registry and `describe_capabilities` discovery tool
- config-only app onboarding through `apps.yaml`, with optional manifest fallback for domain contracts
- config-only external MCP server registration and channel formatter contracts through `apps.yaml`
- registry-driven execution through `invoke_capability`
- timeout, retry, circuit-breaker, and fallback handling for registered external MCP tools
- typed request/response models
- session store with memory and Valkey backends
- idempotency store with memory and Valkey backends
- SQL policy validator
- fallback chat planner for safe generated reads plus confirmation-gated writes
- SQLite-backed query engine
- report execution from configured domain contracts
- workflow start/continue skeleton
- builder graph validation + FastMCP preview bridge
- development domain contract examples
- localhost demo path via `apps.local.yaml` plus `domains/remp_local.yaml` for a real MySQL-backed management walkthrough
- compatibility HTTP adapter for the existing chatbot widget with `/session/start` and `/chat` mounted alongside `/mcp`
- optional `apps.demo.yaml` bootstrap with explicit `TAG_FASTMCP_ENABLE_DEMO_SEED=true` when you want the bundled SQLite maintenance and dispatch demo datasets seeded for local walkthroughs
- core chat service for widget session history, planner entry, and clarification-agent fallback
- core admin chat service for trusted admin context, planner entry, live admin orchestration runtime, approval/proposal pause points, and formatter output
- admin HTTP bearer JWT auth baseline with trusted claim-to-context mapping and development header fallback
- Phase 2 request-context and policy-envelope services with session-bound app scope
- Phase 3 agent registry with five approved agent classes, bounded selection rules, a live admin orchestration runtime, and a live schema-intelligence understanding-doc runtime
- interactive understanding-workbook capture service plus `scripts/capture_understanding.py` for schema-plus-sample-row onboarding interviews
- Phase 4 intent planner, plan compiler, and orchestration service for bounded report, workflow, external-tool, rejection, and heavy-escalation decisions
- Phase 5 visibility policy and formatter service with rich widget stream support and presentation attached to routed responses
- Phase 6 local durable control-plane store plus approval and agent lifecycle services for paused execution, proposal drafts, registration, activation, and audit records
- trusted admin MCP lifecycle tools for approval review, proposal listing, decision, registration, activation, and resume
- trusted admin HTTP lifecycle routes layered over the same core admin service
- dynamic active-agent exposure through `describe_capabilities` after lifecycle activation
- Phase 7 React architecture console plus live browser console for app chat, admin chat, approval, proposal, and lifecycle interaction
- Phase 8 repo-specific prompt pack for bounded Codex implementation by phase
- tests for core invariants

## What To Build Next

### Priority 1

- use `docs/codex-implementation-prompts.md` as the default execution pack for phased Codex implementation
- extend the existing `RequestContext`, `PolicyEnvelope`, planner, and orchestration baseline into real admin flows
- extend the existing agent registry from catalog and selection scaffolding into richer heavy and proposal runtimes beyond the current admin and schema baselines
- extend the current admin bearer JWT baseline into full IdP/JWKS-backed trusted auth for admin and future widget surfaces
- harden the current live console into a production admin dashboard UX on top of the existing admin HTTP lifecycle surface
- promote the capability registry from config-derived discovery into the formal onboarding contract for adapters and routing
- formalize the conversation and orchestration layer so the current deterministic planner can move into LangGraph cleanly
- design the MCP registry and routing control plane around PostgreSQL-backed durable records
- auth provider integration
- move the current local SQL control-plane baseline onto dedicated PostgreSQL-backed records for registry data, audits, tenants, approvals, and durable workflow records
- multi-process lifecycle cleanup for shared infrastructure clients if the deployment runtime needs explicit shutdown hooks

### Priority 2

- multi-domain registry
- config-only onboarding for external MCP server registrations
- channel formatter contracts so new applications can plug in without orchestration rewrites
- extend the formatter and UX baseline beyond widget chat and the live console into the broader admin dashboard surface
- keep the visual artifact contract in `docs/visual-artifacts.md` aligned with the runtime and formatter contracts
- extend registry-driven routing beyond the current report, workflow, and simple external-tool orchestration baseline
- represent agent classes and approval metadata in the capability registry
- compile bounded multi-step plans through the existing guarded execution core
- add role-aware output visibility and formatter execution
- shared reliability state if multiple workers need coordinated circuit-breaker behavior
- report parameter binding
- stronger workflow actions

### Priority 3

- visual observability using Langfuse plus the OTel, Grafana, Loki, Tempo, and Prometheus stack
- application and channel-specific output formatting
- NL-to-SQL planner
- richer clarification flows
- heavy-agent runtime orchestration and richer proposal lifecycle or admin UX
- compatibility HTTP adapter if required by downstream clients

## Recommended References

If you need implementation references or patterns, start with:

- `langchain-ai/langgraph`
- `langfuse/langfuse`
- `FlowiseAI/Flowise`
- `mastra-ai/mastra`

## What Not To Break

- SQL mutation safety
- forbidden-table blocking
- idempotent replay behavior
- session continuity
- typed response contracts

## Decision Rule

If a feature needs shared state or policy, put it in the internal core.

If a feature only exposes an existing safe capability to clients, it likely belongs in a tool.

## Prompt Pack Rule

When restarting phased implementation, prefer the repo-specific prompts in `docs/codex-implementation-prompts.md` over inventing a new giant prompt from scratch.
