from __future__ import annotations

from typing import Iterable

import sqlglot
from sqlglot import exp

from tag_fastmcp.models.contracts import PolicyDecision


class SQLPolicyValidator:
    def __init__(
        self,
        *,
        allowed_tables: set[str],
        protected_tables: set[str],
        allow_mutations: bool = False,
        require_select_where: bool = True,
    ) -> None:
        self.allowed_tables = {value.lower() for value in allowed_tables}
        self.protected_tables = {value.lower() for value in protected_tables}
        self.allow_mutations = allow_mutations
        self.require_select_where = require_select_where
        self.forbidden_commands = {exp.Drop, exp.Delete, exp.Alter, exp.Create}
        self.allowed_top_level = (exp.Select, exp.Insert, exp.Update)

    @staticmethod
    def _extract_table_names(parsed: exp.Expression) -> list[str]:
        return [str(table.name or "").strip().lower() for table in parsed.find_all(exp.Table)]

    @staticmethod
    def _has_where(parsed: exp.Expression) -> bool:
        return parsed.args.get("where") is not None

    @staticmethod
    def _normalize_sql(parsed: exp.Expression) -> str:
        return parsed.sql(pretty=False)

    @staticmethod
    def _dedupe(values: Iterable[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result

    def validate(self, sql: str, *, allow_mutations_override: bool | None = None) -> PolicyDecision:
        try:
            parsed = sqlglot.parse_one(sql)
        except Exception as exc:
            return PolicyDecision(allowed=False, reason=f"SQL parse failed: {exc}")

        if type(parsed) in self.forbidden_commands:
            return PolicyDecision(allowed=False, reason=f"Forbidden SQL command detected: {type(parsed).__name__}")

        if not isinstance(parsed, self.allowed_top_level):
            return PolicyDecision(allowed=False, reason=f"Unsupported statement type: {type(parsed).__name__}")

        for node in parsed.walk():
            if type(node) in self.forbidden_commands:
                return PolicyDecision(allowed=False, reason=f"Forbidden SQL command detected: {type(node).__name__}")

        allow_mutations = self.allow_mutations
        if allow_mutations_override is not None:
            allow_mutations = allow_mutations and bool(allow_mutations_override)
        if isinstance(parsed, (exp.Insert, exp.Update)) and not allow_mutations:
            return PolicyDecision(allowed=False, reason="Mutations are disabled by policy.")

        if isinstance(parsed, exp.Select) and self.require_select_where and not self._has_where(parsed):
            return PolicyDecision(allowed=False, reason="Unfiltered SELECT is blocked by policy.")

        if isinstance(parsed, exp.Update) and not self._has_where(parsed):
            return PolicyDecision(allowed=False, reason="UPDATE without WHERE is blocked by policy.")

        tables = self._dedupe(self._extract_table_names(parsed))
        if not tables:
            return PolicyDecision(allowed=False, reason="No table references detected.")

        for table in tables:
            if table in self.protected_tables:
                return PolicyDecision(allowed=False, reason=f"Protected table blocked: {table}", tables=tables)
            if self.allowed_tables and table not in self.allowed_tables:
                return PolicyDecision(allowed=False, reason=f"Table not allowed by domain policy: {table}", tables=tables)

        return PolicyDecision(
            allowed=True,
            reason="SQL allowed.",
            tables=tables,
            normalized_sql=self._normalize_sql(parsed),
        )
