from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from tag_fastmcp.core.app_router import AppRouter
from tag_fastmcp.core.idempotency import (
    IdempotencyService,
    InMemoryIdempotencyStore,
    ValkeyIdempotencyStore,
)
from tag_fastmcp.core.response_builder import ResponseBuilder
from tag_fastmcp.core.session_store import (
    InMemorySessionStore,
    SessionStore,
    ValkeySessionStore,
)
from tag_fastmcp.settings import AppSettings, get_settings


@dataclass
class AppContainer:
    settings: AppSettings
    session_store: SessionStore
    idempotency: IdempotencyService
    app_router: AppRouter
    responses: ResponseBuilder

    async def close(self) -> None:
        await self.session_store.close()
        await self.idempotency.close()

    @property
    def builder_runtime(self):  # type: ignore[no-untyped-def]
        if len(self.app_router.registry.apps) != 1:
            raise ValueError("builder_runtime is ambiguous when multiple apps are configured. Resolve an app context first.")
        app_id = next(iter(self.app_router.registry.apps))
        return self.app_router.resolve(app_id).builder_runtime


def _build_session_store(settings: AppSettings) -> SessionStore:
    if settings.session_store_backend in {"valkey", "redis"}:
        return ValkeySessionStore(
            valkey_url=settings.valkey_url,
            key_prefix=settings.valkey_key_prefix,
            session_ttl_seconds=settings.session_ttl_seconds,
        )
    return InMemorySessionStore()


def _build_idempotency(settings: AppSettings) -> IdempotencyService:
    if settings.idempotency_store_backend in {"valkey", "redis"}:
        store = ValkeyIdempotencyStore(
            valkey_url=settings.valkey_url,
            key_prefix=settings.valkey_key_prefix,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        )
    else:
        store = InMemoryIdempotencyStore()
    return IdempotencyService(store)


def build_container(settings: AppSettings | None = None) -> AppContainer:
    resolved_settings = settings or get_settings()
    session_store = _build_session_store(resolved_settings)
    idempotency = _build_idempotency(resolved_settings)
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
