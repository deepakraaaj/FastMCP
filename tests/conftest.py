from __future__ import annotations

from pathlib import Path

import pytest

from tag_fastmcp.app import create_app
from tag_fastmcp.core.container import build_container
from tag_fastmcp.settings import AppSettings


@pytest.fixture
def app_settings(tmp_path: Path) -> AppSettings:
    # Create a mock apps.yaml
    apps_yaml = tmp_path / "apps.yaml"
    manifest_path = Path(__file__).resolve().parents[1] / "domains" / "maintenance.yaml"
    db_path = tmp_path / "test.sqlite3"
    
    with apps_yaml.open("w") as f:
        f.write(f"""
apps:
  maintenance:
    display_name: "Maintenance Test"
    database_url: "sqlite+aiosqlite:///{db_path}"
    manifest: "{manifest_path}"
""")

    return AppSettings(
        apps_config_path=apps_yaml,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        stateless_http=True,
        root_path=tmp_path
    )


@pytest.fixture
async def test_app(app_settings):
    container = build_container(app_settings)
    app = create_app(settings=app_settings, container=container)
    
    # Bootstrap schema for tests since the engine is now domain-agnostic
    from sqlalchemy import text
    app_ctx = container.app_router.resolve("maintenance")
    async with app_ctx.query_engine._engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                facility_id INTEGER,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (facility_id) REFERENCES facilities (id)
            );
        """))
        await conn.execute(text("INSERT INTO facilities (name) VALUES ('Test Facility')"))
        await conn.execute(text("INSERT INTO tasks (title, status) VALUES ('Initial Task', 'pending')"))
    
    return app
