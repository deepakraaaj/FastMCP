from __future__ import annotations

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import BaseToolRequest


class DiscoverSchemaRequest(BaseToolRequest):
    pass


def register_schema_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def discover_schema(request: DiscoverSchemaRequest) -> dict:
        """Auto-discover the database schema for the given application."""
        app_ctx = container.app_router.resolve(request.app_id)
        schema = await app_ctx.schema_discovery.discover()
        return {
            "app_id": request.app_id,
            "display_name": app_ctx.display_name,
            "schema": schema.model_dump(),
        }
