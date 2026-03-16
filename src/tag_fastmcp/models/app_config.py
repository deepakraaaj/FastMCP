from __future__ import annotations

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    display_name: str
    database_url: str
    manifest: str


class AppsRegistry(BaseModel):
    apps: dict[str, AppConfig] = Field(default_factory=dict)
