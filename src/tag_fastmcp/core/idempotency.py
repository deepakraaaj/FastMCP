from __future__ import annotations

import hashlib
import json
from typing import Any


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        payload = self._store.get(key)
        return dict(payload) if payload is not None else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = dict(value)


class IdempotencyService:
    def __init__(self, store: InMemoryIdempotencyStore):
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

    def load(self, tool_name: str, session_id: str | None, idempotency_key: str | None, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        return self.store.get(self.fingerprint(tool_name, session_id, idempotency_key, payload))

    def save(self, tool_name: str, session_id: str | None, idempotency_key: str | None, payload: dict[str, Any], response: dict[str, Any]) -> None:
        if not idempotency_key:
            return
        self.store.set(self.fingerprint(tool_name, session_id, idempotency_key, payload), response)
