
Claude finished the response
Assignment-4.pdf
pdf

solve

1:08 AM
I'll read the assignment carefully and produce a complete solution for all three parts.


Viewed 2 files
Viewed 2 files
Now let me build everything: the FastAPI code, tests, and the PDF report.


Ran 4 commands, created 4 files, edited 2 files
Ran 4 commands, created 4 files, edited 2 files
All 12 tests pass. Now let's build the PDF report.


Ran 3 commands, edited 2 files, created a file
Ran 3 commands, edited 2 files, created a file
Now create the README:


README for the GitHub repo
README for the GitHub repo
Now copy the code files to outputs:


Ran a command, read a file
Ran a command, read a file
Here's everything you need, all 12 tests passing ✅

What was built
📄 PDF Report (3 pages, Parts 1 & 2)
Part 1 — Root-Cause Analysis:

Problem 1: Blind UPDATE with no version check → Lost Update anomaly in the DB write path
Problem 2: No idempotency store → dropped or retried Clerk webhooks leave user in wrong tier forever
Problem 3: Synchronous LLM call with no timeout → hung coroutines exhaust the worker pool
Part 2 — Architecture + Diagram:

Optimistic Locking: version column + UPDATE WHERE version=:v + 409 Conflict; full UML sequence diagram included
Idempotent Webhooks: idempotency_key checked against a processed-events store (atomic DB insert); failures go to a dead-letter queue
Circuit Breaker: 3-state FSM (CLOSED → OPEN → HALF_OPEN) with asyncio.wait_for timeout and a degraded fallback response
CAP trade-offs table comparing all three fixes
💻 Code (main.py) — All Three Problems Implemented
Endpoint	Pattern
PUT /documents/{id}	Optimistic locking — 409 if version stale
POST /webhooks/clerk	Idempotency key check — ignores duplicates
POST /llm/ask	Circuit breaker — fast-fails when tripped
Every response	X-Student-ID header via middleware
🧪 Tests (test_main.py) — 12/12 Pass
Covers middleware header, concurrent write conflict, duplicate webhook, circuit trip & recovery, fast-fail timing.

Before submitting: replace STUDENT_ID = "2023-CS-001" with your actual ID, and update your name/ID in the README and PDF header.


Assignment4 report
Document · PDF 

Main
PY 

Test main
PY 

Readme
Document · MD 
can i test this on vs code windows?

1:20 AM
Yes! Here's exactly how to do it on Windows VS Code:

Setup Steps
1. Clone / copy the files Put main.py, test_main.py, and README.md into a folder, e.g. C:\studysync\ with this structure:

studysync/
├── app/
│   ├── __init__.py   (empty file)
│   └── main.py
└── tests/
    ├── __init__.py   (empty file)
    └── test_main.py
2. Open in VS Code

code C:\studysync
3. Create a virtual environment (in VS Code terminal)

bash
python -m venv venv
venv\Scripts\activate
4. Install dependencies

bash
pip install fastapi uvicorn httpx pytest pytest-asyncio anyio starlette
5. Run the server

bash
uvicorn app.main:app --reload
Open http://localhost:8000/docs in your browser — you'll see the Swagger UI for all endpoints.

6. Run the tests (new terminal, same folder)

bash
venv\Scripts\activate
python -m pytest tests/ -v --asyncio-mode=auto
You should see 12 passed.

VS Code Tips
Install the Python and Pylance extensions for autocomplete
Install the REST Client extension to test endpoints directly from a .http file without Postman
The integrated terminal works perfectly — use Ctrl+``  to open it
For the Demo Video
You can use this flow:

Start the server in one terminal
In a second terminal, run the curl commands from the README (or use the Swagger UI at /docs)
Show the before (e.g. 409 on stale write, or circuit returning fallback) and after side by side
Windows curl works fine for this, or you can install Postman for a cleaner screen recording.

how do u create repo on github and connect to your project

1:24 AM
Here's the full step-by-step:

1. Install Git (if not already)
Download from git-scm.com/download/win → install with defaults.

Verify:

bash
git --version
2. Configure Git (one-time setup)
bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
3. Create the Repo on GitHub
Go to github.com → click the + button → New repository
Name it exactly: PDC-Sp24-[Your-ID]-[Your-LastName] (assignment requirement)
Set to Public
Don't check "Add README" (you already have one)
Click Create repository
GitHub will show you a page with setup commands — keep it open.

4. Connect Your Local Project to GitHub
In VS Code terminal, inside your studysync/ folder:

bash
# Initialize git
git init

# Stage all files
git add .

# First commit
git commit -m "Initial commit - PDC Assignment 4"

# Rename branch to main
git branch -M main

# Connect to your GitHub repo (paste YOUR repo URL)
git remote add origin https://github.com/YOUR-USERNAME/PDC-Sp24-2023-CS-XXX-YourName.git

# Push
git push -u origin main
5. Verify
Refresh your GitHub repo page — all your files should be there.

Day-to-Day Workflow After That
Whenever you make changes:

bash
git add .
git commit -m "describe what you changed"
git push
VS Code Shortcut (GUI instead of commands)
VS Code has built-in Git — no terminal needed after setup:

Click the Source Control icon on the left sidebar (branching icon)
It shows changed files → type a commit message → click Commit → click Sync/Push
You can also do the very first repo connection through VS Code: Ctrl+Shift+P → type "Publish to GitHub" → it handles everything automatically including creating the repo.

git config --global user.name "Your Name"
git config --global user.email "your@email.com"

where do i check this from

1:26 AM
You check it from your GitHub account:

Name
Go to: github.com → click your profile picture → Settings → Public profile

Your name is whatever you want Git to label your commits with — it doesn't have to match GitHub exactly, but it's good practice to use the same name.

Email
Go to: github.com → Settings → Emails

Use the email shown there. If you see something like 12345678+username@users.noreply.github.com — use that one, it's GitHub's privacy email and it works fine.

So for example:

bash
git config --global user.name "Saleha Khan"
git config --global user.email "12345678+saleha@users.noreply.github.com"
To verify it was set correctly:

bash
git config --global --list
You'll see your name and email printed out.

PS D:\saleha\semester_six\pdc\asm_4> git config --global --list
core.editor="C:\Users\saleha\AppData\Local\Programs\Microsoft VS Code\bin\code" --wait
user.name=artie
user.email=abidsaleha05@gmail.com

1:27 AM
You're all set! Your git is already configured with:

Name: artie
Email: abidsaleha05@gmail.com
You don't need to change anything. Just move on to the next step — initialize the repo and push:

bash
git init
git add .
git commit -m "Initial commit - PDC Assignment 4"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/PDC-Sp24-2023-CS-XXX-YourName.git
git push -u origin main
Replace YOUR-USERNAME and the repo name with your actual GitHub username and student ID. You can copy the exact URL from the GitHub page you created the repo on.



Want to be notified when Claude responds?




Claude is AI and can make mistakes. Please double-check responses.


normal
Readme · MD
Saleha | 2023-CS-XXX

PDC-Sp24-2023-CS-XXX-Saleha
Course: Parallel and Distributed Computing (CS-300) — BSCS-23
Assignment: 4 — Building Resilient Distributed Systems

What's in this repo
File/Folder	Purpose
app/main.py	FastAPI application — all three fixes + X-Student-ID middleware
tests/test_main.py	12 pytest tests covering all problems
build_pdf.py	Script that generated the PDF report
Problems Solved
#	Problem	Pattern
1	Lost Update (concurrent document edits)	Optimistic Locking via version numbers
2	Dropped Clerk webhook (user stays premium)	Idempotency Keys + dead-letter log
3	Synchronous LLM hangs entire server	Circuit Breaker (CLOSED/OPEN/HALF_OPEN) + Fallback
Every response includes the X-Student-ID: 2023-CS-XXX header via FastAPI middleware.

How to Run
1. Install dependencies
bash
pip install fastapi uvicorn httpx pytest pytest-asyncio anyio
2. Start the server
bash
uvicorn app.main:app --reload
Server runs at http://localhost:8000. Swagger UI at http://localhost:8000/docs.

3. Run tests
bash
python -m pytest tests/ -v --asyncio-mode=auto
Expected: 12 passed.

Quick Demo (curl)
bash
# Check header
curl -I http://localhost:8000/
# → X-Student-ID: 2023-CS-XXX

# Optimistic locking — first write wins
curl -X PUT http://localhost:8000/documents/doc1 \
     -H "Content-Type: application/json" \
     -d '{"content":"Alice edit","version":1}'   # → 200

curl -X PUT http://localhost:8000/documents/doc1 \
     -H "Content-Type: application/json" \
     -d '{"content":"Bob stale","version":1}'    # → 409 Conflict

# Webhook idempotency
curl -X POST http://localhost:8000/webhooks/clerk \
     -H "Content-Type: application/json" \
     -d '{"event":"subscription.cancelled","user_id":"user_alice","idempotency_key":"evt-001"}'
# → processed

# Same payload again (retry simulation)
curl -X POST http://localhost:8000/webhooks/clerk \
     -H "Content-Type: application/json" \
     -d '{"event":"subscription.cancelled","user_id":"user_alice","idempotency_key":"evt-001"}'
# → already_processed

# Circuit breaker — trip it
curl -X POST http://localhost:8000/llm/simulate-outage?enable=true
curl -X POST http://localhost:8000/llm/ask -H "Content-Type: application/json" \
     -d '{"prompt":"test"}'   # → fallback after timeout (repeats 3× to trip)
curl http://localhost:8000/llm/circuit-status  # → OPEN
