from __future__ import annotations

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import BaseToolRequest
from tag_fastmcp.tools._enforcement import apply_tool_enforcement


class AgentChatRequest(BaseToolRequest):
    message: str = Field(..., description="User message in natural language")
    history: list[dict] | None = Field(default=None, description="Optional conversation history")


def register_agent_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def agent_chat(request: AgentChatRequest) -> dict:
        """Interact with the domain-aware Clarification Agent."""
        request_context, policy_envelope = await apply_tool_enforcement(
            container,
            request,
            session_id=request.session_id,
            allow_platform_tools=True,
        )
        agent_selection = container.agent_registry.select_agent(
            request_context,
            policy_envelope,
            preferred_agent_kind="app_scoped_chat",
        )
        app_ctx = container.app_router.resolve(policy_envelope.primary_app_id or request.app_id)

        # Initialize agent with vLLM settings
        from tag_fastmcp.agent.clarification_agent import ClarificationAgent
        agent = ClarificationAgent(
            base_url=container.settings.llm_base_url,
            model_name=container.settings.llm_model,
        )

        reply = await agent.chat(app_ctx, request.message, request.history)
        return {
            "app_id": app_ctx.app_id,
            "request_context_id": request_context.request_id,
            "policy_envelope_id": policy_envelope.envelope_id,
            "agent_id": agent_selection.agent_id,
            "agent_kind": agent_selection.agent_kind,
            "reply": reply,
        }
