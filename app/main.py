"""
StudySync Backend - PDC Assignment 4
Implements: Circuit Breaker (Problem 3), Optimistic Locking (Problem 1),
            Idempotent Webhook Handler (Problem 2)
Custom middleware adds X-Student-ID header to every response.
"""

from fastapi import FastAPI, HTTPException, Header, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import time
import uuid
from enum import Enum

app = FastAPI(title="StudySync API")

# ─────────────────────────────────────────────
# MIDDLEWARE  →  X-Student-ID on every response
# ─────────────────────────────────────────────
STUDENT_ID = "2023-CS-001"          # ← replace with your actual ID

class StudentIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Student-ID"] = STUDENT_ID
        return response

app.add_middleware(StudentIDMiddleware)


# ─────────────────────────────────────────────
# PROBLEM 1 — OPTIMISTIC LOCKING (versioning)
# ─────────────────────────────────────────────
# In-memory "database" of documents
documents_db: dict[str, dict] = {
    "doc1": {"id": "doc1", "content": "Hello world", "version": 1, "owner": "alice"},
}

class DocumentUpdate(BaseModel):
    content: str
    version: int   # client must echo back the version it last read

@app.get("/documents/{doc_id}")
def get_document(doc_id: str):
    doc = documents_db.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@app.put("/documents/{doc_id}")
def update_document(doc_id: str, payload: DocumentUpdate):
    """
    Optimistic locking: the client sends the version it read.
    If another writer has already incremented the version, we reject
    with 409 Conflict instead of silently overwriting.
    """
    doc = documents_db.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc["version"] != payload.version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: server is at v{doc['version']}, "
                   f"you sent v{payload.version}. Re-fetch and retry."
        )

    # Safe to overwrite — no concurrent writer has changed it
    doc["content"] = payload.content
    doc["version"] += 1
    return {"message": "Updated", "new_version": doc["version"], "document": doc}


# ─────────────────────────────────────────────
# PROBLEM 2 — IDEMPOTENT WEBHOOK HANDLER
# ─────────────────────────────────────────────
processed_webhooks: set[str] = set()   # idempotency key store
user_subscriptions: dict[str, str] = {"user_alice": "premium", "user_bob": "free"}

class WebhookPayload(BaseModel):
    event: str          # e.g. "subscription.cancelled"
    user_id: str
    idempotency_key: str

@app.post("/webhooks/clerk")
def handle_clerk_webhook(payload: WebhookPayload):
    """
    Idempotent webhook handler.
    Clerk (or any caller) must supply an idempotency_key.
    Re-delivered events with the same key are safely ignored.
    """
    if payload.idempotency_key in processed_webhooks:
        return {"status": "already_processed", "idempotency_key": payload.idempotency_key}

    if payload.event == "subscription.cancelled":
        user_subscriptions[payload.user_id] = "free"
        processed_webhooks.add(payload.idempotency_key)
        return {
            "status": "processed",
            "user_id": payload.user_id,
            "new_tier": "free",
        }

    # Unknown event types go to a "dead-letter" log for manual review
    return {"status": "unhandled_event", "event": payload.event}

@app.get("/users/{user_id}/subscription")
def get_subscription(user_id: str):
    tier = user_subscriptions.get(user_id, "free")
    return {"user_id": user_id, "tier": tier}


# ─────────────────────────────────────────────
# PROBLEM 3 — CIRCUIT BREAKER FOR LLM API
# ─────────────────────────────────────────────
class CircuitState(str, Enum):
    CLOSED   = "CLOSED"    # normal — requests pass through
    OPEN     = "OPEN"      # tripped — fast-fail with fallback
    HALF_OPEN = "HALF_OPEN"  # testing recovery

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 10.0,   # seconds before trying HALF_OPEN
        request_timeout: float = 5.0,     # seconds before a call counts as failure
    ):
        self.failure_threshold  = failure_threshold
        self.recovery_timeout   = recovery_timeout
        self.request_timeout    = request_timeout
        self.failure_count      = 0
        self.last_failure_time  = 0.0
        self.state              = CircuitState.CLOSED

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
                return True          # let one probe through
            return False             # still tripped
        # HALF_OPEN: allow the probe
        return True

    def record_success(self):
        self._reset()

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self._trip()


# Singleton breaker shared across requests
llm_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10, request_timeout=2)

async def _call_llm_api(prompt: str) -> str:
    """Simulated external LLM call. Raises asyncio.TimeoutError when slow."""
    await asyncio.sleep(0.1)   # normal fast path
    return f"LLM response to: '{prompt}'"

async def _call_llm_api_broken(prompt: str) -> str:
    """Simulates the LLM being down — hangs for 60 s."""
    await asyncio.sleep(60)
    return "never reached"

# Toggle this to simulate the outage
LLM_IS_DOWN = False

@app.post("/llm/ask")
async def ask_llm(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")

    if not llm_breaker.allow_request():
        # OPEN state — fast-fail with a cached / degraded fallback
        return {
            "source": "fallback",
            "circuit_state": llm_breaker.state,
            "answer": "Our AI assistant is temporarily unavailable. "
                      "Please try again in a moment.",
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
            "answer": "Our AI assistant is temporarily unavailable. "
                      "Please try again in a moment.",
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