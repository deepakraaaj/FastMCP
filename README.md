# TAG FastMCP

A **domain-agnostic, multi-application** MCP runtime with a visual workflow builder.

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
- **Self-hosted LLM.** The clarification agent calls your own vLLM endpoint — no external API keys needed.

---

## Quick Start

### 1. Backend (MCP Server)

```bash
# Install Python dependencies
uv sync

# Configure your environment
cp .env.example .env
# Edit .env with your DATABASE_URL and LLM_BASE_URL

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
| `DATABASE_URL` | Async DB connection string | `sqlite+aiosqlite:///data/tag.db` |
| `LLM_BASE_URL` | vLLM-compatible API endpoint | `http://192.168.15.112:8000/v1` |
| `LLM_MODEL` | Model name for the agent | `auto` |
| `HOST` | Server bind address | `127.0.0.1` |
| `PORT` | Server bind port | `8001` |

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
│   │   ├── session_store.py       # Session timeline
│   │   ├── idempotency.py         # Replay-safe response store
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
