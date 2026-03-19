from __future__ import annotations

import base64
import json
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from pydantic import BaseModel, ValidationError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route

from tag_fastmcp.app import create_app
from tag_fastmcp.core.container import AppContainer, build_container, get_container
from tag_fastmcp.models.contracts import (
    ActivateRegistrationRequest,
    ApprovalDecisionRequest,
    ApprovalQueueRequest,
    ProposalListRequest,
    RegistrationListRequest,
    RegisterProposalRequest,
    ResumeExecutionRequest,
)
from tag_fastmcp.models.http_api import (
    AdminChatRequest,
    AdminActivateRegistrationBody,
    AdminApprovalDecisionBody,
    AdminApprovalQueueParams,
    AdminProposalListParams,
    AdminRegisterProposalBody,
    AdminRegistrationListParams,
    AdminResumeExecutionBody,
    AdminUserContext,
    WidgetChatRequest,
    WidgetSessionStartResponse,
    WidgetStreamEvent,
    WidgetStreamEventV2,
    WidgetUserContext,
)
from tag_fastmcp.settings import AppSettings, get_settings


def _decode_user_context(raw_value: str | None) -> WidgetUserContext | None:
    if not raw_value:
        return None
    try:
        decoded = base64.b64decode(raw_value).decode("utf-8")
        return WidgetUserContext.model_validate_json(decoded)
    except Exception:
        return None


def _decode_admin_context(raw_value: str | None) -> AdminUserContext | None:
    if not raw_value:
        return None
    try:
        decoded = base64.b64decode(raw_value).decode("utf-8")
        return AdminUserContext.model_validate_json(decoded)
    except Exception:
        return None


def _requested_app_id(request: Request, body: dict[str, Any] | None = None) -> str | None:
    if body and body.get("app_id"):
        return str(body["app_id"])
    header_value = request.headers.get("x-app-id")
    return header_value.strip() if header_value and header_value.strip() else None


def _text_chunks(message: str, size: int = 80) -> list[str]:
    normalized = message.strip()
    if not normalized:
        return []
    return [normalized[index : index + size] for index in range(0, len(normalized), size)]


def _json_line(event: BaseModel) -> bytes:
    return (event.model_dump_json() + "\n").encode("utf-8")


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - exercised through route behavior
        raise ValueError("Invalid JSON body.") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")
    return payload


def _admin_request_fields(
    admin_context: AdminUserContext,
    *,
    app_id: str | None,
    session_id: str | None,
    trace_id: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if admin_context.allowed_app_ids:
        metadata["allowed_app_ids"] = list(admin_context.allowed_app_ids)
    return {
        "app_id": app_id,
        "session_id": session_id,
        "actor_id": admin_context.actor_id,
        "auth_subject": admin_context.auth_subject or admin_context.actor_id,
        "tenant_id": admin_context.tenant_id,
        "role": admin_context.role,
        "auth_scopes": list(admin_context.auth_scopes),
        "trace_id": trace_id,
        "metadata": metadata,
    }


def _admin_context_or_error(request: Request) -> AdminUserContext:
    admin_context = _decode_admin_context(request.headers.get("x-admin-context"))
    if admin_context is None:
        raise PermissionError("Valid x-admin-context header is required for admin routes.")
    return admin_context


def create_http_app(
    settings: AppSettings | None = None,
    container: AppContainer | None = None,
) -> Starlette:
    resolved_settings = settings or get_settings()
    resolved_container = container or build_container(resolved_settings)
    mcp_app = create_app(settings=resolved_settings, container=resolved_container).http_app(
        path=resolved_settings.path,
        transport=resolved_settings.transport,
        stateless_http=resolved_settings.stateless_http,
    )
    chat_service = resolved_container.chat_service

    @asynccontextmanager
    async def lifespan(_: Starlette):
        try:
            yield
        finally:
            await resolved_container.close()

    async def health(_: Request) -> Response:
        return JSONResponse({"status": "ok", "service": resolved_settings.app_name})

    async def start_session(request: Request) -> Response:
        user_context = _decode_user_context(request.headers.get("x-user-context"))
        try:
            session_id, app_id = await chat_service.start_session(
                requested_app_id=_requested_app_id(request),
                user_context=user_context,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        payload = WidgetSessionStartResponse(session_id=session_id, app_id=app_id)
        return JSONResponse(payload.model_dump(mode="json"))

    async def chat(request: Request) -> Response:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

        try:
            payload = WidgetChatRequest.model_validate(body)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)

        requested_app_id = _requested_app_id(request, body)
        user_context = _decode_user_context(request.headers.get("x-user-context"))
        rich_output = request.query_params.get("rich", "").strip().lower() in {"1", "true", "yes", "on"}

        async def event_stream():
            try:
                result = await chat_service.chat(
                    session_id=payload.session_id,
                    message=payload.message,
                    requested_app_id=requested_app_id,
                    user_context=user_context,
                )
                for chunk in _text_chunks(result.message):
                    yield _json_line(
                        WidgetStreamEvent(
                            type="token",
                            content=chunk,
                            session_id=result.session_id,
                            app_id=result.app_id,
                        )
                    )
                if rich_output and result.channel_response is not None:
                    for block in result.channel_response.blocks:
                        yield _json_line(
                            WidgetStreamEventV2(
                                type="block",
                                session_id=result.session_id,
                                app_id=result.app_id,
                                payload=block.model_dump(mode="json"),
                            )
                        )
                    yield _json_line(
                        WidgetStreamEventV2(
                            type="state",
                            session_id=result.session_id,
                            app_id=result.app_id,
                            payload=result.channel_response.state.model_dump(mode="json"),
                        )
                    )
                    for action in result.channel_response.actions:
                        yield _json_line(
                            WidgetStreamEventV2(
                                type="action",
                                session_id=result.session_id,
                                app_id=result.app_id,
                                payload=action.model_dump(mode="json"),
                            )
                        )
                result_event = {
                    "type": "result",
                    "message": result.message,
                    "session_id": result.session_id,
                    "app_id": result.app_id,
                    **result.metadata,
                }
                if rich_output and result.channel_response is not None:
                    result_event["channel_response"] = result.channel_response.model_dump(mode="json")
                yield (json.dumps(result_event) + "\n").encode("utf-8")
            except ValueError as exc:
                yield _json_line(WidgetStreamEvent(type="error", message=str(exc)))
            except Exception:
                yield _json_line(
                    WidgetStreamEvent(
                        type="error",
                        message="A temporary system issue occurred. Please try again.",
                    )
                )

        return StreamingResponse(
            event_stream(),
            media_type="application/x-ndjson",
        )

    async def admin_list_approvals(request: Request) -> Response:
        try:
            admin_context = _admin_context_or_error(request)
            params = AdminApprovalQueueParams.model_validate(dict(request.query_params))
            response = await resolved_container.admin_service.list_approval_queue(
                ApprovalQueueRequest(
                    **_admin_request_fields(
                        admin_context,
                        app_id=params.app_id,
                        session_id=params.session_id,
                        trace_id=params.trace_id,
                    ),
                    status=params.status,
                    scope_type=params.scope_type,
                )
            )
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(response.model_dump(mode="json"))

    async def admin_decide_approval(request: Request) -> Response:
        try:
            admin_context = _admin_context_or_error(request)
            body = AdminApprovalDecisionBody.model_validate(await _json_body(request))
            response = await resolved_container.admin_service.decide_approval(
                ApprovalDecisionRequest(
                    **_admin_request_fields(
                        admin_context,
                        app_id=body.app_id,
                        session_id=body.session_id,
                        trace_id=body.trace_id,
                    ),
                    approval_id=str(request.path_params["approval_id"]),
                    decision=body.decision,
                    comment=body.comment,
                )
            )
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(response.model_dump(mode="json"))

    async def admin_resume_approval(request: Request) -> Response:
        try:
            admin_context = _admin_context_or_error(request)
            body = AdminResumeExecutionBody.model_validate(await _json_body(request))
            response = await resolved_container.admin_service.resume_approved_execution(
                ResumeExecutionRequest(
                    **_admin_request_fields(
                        admin_context,
                        app_id=body.app_id,
                        session_id=body.session_id,
                        trace_id=body.trace_id,
                    ),
                    approval_id=str(request.path_params["approval_id"]),
                )
            )
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(response.model_dump(mode="json"))

    async def admin_list_proposals(request: Request) -> Response:
        try:
            admin_context = _admin_context_or_error(request)
            params = AdminProposalListParams.model_validate(dict(request.query_params))
            response = await resolved_container.admin_service.list_agent_proposals(
                ProposalListRequest(
                    **_admin_request_fields(
                        admin_context,
                        app_id=params.app_id,
                        session_id=params.session_id,
                        trace_id=params.trace_id,
                    ),
                    status=params.status,
                )
            )
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(response.model_dump(mode="json"))

    async def admin_list_registrations(request: Request) -> Response:
        try:
            admin_context = _admin_context_or_error(request)
            params = AdminRegistrationListParams.model_validate(dict(request.query_params))
            response = await resolved_container.admin_service.list_agent_registrations(
                RegistrationListRequest(
                    **_admin_request_fields(
                        admin_context,
                        app_id=params.app_id,
                        session_id=params.session_id,
                        trace_id=params.trace_id,
                    ),
                    proposal_id=params.proposal_id,
                    registry_state=params.registry_state,
                )
            )
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(response.model_dump(mode="json"))

    async def admin_register_proposal(request: Request) -> Response:
        try:
            admin_context = _admin_context_or_error(request)
            body = AdminRegisterProposalBody.model_validate(await _json_body(request))
            response = await resolved_container.admin_service.register_agent_proposal(
                RegisterProposalRequest(
                    **_admin_request_fields(
                        admin_context,
                        app_id=body.app_id,
                        session_id=body.session_id,
                        trace_id=body.trace_id,
                    ),
                    proposal_id=str(request.path_params["proposal_id"]),
                    version=body.version,
                )
            )
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(response.model_dump(mode="json"))

    async def admin_activate_registration(request: Request) -> Response:
        try:
            admin_context = _admin_context_or_error(request)
            body = AdminActivateRegistrationBody.model_validate(await _json_body(request))
            response = await resolved_container.admin_service.activate_agent_registration(
                ActivateRegistrationRequest(
                    **_admin_request_fields(
                        admin_context,
                        app_id=body.app_id,
                        session_id=body.session_id,
                        trace_id=body.trace_id,
                    ),
                    registration_id=str(request.path_params["registration_id"]),
                )
            )
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(response.model_dump(mode="json"))

    async def admin_chat(request: Request) -> Response:
        try:
            admin_context = _admin_context_or_error(request)
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

        try:
            payload = AdminChatRequest.model_validate(body)
        except ValidationError as exc:
            return JSONResponse({"error": exc.errors()}, status_code=422)

        rich_output = request.query_params.get("rich", "").strip().lower() in {"1", "true", "yes", "on"}

        async def event_stream():
            try:
                result = await resolved_container.admin_chat_service.chat(
                    session_id=payload.session_id,
                    message=payload.message,
                    requested_app_id=payload.app_id,
                    channel_id=payload.channel_id,
                    admin_context=admin_context,
                )
                for chunk in _text_chunks(result.message):
                    yield _json_line(
                        WidgetStreamEvent(
                            type="token",
                            content=chunk,
                            session_id=result.session_id,
                            app_id=result.app_id,
                        )
                    )
                if rich_output and result.channel_response is not None:
                    for block in result.channel_response.blocks:
                        yield _json_line(
                            WidgetStreamEventV2(
                                type="block",
                                session_id=result.session_id,
                                app_id=result.app_id,
                                payload=block.model_dump(mode="json"),
                            )
                        )
                    yield _json_line(
                        WidgetStreamEventV2(
                            type="state",
                            session_id=result.session_id,
                            app_id=result.app_id,
                            payload=result.channel_response.state.model_dump(mode="json"),
                        )
                    )
                    for action in result.channel_response.actions:
                        yield _json_line(
                            WidgetStreamEventV2(
                                type="action",
                                session_id=result.session_id,
                                app_id=result.app_id,
                                payload=action.model_dump(mode="json"),
                            )
                        )
                result_event = {
                    "type": "result",
                    "message": result.message,
                    "session_id": result.session_id,
                    "app_id": result.app_id,
                    **result.metadata,
                }
                if rich_output and result.channel_response is not None:
                    result_event["channel_response"] = result.channel_response.model_dump(mode="json")
                yield (json.dumps(result_event) + "\n").encode("utf-8")
            except ValueError as exc:
                yield _json_line(WidgetStreamEvent(type="error", message=str(exc)))
            except Exception:
                yield _json_line(
                    WidgetStreamEvent(
                        type="error",
                        message="A temporary system issue occurred. Please try again.",
                    )
                )

        return StreamingResponse(
            event_stream(),
            media_type="application/x-ndjson",
        )

    return Starlette(
        debug=resolved_settings.environment == "development",
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
            )
        ],
        routes=[
            Route("/healthz", health, methods=["GET"]),
            Route("/session/start", start_session, methods=["POST"]),
            Route("/chat", chat, methods=["POST"]),
            Route("/admin/approvals", admin_list_approvals, methods=["GET"]),
            Route("/admin/approvals/{approval_id:str}/decision", admin_decide_approval, methods=["POST"]),
            Route("/admin/approvals/{approval_id:str}/resume", admin_resume_approval, methods=["POST"]),
            Route("/admin/agents/proposals", admin_list_proposals, methods=["GET"]),
            Route("/admin/agents/registrations", admin_list_registrations, methods=["GET"]),
            Route("/admin/agents/proposals/{proposal_id:str}/register", admin_register_proposal, methods=["POST"]),
            Route("/admin/agents/registrations/{registration_id:str}/activate", admin_activate_registration, methods=["POST"]),
            Route("/admin/chat", admin_chat, methods=["POST"]),
            Mount("/", app=mcp_app),
        ],
        lifespan=lifespan,
    )


http_app = create_http_app(container=get_container())


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        http_app,
        host=settings.host,
        port=settings.port,
    )
