from __future__ import annotations

from fastmcp import FastMCP

from tag_fastmcp.core.container import AppContainer, build_container, get_container
from tag_fastmcp.settings import AppSettings, get_settings
from tag_fastmcp.tools import (
    register_builder_tools,
    register_lifecycle_tools,
    register_query_tools,
    register_report_tools,
    register_routing_tools,
    register_schema_tools,
    register_agent_tools,
    register_system_tools,
    register_workflow_tools,
)


def create_app(settings: AppSettings | None = None, container: AppContainer | None = None) -> FastMCP:
    resolved_container = container or build_container(settings)
    app = FastMCP(
        name=resolved_container.settings.app_name,
        version=resolved_container.settings.app_version,
        instructions=(
            "Use these tools for safe, typed maintenance operations. "
            "Start a session first, prefer report or workflow tools for known actions, "
            "and use execute_sql only for validated domain-safe SQL."
        ),
    )
    register_system_tools(app, resolved_container)
    register_builder_tools(app, resolved_container)
    register_lifecycle_tools(app, resolved_container)
    register_query_tools(app, resolved_container)
    register_report_tools(app, resolved_container)
    register_routing_tools(app, resolved_container)
    register_schema_tools(app, resolved_container)
    register_agent_tools(app, resolved_container)
    register_workflow_tools(app, resolved_container)
    return app


app = create_app(container=get_container())


def main() -> None:
    settings = get_settings()
    app.run(
        transport=settings.transport,
        host=settings.host,
        port=settings.port,
        path=settings.path,
        stateless_http=settings.stateless_http,
    )
