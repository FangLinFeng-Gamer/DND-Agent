# Streaming DM Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add streaming DM responses with visible frontend waiting state and one-at-a-time message handling per adventure.

**Architecture:** Keep the existing non-streaming `/messages` endpoint intact, and add a focused `/messages/stream` NDJSON endpoint. Backend streaming reuses `DMService` orchestration and adds an adventure lock manager plus OpenAI-compatible SSE parsing; frontend uses `fetch()` `ReadableStream` and a `dmBusy` flag to disable input before model output begins.

**Tech Stack:** FastAPI `StreamingResponse`, SQLite-backed services, pytest, static HTML/CSS/JavaScript, browser `ReadableStream`, OpenAI-compatible chat completion streaming.

---

### Task 1: Backend Streaming API and Lock

**Files:**
- Modify: `backend/src/api/adventures.py`
- Modify: `backend/src/services/dm.py`
- Create: `backend/src/services/adventure_locks.py`
- Test: `test/test_dm_streaming.py`

- [ ] **Step 1: Write failing tests**

Create `test/test_dm_streaming.py` with tests that call `POST /api/adventures/{id}/messages/stream`, read NDJSON lines, and assert that `status`, at least one `delta`, and `final` are emitted.

Also test lock behavior by acquiring the adventure lock directly and verifying the stream endpoint returns HTTP 409 with `dm_busy`.

Run: `uv run pytest test/test_dm_streaming.py -q`

Expected: FAIL because the stream endpoint and lock service do not exist.

- [ ] **Step 2: Implement lock service**

Create `AdventureLockService` with in-process `threading.Lock` instances keyed by adventure id and a non-blocking context manager that raises `dm_busy` if already locked.

- [ ] **Step 3: Implement stream endpoint**

Add `POST /api/adventures/{adventure_id}/messages/stream`, returning `StreamingResponse` with media type `application/x-ndjson`.

- [ ] **Step 4: Implement DM event generator**

Add `DMService.advance_stream()` that appends the player message once, emits status/player/delta/final events, and reuses existing scene persistence logic.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
uv run pytest test/test_dm_streaming.py -q
```

Expected: tests pass.

Commit:

```powershell
git add backend/src/api/adventures.py backend/src/services/dm.py backend/src/services/adventure_locks.py test/test_dm_streaming.py
git commit -m "feat: stream dm adventure responses"
```

### Task 2: OpenAI-Compatible Streaming Client

**Files:**
- Modify: `backend/src/services/llm_client.py`
- Test: `test/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

Add a test that mocks an SSE response with `data: {"choices":[{"delta":{"content":"..."}}]}` chunks and verifies `OpenAICompatibleClient.stream_chat()` yields text chunks.

Run: `uv run pytest test/test_llm_client.py -q`

Expected: FAIL because `stream_chat()` does not exist.

- [ ] **Step 2: Implement stream client**

Add `stream_chat(model, messages)` that sends `stream: true`, reads SSE `data:` lines, yields `delta.content`, and stops on `[DONE]`.

- [ ] **Step 3: Wire into DM stream**

Use `stream_chat()` for active-model streaming, accumulate the full JSON response for final parsing, and fallback to chunked offline narration on errors.

- [ ] **Step 4: Verify and commit**

Run:

```powershell
uv run pytest test/test_llm_client.py test/test_dm_streaming.py -q
```

Expected: tests pass.

Commit:

```powershell
git add backend/src/services/llm_client.py backend/src/services/dm.py test/test_llm_client.py test/test_dm_streaming.py
git commit -m "feat: stream openai compatible dm output"
```

### Task 3: Frontend Busy State and Streaming Reader

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/app.js`
- Modify: `frontend/static/styles.css`
- Modify: `test/test_frontend_i18n.py`
- Create: `test/test_frontend_streaming_ui.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

- `/messages/stream` appears in `app.js`
- `dmBusy` appears in `app.js`
- send controls are disabled while busy
- typing indicator CSS exists
- English and Chinese busy strings exist

Run: `uv run pytest test/test_frontend_streaming_ui.py test/test_frontend_i18n.py -q`

Expected: FAIL because streaming UI is not implemented.

- [ ] **Step 2: Implement busy state**

Add `state.dmBusy`, `setDmBusy(isBusy)`, and guard `sendMessage()` so it returns while busy.

- [ ] **Step 3: Implement stream reading**

Change `sendMessage()` to call `/messages/stream`, parse NDJSON chunks from `response.body.getReader()`, update the pending DM message on `delta`, and apply the `final` state.

- [ ] **Step 4: Implement animation and localization**

Add typing indicator markup/classes and translations:

- `dmThinking`
- `dmStillResponding`
- `dmResponseFailed`

- [ ] **Step 5: Verify and commit**

Run:

```powershell
uv run pytest test/test_frontend_streaming_ui.py test/test_frontend_i18n.py -q
node --check frontend/static/app.js
```

Expected: tests pass and JavaScript syntax check exits 0.

Commit:

```powershell
git add frontend/static/index.html frontend/static/app.js frontend/static/styles.css test/test_frontend_i18n.py test/test_frontend_streaming_ui.py
git commit -m "feat: add streaming dm chat ui"
```

### Task 4: Full Regression and Runtime Smoke

**Files:**
- No planned source changes unless verification exposes a defect.

- [ ] **Step 1: Run full verification**

Run:

```powershell
uv run pytest -q
node --check frontend/static/app.js
```

Expected: all tests pass and JavaScript syntax check exits 0.

- [ ] **Step 2: Runtime smoke**

Restart the local service, create or select an adventure, send a message through `/messages/stream`, and verify NDJSON includes `status`, `delta`, and `final`.

- [ ] **Step 3: Commit fixes if required**

If smoke exposes a defect, add a failing regression test first, fix it, rerun verification, and commit.
