from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tag_fastmcp.agent.schema_intelligence_agent import SchemaIntelligenceAgent
from tag_fastmcp.models.schema_models import (
    TableSample,
    UnderstandingInterviewQuestion,
    UnderstandingWorkbook,
)

if TYPE_CHECKING:
    from tag_fastmcp.core.app_router import AppContext
    from tag_fastmcp.models.schema_models import TableUnderstanding, UnderstandingDocument


@dataclass
class UnderstandingCaptureService:
    schema_agent: SchemaIntelligenceAgent = field(default_factory=SchemaIntelligenceAgent)

    async def build_workbook(
        self,
        app_ctx: AppContext,
        *,
        max_tables: int = 8,
        sample_rows_per_table: int = 3,
    ) -> UnderstandingWorkbook:
        understanding_doc = await self.schema_agent.generate_understanding_doc(
            app_ctx,
            max_tables=max_tables,
        )
        table_samples = await self._table_samples(
            app_ctx,
            understanding_doc.table_summaries,
            sample_rows_per_table=sample_rows_per_table,
        )
        questions = self._questions(understanding_doc, table_samples)
        markdown = self._markdown(
            understanding_doc=understanding_doc,
            table_samples=table_samples,
            questions=questions,
            answers={},
        )
        return UnderstandingWorkbook(
            app_id=app_ctx.app_id,
            display_name=app_ctx.display_name,
            generated_at=datetime.now(UTC),
            understanding_doc=understanding_doc,
            table_samples=table_samples,
            questions=questions,
            answers={},
            markdown=markdown,
        )

    def apply_answers(
        self,
        workbook: UnderstandingWorkbook,
        answers: dict[str, str],
    ) -> UnderstandingWorkbook:
        normalized_answers = {
            key: value.strip()
            for key, value in answers.items()
            if value is not None and value.strip()
        }
        markdown = self._markdown(
            understanding_doc=workbook.understanding_doc,
            table_samples=workbook.table_samples,
            questions=workbook.questions,
            answers=normalized_answers,
        )
        return workbook.model_copy(
            update={
                "answers": normalized_answers,
                "markdown": markdown,
            }
        )

    async def _table_samples(
        self,
        app_ctx: AppContext,
        table_summaries: list[TableUnderstanding],
        *,
        sample_rows_per_table: int,
    ) -> list[TableSample]:
        allowed_tables = app_ctx.domain_registry.allowed_tables()
        samples: list[TableSample] = []
        for table in table_summaries:
            if table.table_name.lower() not in allowed_tables:
                continue
            rows = await app_ctx.query_engine.sample_rows(
                table.table_name,
                limit=sample_rows_per_table,
            )
            samples.append(
                TableSample(
                    table_name=table.table_name,
                    sample_rows=self._normalize_rows(rows),
                    sample_row_count=len(rows),
                )
            )
        return samples

    @staticmethod
    def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            normalized_row: dict[str, Any] = {}
            for key, value in row.items():
                if value is None or isinstance(value, (int, float, bool)):
                    normalized_row[key] = value
                else:
                    text = str(value)
                    normalized_row[key] = text if len(text) <= 120 else f"{text[:117]}..."
            normalized.append(normalized_row)
        return normalized

    def _questions(
        self,
        understanding_doc: UnderstandingDocument,
        table_samples: list[TableSample],
    ) -> list[UnderstandingInterviewQuestion]:
        samples_by_table = {sample.table_name: sample for sample in table_samples}
        questions: list[UnderstandingInterviewQuestion] = [
            UnderstandingInterviewQuestion(
                question_id="app.business_goal",
                prompt=(
                    f"What is the main business goal of {understanding_doc.display_name}, "
                    "and what should the chatbot help users do most often?"
                ),
                context=understanding_doc.overview,
                required=True,
            ),
            UnderstandingInterviewQuestion(
                question_id="app.user_intents",
                prompt="What are the top user questions or actions this app chatbot must support?",
                sample_values=understanding_doc.suggested_questions[:5],
                required=True,
            ),
            UnderstandingInterviewQuestion(
                question_id="app.write_rules",
                prompt=(
                    "Which inserts or updates are actually safe in this app, and which tables or fields "
                    "must stay read-only even if the schema allows writes?"
                ),
                context=(
                    f"allow_mutations={str(understanding_doc.allow_mutations).lower()}, "
                    f"protected_tables={', '.join(understanding_doc.protected_tables) or 'none'}"
                ),
                required=True,
            ),
        ]

        for table in understanding_doc.table_summaries:
            sample = samples_by_table.get(table.table_name)
            questions.append(
                UnderstandingInterviewQuestion(
                    question_id=f"table.{table.table_name}.purpose",
                    prompt=f"What business concept or process does the '{table.table_name}' table represent?",
                    table_name=table.table_name,
                    context=table.summary,
                    sample_values=self._sample_value_hints(sample),
                    required=True,
                )
            )
            if any("status" in column.semantic_tags for column in table.columns):
                questions.append(
                    UnderstandingInterviewQuestion(
                        question_id=f"table.{table.table_name}.status_meaning",
                        prompt=(
                            f"What do the status/state values in '{table.table_name}' mean in business terms?"
                        ),
                        table_name=table.table_name,
                        sample_values=self._column_value_hints(sample, {"status", "state"}),
                    )
                )
            if table.related_tables:
                questions.append(
                    UnderstandingInterviewQuestion(
                        question_id=f"table.{table.table_name}.relationships",
                        prompt=(
                            f"How should the chatbot describe or use the relationship between "
                            f"'{table.table_name}' and {', '.join(table.related_tables)}?"
                        ),
                        table_name=table.table_name,
                        context=(
                            "Detected related tables: "
                            f"{', '.join(table.related_tables)}"
                        ),
                    )
                )

        return questions

    @staticmethod
    def _sample_value_hints(sample: TableSample | None) -> list[str]:
        if sample is None:
            return []
        hints: list[str] = []
        for row in sample.sample_rows[:2]:
            parts = [f"{key}={value}" for key, value in list(row.items())[:3]]
            if parts:
                hints.append(", ".join(parts))
        return hints

    @staticmethod
    def _column_value_hints(sample: TableSample | None, tokens: set[str]) -> list[str]:
        if sample is None:
            return []
        hints: list[str] = []
        for row in sample.sample_rows:
            for key, value in row.items():
                if any(token in key.lower() for token in tokens) and value is not None:
                    hints.append(f"{key}={value}")
        return sorted(set(hints))[:5]

    def _markdown(
        self,
        *,
        understanding_doc: UnderstandingDocument,
        table_samples: list[TableSample],
        questions: list[UnderstandingInterviewQuestion],
        answers: dict[str, str],
    ) -> str:
        lines = [
            f"# {understanding_doc.display_name} Understanding Workbook",
            "",
            "## Generated Understanding",
            understanding_doc.markdown,
            "",
            "## Sample Rows",
        ]
        if table_samples:
            for sample in table_samples:
                lines.extend(
                    [
                        f"### {sample.table_name}",
                        f"- sample_row_count: {sample.sample_row_count}",
                    ]
                )
                if sample.sample_rows:
                    for row in sample.sample_rows:
                        lines.append(f"- {row}")
                else:
                    lines.append("- no sample rows returned")
        else:
            lines.append("- no sample rows collected")

        lines.extend(["", "## Interview Questions"])
        for question in questions:
            lines.append(f"### {question.question_id}")
            lines.append(question.prompt)
            if question.context:
                lines.append(f"Context: {question.context}")
            if question.sample_values:
                lines.append(f"Sample hints: {', '.join(question.sample_values)}")
            answer = answers.get(question.question_id)
            lines.append(f"Answer: {answer if answer else '[pending]'}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"
