Saleha Abid | bscs23204

# PDC-Sp24-bscs23204-Abid

**Course:** Parallel and Distributed Computing
**Assignment:** 4 — Building Resilient Distributed Systems  
**Chosen Problem:** Problem 3 — Fault Tolerance (Circuit Breaker)

---

## Folder Structure

```
asm4/
├── app/
│   ├── __init__.py      ← empty file, must exist
│   └── main.py
└── tests/
    ├── __init__.py      ← empty file, must exist
    └── test_main.py
```

---

## What Was Built

The external LLM API sometimes goes down and takes 60 seconds to timeout.
Because FastAPI was waiting synchronously, the entire server would hang for everyone.

**Fix:** A Circuit Breaker with three states:

| State | When | Behaviour |
|---|---|---|
| CLOSED | Normal | Requests go through to the LLM |
| OPEN | After 3 failures | Fast-fail instantly, return fallback message |
| HALF_OPEN | After 10s recovery | Let one probe through to test if LLM is back |

Every response also includes the `X-Student-ID: bscs23204` header via FastAPI middleware.

---

## How to Run (Windows PowerShell)

### 1. Create and activate virtual environment

```powershell
python -m venv venv
venv\Scripts\activate
```

### 2. Install dependencies

```powershell
pip install fastapi uvicorn httpx pytest pytest-asyncio anyio starlette
```

### 3. Start the server

```powershell
uvicorn app.main:app --reload
```

Server: `http://localhost:8000`  
Swagger UI: `http://localhost:8000/docs`

### 4. Run tests (second terminal)

```powershell
venv\Scripts\activate
python -m pytest tests/ -v --asyncio-mode=auto
```

Expected: **7 passed**

---

## Demo Commands (Windows PowerShell)

Open a second PowerShell terminal while the server is running.

---

### Step 1 — Verify X-Student-ID header

```powershell
$response = Invoke-WebRequest -Uri http://localhost:8000/ -UseBasicParsing
$response.Headers["X-Student-ID"]
```

Expected output: `bscs23204`

---

### Step 2 — LLM works normally (circuit CLOSED)

```powershell
Invoke-RestMethod -Uri http://localhost:8000/llm/ask -Method POST -ContentType "application/json" -Body '{"prompt":"hello"}'
```

Expected:
```
source        : llm
circuit_state : CLOSED
answer        : LLM response to: 'hello'
```

---

### Step 3 — Simulate LLM going down

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/llm/simulate-outage?enable=true" -Method POST
```

Expected: `llm_is_down: True`

---

### Step 4 — Hit the LLM 3 times (trips the circuit breaker)

```powershell
Invoke-RestMethod -Uri http://localhost:8000/llm/ask -Method POST -ContentType "application/json" -Body '{"prompt":"test"}'
Invoke-RestMethod -Uri http://localhost:8000/llm/ask -Method POST -ContentType "application/json" -Body '{"prompt":"test"}'
Invoke-RestMethod -Uri http://localhost:8000/llm/ask -Method POST -ContentType "application/json" -Body '{"prompt":"test"}'
```

Watch `failure_count` go 1 → 2 → 3 and `circuit_state` flip to `OPEN` on the 3rd call.

---

### Step 5 — Check circuit is now OPEN

```powershell
Invoke-RestMethod -Uri http://localhost:8000/llm/circuit-status
```

Expected:
```
state             : OPEN
failure_count     : 3
failure_threshold : 3
```

---

### Step 6 — Further calls return fallback instantly (server no longer hangs)

```powershell
Invoke-RestMethod -Uri http://localhost:8000/llm/ask -Method POST -ContentType "application/json" -Body '{"prompt":"still broken"}'
```

Expected:
```
source        : fallback
circuit_state : OPEN
answer        : Our AI assistant is temporarily unavailable. Please try again in a moment.
```

Returns immediately — the server is protected and still serving other users.

---

### Step 7 — LLM recovers, circuit resets (wait 10 seconds first)

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/llm/simulate-outage?enable=false" -Method POST
```

Wait 10 seconds, then:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/llm/ask -Method POST -ContentType "application/json" -Body '{"prompt":"are you back"}'
```

Expected: `source: llm, circuit_state: CLOSED` — fully recovered.
