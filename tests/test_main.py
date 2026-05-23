"""
Tests for StudySync PDC Assignment 4
Covers:
  - Optimistic Locking (Problem 1)
  - Idempotent Webhook Handler (Problem 2)
  - Circuit Breaker (Problem 3)
  - X-Student-ID middleware header
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

# Import the app and reset shared state before each test
import app.main as main_module
from app.main import app, documents_db, processed_webhooks, user_subscriptions, llm_breaker


@pytest.fixture(autouse=True)
def reset_state():
    """Reset all in-memory state before every test."""
    documents_db.clear()
    documents_db["doc1"] = {"id": "doc1", "content": "Hello world", "version": 1, "owner": "alice"}
    processed_webhooks.clear()
    user_subscriptions.clear()
    user_subscriptions["user_alice"] = "premium"
    user_subscriptions["user_bob"] = "free"
    llm_breaker.failure_count = 0
    llm_breaker.state = main_module.CircuitState.CLOSED
    llm_breaker.last_failure_time = 0.0
    main_module.LLM_IS_DOWN = False


# ─────────────────────────────────────────────
# Middleware: X-Student-ID header
# ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_student_id_header_present():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
    assert "x-student-id" in r.headers, "X-Student-ID header must be present on every response"
    assert r.headers["x-student-id"] == main_module.STUDENT_ID


@pytest.mark.asyncio
async def test_student_id_header_on_all_routes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        routes = ["/", "/documents/doc1", "/llm/circuit-status", "/users/user_alice/subscription"]
        for route in routes:
            r = await client.get(route)
            assert "x-student-id" in r.headers, f"Missing header on {route}"


# ─────────────────────────────────────────────
# Problem 1: Optimistic Locking
# ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_first_write_succeeds():
    """A normal update with correct version should succeed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.put("/documents/doc1", json={"content": "Updated content", "version": 1})
    assert r.status_code == 200
    assert r.json()["new_version"] == 2


@pytest.mark.asyncio
async def test_concurrent_write_conflict_detected():
    """
    Simulate two users both reading version 1, then both trying to write.
    First write succeeds (→ version 2).
    Second write with stale version 1 must be REJECTED with 409.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Both users read version 1
        r1 = await client.get("/documents/doc1")
        assert r1.json()["version"] == 1

        # User A writes first
        write_a = await client.put(
            "/documents/doc1",
            json={"content": "Alice's changes", "version": 1}
        )
        assert write_a.status_code == 200, "Alice's write should succeed"
        assert write_a.json()["new_version"] == 2

        # User B tries to write with the stale version — must fail
        write_b = await client.put(
            "/documents/doc1",
            json={"content": "Bob's conflicting changes", "version": 1}
        )
        assert write_b.status_code == 409, "Bob's stale write must be rejected (Lost Update prevented)"
        assert "conflict" in write_b.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sequential_writes_succeed():
    """After a 409, the client re-fetches and retries with the new version — should succeed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Alice writes
        await client.put("/documents/doc1", json={"content": "Alice's", "version": 1})
        # Bob re-fetches (version is now 2) and retries
        r = await client.put("/documents/doc1", json={"content": "Bob's retry", "version": 2})
    assert r.status_code == 200
    assert r.json()["new_version"] == 3


# ─────────────────────────────────────────────
# Problem 2: Idempotent Webhook Handler
# ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_webhook_cancels_subscription():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/webhooks/clerk", json={
            "event": "subscription.cancelled",
            "user_id": "user_alice",
            "idempotency_key": "evt-001"
        })
    assert r.status_code == 200
    assert r.json()["status"] == "processed"
    assert user_subscriptions["user_alice"] == "free"


@pytest.mark.asyncio
async def test_duplicate_webhook_is_idempotent():
    """
    If the network retries the same webhook (same idempotency_key),
    it must NOT double-process. The subscription stays 'free', not toggled.
    """
    payload = {
        "event": "subscription.cancelled",
        "user_id": "user_alice",
        "idempotency_key": "evt-002"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post("/webhooks/clerk", json=payload)
        assert r1.json()["status"] == "processed"

        # Simulate network retry — exact same payload
        r2 = await client.post("/webhooks/clerk", json=payload)
        assert r2.json()["status"] == "already_processed", \
            "Duplicate webhook must be safely ignored"

    # Subscription correctly downgraded exactly once
    assert user_subscriptions["user_alice"] == "free"


@pytest.mark.asyncio
async def test_dropped_webhook_causes_state_mismatch():
    """
    Demonstrate the BUG: without idempotency, a dropped webhook leaves the
    user permanently premium. Here we verify the fix works correctly when
    the key is NOT in the processed set (i.e., first delivery).
    """
    assert user_subscriptions["user_alice"] == "premium"  # starts premium
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/webhooks/clerk", json={
            "event": "subscription.cancelled",
            "user_id": "user_alice",
            "idempotency_key": "evt-003"
        })
    assert user_subscriptions["user_alice"] == "free"     # now correctly downgraded


# ─────────────────────────────────────────────
# Problem 3: Circuit Breaker
# ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_llm_works_normally():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/llm/ask", json={"prompt": "Explain recursion"})
    assert r.status_code == 200
    assert r.json()["source"] == "llm"


@pytest.mark.asyncio
async def test_circuit_trips_after_failures_and_returns_fallback():
    """
    Simulate the LLM being down. After failure_threshold failures,
    the circuit should OPEN and subsequent calls must return fallback
    WITHOUT waiting on the LLM at all (fast-fail).
    """
    main_module.LLM_IS_DOWN = True
    llm_breaker.request_timeout = 0.05   # 50ms so test is fast

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Fire enough requests to trip the breaker
        for i in range(llm_breaker.failure_threshold):
            r = await client.post("/llm/ask", json={"prompt": f"query {i}"})
            assert r.json()["source"] == "fallback", f"Request {i} should return fallback"

        assert llm_breaker.state == main_module.CircuitState.OPEN, \
            "Circuit should be OPEN after repeated failures"

        # Once tripped: fast-fail without hitting the LLM
        import time
        start = time.time()
        r = await client.post("/llm/ask", json={"prompt": "any"})
        elapsed = time.time() - start

        assert r.json()["source"] == "fallback"
        assert elapsed < 0.5, f"Tripped circuit should fast-fail, took {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_circuit_recovers_after_timeout():
    """
    After recovery_timeout seconds, circuit moves to HALF_OPEN and
    a successful probe closes it again.
    """
    # Manually trip the breaker
    llm_breaker.state = main_module.CircuitState.OPEN
    llm_breaker.failure_count = llm_breaker.failure_threshold
    llm_breaker.last_failure_time = 0.0   # expired immediately
    llm_breaker.request_timeout = 5.0     # restore normal timeout
    main_module.LLM_IS_DOWN = False       # LLM is healthy again

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/llm/ask", json={"prompt": "recovery probe"})

    assert r.json()["source"] == "llm", "After recovery timeout, probe should succeed"
    assert llm_breaker.state == main_module.CircuitState.CLOSED, \
        "Successful probe should CLOSE the circuit"


@pytest.mark.asyncio
async def test_before_fix_server_would_block():
    """
    Demonstrates what happens WITHOUT the circuit breaker:
    every call blocks for the full timeout duration.
    With the breaker, after tripping, calls return instantly.
    """
    import time
    llm_breaker.request_timeout = 0.1   # 100ms timeout for speed
    main_module.LLM_IS_DOWN = True

    # Trip the breaker
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(llm_breaker.failure_threshold):
            await client.post("/llm/ask", json={"prompt": "trigger"})

        # Now every subsequent call fast-fails < 10ms
        start = time.time()
        for _ in range(5):
            r = await client.post("/llm/ask", json={"prompt": "fast-fail test"})
            assert r.json()["source"] == "fallback"
        elapsed = time.time() - start

    assert elapsed < 0.3, \
        f"5 post-trip calls should be near-instant, took {elapsed:.2f}s (no timeout waits)"