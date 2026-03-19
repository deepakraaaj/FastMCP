from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tag_fastmcp.core.database_urls import normalize_database_url
from tag_fastmcp.models.contracts import (
    AgentProposalDraft,
    AgentRegistrationRecord,
    ApprovalRequest,
    ExecutionApprovalPayload,
    LifecycleAuditEvent,
    PausedExecutionRecord,
)

class ControlPlaneStore(Protocol):
    async def put_approval_request(self, approval: ApprovalRequest) -> None: ...

    async def get_approval_request(self, approval_id: str) -> ApprovalRequest: ...

    async def list_approval_requests(
        self,
        *,
        status: str | None = None,
        scope_type: str | None = None,
    ) -> list[ApprovalRequest]: ...

    async def put_execution_approval_payload(self, payload: ExecutionApprovalPayload) -> None: ...

    async def get_execution_approval_payload(self, approval_id: str) -> ExecutionApprovalPayload | None: ...

    async def put_proposal_draft(self, proposal: AgentProposalDraft) -> None: ...

    async def get_proposal_draft(self, proposal_id: str) -> AgentProposalDraft: ...

    async def list_proposal_drafts(self, *, status: str | None = None) -> list[AgentProposalDraft]: ...

    async def put_registration_record(self, record: AgentRegistrationRecord) -> None: ...

    async def get_registration_record(self, registration_id: str) -> AgentRegistrationRecord: ...

    async def list_registration_records(
        self,
        *,
        proposal_id: str | None = None,
        registry_state: str | None = None,
    ) -> list[AgentRegistrationRecord]: ...

    async def put_paused_execution(self, record: PausedExecutionRecord) -> None: ...

    async def get_paused_execution_by_approval(self, approval_id: str) -> PausedExecutionRecord | None: ...

    async def append_audit_event(self, event: LifecycleAuditEvent) -> None: ...

    async def list_audit_events(
        self,
        *,
        approval_id: str | None = None,
        proposal_id: str | None = None,
        registration_id: str | None = None,
    ) -> list[LifecycleAuditEvent]: ...

    async def close(self) -> None: ...


@dataclass
class SqlControlPlaneStore:
    database_url: str

    def __post_init__(self) -> None:
        self._engine: AsyncEngine = create_async_engine(
            normalize_database_url(self.database_url),
            pool_pre_ping=True,
        )
        self._metadata = MetaData()
        self._ready = False
        self._lock = asyncio.Lock()

        self._approval_requests = Table(
            "control_plane_approval_requests",
            self._metadata,
            Column("approval_id", String(128), primary_key=True),
            Column("scope_type", String(64), nullable=False),
            Column("status", String(64), nullable=False),
            Column("tenant_id", String(255), nullable=True),
            Column("requested_by_role", String(64), nullable=False),
            Column("approver_role", String(64), nullable=True),
            Column("proposal_draft_ref", String(128), nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("decided_at", DateTime(timezone=True), nullable=True),
            Column("expires_at", DateTime(timezone=True), nullable=True),
            Column("payload_json", Text, nullable=False),
        )
        self._approval_payloads = Table(
            "control_plane_execution_approval_payloads",
            self._metadata,
            Column("approval_id", String(128), primary_key=True),
            Column("payload_json", Text, nullable=False),
        )
        self._proposal_drafts = Table(
            "control_plane_agent_proposals",
            self._metadata,
            Column("proposal_id", String(128), primary_key=True),
            Column("status", String(64), nullable=False),
            Column("tenant_id", String(255), nullable=True),
            Column("linked_approval_id", String(128), nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            Column("payload_json", Text, nullable=False),
        )
        self._registration_records = Table(
            "control_plane_agent_registrations",
            self._metadata,
            Column("registration_id", String(128), primary_key=True),
            Column("proposal_id", String(128), nullable=False),
            Column("registry_state", String(64), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("activated_at", DateTime(timezone=True), nullable=True),
            Column("payload_json", Text, nullable=False),
        )
        self._paused_executions = Table(
            "control_plane_paused_executions",
            self._metadata,
            Column("pause_id", String(128), primary_key=True),
            Column("approval_id", String(128), nullable=False, unique=True),
            Column("status", String(64), nullable=False),
            Column("request_id", String(128), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("resumed_at", DateTime(timezone=True), nullable=True),
            Column("payload_json", Text, nullable=False),
        )
        self._audit_events = Table(
            "control_plane_lifecycle_audit_events",
            self._metadata,
            Column("event_id", String(128), primary_key=True),
            Column("event_type", String(128), nullable=False),
            Column("approval_id", String(128), nullable=True),
            Column("proposal_id", String(128), nullable=True),
            Column("registration_id", String(128), nullable=True),
            Column("timestamp", DateTime(timezone=True), nullable=False),
            Column("payload_json", Text, nullable=False),
        )

    async def _ensure_ready(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            async with self._engine.begin() as conn:
                await conn.run_sync(self._metadata.create_all)
            self._ready = True

    async def put_approval_request(self, approval: ApprovalRequest) -> None:
        await self._ensure_ready()
        await self._upsert(
            self._approval_requests,
            key_column="approval_id",
            key_value=approval.approval_id,
            values={
                "approval_id": approval.approval_id,
                "scope_type": approval.scope_type,
                "status": approval.status,
                "tenant_id": approval.tenant_id,
                "requested_by_role": approval.requested_by_role,
                "approver_role": approval.approver_role,
                "proposal_draft_ref": approval.proposal_draft_ref,
                "created_at": approval.created_at,
                "decided_at": approval.decided_at,
                "expires_at": approval.expires_at,
                "payload_json": approval.model_dump_json(),
            },
        )

    async def get_approval_request(self, approval_id: str) -> ApprovalRequest:
        await self._ensure_ready()
        row = await self._fetch_one(
            self._approval_requests,
            self._approval_requests.c.approval_id == approval_id,
        )
        if row is None:
            raise KeyError(f"Unknown approval '{approval_id}'.")
        return ApprovalRequest.model_validate_json(row["payload_json"])

    async def list_approval_requests(
        self,
        *,
        status: str | None = None,
        scope_type: str | None = None,
    ) -> list[ApprovalRequest]:
        await self._ensure_ready()
        query = select(self._approval_requests).order_by(self._approval_requests.c.created_at.desc())
        if status is not None:
            query = query.where(self._approval_requests.c.status == status)
        if scope_type is not None:
            query = query.where(self._approval_requests.c.scope_type == scope_type)
        async with self._engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        return [ApprovalRequest.model_validate_json(row["payload_json"]) for row in rows]

    async def put_execution_approval_payload(self, payload: ExecutionApprovalPayload) -> None:
        await self._ensure_ready()
        await self._upsert(
            self._approval_payloads,
            key_column="approval_id",
            key_value=payload.approval_id,
            values={
                "approval_id": payload.approval_id,
                "payload_json": payload.model_dump_json(),
            },
        )

    async def get_execution_approval_payload(self, approval_id: str) -> ExecutionApprovalPayload | None:
        await self._ensure_ready()
        row = await self._fetch_one(
            self._approval_payloads,
            self._approval_payloads.c.approval_id == approval_id,
        )
        if row is None:
            return None
        return ExecutionApprovalPayload.model_validate_json(row["payload_json"])

    async def put_proposal_draft(self, proposal: AgentProposalDraft) -> None:
        await self._ensure_ready()
        await self._upsert(
            self._proposal_drafts,
            key_column="proposal_id",
            key_value=proposal.proposal_id,
            values={
                "proposal_id": proposal.proposal_id,
                "status": proposal.status,
                "tenant_id": proposal.tenant_id,
                "linked_approval_id": proposal.linked_approval_id,
                "created_at": proposal.created_at,
                "updated_at": proposal.updated_at,
                "payload_json": proposal.model_dump_json(),
            },
        )

    async def get_proposal_draft(self, proposal_id: str) -> AgentProposalDraft:
        await self._ensure_ready()
        row = await self._fetch_one(
            self._proposal_drafts,
            self._proposal_drafts.c.proposal_id == proposal_id,
        )
        if row is None:
            raise KeyError(f"Unknown proposal '{proposal_id}'.")
        return AgentProposalDraft.model_validate_json(row["payload_json"])

    async def list_proposal_drafts(self, *, status: str | None = None) -> list[AgentProposalDraft]:
        await self._ensure_ready()
        query = select(self._proposal_drafts).order_by(self._proposal_drafts.c.updated_at.desc())
        if status is not None:
            query = query.where(self._proposal_drafts.c.status == status)
        async with self._engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        return [AgentProposalDraft.model_validate_json(row["payload_json"]) for row in rows]

    async def put_registration_record(self, record: AgentRegistrationRecord) -> None:
        await self._ensure_ready()
        await self._upsert(
            self._registration_records,
            key_column="registration_id",
            key_value=record.registration_id,
            values={
                "registration_id": record.registration_id,
                "proposal_id": record.proposal_id,
                "registry_state": record.registry_state,
                "created_at": record.created_at,
                "activated_at": record.activated_at,
                "payload_json": record.model_dump_json(),
            },
        )

    async def get_registration_record(self, registration_id: str) -> AgentRegistrationRecord:
        await self._ensure_ready()
        row = await self._fetch_one(
            self._registration_records,
            self._registration_records.c.registration_id == registration_id,
        )
        if row is None:
            raise KeyError(f"Unknown registration '{registration_id}'.")
        return AgentRegistrationRecord.model_validate_json(row["payload_json"])

    async def list_registration_records(
        self,
        *,
        proposal_id: str | None = None,
        registry_state: str | None = None,
    ) -> list[AgentRegistrationRecord]:
        await self._ensure_ready()
        query = select(self._registration_records).order_by(self._registration_records.c.created_at.desc())
        if proposal_id is not None:
            query = query.where(self._registration_records.c.proposal_id == proposal_id)
        if registry_state is not None:
            query = query.where(self._registration_records.c.registry_state == registry_state)
        async with self._engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        return [AgentRegistrationRecord.model_validate_json(row["payload_json"]) for row in rows]

    async def put_paused_execution(self, record: PausedExecutionRecord) -> None:
        await self._ensure_ready()
        await self._upsert(
            self._paused_executions,
            key_column="pause_id",
            key_value=record.pause_id,
            values={
                "pause_id": record.pause_id,
                "approval_id": record.approval_id,
                "status": record.status,
                "request_id": record.request_id,
                "created_at": record.created_at,
                "resumed_at": record.resumed_at,
                "payload_json": record.model_dump_json(),
            },
        )

    async def get_paused_execution_by_approval(self, approval_id: str) -> PausedExecutionRecord | None:
        await self._ensure_ready()
        row = await self._fetch_one(
            self._paused_executions,
            self._paused_executions.c.approval_id == approval_id,
        )
        if row is None:
            return None
        return PausedExecutionRecord.model_validate_json(row["payload_json"])

    async def append_audit_event(self, event: LifecycleAuditEvent) -> None:
        await self._ensure_ready()
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(self._audit_events).values(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    approval_id=event.approval_id,
                    proposal_id=event.proposal_id,
                    registration_id=event.registration_id,
                    timestamp=event.timestamp,
                    payload_json=event.model_dump_json(),
                )
            )

    async def list_audit_events(
        self,
        *,
        approval_id: str | None = None,
        proposal_id: str | None = None,
        registration_id: str | None = None,
    ) -> list[LifecycleAuditEvent]:
        await self._ensure_ready()
        query = select(self._audit_events).order_by(self._audit_events.c.timestamp.asc())
        if approval_id is not None:
            query = query.where(self._audit_events.c.approval_id == approval_id)
        if proposal_id is not None:
            query = query.where(self._audit_events.c.proposal_id == proposal_id)
        if registration_id is not None:
            query = query.where(self._audit_events.c.registration_id == registration_id)
        async with self._engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        return [LifecycleAuditEvent.model_validate_json(row["payload_json"]) for row in rows]

    async def close(self) -> None:
        await self._engine.dispose()

    async def _upsert(
        self,
        table: Table,
        *,
        key_column: str,
        key_value: str,
        values: dict[str, object],
    ) -> None:
        async with self._engine.begin() as conn:
            existing = await conn.execute(select(table.c[key_column]).where(table.c[key_column] == key_value))
            if existing.first() is None:
                await conn.execute(insert(table).values(**values))
            else:
                await conn.execute(update(table).where(table.c[key_column] == key_value).values(**values))

    async def _fetch_one(self, table: Table, predicate) -> dict[str, object] | None:  # type: ignore[no-untyped-def]
        async with self._engine.connect() as conn:
            result = await conn.execute(select(table).where(predicate))
            row = result.mappings().first()
        return dict(row) if row is not None else None


def utcnow() -> datetime:
    return datetime.now(UTC)
