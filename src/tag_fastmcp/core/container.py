from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from tag_fastmcp.core.app_router import AppRouter
from tag_fastmcp.core.idempotency import IdempotencyService, InMemoryIdempotencyStore
from tag_fastmcp.core.response_builder import ResponseBuilder
from tag_fastmcp.core.session_store import InMemorySessionStore
from tag_fastmcp.settings import AppSettings, get_settings


@dataclass
class AppContainer:
    settings: AppSettings
    session_store: InMemorySessionStore
    idempotency: IdempotencyService
    app_router: AppRouter
    responses: ResponseBuilder


def build_container(settings: AppSettings | None = None) -> AppContainer:
    resolved_settings = settings or get_settings()
    session_store = InMemorySessionStore()
    idempotency = IdempotencyService(InMemoryIdempotencyStore())
    app_router = AppRouter(settings=resolved_settings, session_store=session_store)

    return AppContainer(
        settings=resolved_settings,
        session_store=session_store,
        idempotency=idempotency,
        app_router=app_router,
        responses=ResponseBuilder(),
    )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return build_container()
