from __future__ import annotations

from fastmcp import FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.builder import BuilderGraph


def register_builder_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def validate_builder_graph(graph: BuilderGraph, app_id: str) -> dict:
        app_ctx = container.app_router.resolve(app_id)
        result = app_ctx.builder_runtime.validate(graph)
        return result.model_dump(mode="json")

    @app.tool
    async def preview_builder_graph(graph: BuilderGraph, app_id: str) -> dict:
        app_ctx = container.app_router.resolve(app_id)
        # Pass the current app instance or host:port
        preview = await app_ctx.builder_runtime.preview(graph, app)
        return preview.model_dump(mode="json")
