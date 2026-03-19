from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import ExecuteSQLRequest, SummaryRequest
from tag_fastmcp.tools._enforcement import apply_tool_enforcement


async def _resolved_session_id(request_session_id: str | None, ctx: Context) -> str | None:
    return request_session_id or await ctx.get_state("active_session_id")


def register_query_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def execute_sql(request: ExecuteSQLRequest, ctx: Context) -> dict:
        session_id = await _resolved_session_id(request.session_id, ctx)

        cached = await container.idempotency.load(
            "execute_sql",
            session_id,
            request.idempotency_key,
            request.model_dump(mode="json"),
        )
        if cached is not None:
            cached.setdefault("meta", {})
            cached["meta"]["idempotent_replay"] = True
            return cached

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
        policy = app_ctx.sql_policy.validate(
            request.sql,
            allow_mutations_override=request.allow_mutations,
        )
        if not policy.allowed:
            blocked = container.responses.sql(
                status="blocked",
                message=policy.reason,
                sql=None,
                session_id=session_id,
                trace_id=request.trace_id,
                warnings=["SQL execution blocked by policy."],
                meta={
                    "idempotent_replay": False,
                    "request_context_id": request_context.request_id,
                    "policy_envelope_id": policy_envelope.envelope_id,
                },
            ).model_dump(mode="json")
            await container.idempotency.save(
                "execute_sql",
                session_id,
                request.idempotency_key,
                request.model_dump(mode="json"),
                blocked,
            )
            return blocked

        result = await app_ctx.query_engine.execute_sql(request.sql, policy)
        await container.session_store.set_last_query(session_id, result.query)
        await container.session_store.append_event(
            session_id,
            {
                "type": "sql",
                "query": result.query,
                "row_count": result.row_count,
            },
        )
        response = container.responses.sql(
            status="ok",
            message=f"Executed SQL against {', '.join(result.policy.tables)}.",
            sql=result,
            session_id=session_id,
            trace_id=request.trace_id,
            meta={
                "idempotent_replay": False,
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
            },
        ).model_dump(mode="json")
        await container.idempotency.save(
            "execute_sql",
            session_id,
            request.idempotency_key,
            request.model_dump(mode="json"),
            response,
        )
        return response

    @app.tool
    async def summarize_last_query(request: SummaryRequest, ctx: Context) -> dict:
        session_id = await _resolved_session_id(request.session_id, ctx)
        request_context, policy_envelope = await apply_tool_enforcement(
            container,
            request,
            session_id=session_id,
            allow_platform_tools=True,
        )
        if session_id is None:
            raise ValueError("session_id is required. Start a session first or pass session_id explicitly.")
        app_ctx = container.app_router.resolve(policy_envelope.primary_app_id or request.app_id)
        snapshot = await container.session_store.get(session_id)
        if not snapshot.last_query:
            return container.responses.sql(
                status="error",
                message="No previous query found for this session.",
                sql=None,
                session_id=session_id,
                trace_id=request.trace_id,
                warnings=["Run execute_sql first."],
                meta={
                    "request_context_id": request_context.request_id,
                    "policy_envelope_id": policy_envelope.envelope_id,
                },
            ).model_dump(mode="json")

        policy = app_ctx.sql_policy.validate(snapshot.last_query, allow_mutations_override=False)
        result = await app_ctx.query_engine.execute_sql(snapshot.last_query, policy)
        message = f"Last query returned {result.row_count} rows."
        return container.responses.sql(
            status="ok",
            message=message,
            sql=result,
            session_id=session_id,
            trace_id=request.trace_id,
            meta={
                "request_context_id": request_context.request_id,
                "policy_envelope_id": policy_envelope.envelope_id,
            },
        ).model_dump(mode="json")
