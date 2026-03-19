from __future__ import annotations

from fakeredis.aioredis import FakeRedis

from tag_fastmcp.core.idempotency import IdempotencyService, ValkeyIdempotencyStore
from tag_fastmcp.core.session_store import ValkeySessionStore, WorkflowState


async def test_valkey_session_store_persists_session_state() -> None:
    client = FakeRedis(decode_responses=True)
    store = ValkeySessionStore(
        client=client,
        key_prefix="test-tag-fastmcp",
        session_ttl_seconds=300,
    )

    session = await store.start_session(actor_id="worker-1")
    await store.append_event(session.session_id, {"type": "sql", "row_count": 2})
    await store.set_last_query(session.session_id, "SELECT id FROM tasks WHERE status = 'pending'")
    await store.set_workflow(
        session.session_id,
        WorkflowState(
            workflow_id="create_task",
            collected_data={"title": "Inspect gearbox"},
        ),
    )
    await store.bind_scope(
        session.session_id,
        app_id="maintenance",
        tenant_id="tenant-7",
        execution_mode="app_chat",
    )

    snapshot = await store.get(session.session_id)
    ttl = await client.ttl(f"test-tag-fastmcp:session:{session.session_id}")

    assert snapshot.actor_id == "worker-1"
    assert snapshot.tenant_id == "tenant-7"
    assert snapshot.bound_app_id == "maintenance"
    assert snapshot.execution_mode == "app_chat"
    assert snapshot.history == [{"type": "sql", "row_count": 2}]
    assert snapshot.last_query == "SELECT id FROM tasks WHERE status = 'pending'"
    assert snapshot.active_workflow is not None
    assert snapshot.active_workflow.workflow_id == "create_task"
    assert snapshot.active_workflow.collected_data == {"title": "Inspect gearbox"}
    assert ttl > 0

    await store.close()


async def test_valkey_idempotency_store_round_trips_cached_response() -> None:
    client = FakeRedis(decode_responses=True)
    service = IdempotencyService(
        ValkeyIdempotencyStore(
            client=client,
            key_prefix="test-tag-fastmcp",
            idempotency_ttl_seconds=300,
        )
    )
    payload = {
        "app_id": "maintenance",
        "sql": "SELECT id, title FROM tasks WHERE status = 'pending'",
    }
    response = {
        "status": "ok",
        "route": "SQL",
        "meta": {"idempotent_replay": False},
    }

    await service.save("execute_sql", "session-1", "same-request", payload, response)
    cached = await service.load("execute_sql", "session-1", "same-request", payload)
    ttl = await client.ttl(
        "test-tag-fastmcp:idempotency:"
        f"{service.fingerprint('execute_sql', 'session-1', 'same-request', payload)}"
    )

    assert cached == response
    assert ttl > 0

    await service.close()
