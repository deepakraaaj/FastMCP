# TAG FastMCP

A **domain-agnostic, multi-application** MCP runtime and seed layer for a broader enterprise agent platform.

> Built on [FastMCP](https://gofastmcp.com) · Self-hosted vLLM agent layer · React Flow visual canvas

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Architecture Console  (React + React Flow)                     │
│  Policy topology · Scenario mockups · Approval states           │
├─────────────────────────────────────────────────────────────────┤
│  MCP Tool Layer  (FastMCP 3.x)                                  │
│  execute_sql · discover_schema · invoke_capability              │
│  lifecycle review tools · agent_chat · workflows                │
├─────────────────────────────────────────────────────────────────┤
│  Core Engine  (Domain-Agnostic)                                 │
│  AppRouter → per-app context (DB, policy, registry)             │
│  AsyncQueryEngine · SchemaDiscovery · ClarificationAgent        │
│  Session · Idempotency · SQL Policy · Response Builder          │
├─────────────────────────────────────────────────────────────────┤
│  Data Layer                                                     │
│  Any async DB  (MySQL, PostgreSQL, SQLite)                      │
│  Self-hosted vLLM  (Llama 3, Mistral, etc.)                    │
└─────────────────────────────────────────────────────────────────┘
```

## Key Principles

- **No application-specific code in the core.** All domain logic lives in YAML manifests under `domains/` and app config in `apps.yaml`.
- **Multi-app by design.** A single server handles multiple applications via `app_id` routing.
- **Async everywhere.** The query engine uses `sqlalchemy[asyncio]` for non-blocking DB access.
- **FastMCP is the execution surface, not the whole platform.** Keep MCP handlers thin and use them to expose safe typed capabilities to the broader orchestration layer.
- **LangGraph is the long-term orchestration layer.** Clarification loops, agent state, routing, approvals, and multi-step planning should converge there rather than being buried inside MCP handlers.
- **Capability discovery is the plug-and-play contract.** New apps, reports, workflows, and tools should become discoverable through a typed registry before orchestration logic depends on them.
- **Valkey for ephemeral runtime state.** Cache, session state, idempotency keys, short-lived workflow state, rate limits, and lightweight pub/sub or streams belong in Valkey.
- **PostgreSQL for durable control-plane data.** Registry metadata, tenants, audits, approvals, and durable workflow records should live in PostgreSQL rather than the ephemeral store.
- **Self-hosted LLM.** The clarification agent calls your own vLLM endpoint — no external API keys needed.

## Long-Term Platform Direction

Recommended stack for the broader platform around this repository:

- `LangGraph` for conversation and agent orchestration
- `FastMCP` for MCP servers and tool adapters
- `Langfuse` for AI traces, debugging, and evals
- `OpenTelemetry + Grafana + Loki + Tempo + Prometheus` for platform observability
- `React Flow` for the visual agent and MCP topology
- `Valkey + PostgreSQL` for shared state, cache, sessions, registry, and durable records
- `EKS` as the primary deployment target

This repository should therefore be evolved as one layer of the system, not the entire system.

## Build Domains

When planning work, split the application into these five problem groups:

- conversation and orchestration
- MCP registry and routing
- execution reliability
- visual observability
- application output formatting

## Plug-And-Play Baseline

The current runtime now exposes a typed capability registry through `describe_capabilities`.

That registry is the starting contract for:

- MCP server discovery
- agent discovery
- app-level report and workflow discovery
- future routing decisions
- config-only onboarding paths

The current onboarding baseline is:

1. register an app in `apps.yaml`
2. define reports and workflows in its manifest
3. let the core capability registry derive the discoverable contract
4. keep MCP tools thin and let orchestration consume registry metadata rather than hardcoded branches

The next plug-and-play baseline now also supports:

- config-only external MCP server registration in `apps.yaml`
- config-only channel formatter contracts in `apps.yaml`
- registry discovery of external tools and formatter capabilities through `describe_capabilities`
- registry-driven execution through `invoke_capability`
- trusted admin chat over HTTP using the same request-context, planner, formatter, and lifecycle core
- trusted admin lifecycle review, decision, registration, activation, and resume tools over MCP
- trusted admin lifecycle review, decision, registration, activation, and resume routes over HTTP
- dynamic discovery of activated agents through `describe_capabilities`

`invoke_capability` is the first registry-consuming execution path. It can:

- select a report or workflow by tags instead of hardcoded tool branching
- dispatch a registered external MCP tool by capability id
- attach channel formatter metadata to the routing result

The current reliability baseline for registered external MCP tools includes:

- per-tool timeout budgets
- bounded retries with backoff
- server-level circuit breaker state
- exact fallback capability ids for deterministic degradation

---

## Quick Start

### 1. Backend (MCP Server)

```bash
# Install Python dependencies
uv sync

# Configure your environment
cp .env.example .env
# Edit `.env` with your apps config, database, LLM, and optional Valkey settings

# Optional: run the bundled demo apps instead of your primary config
# TAG_FASTMCP_APPS_CONFIG_PATH=apps.demo.yaml

# Start the MCP server
uv run tag-fastmcp
```

Server runs at `http://127.0.0.1:8001`.

When `TAG_FASTMCP_APPS_CONFIG_PATH=apps.demo.yaml`, startup now auto-seeds the bundled SQLite maintenance and dispatch demo databases so the widget and admin console have sample data immediately.

Available HTTP surfaces:

- MCP transport: `http://127.0.0.1:8001/mcp`
- Widget session bootstrap: `POST http://127.0.0.1:8001/session/start`
- Widget chat stream: `POST http://127.0.0.1:8001/chat?stream=false`
- Admin chat stream: `POST http://127.0.0.1:8001/admin/chat?stream=false`
- Admin approval queue: `GET http://127.0.0.1:8001/admin/approvals`
- Admin approval decision: `POST http://127.0.0.1:8001/admin/approvals/{approval_id}/decision`
- Admin approval resume: `POST http://127.0.0.1:8001/admin/approvals/{approval_id}/resume`
- Admin proposal list: `GET http://127.0.0.1:8001/admin/agents/proposals`
- Admin proposal register: `POST http://127.0.0.1:8001/admin/agents/proposals/{proposal_id}/register`
- Admin registration list: `GET http://127.0.0.1:8001/admin/agents/registrations`
- Admin registration activate: `POST http://127.0.0.1:8001/admin/agents/registrations/{registration_id}/activate`
- Health probe: `GET http://127.0.0.1:8001/healthz`

Admin HTTP routes currently expect a development-time `x-admin-context` header containing base64-encoded JSON for actor, role, scopes, and allowed apps. This is a transport placeholder until real auth integration lands. Admin chat now runs through the live bounded `admin_orchestration` runtime, while heavy cross-db execution and real auth are still later steps.

### 2. Architecture Console (UI)

```bash
cd ui
npm install
npm run dev
```

Opens at `http://localhost:3000`. The UI now combines the Phase 7 architecture console with a live browser surface for widget chat, admin chat, approvals, proposals, and registration activation. The Vite dev server proxies `/session`, `/chat`, `/admin`, `/healthz`, and `/mcp` to the backend.

### 3. Run Tests

```bash
uv run pytest
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `TAG_FASTMCP_DATABASE_URL` | Async runtime DB connection string | `sqlite+aiosqlite:///data/tag_fastmcp.sqlite3` |
| `TAG_FASTMCP_CONTROL_PLANE_DATABASE_URL` | Async DB for approvals, proposal drafts, registrations, and lifecycle audit records; defaults to `TAG_FASTMCP_DATABASE_URL` when unset | unset |
| `TAG_FASTMCP_APPS_CONFIG_PATH` | Path to the multi-app registry YAML | `apps.yaml` |
| `TAG_FASTMCP_DEFAULT_CHAT_APP_ID` | Default app for widget chat when no `x-app-id` is supplied | unset |
| `TAG_FASTMCP_LLM_BASE_URL` | vLLM-compatible API endpoint | `http://192.168.15.112:8000/v1` |
| `TAG_FASTMCP_LLM_MODEL` | Model name for the agent | `default` |
| `TAG_FASTMCP_HOST` | Server bind address | `127.0.0.1` |
| `TAG_FASTMCP_PORT` | Server bind port | `8001` |
| `TAG_FASTMCP_SESSION_STORE_BACKEND` | `memory` or `valkey` for session storage | `memory` |
| `TAG_FASTMCP_IDEMPOTENCY_STORE_BACKEND` | `memory` or `valkey` for replay storage | `memory` |
| `TAG_FASTMCP_VALKEY_URL` | Valkey connection string for ephemeral state | `valkey://127.0.0.1:6379/0` |
| `TAG_FASTMCP_VALKEY_KEY_PREFIX` | Shared key prefix for ephemeral state | `tag_fastmcp` |
| `TAG_FASTMCP_SESSION_TTL_SECONDS` | Session TTL in Valkey, `0` disables expiry | `86400` |
| `TAG_FASTMCP_IDEMPOTENCY_TTL_SECONDS` | Replay-cache TTL in Valkey, `0` disables expiry | `86400` |

---

## Repository Layout

```
├── src/tag_fastmcp/
│   ├── app.py                     # FastMCP app factory
│   ├── http_api.py                # Widget/admin HTTP adapters + mounted /mcp server
│   ├── settings.py                # Environment-backed settings
│   ├── core/
│   │   ├── app_router.py          # Multi-app context resolver
│   │   ├── agent_registry.py      # Bounded agent catalog and selection rules
│   │   ├── agent_lifecycle_service.py # Proposal draft, registration, and activation lifecycle
│   │   ├── admin_service.py       # Shared admin lifecycle transport logic
│   │   ├── admin_chat_service.py  # Shared admin chat orchestration bridge
│   │   ├── approval_service.py    # Durable approval requests, decisions, and resume gates
│   │   ├── capability_router.py   # Registry-driven execution and dispatch
│   │   ├── capability_registry.py # Plug-and-play capability discovery
│   │   ├── chat_service.py        # Widget chat/session orchestration
│   │   ├── circuit_breaker.py     # External MCP dependency breaker state
│   │   ├── container.py           # Dependency graph
│   │   ├── control_plane_store.py # Local durable lifecycle record storage
│   │   ├── formatter_service.py   # Visibility-aware channel response rendering
│   │   ├── intent_planner.py      # Deterministic NL intent analysis and candidate ranking
│   │   ├── orchestration_service.py # Planner/compiler coordination for chat and direct-tool paths
│   │   ├── plan_compiler.py       # Compile orchestration decisions into routed execution requests
│   │   ├── policy_envelope.py     # Scope and capability enforcement
│   │   ├── query_engine.py        # Async SQL executor
│   │   ├── request_context.py     # Trusted request normalization
│   │   ├── schema_discovery.py    # Auto-introspect any database
│   │   ├── sql_policy.py          # SQL validation & mutation policy
│   │   ├── session_store.py       # Session timeline + memory/Valkey backends
│   │   ├── idempotency.py         # Replay-safe response store + memory/Valkey backends
│   │   ├── response_builder.py    # Typed response envelopes
│   │   ├── visibility_policy.py   # Role-aware visibility derivation
│   │   ├── workflow_engine.py     # Guided workflow state
│   │   └── domain_registry.py     # Manifest loading
│   ├── agent/
│   │   ├── admin_orchestration_agent.py # Live bounded admin orchestration runtime
│   │   ├── clarification_agent.py # vLLM-powered clarification
│   │   ├── stubs.py               # Phase 3 stub agents for later runtimes
│   │   └── prompts.py             # System prompts for agent
│   ├── models/
│   │   ├── contracts.py           # Typed request/response models
│   │   ├── app_config.py          # Multi-app config models
│   │   ├── schema_models.py       # Schema introspection models
│   │   └── builder.py             # Builder graph models
│   └── tools/
│       ├── query_tools.py         # execute_sql, summarize
│       ├── routing_tools.py       # invoke_capability
│       ├── lifecycle_tools.py     # approval review, registration, activation, resume
│       ├── schema_tools.py        # discover_schema
│       ├── agent_tools.py         # agent_chat
│       ├── report_tools.py        # run_report
│       ├── workflow_tools.py      # start/continue workflow
│       ├── builder_tools.py       # graph validation
│       └── system_tools.py        # health, session info
├── ui/                            # Architecture console / visual artifacts demo
│   ├── src/
│   │   ├── App.jsx                # Architecture console plus live runtime surface
│   │   ├── components/
│   │   │   └── LiveConsole.jsx    # Live widget/admin/lifecycle browser console
│   │   └── nodes/
│   │       └── SystemNode.jsx     # Topology node component
│   ├── package.json
│   └── vite.config.js
├── domains/                       # Domain manifests (YAML)
├── apps.yaml                      # Multi-app registry
├── tests/
├── docs/
└── AGENTS.md
```

---

## Adding a New Application

1. Add a DB connection and manifest path to `apps.yaml`:
   ```yaml
   apps:
     my_app:
       display_name: "My Application"
       database_url: "mysql+aiomysql://user:pass@host:3306/mydb"
       domain_manifest_path: "domains/my_app.yaml"
   ```

2. Create a domain manifest at `domains/my_app.yaml` with your reports and workflows.

3. Optionally register external MCP servers and channel formatter contracts:
   ```yaml
   mcp_servers:
     github:
       display_name: "GitHub MCP"
       description: "External GitHub integration server."
       transport: "streamable-http"
       endpoint: "http://github-mcp.local/mcp"
       auth_mode: "bearer"
       app_ids: ["my_app"]
       tools:
         search_issues:
           display_name: "Search Issues"
           description: "Search repository issues."
           input_schema: "GitHubIssueSearchRequest"
           output_schema: "GitHubIssueSearchResponse"

   channels:
     web_chat:
       display_name: "Web Chat"
       description: "Browser chat surface."
       app_ids: ["my_app"]
       formatter:
         formatter_id: "web_chat.default"
         request_contract: "ChannelRequest[web_chat]"
         response_contract: "ChannelResponse[text|card|dashboard]"
         output_modes: ["text", "card", "dashboard"]
         supports_streaming: true
         supports_actions: true
   ```

## Widget Compatibility

The repository now exposes a lightweight HTTP adapter for the existing KritiBot widget contract.

Expected widget calls:

- `POST /session/start`
- `POST /chat?stream=false`
- `x-app-id` header when multiple apps are configured
- `x-user-context` header with base64-encoded JSON user metadata

The adapter keeps session continuity in the internal core and routes text chat through the clarification agent for the selected application.

4. All MCP tool calls now accept `app_id: "my_app"` to route to the correct context, and `describe_capabilities` will expose the new app, external server tools, and formatter contracts.

---

## Read First (for contributors)

1. `docs/application-context.md`
2. `docs/architecture.md`
3. `docs/continuation-guide.md`
4. `AGENTS.md`
