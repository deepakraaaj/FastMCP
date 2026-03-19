from __future__ import annotations

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import BaseToolRequest
from tag_fastmcp.tools._enforcement import apply_tool_enforcement


class DiscoverSchemaRequest(BaseToolRequest):
    pass


def register_schema_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def discover_schema(request: DiscoverSchemaRequest) -> dict:
        """Auto-discover the database schema for the given application."""
        request_context, policy_envelope = await apply_tool_enforcement(
            container,
            request,
            session_id=request.session_id,
            allow_platform_tools=True,
        )
        app_ctx = container.app_router.resolve(policy_envelope.primary_app_id or request.app_id)
        schema = await app_ctx.schema_discovery.discover()
        return {
            "app_id": app_ctx.app_id,
            "display_name": app_ctx.display_name,
            "request_context_id": request_context.request_id,
            "policy_envelope_id": policy_envelope.envelope_id,
            "schema": schema.model_dump(),
        }
