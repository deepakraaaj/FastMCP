from __future__ import annotations

from fastmcp import FastMCP

from tag_fastmcp.core.container import AppContainer, build_container, get_container
from tag_fastmcp.settings import AppSettings, get_settings
from tag_fastmcp.tools.agent_tools import register_agent_tools
from tag_fastmcp.tools.query_tools import register_query_tools
from tag_fastmcp.tools.report_tools import register_report_tools
from tag_fastmcp.tools.schema_tools import register_schema_tools
from tag_fastmcp.tools.system_tools import register_system_tools
from tag_fastmcp.tools.workflow_tools import register_workflow_tools


def create_app(settings: AppSettings | None = None, container: AppContainer | None = None) -> FastMCP:
    resolved_container = container or build_container(settings)
    enable_platform_features = resolved_container.settings.enable_platform_features
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
    register_query_tools(app, resolved_container)
    register_report_tools(app, resolved_container)
    register_schema_tools(app, resolved_container)
    register_agent_tools(app, resolved_container)
    register_workflow_tools(app, resolved_container)
    if enable_platform_features:
        from tag_fastmcp.tools.builder_tools import register_builder_tools
        from tag_fastmcp.tools.lifecycle_tools import register_lifecycle_tools
        from tag_fastmcp.tools.routing_tools import register_routing_tools

        register_builder_tools(app, resolved_container)
        register_lifecycle_tools(app, resolved_container)
        register_routing_tools(app, resolved_container)
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
