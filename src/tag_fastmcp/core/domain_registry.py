from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from tag_fastmcp.models.app_config import AppConfig


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
    def __init__(
        self,
        manifest_path: Path | None = None,
        *,
        manifest: DomainManifest | None = None,
        source_label: str | None = None,
    ):
        if manifest_path is None and manifest is None:
            raise ValueError("DomainRegistry requires a manifest path or inline manifest payload.")
        self.manifest_path = manifest_path
        self.source_label = source_label or (str(manifest_path) if manifest_path is not None else "config:inline")
        self._manifest = manifest or self._load_manifest()

    @classmethod
    def from_app_config(cls, app_id: str, config: AppConfig, *, root_path: Path) -> DomainRegistry:
        if config.manifest:
            manifest_path = Path(config.manifest)
            if not manifest_path.is_absolute():
                manifest_path = root_path / manifest_path
            return cls(manifest_path, source_label=str(manifest_path))

        if not config.allowed_tables:
            raise ValueError(
                f"App '{app_id}' must define either a manifest path or inline allowed_tables in apps config."
            )

        manifest = DomainManifest(
            name=config.name or app_id,
            description=config.description or f"{config.display_name} domain",
            allowed_tables=list(config.allowed_tables),
            protected_tables=list(config.protected_tables),
            reports={
                report_name: ReportSpec.model_validate(report.model_dump(mode="json"))
                for report_name, report in config.reports.items()
            },
            workflows={
                workflow_id: WorkflowSpec.model_validate(workflow.model_dump(mode="json"))
                for workflow_id, workflow in config.workflows.items()
            },
        )
        return cls(
            manifest=manifest,
            source_label=f"config:apps.{app_id}",
        )

    def _load_manifest(self) -> DomainManifest:
        if self.manifest_path is None:
            raise ValueError("Inline domain registry does not have a manifest path to load.")
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
