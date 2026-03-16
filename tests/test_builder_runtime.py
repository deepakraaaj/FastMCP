from __future__ import annotations

import json
from pathlib import Path

from fastmcp import Client

from tag_fastmcp.models.builder import BuilderGraph


def _load_example(name: str) -> BuilderGraph:
    root = Path(__file__).resolve().parents[1]
    with (root / "builder" / "examples" / name).open("r", encoding="utf-8") as handle:
        return BuilderGraph.model_validate(json.load(handle))


async def test_validate_builder_graph_tool_accepts_report_example(test_app) -> None:
    graph = _load_example("overdue_tasks_report.json")
    async with Client(test_app) as client:
        result = await client.call_tool(
            "validate_builder_graph",
            {"graph": graph.model_dump(mode="json")},
        )
    assert result.structured_content["valid"] is True
    assert result.structured_content["ordered_node_ids"] == ["start-1", "report-1", "respond-1"]


async def test_builder_preview_executes_against_fastmcp(test_app, app_settings) -> None:
    from tag_fastmcp.core.container import build_container

    container = build_container(app_settings)
    graph = _load_example("overdue_tasks_report.json")
    preview = await container.builder_runtime.preview(graph, test_app)
    assert preview.valid is True
    assert preview.steps[1].tool_name == "run_report"
    assert preview.steps[1].output["route"] == "REPORT"
    assert preview.steps[1].output["report"]["report_name"] == "overdue_tasks"


def test_builder_validation_rejects_unknown_report(app_settings) -> None:
    from tag_fastmcp.core.container import build_container

    container = build_container(app_settings)
    graph = BuilderGraph.model_validate(
        {
            "name": "Broken Report Graph",
            "nodes": [
                {"id": "start-1", "type": "start"},
                {"id": "report-1", "type": "run_report", "config": {"report_name": "missing_report"}},
                {"id": "respond-1", "type": "respond", "config": {"message": "done"}},
            ],
            "edges": [
                {"source": "start-1", "target": "report-1"},
                {"source": "report-1", "target": "respond-1"},
            ],
        }
    )
    result = container.builder_runtime.validate(graph)
    assert result.valid is False
    assert any("Unknown report" in issue.message for issue in result.issues)


def test_builder_validation_rejects_blocked_sql(app_settings) -> None:
    from tag_fastmcp.core.container import build_container

    container = build_container(app_settings)
    graph = BuilderGraph.model_validate(
        {
            "name": "Unsafe SQL Graph",
            "nodes": [
                {"id": "start-1", "type": "start"},
                {"id": "query-1", "type": "execute_sql", "config": {"sql": "SELECT * FROM tasks"}},
                {"id": "respond-1", "type": "respond", "config": {"message": "done"}},
            ],
            "edges": [
                {"source": "start-1", "target": "query-1"},
                {"source": "query-1", "target": "respond-1"},
            ],
        }
    )
    result = container.builder_runtime.validate(graph)
    assert result.valid is False
    assert any("SQL blocked" in issue.message for issue in result.issues)
