from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import ContinueWorkflowRequest, StartWorkflowRequest
from tag_fastmcp.tools._enforcement import apply_tool_enforcement


def register_workflow_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def start_workflow(request: StartWorkflowRequest, ctx: Context) -> dict:
        session_id = request.session_id or await ctx.get_state("active_session_id")
        request_context, policy_envelope = await apply_tool_enforcement(
            container,
            request,
            session_id=session_id,
            allow_platform_tools=True,
        )
        if session_id is None:
            raise ValueError("session_id is required. Start a session first or pass session_id explicitly.")
        await ctx.set_state("active_session_id", session_id)

        app_ctx = container.app_router.resolve(policy_envelope.primary_app_id or request.app_id)
        result = await app_ctx.workflow_engine.start(session_id, request.workflow_id, request.values)
        message = result.next_prompt if result.state == "pending" else "Workflow collected all required fields."
        return container.responses.workflow(
            message=message,
            workflow=result,
            session_id=session_id,
            trace_id=request.trace_id,
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
            },
        ).model_dump(mode="json")

    @app.tool
    async def continue_workflow(request: ContinueWorkflowRequest, ctx: Context) -> dict:
        session_id = request.session_id or await ctx.get_state("active_session_id")
        request_context, policy_envelope = await apply_tool_enforcement(
            container,
            request,
            session_id=session_id,
            allow_platform_tools=True,
        )
        if session_id is None:
            raise ValueError("session_id is required. Start a session first or pass session_id explicitly.")
        await ctx.set_state("active_session_id", session_id)

        app_ctx = container.app_router.resolve(policy_envelope.primary_app_id or request.app_id)
        result = await app_ctx.workflow_engine.continue_workflow(session_id, request.values)
        message = result.next_prompt if result.state == "pending" else "Workflow collected all required fields."
        return container.responses.workflow(
            message=message,
            workflow=result,
            session_id=session_id,
            trace_id=request.trace_id,
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
            },
        ).model_dump(mode="json")
