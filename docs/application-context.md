# TAG FastMCP Application Context

Date: 2026-03-16
Purpose: Canonical fast-start context for this repository.

## What This Project Is

This project is a FastMCP-first rebuild of the TAG assistant runtime.

The target is not a demo MCP server. The target is a smaller and more explicit production architecture where MCP is the public tool surface and a compact internal core owns policy, state, and domain behavior.

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
- bootstrapped development database
- AI handoff docs included from the start

## Current Gaps

- no auth provider yet
- no Redis-backed persistence yet
- no NL-to-SQL planner yet
- single-domain sample only

## Important Rule

Do not hide critical business policy in FastMCP tool handlers. Keep those rules in the internal core.
