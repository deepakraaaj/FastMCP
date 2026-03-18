from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import InvokeCapabilityRequest


async def _resolved_session_id(request_session_id: str | None, ctx: Context) -> str | None:
    return request_session_id or await ctx.get_state("active_session_id")


def register_routing_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def invoke_capability(request: InvokeCapabilityRequest, ctx: Context) -> dict:
        session_id = await _resolved_session_id(request.session_id, ctx)
        routing = await container.capability_router.invoke(request, session_id=session_id)
        if session_id is not None:
            await ctx.set_state("active_session_id", session_id)

        status = routing.downstream_status or "ok"
        message = routing.output.get("message") if isinstance(routing.output, dict) else None
        return container.responses.routing(
            status=status,
            message=str(message or f"Capability '{routing.selected_capability_id}' executed."),
            routing=routing,
            session_id=session_id,
            trace_id=request.trace_id,
            warnings=routing.warnings,
            meta={
                "selection_mode": routing.selection_mode,
                "selected_capability_id": routing.selected_capability_id,
                "formatter_id": routing.formatter_id,
                "server_id": routing.server_id,
            },
        ).model_dump(mode="json")
