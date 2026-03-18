from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CircuitBreakerSnapshot:
    state: str = "closed"
    failure_count: int = 0
    opened_until_monotonic: float | None = None


class InMemoryCircuitBreakerStore:
    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreakerSnapshot] = {}

    def get(self, breaker_id: str) -> CircuitBreakerSnapshot:
        return self._breakers.setdefault(breaker_id, CircuitBreakerSnapshot())


class CircuitBreakerService:
    def __init__(self, store: InMemoryCircuitBreakerStore | None = None) -> None:
        self.store = store or InMemoryCircuitBreakerStore()

    def before_call(self, breaker_id: str) -> str:
        snapshot = self.store.get(breaker_id)
        now = time.monotonic()
        if snapshot.state == "open":
            if snapshot.opened_until_monotonic is not None and now >= snapshot.opened_until_monotonic:
                snapshot.state = "half_open"
                snapshot.failure_count = 0
                snapshot.opened_until_monotonic = None
                return "half_open"
            return "open"
        return snapshot.state

    def record_success(self, breaker_id: str) -> str:
        snapshot = self.store.get(breaker_id)
        snapshot.state = "closed"
        snapshot.failure_count = 0
        snapshot.opened_until_monotonic = None
        return snapshot.state

    def record_failure(self, breaker_id: str, *, threshold: int, reset_seconds: int) -> str:
        snapshot = self.store.get(breaker_id)
        snapshot.failure_count += 1
        if snapshot.failure_count >= threshold:
            snapshot.state = "open"
            snapshot.opened_until_monotonic = time.monotonic() + max(reset_seconds, 0)
            return snapshot.state
        snapshot.state = "closed"
        return snapshot.state
