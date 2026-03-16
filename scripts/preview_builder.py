from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from tag_fastmcp.app import create_app
from tag_fastmcp.core.container import build_container
from tag_fastmcp.models.builder import BuilderGraph
from tag_fastmcp.settings import get_settings


async def _main(graph_path: Path) -> int:
    settings = get_settings()
    container = build_container(settings)
    app = create_app(settings=settings, container=container)

    with graph_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    graph = BuilderGraph.model_validate(payload)
    preview = await container.builder_runtime.preview(graph, app)
    print(json.dumps(preview.model_dump(mode="json"), indent=2))
    return 0 if preview.valid else 1


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/preview_builder.py <graph.json>")
        return 2
    return asyncio.run(_main(Path(sys.argv[1]).resolve()))


if __name__ == "__main__":
    raise SystemExit(main())
