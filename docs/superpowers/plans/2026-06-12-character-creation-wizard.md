# Character Creation Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved structured character creation wizard and synchronize structured choices and validation failures with the chat agent.

**Architecture:** Add a backend guide service that exposes localized step options from the PHB repository and a structured mutation path that records sync messages in the existing character creation session. The frontend renders a wizard panel next to the existing chat panel and drives the existing session through structured API calls.

**Tech Stack:** FastAPI, Pydantic, SQLite session store, existing PHB rule repository, vanilla ES modules, Node-based frontend tests, pytest.

---

## File Structure

- `backend/src/schemas/character_creation.py`: add response models for wizard guide data and structured mutation outcomes.
- `backend/src/services/character_creation_guide.py`: create a focused service that builds step metadata and options from `PHBRuleRepository`.
- `backend/src/services/character_drafts.py`: add guide retrieval and structured mutation sync behavior.
- `backend/src/api/character_creation.py`: add guide endpoint and return structured mutation failures as sessions instead of bare API errors where possible.
- `frontend/static/index.html`: add a structured wizard mount point.
- `frontend/static/js/state.js`: bind the new wizard mount element.
- `frontend/static/js/character-creation.js`: render wizard steps, call guide/mutation APIs, and keep chat messages in sync.
- `frontend/static/styles.css`: style step rail, option cards, counters, and compact ability controls.
- `backend/test/test_character_creation_wizard.py`: backend behavior tests.
- `backend/test/test_frontend_character_creation.py`: frontend rendering/sync tests.

## Tasks

### Task 1: Backend Guide Data

**Files:**
- Modify: `backend/src/schemas/character_creation.py`
- Create: `backend/src/services/character_creation_guide.py`
- Modify: `backend/src/api/character_creation.py`
- Test: `backend/test/test_character_creation_wizard.py`

- [ ] **Step 1: Write failing backend guide test**

Create a test that starts a session and requests guide data. Assert the first active step contains identity metadata, and that class options include `class.wizard` with localized labels.

- [ ] **Step 2: Run red test**

Run: `uv run pytest -q backend/test/test_character_creation_wizard.py::test_character_creation_guide_exposes_current_step_options`

Expected: fail because the guide endpoint/service does not exist.

- [ ] **Step 3: Implement guide models and service**

Add guide response models and a service that returns ordered steps plus localized option cards for identity, class, race, background, abilities, spells, and review.

- [ ] **Step 4: Add guide endpoint**

Add `GET /api/character-creation/sessions/{session_id}/guide`.

- [ ] **Step 5: Run green test**

Run: `uv run pytest -q backend/test/test_character_creation_wizard.py::test_character_creation_guide_exposes_current_step_options`

Expected: pass.

### Task 2: Structured Mutation Chat Sync

**Files:**
- Modify: `backend/src/services/character_drafts.py`
- Modify: `backend/src/api/character_creation.py`
- Test: `backend/test/test_character_creation_wizard.py`

- [ ] **Step 1: Write failing success-sync test**

Patch a session draft through the structured mutation endpoint and assert:

- The draft changed.
- A synthetic user message was recorded.
- An assistant sync message was recorded.
- The returned session includes the sync assistant message.

- [ ] **Step 2: Write failing validation-sync test**

Submit invalid ability scores through structured mutation and assert:

- The draft revision did not advance.
- Validation errors are returned.
- The assistant message explains the validation failure.
- The failed attempt is present in message history.

- [ ] **Step 3: Run red tests**

Run: `uv run pytest -q backend/test/test_character_creation_wizard.py`

Expected: fail because mutation does not append sync messages and failures are still API errors.

- [ ] **Step 4: Implement structured mutation sync**

Update `CharacterDraftService.mutate` so successful structured changes append user/assistant sync messages. Add a failure path that catches validation `ValueError`, appends attempted-choice and assistant failure messages, and returns the unchanged session with validation errors.

- [ ] **Step 5: Run green tests**

Run: `uv run pytest -q backend/test/test_character_creation_wizard.py`

Expected: pass.

### Task 3: Frontend Wizard Rendering

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/js/state.js`
- Modify: `frontend/static/js/character-creation.js`
- Test: `backend/test/test_frontend_character_creation.py`

- [ ] **Step 1: Write failing frontend rendering test**

Use a DOM stub to import `character-creation.js`, seed a session and guide payload, call `renderCharacterCreation`, and assert option card text for Wizard/Race/Background appears in the wizard mount.

- [ ] **Step 2: Run red test**

Run: `uv run pytest -q backend/test/test_frontend_character_creation.py`

Expected: fail because no wizard mount/rendering exists.

- [ ] **Step 3: Implement wizard mount and renderers**

Add `#character-wizard` in the character draft panel, bind it in `state.js`, and render step rail, active prompt, choices, counts, and validation hints.

- [ ] **Step 4: Run green test**

Run: `uv run pytest -q backend/test/test_frontend_character_creation.py`

Expected: pass.

### Task 4: Frontend Structured Actions

**Files:**
- Modify: `frontend/static/js/character-creation.js`
- Test: `backend/test/test_frontend_character_creation.py`

- [ ] **Step 1: Write failing action-sync test**

Simulate clicking a class option. Assert the frontend calls `PATCH /api/character-creation/sessions/{id}/draft`, updates `state.characterCreationSession`, and appends the returned assistant message to chat.

- [ ] **Step 2: Run red test**

Run: `uv run pytest -q backend/test/test_frontend_character_creation.py`

Expected: fail because option cards are not interactive.

- [ ] **Step 3: Implement action handlers**

Map guide step kinds to existing mutation operations and payloads. On success, update session and chat. On returned validation errors, keep the session and show assistant explanation.

- [ ] **Step 4: Run green test**

Run: `uv run pytest -q backend/test/test_frontend_character_creation.py`

Expected: pass.

### Task 5: Styling and Verification

**Files:**
- Modify: `frontend/static/styles.css`

- [ ] **Step 1: Add CSS for wizard controls**

Add responsive styles for step rail, option cards, selection counters, spell grouping, and point-buy controls.

- [ ] **Step 2: Run full automated tests**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Restart service**

Restart uvicorn on `127.0.0.1:5001`.

- [ ] **Step 4: Browser sanity check**

Open `http://127.0.0.1:5001`, create a character session, confirm the wizard shows choices and chat sync messages appear after a structured choice.
