from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from tag_fastmcp.models.schema_models import (
    ColumnUnderstanding,
    RelationshipHint,
    TableUnderstanding,
    UnderstandingDocument,
)

if TYPE_CHECKING:
    from tag_fastmcp.core.app_router import AppContext
    from tag_fastmcp.models.schema_models import ColumnInfo, DatabaseSchema, TableSchema


@dataclass
class SchemaIntelligenceAgent:
    max_notable_columns: int = 8

    async def generate_understanding_doc(
        self,
        app_ctx: AppContext,
        *,
        max_tables: int = 12,
    ) -> UnderstandingDocument:
        schema = await app_ctx.schema_discovery.discover()
        manifest = app_ctx.domain_registry.manifest
        allowed_tables = [name for name in manifest.allowed_tables if name in schema.tables]
        protected_tables = set(manifest.protected_tables)
        relationship_hints = self._relationship_hints(schema, allowed_tables)
        relationship_counts = self._relationship_counts(relationship_hints)
        ranked_tables = sorted(
            allowed_tables,
            key=lambda name: (
                -self._table_priority(name, schema, relationship_counts, protected_tables),
                name,
            ),
        )
        selected_tables = ranked_tables[:max_tables]
        omitted_tables = ranked_tables[max_tables:]
        table_summaries = [
            self._table_summary(
                schema.tables[table_name],
                relationship_hints,
                protected=table_name in protected_tables,
            )
            for table_name in selected_tables
        ]
        report_ids = sorted(manifest.reports.keys())
        workflow_ids = sorted(manifest.workflows.keys())
        safe_query_examples = self._safe_query_examples(table_summaries, report_ids, workflow_ids)
        suggested_questions = self._suggested_questions(table_summaries, report_ids, workflow_ids)
        overview = self._overview(
            app_ctx=app_ctx,
            allowed_table_count=len(allowed_tables),
            protected_tables=sorted(protected_tables),
            relationship_hints=relationship_hints,
            report_ids=report_ids,
            workflow_ids=workflow_ids,
            omitted_count=len(omitted_tables),
        )
        markdown = self._markdown(
            app_ctx=app_ctx,
            overview=overview,
            table_summaries=table_summaries,
            relationship_hints=relationship_hints,
            safe_query_examples=safe_query_examples,
            suggested_questions=suggested_questions,
            report_ids=report_ids,
            workflow_ids=workflow_ids,
            protected_tables=sorted(protected_tables),
            omitted_tables=omitted_tables,
        )
        return UnderstandingDocument(
            app_id=app_ctx.app_id,
            display_name=app_ctx.display_name,
            domain_name=manifest.name,
            domain_description=manifest.description,
            source_label=app_ctx.domain_registry.source_label,
            generated_at=datetime.now(UTC),
            allow_mutations=app_ctx.sql_policy.allow_mutations,
            require_select_where=app_ctx.sql_policy.require_select_where,
            allowed_table_count=len(allowed_tables),
            protected_tables=sorted(protected_tables),
            report_ids=report_ids,
            workflow_ids=workflow_ids,
            overview=overview,
            table_summaries=table_summaries,
            relationship_hints=relationship_hints,
            safe_query_examples=safe_query_examples,
            suggested_questions=suggested_questions,
            omitted_tables=omitted_tables,
            markdown=markdown,
        )

    @staticmethod
    def _relationship_hints(schema: DatabaseSchema, allowed_tables: list[str]) -> list[RelationshipHint]:
        allowed = set(allowed_tables)
        hints: list[RelationshipHint] = []
        for table_name in allowed_tables:
            table = schema.tables[table_name]
            for fk in table.foreign_keys:
                if fk.referred_table not in allowed:
                    continue
                join_pairs = [
                    f"{table_name}.{source} = {fk.referred_table}.{target}"
                    for source, target in zip(fk.constrained_columns, fk.referred_columns)
                ]
                join_condition = " AND ".join(join_pairs)
                hints.append(
                    RelationshipHint(
                        from_table=table_name,
                        from_columns=list(fk.constrained_columns),
                        to_table=fk.referred_table,
                        to_columns=list(fk.referred_columns),
                        join_condition=join_condition,
                        relationship_summary=(
                            f"{SchemaIntelligenceAgent._humanize(table_name)} references "
                            f"{SchemaIntelligenceAgent._humanize(fk.referred_table)}."
                        ),
                    )
                )
        return sorted(
            hints,
            key=lambda item: (item.from_table, item.to_table, item.join_condition),
        )

    @staticmethod
    def _relationship_counts(relationship_hints: list[RelationshipHint]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for hint in relationship_hints:
            counts[hint.from_table] = counts.get(hint.from_table, 0) + 1
            counts[hint.to_table] = counts.get(hint.to_table, 0) + 1
        return counts

    def _table_summary(
        self,
        table: TableSchema,
        relationship_hints: list[RelationshipHint],
        *,
        protected: bool,
    ) -> TableUnderstanding:
        relevant_hints = [
            hint
            for hint in relationship_hints
            if hint.from_table == table.name or hint.to_table == table.name
        ]
        related_tables = sorted(
            {
                hint.to_table if hint.from_table == table.name else hint.from_table
                for hint in relevant_hints
            }
        )
        primary_keys = [column.name for column in table.columns if column.primary_key]
        column_map = {column.name: column for column in table.columns}
        fk_columns = {
            column_name
            for hint in relevant_hints
            if hint.from_table == table.name
            for column_name in hint.from_columns
        }
        columns = [
            self._column_understanding(column, foreign_key=column.name in fk_columns)
            for column in table.columns
        ]
        notable_columns = [
            column.name
            for column in table.columns
            if column.name not in primary_keys
        ][: self.max_notable_columns]
        if not notable_columns:
            notable_columns = [column.name for column in table.columns[: self.max_notable_columns]]
        return TableUnderstanding(
            table_name=table.name,
            category=self._table_category(table.name),
            summary=self._table_summary_text(
                table.name,
                column_map=column_map,
                relationship_count=len(relevant_hints),
                protected=protected,
            ),
            column_count=len(table.columns),
            primary_keys=primary_keys,
            notable_columns=notable_columns,
            related_tables=related_tables,
            columns=columns,
        )

    @staticmethod
    def _column_understanding(column: ColumnInfo, *, foreign_key: bool) -> ColumnUnderstanding:
        tags: list[str] = []
        name_lower = column.name.lower()
        if column.primary_key:
            tags.append("primary_key")
        if foreign_key:
            tags.append("foreign_key")
        if name_lower.endswith("_id") and "foreign_key" not in tags:
            tags.append("identifier")
        if any(token in name_lower for token in {"name", "title", "description"}):
            tags.append("label")
        if any(token in name_lower for token in {"status", "state"}):
            tags.append("status")
        if any(token in name_lower for token in {"created", "updated", "date", "time"}):
            tags.append("timestamp")
        if column.nullable:
            tags.append("optional")
        return ColumnUnderstanding(
            name=column.name,
            type=column.type,
            nullable=column.nullable,
            default=column.default,
            primary_key=column.primary_key,
            semantic_tags=tags,
        )

    @staticmethod
    def _table_category(table_name: str) -> str:
        value = table_name.lower()
        if "log" in value or "history" in value or "audit" in value:
            return "audit"
        if "mapping" in value or value.endswith("_map"):
            return "association"
        if any(value.endswith(suffix) for suffix in ("_type", "_category", "_state", "_status", "_master")):
            return "reference"
        if any(token in value for token in {"user", "role", "privilege", "permission"}):
            return "access_control"
        if any(token in value for token in {"task", "order", "transaction", "detail"}):
            return "operational"
        return "domain"

    @staticmethod
    def _table_summary_text(
        table_name: str,
        *,
        column_map: dict[str, ColumnInfo],
        relationship_count: int,
        protected: bool,
    ) -> str:
        human_name = SchemaIntelligenceAgent._humanize(table_name)
        category = SchemaIntelligenceAgent._table_category(table_name)
        if category == "association":
            summary = f"Association table linking records around {human_name}."
        elif category == "audit":
            summary = f"Audit or history table capturing changes and events for {human_name}."
        elif category == "reference":
            summary = f"Reference table defining reusable {human_name} values."
        elif category == "access_control":
            summary = f"Access-control table managing {human_name} records."
        elif relationship_count >= 2:
            summary = f"Operational hub table coordinating {human_name} data with neighboring entities."
        else:
            summary = f"Primary domain table for {human_name} records."

        if "status" in column_map or "state" in column_map:
            summary += " Includes lifecycle/status tracking."
        if "created_at" in column_map or "updated_at" in column_map:
            summary += " Includes change timestamps."
        if protected:
            summary += " Marked as protected by policy."
        return summary

    @staticmethod
    def _table_priority(
        table_name: str,
        schema: DatabaseSchema,
        relationship_counts: dict[str, int],
        protected_tables: set[str],
    ) -> int:
        name = table_name.lower()
        score = relationship_counts.get(table_name, 0) * 3 + len(schema.tables[table_name].columns)
        if table_name in protected_tables:
            score -= 5
        if any(token in name for token in {"log", "history", "audit", "schema"}):
            score -= 4
        if any(token in name for token in {"task", "order", "transaction", "facility", "product", "user"}):
            score += 3
        if "mapping" in name:
            score -= 1
        return score

    def _safe_query_examples(
        self,
        table_summaries: list[TableUnderstanding],
        report_ids: list[str],
        workflow_ids: list[str],
    ) -> list[str]:
        examples: list[str] = []
        for report_id in report_ids[:3]:
            examples.append(f"Prefer the configured report '{report_id}' when you need a repeatable read workflow.")
        for workflow_id in workflow_ids[:3]:
            examples.append(f"Use the configured workflow '{workflow_id}' for guided write collection instead of ad hoc mutations.")
        for table in table_summaries[:3]:
            if any("status" in column.name.lower() for column in table.columns):
                examples.append(f"Filter '{table.table_name}' by status/state fields and keep reads app-scoped.")
                continue
            if table.primary_keys:
                examples.append(f"Start '{table.table_name}' reads from the primary key {', '.join(table.primary_keys)} when possible.")
            else:
                examples.append(f"Use selective filters when reading '{table.table_name}' because broad scans are guarded.")
        return examples[:6]

    def _suggested_questions(
        self,
        table_summaries: list[TableUnderstanding],
        report_ids: list[str],
        workflow_ids: list[str],
    ) -> list[str]:
        suggestions: list[str] = []
        for report_id in report_ids[:2]:
            suggestions.append(f"Run the '{report_id}' report for this app.")
        for workflow_id in workflow_ids[:2]:
            suggestions.append(f"Start the '{workflow_id}' workflow for this app.")
        for table in table_summaries[:3]:
            suggestions.append(f"What does the '{table.table_name}' table represent in {table.table_name.replace('_', ' ')} operations?")
        return suggestions[:6]

    @staticmethod
    def _overview(
        *,
        app_ctx: AppContext,
        allowed_table_count: int,
        protected_tables: list[str],
        relationship_hints: list[RelationshipHint],
        report_ids: list[str],
        workflow_ids: list[str],
        omitted_count: int,
    ) -> str:
        manifest = app_ctx.domain_registry.manifest
        relationship_phrase = (
            f"{len(relationship_hints)} table relationships are visible inside the allowed scope."
            if relationship_hints
            else "No foreign-key relationships were detected inside the allowed scope."
        )
        report_phrase = (
            f"Configured reports: {', '.join(report_ids)}."
            if report_ids
            else "No configured reports are available yet."
        )
        workflow_phrase = (
            f"Configured workflows: {', '.join(workflow_ids)}."
            if workflow_ids
            else "No configured workflows are available yet."
        )
        mutation_phrase = (
            "Mutations are currently allowed under the app SQL policy."
            if app_ctx.sql_policy.allow_mutations
            else "Mutations are currently disabled under the app SQL policy."
        )
        select_phrase = (
            "Read queries are expected to include WHERE filters."
            if app_ctx.sql_policy.require_select_where
            else "Read queries may run without a WHERE filter."
        )
        omitted_phrase = (
            f" The document summarizes the top {allowed_table_count - omitted_count} tables and omits {omitted_count} lower-priority tables for brevity."
            if omitted_count
            else ""
        )
        protected_phrase = (
            f"Protected tables: {', '.join(protected_tables)}."
            if protected_tables
            else "No protected tables are configured."
        )
        description = manifest.description or f"Configured domain contract for {app_ctx.display_name}."
        return (
            f"{app_ctx.display_name} is mapped to domain '{manifest.name}'. {description} "
            f"The current app contract allows {allowed_table_count} tables. {relationship_phrase} "
            f"{report_phrase} {workflow_phrase} {mutation_phrase} {select_phrase} {protected_phrase}{omitted_phrase}"
        ).strip()

    def _markdown(
        self,
        *,
        app_ctx: AppContext,
        overview: str,
        table_summaries: list[TableUnderstanding],
        relationship_hints: list[RelationshipHint],
        safe_query_examples: list[str],
        suggested_questions: list[str],
        report_ids: list[str],
        workflow_ids: list[str],
        protected_tables: list[str],
        omitted_tables: list[str],
    ) -> str:
        report_lines = [f"- {report_id}" for report_id in report_ids] or ["- none"]
        workflow_lines = [f"- {workflow_id}" for workflow_id in workflow_ids] or ["- none"]
        lines = [
            f"# {app_ctx.display_name} Understanding Document",
            "",
            "## Overview",
            overview,
            "",
            "## Runtime Guardrails",
            f"- allow_mutations: {str(app_ctx.sql_policy.allow_mutations).lower()}",
            f"- require_select_where: {str(app_ctx.sql_policy.require_select_where).lower()}",
            f"- protected_tables: {', '.join(protected_tables) if protected_tables else 'none'}",
            "",
            "## Reports",
        ]
        lines.extend(report_lines)
        lines.extend(["", "## Workflows"])
        lines.extend(workflow_lines)
        lines.extend(["", "## Relationship Hints"])
        if relationship_hints:
            lines.extend(f"- {hint.join_condition}" for hint in relationship_hints)
        else:
            lines.append("- none")

        lines.extend(["", "## Tables"])
        for table in table_summaries:
            lines.extend(
                [
                    f"### {table.table_name}",
                    f"- category: {table.category}",
                    f"- summary: {table.summary}",
                    f"- primary_keys: {', '.join(table.primary_keys) if table.primary_keys else 'none'}",
                    f"- notable_columns: {', '.join(table.notable_columns) if table.notable_columns else 'none'}",
                    f"- related_tables: {', '.join(table.related_tables) if table.related_tables else 'none'}",
                ]
            )

        lines.extend(["", "## Safe Query Examples"])
        if safe_query_examples:
            lines.extend(f"- {item}" for item in safe_query_examples)
        else:
            lines.append("- none")
        lines.extend(["", "## Suggested Questions"])
        if suggested_questions:
            lines.extend(f"- {item}" for item in suggested_questions)
        else:
            lines.append("- none")
        if omitted_tables:
            lines.extend(["", "## Omitted Tables", f"- {', '.join(omitted_tables)}"])
        return "\n".join(lines)

    @staticmethod
    def _humanize(value: str) -> str:
        return value.replace("_", " ").strip()
