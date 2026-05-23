"""
Tests for StudySync PDC Assignment 4
Problem 3: Circuit Breaker (Fault Tolerance)
Also verifies X-Student-ID middleware header.
"""

import pytest
import time
from httpx import AsyncClient, ASGITransport
import app.main as main_module
from app.main import app, llm_breaker


@pytest.fixture(autouse=True)
def reset_state():
    """Reset circuit breaker state before every test."""
    llm_breaker.failure_count     = 0
    llm_breaker.state             = main_module.CircuitState.CLOSED
    llm_breaker.last_failure_time = 0.0
    llm_breaker.request_timeout   = 2.0
    main_module.LLM_IS_DOWN       = False


# ─────────────────────────────────────────────
# Middleware: X-Student-ID header
# ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_student_id_header_present():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
    assert "x-student-id" in r.headers, "X-Student-ID header must be on every response"
    assert r.headers["x-student-id"] == main_module.STUDENT_ID


# ─────────────────────────────────────────────
# Circuit Breaker Tests
# ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_llm_works_normally():
    """When LLM is healthy, requests go through and circuit stays CLOSED."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/llm/ask", json={"prompt": "Explain recursion"})
    assert r.status_code == 200
    assert r.json()["source"] == "llm"
    assert r.json()["circuit_state"] == "CLOSED"


@pytest.mark.asyncio
async def test_circuit_trips_after_threshold_failures():
    """
    BEFORE fix: server would block for 60s on every call.
    AFTER fix: after 3 failures the circuit trips to OPEN.
    """
    main_module.LLM_IS_DOWN       = True
    llm_breaker.request_timeout   = 0.05  # 50ms so test runs fast

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(llm_breaker.failure_threshold):
            r = await client.post("/llm/ask", json={"prompt": f"query {i}"})
            assert r.json()["source"] == "fallback", f"Call {i} should return fallback"

    assert llm_breaker.state == main_module.CircuitState.OPEN, \
        "Circuit must be OPEN after hitting failure threshold"


@pytest.mark.asyncio
async def test_open_circuit_fast_fails_without_waiting():
    """
    Once OPEN, calls must return instantly — no waiting for the LLM.
    This is the core protection: the server stops being blocked.
    """
    main_module.LLM_IS_DOWN     = True
    llm_breaker.request_timeout = 0.05

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trip the breaker
        for _ in range(llm_breaker.failure_threshold):
            await client.post("/llm/ask", json={"prompt": "trip"})

        # Now measure fast-fail speed
        start = time.time()
        for _ in range(5):
            r = await client.post("/llm/ask", json={"prompt": "fast-fail"})
            assert r.json()["source"] == "fallback"
        elapsed = time.time() - start

    assert elapsed < 0.3, \
        f"5 fast-fail calls took {elapsed:.2f}s — should be near-instant"


@pytest.mark.asyncio
async def test_circuit_recovers_when_llm_healthy_again():
    """
    After recovery_timeout expires, circuit goes HALF_OPEN.
    A successful probe resets it back to CLOSED.
    """
    # Manually set to OPEN with an expired timer
    llm_breaker.state             = main_module.CircuitState.OPEN
    llm_breaker.failure_count     = llm_breaker.failure_threshold
    llm_breaker.last_failure_time = 0.0   # immediately expired
    llm_breaker.request_timeout   = 5.0
    main_module.LLM_IS_DOWN       = False  # LLM is healthy again

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/llm/ask", json={"prompt": "recovery probe"})

    assert r.json()["source"] == "llm", "Probe should reach the LLM after recovery timeout"
    assert llm_breaker.state == main_module.CircuitState.CLOSED, \
        "Successful probe must close the circuit"


@pytest.mark.asyncio
async def test_fallback_message_is_user_friendly():
    """Fallback response must be a readable message, not an error dump."""
    main_module.LLM_IS_DOWN     = True
    llm_breaker.request_timeout = 0.05

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/llm/ask", json={"prompt": "anything"})

    assert "answer" in r.json()
    assert len(r.json()["answer"]) > 10  # not empty


@pytest.mark.asyncio
async def test_circuit_status_endpoint():
    """The /llm/circuit-status endpoint must expose breaker state."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/llm/circuit-status")
    data = r.json()
    assert "state" in data
    assert "failure_count" in data
    assert "failure_threshold" in data