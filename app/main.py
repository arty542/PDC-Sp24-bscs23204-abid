"""
StudySync Backend - PDC Assignment 4
Implements: Circuit Breaker (Problem 3 — Fault Tolerance)
Custom middleware adds X-Student-ID header to every response.
"""

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from enum import Enum
import asyncio
import time

app = FastAPI(title="StudySync API")

# ─────────────────────────────────────────────
# MIDDLEWARE  →  X-Student-ID on every response
# ─────────────────────────────────────────────
STUDENT_ID = "bscs23204"

class StudentIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Student-ID"] = STUDENT_ID
        return response

app.add_middleware(StudentIDMiddleware)


# ─────────────────────────────────────────────
# PROBLEM 3 — CIRCUIT BREAKER FOR LLM API
# ─────────────────────────────────────────────
class CircuitState(str, Enum):
    CLOSED    = "CLOSED"     # normal — requests pass through
    OPEN      = "OPEN"       # tripped — fast-fail with fallback
    HALF_OPEN = "HALF_OPEN"  # testing recovery

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 10.0,  # seconds before trying HALF_OPEN
        request_timeout: float = 5.0,    # seconds before a call counts as failure
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.request_timeout   = request_timeout
        self.failure_count     = 0
        self.last_failure_time = 0.0
        self.state             = CircuitState.CLOSED

    def _trip(self):
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()

    def _reset(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True   # let one probe through
            return False      # still tripped — fast-fail
        return True           # HALF_OPEN: allow the probe

    def record_success(self):
        self._reset()

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self._trip()


# Singleton breaker shared across all requests
llm_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10, request_timeout=2)

async def _call_llm_api(prompt: str) -> str:
    """Simulates a healthy LLM — responds quickly."""
    await asyncio.sleep(0.1)
    return f"LLM response to: '{prompt}'"

async def _call_llm_api_broken(prompt: str) -> str:
    """Simulates a down LLM — hangs for 60 seconds."""
    await asyncio.sleep(60)
    return "never reached"

# Toggle via /llm/simulate-outage
LLM_IS_DOWN = False


@app.post("/llm/ask")
async def ask_llm(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")

    # Circuit is OPEN — fast-fail immediately, no LLM call
    if not llm_breaker.allow_request():
        return {
            "source": "fallback",
            "circuit_state": llm_breaker.state,
            "answer": "Our AI assistant is temporarily unavailable. Please try again in a moment.",
        }

    try:
        call = _call_llm_api_broken if LLM_IS_DOWN else _call_llm_api
        result = await asyncio.wait_for(call(prompt), timeout=llm_breaker.request_timeout)
        llm_breaker.record_success()
        return {
            "source": "llm",
            "circuit_state": llm_breaker.state,
            "answer": result,
        }
    except (asyncio.TimeoutError, Exception) as exc:
        llm_breaker.record_failure()
        return {
            "source": "fallback",
            "circuit_state": llm_breaker.state,
            "failure_count": llm_breaker.failure_count,
            "answer": "Our AI assistant is temporarily unavailable. Please try again in a moment.",
            "error": str(exc),
        }


@app.get("/llm/circuit-status")
def circuit_status():
    return {
        "state": llm_breaker.state,
        "failure_count": llm_breaker.failure_count,
        "failure_threshold": llm_breaker.failure_threshold,
        "recovery_timeout_seconds": llm_breaker.recovery_timeout,
    }


@app.post("/llm/simulate-outage")
def simulate_outage(enable: bool = True):
    """Toggle LLM outage for demo purposes."""
    global LLM_IS_DOWN
    LLM_IS_DOWN = enable
    return {"llm_is_down": LLM_IS_DOWN}


@app.get("/")
def root():
    return {"service": "StudySync API", "student_id": STUDENT_ID}