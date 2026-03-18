from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import ContinueWorkflowRequest, StartWorkflowRequest


def register_workflow_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def start_workflow(request: StartWorkflowRequest, ctx: Context) -> dict:
        app_ctx = container.app_router.resolve(request.app_id)
        session_id = request.session_id or await ctx.get_state("active_session_id")
        if session_id is None:
            raise ValueError("session_id is required. Start a session first or pass session_id explicitly.")
        await container.session_store.ensure(session_id, actor_id=request.actor_id)
        await ctx.set_state("active_session_id", session_id)

        result = await app_ctx.workflow_engine.start(session_id, request.workflow_id, request.values)
        message = result.next_prompt if result.state == "pending" else "Workflow collected all required fields."
        return container.responses.workflow(
            message=message,
            workflow=result,
            session_id=session_id,
            trace_id=request.trace_id,
        ).model_dump(mode="json")

    @app.tool
    async def continue_workflow(request: ContinueWorkflowRequest, ctx: Context) -> dict:
        app_ctx = container.app_router.resolve(request.app_id)
        session_id = request.session_id or await ctx.get_state("active_session_id")
        if session_id is None:
            raise ValueError("session_id is required. Start a session first or pass session_id explicitly.")
        await container.session_store.ensure(session_id, actor_id=request.actor_id)
        await ctx.set_state("active_session_id", session_id)

        result = await app_ctx.workflow_engine.continue_workflow(session_id, request.values)
        message = result.next_prompt if result.state == "pending" else "Workflow collected all required fields."
        return container.responses.workflow(
            message=message,
            workflow=result,
            session_id=session_id,
            trace_id=request.trace_id,
        ).model_dump(mode="json")
