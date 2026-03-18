from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

import valkey.asyncio as valkey


class IdempotencyStore(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def set(self, key: str, value: dict[str, Any]) -> None: ...

    async def close(self) -> None: ...


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        payload = self._store.get(key)
        return dict(payload) if payload is not None else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = dict(value)

    async def close(self) -> None:
        return None


class ValkeyIdempotencyStore:
    def __init__(
        self,
        valkey_url: str | None = None,
        *,
        key_prefix: str = "tag_fastmcp",
        idempotency_ttl_seconds: int = 86_400,
        client: Any | None = None,
    ) -> None:
        if client is None and valkey_url is None:
            raise ValueError("valkey_url is required when no Valkey client is provided.")
        self._client = client or valkey.Valkey.from_url(valkey_url, decode_responses=True)
        self._key_prefix = key_prefix
        self._idempotency_ttl_seconds = idempotency_ttl_seconds

    def _idempotency_key(self, key: str) -> str:
        return f"{self._key_prefix}:idempotency:{key}"

    def _ttl(self) -> int | None:
        return self._idempotency_ttl_seconds if self._idempotency_ttl_seconds > 0 else None

    async def get(self, key: str) -> dict[str, Any] | None:
        payload = await self._client.get(self._idempotency_key(key))
        if payload is None:
            return None
        return json.loads(payload)

    async def set(self, key: str, value: dict[str, Any]) -> None:
        await self._client.set(
            self._idempotency_key(key),
            json.dumps(value, sort_keys=True, default=str),
            ex=self._ttl(),
        )

    async def close(self) -> None:
        await self._client.aclose()


class IdempotencyService:
    def __init__(self, store: IdempotencyStore):
        self.store = store

    @staticmethod
    def fingerprint(tool_name: str, session_id: str | None, idempotency_key: str, payload: dict[str, Any]) -> str:
        material = {
            "tool_name": tool_name,
            "session_id": session_id,
            "idempotency_key": idempotency_key,
            "payload": payload,
        }
        encoded = json.dumps(material, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def load(self, tool_name: str, session_id: str | None, idempotency_key: str | None, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        return await self.store.get(self.fingerprint(tool_name, session_id, idempotency_key, payload))

    async def save(self, tool_name: str, session_id: str | None, idempotency_key: str | None, payload: dict[str, Any], response: dict[str, Any]) -> None:
        if not idempotency_key:
            return
        await self.store.set(self.fingerprint(tool_name, session_id, idempotency_key, payload), response)

    async def close(self) -> None:
        await self.store.close()
