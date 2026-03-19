from __future__ import annotations

from fastmcp import Context, FastMCP

from tag_fastmcp.core.container import AppContainer
from tag_fastmcp.models.contracts import (
    ActivateRegistrationRequest,
    ApprovalDecisionRequest,
    ApprovalQueueRequest,
    ProposalListRequest,
    RegistrationListRequest,
    RegisterProposalRequest,
    ResumeExecutionRequest,
)


def register_lifecycle_tools(app: FastMCP, container: AppContainer) -> None:
    @app.tool
    async def list_approval_queue(request: ApprovalQueueRequest) -> dict:
        return (await container.admin_service.list_approval_queue(request, origin="mcp_tool")).model_dump(mode="json")

    @app.tool
    async def decide_approval(request: ApprovalDecisionRequest) -> dict:
        return (await container.admin_service.decide_approval(request, origin="mcp_tool")).model_dump(mode="json")

    @app.tool
    async def list_agent_proposals(request: ProposalListRequest) -> dict:
        return (await container.admin_service.list_agent_proposals(request, origin="mcp_tool")).model_dump(mode="json")

    @app.tool
    async def list_agent_registrations(request: RegistrationListRequest) -> dict:
        return (await container.admin_service.list_agent_registrations(request, origin="mcp_tool")).model_dump(mode="json")

    @app.tool
    async def register_agent_proposal(request: RegisterProposalRequest) -> dict:
        return (await container.admin_service.register_agent_proposal(request, origin="mcp_tool")).model_dump(mode="json")

    @app.tool
    async def activate_agent_registration(request: ActivateRegistrationRequest) -> dict:
        return (await container.admin_service.activate_agent_registration(request, origin="mcp_tool")).model_dump(mode="json")

    @app.tool
    async def resume_approved_execution(request: ResumeExecutionRequest, ctx: Context) -> dict:
        response = await container.admin_service.resume_approved_execution(request, origin="mcp_tool")
        if response.session_id is not None:
            await ctx.set_state("active_session_id", response.session_id)
        return response.model_dump(mode="json")
