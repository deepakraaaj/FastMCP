from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from tag_fastmcp.builder.service import BuilderRuntimeBridge
from tag_fastmcp.core.domain_registry import DomainRegistry
from tag_fastmcp.core.query_engine import AsyncQueryEngine
from tag_fastmcp.core.schema_discovery import SchemaDiscovery
from tag_fastmcp.core.session_store import SessionStore
from tag_fastmcp.core.sql_policy import SQLPolicyValidator
from tag_fastmcp.core.workflow_engine import WorkflowEngine
from tag_fastmcp.models.app_config import AppsRegistry

if TYPE_CHECKING:
    from tag_fastmcp.settings import AppSettings


class AppRouter:
    def __init__(self, settings: AppSettings, session_store: SessionStore):
        self.settings = settings
        self.session_store = session_store
        self.registry = self._load_registry()
        self._contexts: dict[str, AppContext] = {}

    def _load_registry(self) -> AppsRegistry:
        path = Path(self.settings.apps_config_path)
        if not path.is_absolute():
            path = self.settings.root_path / path

        if not path.exists():
            raise FileNotFoundError(f"Apps config not found at {path}")

        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return AppsRegistry.model_validate(data)

    def resolve(self, app_id: str) -> AppContext:
        if app_id not in self._contexts:
            if app_id not in self.registry.apps:
                raise KeyError(f"Unknown application ID: {app_id}")

            config = self.registry.apps[app_id]
            domain_registry = DomainRegistry(Path(config.manifest))
            sql_policy = SQLPolicyValidator(
                allowed_tables=domain_registry.allowed_tables(),
                protected_tables=domain_registry.protected_tables(),
                allow_mutations=self.settings.allow_mutations,
                require_select_where=self.settings.require_select_where,
            )
            query_engine = AsyncQueryEngine(
                database_url=config.database_url,
                default_row_limit=self.settings.default_row_limit,
            )
            schema_discovery = SchemaDiscovery(database_url=config.database_url)
            workflow_engine = WorkflowEngine(
                session_store=self.session_store,
                domain_registry=domain_registry
            )
            builder_runtime = BuilderRuntimeBridge(
                app_id=app_id,
                domain_registry=domain_registry,
                sql_policy=sql_policy
            )
            self._contexts[app_id] = AppContext(
                app_id=app_id,
                display_name=config.display_name,
                domain_registry=domain_registry,
                sql_policy=sql_policy,
                query_engine=query_engine,
                schema_discovery=schema_discovery,
                workflow_engine=workflow_engine,
                builder_runtime=builder_runtime,
            )
        return self._contexts[app_id]


class AppContext:
    def __init__(
        self,
        app_id: str,
        display_name: str,
        domain_registry: DomainRegistry,
        sql_policy: SQLPolicyValidator,
        query_engine: AsyncQueryEngine,
        schema_discovery: SchemaDiscovery,
        workflow_engine: WorkflowEngine,
        builder_runtime: BuilderRuntimeBridge,
    ):
        self.app_id = app_id
        self.display_name = display_name
        self.domain_registry = domain_registry
        self.sql_policy = sql_policy
        self.query_engine = query_engine
        self.schema_discovery = schema_discovery
        self.workflow_engine = workflow_engine
        self.builder_runtime = builder_runtime
