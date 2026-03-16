from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tag_fastmcp.models.contracts import PolicyDecision, ReportResultPayload, SQLResultPayload


class AsyncQueryEngine:
    def __init__(self, database_url: str, default_row_limit: int) -> None:
        self.database_url = database_url
        self.default_row_limit = default_row_limit
        self._engine = create_async_engine(database_url, pool_pre_ping=True)

    def _ensure_limit(self, sql: str) -> str:
        # Simple string-based limit check to avoid heavy sqlglot dependency in hot path
        # If sqlglot is needed, we should pass the parsed policy expression
        sql_upper = sql.upper()
        if "SELECT" in sql_upper and "LIMIT" not in sql_upper:
            return f"{sql.rstrip(';')} LIMIT {self.default_row_limit}"
        return sql

    async def execute_sql(self, sql: str, policy: PolicyDecision) -> SQLResultPayload:
        executable_sql = self._ensure_limit(policy.normalized_sql or sql)
        async with self._engine.connect() as conn:
            result = await conn.execute(text(executable_sql))
            rows = [dict(row._mapping) for row in result.fetchall()] if result.returns_rows else []
            row_count = len(rows) if result.returns_rows else int(result.rowcount or 0)
            if not result.returns_rows:
                await conn.commit()

        return SQLResultPayload(
            ran=True,
            query=executable_sql,
            row_count=row_count,
            rows_preview=rows,
            policy=policy,
        )

    async def run_report(self, report_name: str, sql: str) -> ReportResultPayload:
        executable_sql = self._ensure_limit(sql)
        async with self._engine.connect() as conn:
            result = await conn.execute(text(executable_sql))
            rows = [dict(row._mapping) for row in result.fetchall()] if result.returns_rows else []

        return ReportResultPayload(
            report_name=report_name,
            query=executable_sql,
            row_count=len(rows),
            rows_preview=rows,
        )

    async def close(self) -> None:
        await self._engine.dispose()
