from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import DomainPayload, SessionPayload


async def _set_active_session(ctx: Context, session_id: str) -> None:
    await ctx.set_state("active_session_id", session_id)


def register_system_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def health_check() -> dict:
        return container.responses.system(
            message="TAG FastMCP is healthy.",
            meta={"environment": container.settings.environment},
        ).model_dump(mode="json")

    @app.tool
    async def start_session(ctx: Context, actor_id: str | None = None, trace_id: str | None = None) -> dict:
        session = container.session_store.start_session(actor_id=actor_id)
        await _set_active_session(ctx, session.session_id)
        response = container.responses.system(
            message="Session started.",
            session=SessionPayload(session_id=session.session_id, actor_id=session.actor_id),
            session_id=session.session_id,
            trace_id=trace_id,
        )
        return response.model_dump(mode="json")

    @app.tool
    async def describe_domain(app_id: str, trace_id: str | None = None) -> dict:
        app_ctx = container.app_router.resolve(app_id)
        manifest = app_ctx.domain_registry.manifest
        response = container.responses.system(
            message=f"Domain '{manifest.name}' is loaded for app '{app_id}'.",
            trace_id=trace_id,
            domain=DomainPayload(
                name=manifest.name,
                description=manifest.description,
                allowed_tables=manifest.allowed_tables,
                reports=sorted(manifest.reports.keys()),
                workflows=sorted(manifest.workflows.keys()),
            ),
        )
        return response.model_dump(mode="json")
