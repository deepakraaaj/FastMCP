# TAG FastMCP

A **domain-agnostic, multi-application** MCP runtime and seed layer for a broader enterprise agent platform.

> Built on [FastMCP](https://gofastmcp.com) · Self-hosted vLLM agent layer · React Flow visual canvas

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Visual Workflow Builder  (React + React Flow)                  │
│  Drag-and-drop node canvas · Config panel · Live execution      │
├─────────────────────────────────────────────────────────────────┤
│  MCP Tool Layer  (FastMCP 3.x)                                  │
│  execute_sql · discover_schema · agent_chat · workflows         │
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

---

## Quick Start

### 1. Backend (MCP Server)

```bash
# Install Python dependencies
uv sync

# Configure your environment
cp .env.example .env
# Edit `.env` with your apps config, database, LLM, and optional Valkey settings

# Start the MCP server
uv run tag-fastmcp
```

Server runs at `http://127.0.0.1:8001/mcp` (streamable-http transport).

### 2. Visual Workflow Builder (UI)

```bash
cd ui
npm install
npm run dev
```

Opens at `http://localhost:3000`. The Vite dev server proxies `/mcp` calls to the backend.

### 3. Run Tests

```bash
uv run pytest
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `TAG_FASTMCP_DATABASE_URL` | Async runtime DB connection string | `sqlite+aiosqlite:///data/tag_fastmcp.sqlite3` |
| `TAG_FASTMCP_APPS_CONFIG_PATH` | Path to the multi-app registry YAML | `apps.yaml` |
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
│   ├── settings.py                # Environment-backed settings
│   ├── core/
│   │   ├── app_router.py          # Multi-app context resolver
│   │   ├── container.py           # Dependency graph
│   │   ├── query_engine.py        # Async SQL executor
│   │   ├── schema_discovery.py    # Auto-introspect any database
│   │   ├── sql_policy.py          # SQL validation & mutation policy
│   │   ├── session_store.py       # Session timeline + memory/Valkey backends
│   │   ├── idempotency.py         # Replay-safe response store + memory/Valkey backends
│   │   ├── response_builder.py    # Typed response envelopes
│   │   ├── workflow_engine.py     # Guided workflow state
│   │   └── domain_registry.py     # Manifest loading
│   ├── agent/
│   │   ├── clarification_agent.py # vLLM-powered clarification
│   │   └── prompts.py             # System prompts for agent
│   ├── models/
│   │   ├── contracts.py           # Typed request/response models
│   │   ├── app_config.py          # Multi-app config models
│   │   ├── schema_models.py       # Schema introspection models
│   │   └── builder.py             # Builder graph models
│   └── tools/
│       ├── query_tools.py         # execute_sql, summarize
│       ├── schema_tools.py        # discover_schema
│       ├── agent_tools.py         # agent_chat
│       ├── report_tools.py        # run_report
│       ├── workflow_tools.py      # start/continue workflow
│       ├── builder_tools.py       # graph validation
│       └── system_tools.py        # health, session info
├── ui/                            # Visual Workflow Builder
│   ├── src/
│   │   ├── App.jsx                # React Flow canvas
│   │   ├── nodes/WorkflowNode.jsx # Custom node component
│   │   └── components/
│   │       ├── Sidebar.jsx        # Draggable node palette
│   │       └── ConfigPanel.jsx    # Node configuration panel
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

3. All MCP tool calls now accept `app_id: "my_app"` to route to the correct context.

---

## Read First (for contributors)

1. `docs/application-context.md`
2. `docs/architecture.md`
3. `docs/continuation-guide.md`
4. `AGENTS.md`
