from __future__ import annotations

from fastmcp import FastMCP
from pydantic import Field

from tag_fastmcp.agent.schema_intelligence_agent import SchemaIntelligenceAgent
from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import BaseToolRequest
from tag_fastmcp.models.schema_models import UnderstandingDocResponse
from tag_fastmcp.tools._enforcement import apply_tool_enforcement


class DiscoverSchemaRequest(BaseToolRequest):
    pass


class GenerateUnderstandingDocRequest(BaseToolRequest):
    max_tables: int = Field(default=12, ge=1, le=100, description="Maximum number of tables to summarize deeply.")


def register_schema_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def discover_schema(request: DiscoverSchemaRequest) -> dict:
        """Auto-discover the database schema for the given application."""
        request_context, policy_envelope = await apply_tool_enforcement(
            container,
            request,
            session_id=request.session_id,
            allow_platform_tools=True,
        )
        app_ctx = container.app_router.resolve(policy_envelope.primary_app_id or request.app_id)
        schema = await app_ctx.schema_discovery.discover()
        return {
            "app_id": app_ctx.app_id,
            "display_name": app_ctx.display_name,
            "request_context_id": request_context.request_id,
            "policy_envelope_id": policy_envelope.envelope_id,
            "schema": schema.model_dump(),
        }

    @app.tool
    async def generate_understanding_doc(request: GenerateUnderstandingDocRequest) -> dict:
        """Generate a structured understanding document for one application schema."""
        request_context, policy_envelope = await apply_tool_enforcement(
            container,
            request,
            session_id=request.session_id,
            allow_platform_tools=True,
        )
        agent_selection = container.agent_registry.select_agent(
            request_context,
            policy_envelope,
            preferred_agent_kind="schema_intelligence",
        )
        app_ctx = container.app_router.resolve(policy_envelope.primary_app_id or request.app_id)
        understanding_doc = await SchemaIntelligenceAgent().generate_understanding_doc(
            app_ctx,
            max_tables=request.max_tables,
        )
        response = UnderstandingDocResponse(
            app_id=app_ctx.app_id,
            display_name=app_ctx.display_name,
            request_context_id=request_context.request_id,
            policy_envelope_id=policy_envelope.envelope_id,
            agent_id=agent_selection.agent_id,
            agent_kind=agent_selection.agent_kind,
            understanding_doc=understanding_doc,
        )
        return response.model_dump(mode="json")
