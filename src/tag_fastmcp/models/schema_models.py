from __future__ import annotations

from datetime import datetime
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


class ColumnUnderstanding(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Any | None = None
    primary_key: bool = False
    semantic_tags: list[str] = Field(default_factory=list)


class RelationshipHint(BaseModel):
    from_table: str
    from_columns: list[str] = Field(default_factory=list)
    to_table: str
    to_columns: list[str] = Field(default_factory=list)
    join_condition: str
    relationship_summary: str


class TableUnderstanding(BaseModel):
    table_name: str
    category: str
    summary: str
    column_count: int
    primary_keys: list[str] = Field(default_factory=list)
    notable_columns: list[str] = Field(default_factory=list)
    related_tables: list[str] = Field(default_factory=list)
    columns: list[ColumnUnderstanding] = Field(default_factory=list)


class UnderstandingDocument(BaseModel):
    app_id: str
    display_name: str
    domain_name: str
    domain_description: str | None = None
    source_label: str
    generated_at: datetime
    allow_mutations: bool = False
    require_select_where: bool = True
    allowed_table_count: int = 0
    protected_tables: list[str] = Field(default_factory=list)
    report_ids: list[str] = Field(default_factory=list)
    workflow_ids: list[str] = Field(default_factory=list)
    overview: str
    table_summaries: list[TableUnderstanding] = Field(default_factory=list)
    relationship_hints: list[RelationshipHint] = Field(default_factory=list)
    safe_query_examples: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    omitted_tables: list[str] = Field(default_factory=list)
    markdown: str


class UnderstandingDocResponse(BaseModel):
    app_id: str
    display_name: str
    request_context_id: str
    policy_envelope_id: str
    agent_id: str
    agent_kind: str
    understanding_doc: UnderstandingDocument


class TableSample(BaseModel):
    table_name: str
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    sample_row_count: int = 0


class UnderstandingInterviewQuestion(BaseModel):
    question_id: str
    prompt: str
    context: str | None = None
    table_name: str | None = None
    sample_values: list[str] = Field(default_factory=list)
    required: bool = False


class UnderstandingWorkbook(BaseModel):
    app_id: str
    display_name: str
    generated_at: datetime
    understanding_doc: UnderstandingDocument
    table_samples: list[TableSample] = Field(default_factory=list)
    questions: list[UnderstandingInterviewQuestion] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)
    markdown: str
