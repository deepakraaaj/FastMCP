from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Any | None = None
    primary_key: bool = False


class ForeignKeyInfo(BaseModel):
    constrained_columns: list[str]
    referred_table: str
    referred_columns: list[str]


class TableSchema(BaseModel):
    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list)


class DatabaseSchema(BaseModel):
    tables: dict[str, TableSchema]
