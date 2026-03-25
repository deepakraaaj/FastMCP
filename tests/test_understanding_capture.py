from __future__ import annotations

from types import SimpleNamespace

import pytest

from tag_fastmcp.core.domain_registry import DomainManifest, DomainRegistry, ReportSpec, WorkflowSpec
from tag_fastmcp.core.understanding_capture import UnderstandingCaptureService
from tag_fastmcp.models.schema_models import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableSchema


class _StubSchemaDiscovery:
    def __init__(self, schema: DatabaseSchema) -> None:
        self._schema = schema

    async def discover(self) -> DatabaseSchema:
        return self._schema


class _StubQueryEngine:
    def __init__(self, rows_by_table: dict[str, list[dict[str, object]]]) -> None:
        self._rows_by_table = rows_by_table

    async def sample_rows(self, table_name: str, limit: int = 5) -> list[dict[str, object]]:
        return self._rows_by_table.get(table_name, [])[:limit]


def _fake_app_context() -> SimpleNamespace:
    schema = DatabaseSchema(
        tables={
            "facilities": TableSchema(
                name="facilities",
                columns=[
                    ColumnInfo(name="id", type="INTEGER", nullable=False, primary_key=True),
                    ColumnInfo(name="name", type="TEXT", nullable=False),
                ],
            ),
            "tasks": TableSchema(
                name="tasks",
                columns=[
                    ColumnInfo(name="id", type="INTEGER", nullable=False, primary_key=True),
                    ColumnInfo(name="facility_id", type="INTEGER", nullable=True),
                    ColumnInfo(name="title", type="TEXT", nullable=False),
                    ColumnInfo(name="status", type="TEXT", nullable=True, default="pending"),
                ],
                foreign_keys=[
                    ForeignKeyInfo(
                        constrained_columns=["facility_id"],
                        referred_table="facilities",
                        referred_columns=["id"],
                    )
                ],
            ),
        }
    )
    manifest = DomainManifest(
        name="maintenance",
        description="Maintenance domain with canned reports and guided workflows.",
        allowed_tables=["tasks", "facilities"],
        protected_tables=["schema_migrations"],
        reports={
            "overdue_tasks": ReportSpec(
                description="Show overdue tasks.",
                sql="SELECT * FROM tasks WHERE status = 'overdue'",
            ),
        },
        workflows={
            "create_task": WorkflowSpec(
                description="Create a task.",
                required_fields=["title", "facility_id", "priority"],
            ),
        },
    )
    return SimpleNamespace(
        app_id="maintenance",
        display_name="Maintenance Test",
        domain_registry=DomainRegistry(manifest=manifest, source_label="config:apps.maintenance"),
        schema_discovery=_StubSchemaDiscovery(schema),
        query_engine=_StubQueryEngine(
            {
                "tasks": [
                    {"id": 1, "facility_id": 10, "title": "Inspect motor", "status": "pending"},
                    {"id": 2, "facility_id": 11, "title": "Replace filter", "status": "overdue"},
                ],
                "facilities": [
                    {"id": 10, "name": "Plant Alpha"},
                    {"id": 11, "name": "Plant Beta"},
                ],
            }
        ),
        sql_policy=SimpleNamespace(
            allow_mutations=False,
            require_select_where=True,
        ),
    )


@pytest.mark.asyncio
async def test_understanding_capture_builds_workbook_with_samples_and_questions() -> None:
    app_ctx = _fake_app_context()
    service = UnderstandingCaptureService()

    workbook = await service.build_workbook(
        app_ctx,
        max_tables=5,
        sample_rows_per_table=2,
    )

    assert workbook.app_id == "maintenance"
    assert [sample.table_name for sample in workbook.table_samples] == ["tasks", "facilities"]
    assert any(question.question_id == "app.business_goal" for question in workbook.questions)
    assert any(question.question_id == "table.tasks.purpose" for question in workbook.questions)
    assert any(question.question_id == "table.tasks.status_meaning" for question in workbook.questions)
    assert "## Sample Rows" in workbook.markdown
    assert "Plant Alpha" in workbook.markdown


@pytest.mark.asyncio
async def test_understanding_capture_applies_answers_into_markdown() -> None:
    app_ctx = _fake_app_context()
    service = UnderstandingCaptureService()

    workbook = await service.build_workbook(
        app_ctx,
        max_tables=5,
        sample_rows_per_table=2,
    )
    completed = service.apply_answers(
        workbook,
        {
            "app.business_goal": "Help maintenance teams track and update work orders safely.",
            "table.tasks.purpose": "Stores the maintenance work orders handled by the chatbot.",
        },
    )

    assert completed.answers["app.business_goal"].startswith("Help maintenance teams")
    assert "Answer: Help maintenance teams track and update work orders safely." in completed.markdown
    assert "Answer: Stores the maintenance work orders handled by the chatbot." in completed.markdown
