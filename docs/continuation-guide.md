# Continuation Guide

Date: 2026-03-16

This file is for the next AI or engineer who takes over.

## What Is Already Built

- FastMCP app factory and server entrypoint
- typed request/response models
- session store
- idempotency store
- SQL policy validator
- SQLite-backed query engine
- report execution from manifest
- workflow start/continue skeleton
- builder graph validation + FastMCP preview bridge
- development domain manifest
- tests for core invariants

## What To Build Next

### Priority 1

- Redis-backed session store
- Redis-backed idempotency store
- auth provider integration

### Priority 2

- multi-domain registry
- report parameter binding
- stronger workflow actions

### Priority 3

- NL-to-SQL planner
- richer clarification flows
- compatibility HTTP adapter if required by downstream clients
- visual builder UI that targets the constrained builder graph schema

## What Not To Break

- SQL mutation safety
- forbidden-table blocking
- idempotent replay behavior
- session continuity
- typed response contracts

## Decision Rule

If a feature needs shared state or policy, put it in the internal core.

If a feature only exposes an existing safe capability to clients, it likely belongs in a tool.
