from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tag_fastmcp.models.contracts import AgentDefinition


@dataclass(frozen=True)
class PhaseStubAgent:
    definition: AgentDefinition

    async def run(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            f"Agent '{self.definition.agent_id}' is represented as a Phase 3 stub. "
            "Its concrete runtime behavior lands in a later phase."
        )


class AdminOrchestrationAgentStub(PhaseStubAgent):
    pass


class SchemaIntelligenceAgentStub(PhaseStubAgent):
    pass


class HeavyCrossDbAgentStub(PhaseStubAgent):
    pass


class AgentProposalAgentStub(PhaseStubAgent):
    pass
