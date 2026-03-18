from __future__ import annotations

from fastmcp import FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.builder import BuilderGraph


def _resolve_app_id(container: AppContainer, graph: BuilderGraph, app_id: str | None) -> str:
    if app_id:
        return app_id
    metadata_app_id = str(graph.metadata.get("app_id", "")).strip()
    if metadata_app_id:
        return metadata_app_id
    if len(container.app_router.registry.apps) == 1:
        return next(iter(container.app_router.registry.apps))
    raise ValueError("app_id is required when multiple apps are configured.")


def register_builder_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def validate_builder_graph(graph: BuilderGraph, app_id: str | None = None) -> dict:
        resolved_app_id = _resolve_app_id(container, graph, app_id)
        app_ctx = container.app_router.resolve(resolved_app_id)
        result = app_ctx.builder_runtime.validate(graph)
        return result.model_dump(mode="json")

    @app.tool
    async def preview_builder_graph(graph: BuilderGraph, app_id: str | None = None) -> dict:
        resolved_app_id = _resolve_app_id(container, graph, app_id)
        app_ctx = container.app_router.resolve(resolved_app_id)
        preview = await app_ctx.builder_runtime.preview(graph, app)
        return preview.model_dump(mode="json")
