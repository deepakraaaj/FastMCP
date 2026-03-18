# TAG FastMCP Application Context

Date: 2026-03-16
Purpose: Canonical fast-start context for this repository.

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

## Current Strengths

- explicit runtime ownership boundaries
- typed request and response contracts
- deterministic SQL policy validation
- constrained builder-to-runtime bridge
- optional Valkey-backed session and idempotency persistence
- bootstrapped development database
- AI handoff docs included from the start

## Current Gaps

- no auth provider yet
- no NL-to-SQL planner yet
- single-domain sample only

## Important Rule

Do not hide critical business policy in FastMCP tool handlers. Keep those rules in the internal core.

For the broader platform shape:

- use Valkey for ephemeral runtime state such as cache, session continuity, idempotency keys, rate limits, short-lived workflow state, and lightweight pub/sub or streams
- use PostgreSQL as the durable source of truth for registry data, tenants, audits, approvals, and durable workflow records
- use LangGraph for orchestration rather than stretching FastMCP into a workflow engine for the whole platform
- split roadmap work into five groups: conversation/orchestration, MCP registry/routing, execution reliability, visual observability, and application output formatting
