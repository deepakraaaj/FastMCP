# Continuation Guide

Date: 2026-03-16

This file is for the next AI or engineer who takes over.

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
- config-only external MCP server registration and channel formatter contracts through `apps.yaml`
- registry-driven execution through `invoke_capability`
- timeout, retry, circuit-breaker, and fallback handling for registered external MCP tools
- typed request/response models
- session store with memory and Valkey backends
- idempotency store with memory and Valkey backends
- SQL policy validator
- SQLite-backed query engine
- report execution from manifest
- workflow start/continue skeleton
- builder graph validation + FastMCP preview bridge
- development domain manifest
- tests for core invariants

## What To Build Next

### Priority 1

- promote the capability registry from manifest-derived discovery into the formal onboarding contract for adapters and routing
- formalize the conversation and orchestration layer so clarification and routing can move into LangGraph cleanly
- design the MCP registry and routing control plane around PostgreSQL-backed durable records
- auth provider integration
- PostgreSQL-backed control-plane persistence for registry data, audits, tenants, approvals, and durable workflow records
- multi-process lifecycle cleanup for shared infrastructure clients if the deployment runtime needs explicit shutdown hooks

### Priority 2

- multi-domain registry
- config-only onboarding for external MCP server registrations
- channel formatter contracts so new applications can plug in without orchestration rewrites
- extend registry-driven routing beyond reports, workflows, and simple external tool dispatch
- shared reliability state if multiple workers need coordinated circuit-breaker behavior
- report parameter binding
- stronger workflow actions

### Priority 3

- visual observability using Langfuse plus the OTel, Grafana, Loki, Tempo, and Prometheus stack
- application and channel-specific output formatting
- NL-to-SQL planner
- richer clarification flows
- compatibility HTTP adapter if required by downstream clients
- visual builder UI that targets the constrained builder graph schema

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
