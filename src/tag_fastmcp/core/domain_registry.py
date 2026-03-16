from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ReportSpec(BaseModel):
    description: str
    sql: str


class WorkflowSpec(BaseModel):
    description: str
    required_fields: list[str] = Field(default_factory=list)


class DomainManifest(BaseModel):
    name: str
    description: str
    allowed_tables: list[str] = Field(default_factory=list)
    protected_tables: list[str] = Field(default_factory=list)
    reports: dict[str, ReportSpec] = Field(default_factory=dict)
    workflows: dict[str, WorkflowSpec] = Field(default_factory=dict)


class DomainRegistry:
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> DomainManifest:
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return DomainManifest.model_validate(payload)

    @property
    def manifest(self) -> DomainManifest:
        return self._manifest

    def allowed_tables(self) -> set[str]:
        return {item.lower() for item in self._manifest.allowed_tables}

    def protected_tables(self) -> set[str]:
        return {item.lower() for item in self._manifest.protected_tables}

    def get_report(self, report_name: str) -> ReportSpec:
        try:
            return self._manifest.reports[report_name]
        except KeyError as exc:
            raise KeyError(f"Unknown report '{report_name}'.") from exc

    def get_workflow(self, workflow_id: str) -> WorkflowSpec:
        try:
            return self._manifest.workflows[workflow_id]
        except KeyError as exc:
            raise KeyError(f"Unknown workflow '{workflow_id}'.") from exc
