from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import RunReportRequest
from tag_fastmcp.tools._enforcement import apply_tool_enforcement


def register_report_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def run_report(request: RunReportRequest, ctx: Context) -> dict:
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
        report = app_ctx.domain_registry.get_report(request.report_name)
        policy = app_ctx.sql_policy.validate(report.sql, allow_mutations_override=False)
        if not policy.allowed:
            return container.responses.sql(
                status="blocked",
                message=policy.reason,
                sql=None,
                session_id=session_id,
                trace_id=request.trace_id,
                warnings=["Report SQL blocked by policy."],
                meta={
                    "request_context_id": request_context.request_id,
                    "policy_envelope_id": policy_envelope.envelope_id,
                },
            ).model_dump(mode="json")

        result = await app_ctx.query_engine.run_report(request.report_name, report.sql)
        await container.session_store.append_event(
            session_id,
            {"type": "report", "report_name": request.report_name, "row_count": result.row_count},
        )
        return container.responses.report(
            message=f"Report '{request.report_name}' executed.",
            report=result,
            session_id=session_id,
            trace_id=request.trace_id,
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
            },
        ).model_dump(mode="json")
