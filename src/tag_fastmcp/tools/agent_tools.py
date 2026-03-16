from __future__ import annotations

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import BaseToolRequest


class AgentChatRequest(BaseToolRequest):
    message: str = Field(..., description="User message in natural language")
    history: list[dict] | None = Field(default=None, description="Optional conversation history")


def register_agent_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def agent_chat(request: AgentChatRequest) -> dict:
        """Interact with the domain-aware Clarification Agent."""
        app_ctx = container.app_router.resolve(request.app_id)
        
        # Initialize agent with vLLM settings
        from tag_fastmcp.agent.clarification_agent import ClarificationAgent
        agent = ClarificationAgent(
            base_url=container.settings.llm_base_url,
            # We should ideally have a setting for this, using a likely default for now
            model_name="default" 
        )
        
        reply = await agent.chat(app_ctx, request.message, request.history)
        return {
            "app_id": request.app_id,
            "reply": reply,
        }
