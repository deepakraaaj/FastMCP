from __future__ import annotations

import uuid

from tag_fastmcp.models.contracts import (
    ChannelResponse,
    DomainPayload,
    LifecyclePayload,
    RegistryPayload,
    ReportResultPayload,
    ResponseEnvelope,
    RoutingPayload,
    SQLResultPayload,
    SessionPayload,
    WorkflowResultPayload,
)


class ResponseBuilder:
    @staticmethod
    def system(
        *,
        message: str,
        session: SessionPayload | None = None,
        domain: DomainPayload | None = None,
        registry: RegistryPayload | None = None,
        lifecycle: LifecyclePayload | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        meta: dict[str, object] | None = None,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            request_id=uuid.uuid4().hex,
            route="SYSTEM",
            status="ok",
            message=message,
            session_id=session_id,
            trace_id=trace_id,
            session=session,
            domain=domain,
            registry=registry,
            lifecycle=lifecycle,
            meta=dict(meta or {}),
        )

    @staticmethod
    def sql(
        *,
        status: str,
        message: str,
        sql: SQLResultPayload | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        warnings: list[str] | None = None,
        meta: dict[str, object] | None = None,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            request_id=uuid.uuid4().hex,
            route="SQL",
            status=status,  # type: ignore[arg-type]
            message=message,
            session_id=session_id,
            trace_id=trace_id,
            warnings=list(warnings or []),
            meta=dict(meta or {}),
            sql=sql,
        )

    @staticmethod
    def report(
        *,
        message: str,
        report: ReportResultPayload,
        session_id: str | None = None,
        trace_id: str | None = None,
        meta: dict[str, object] | None = None,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            request_id=uuid.uuid4().hex,
            route="REPORT",
            status="ok",
            message=message,
            session_id=session_id,
            trace_id=trace_id,
            meta=dict(meta or {}),
            report=report,
        )

    @staticmethod
    def workflow(
        *,
        message: str,
        workflow: WorkflowResultPayload,
        session_id: str | None = None,
        trace_id: str | None = None,
        meta: dict[str, object] | None = None,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            request_id=uuid.uuid4().hex,
            route="WORKFLOW",
            status="ok" if workflow.state == "completed" else "pending",
            message=message,
            session_id=session_id,
            trace_id=trace_id,
            meta=dict(meta or {}),
            workflow=workflow,
        )

    @staticmethod
    def routing(
        *,
        status: str,
        message: str,
        routing: RoutingPayload,
        session_id: str | None = None,
        trace_id: str | None = None,
        warnings: list[str] | None = None,
        meta: dict[str, object] | None = None,
        presentation: ChannelResponse | None = None,
        lifecycle: LifecyclePayload | None = None,
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            request_id=uuid.uuid4().hex,
            route="ROUTING",
            status=status,  # type: ignore[arg-type]
            message=message,
            session_id=session_id,
            trace_id=trace_id,
            warnings=list(warnings or []),
            meta=dict(meta or {}),
            routing=routing,
            presentation=presentation,
            lifecycle=lifecycle,
        )
