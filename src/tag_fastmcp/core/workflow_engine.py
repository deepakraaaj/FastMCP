from __future__ import annotations

from tag_fastmcp.core.domain_registry import DomainRegistry
from tag_fastmcp.core.session_store import InMemorySessionStore, WorkflowState
from tag_fastmcp.models.contracts import WorkflowResultPayload


class WorkflowEngine:
    def __init__(self, session_store: InMemorySessionStore, domain_registry: DomainRegistry):
        self.session_store = session_store
        self.domain_registry = domain_registry

    def start(self, session_id: str, workflow_id: str, values: dict[str, object]) -> WorkflowResultPayload:
        spec = self.domain_registry.get_workflow(workflow_id)
        state = WorkflowState(workflow_id=workflow_id, collected_data=dict(values or {}))
        self.session_store.set_workflow(session_id, state)
        return self._build_response(state)

    def continue_workflow(self, session_id: str, values: dict[str, object]) -> WorkflowResultPayload:
        session = self.session_store.get(session_id)
        if session.active_workflow is None:
            raise ValueError("No active workflow found for this session.")
        session.active_workflow.collected_data.update(values or {})
        return self._build_response(session.active_workflow)

    def _build_response(self, state: WorkflowState) -> WorkflowResultPayload:
        spec = self.domain_registry.get_workflow(state.workflow_id)
        missing_fields = [field for field in spec.required_fields if field not in state.collected_data or state.collected_data[field] in ("", None)]
        completed = not missing_fields
        next_prompt = f"Provide {missing_fields[0]}." if missing_fields else "Workflow input collection is complete."
        return WorkflowResultPayload(
            workflow_id=state.workflow_id,
            state="completed" if completed else "pending",
            collected_data=dict(state.collected_data),
            missing_fields=missing_fields,
            next_prompt=next_prompt,
        )
