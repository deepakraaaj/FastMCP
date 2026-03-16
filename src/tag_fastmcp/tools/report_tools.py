from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import RunReportRequest


def register_report_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def run_report(request: RunReportRequest, ctx: Context) -> dict:
        app_ctx = container.app_router.resolve(request.app_id)
        session_id = request.session_id or await ctx.get_state("active_session_id")
        if session_id is None:
            raise ValueError("session_id is required. Start a session first or pass session_id explicitly.")
        container.session_store.ensure(session_id, actor_id=request.actor_id)
        await ctx.set_state("active_session_id", session_id)

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
            ).model_dump(mode="json")

        result = await app_ctx.query_engine.run_report(request.report_name, report.sql)
        container.session_store.append_event(
            session_id,
            {"type": "report", "report_name": request.report_name, "row_count": result.row_count},
        )
        return container.responses.report(
            message=f"Report '{request.report_name}' executed.",
            report=result,
            session_id=session_id,
            trace_id=request.trace_id,
        ).model_dump(mode="json")
