from __future__ import annotations

from typing import Any

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from tag_fastmcp.core.database_urls import normalize_database_url
from tag_fastmcp.models.schema_models import (
    ColumnInfo,
    DatabaseSchema,
    ForeignKeyInfo,
    TableSchema,
)


class SchemaDiscovery:
    """Introspects any database and returns its structure using SQLAlchemy."""

    def __init__(self, database_url: str):
        self._engine = create_async_engine(normalize_database_url(database_url))

    async def discover(self) -> DatabaseSchema:
        """Returns all tables, columns, types, PKs, FKs."""
        # Note: SQLAlchemy inspection is usually synchronous, but we can run it 
        # in a thread pool using the engine's sync connection.
        def _inspect(conn):
            inspector = inspect(conn)
            tables = {}
            for table_name in inspector.get_table_names():
                columns = [
                    ColumnInfo(
                        name=col["name"],
                        type=str(col["type"]),
                        nullable=col["nullable"],
                        default=col.get("default"),
                        primary_key=col.get("primary_key", False) or col["name"] in inspector.get_pk_constraint(table_name)["constrained_columns"],
                    )
                    for col in inspector.get_columns(table_name)
                ]
                fks = [
                    ForeignKeyInfo(
                        constrained_columns=fk["constrained_columns"],
                        referred_table=fk["referred_table"],
                        referred_columns=fk["referred_columns"],
                    )
                    for fk in inspector.get_foreign_keys(table_name)
                ]
                tables[table_name] = TableSchema(
                    name=table_name,
                    columns=columns,
                    foreign_keys=fks,
                )
            return DatabaseSchema(tables=tables)

        async with self._engine.connect() as conn:
            return await conn.run_sync(_inspect)

    async def get_sample_data(self, table_name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Returns sample rows from a table."""
        from sqlalchemy import text
        async with self._engine.connect() as conn:
            result = await conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}"))
            return [dict(row._mapping) for row in result.fetchall()]

    async def close(self):
        await self._engine.dispose()
