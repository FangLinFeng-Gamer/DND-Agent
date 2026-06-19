# LLM DM Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable OpenAI-compatible model settings, a model-backed DM Agent with offline fallback, context summarization, important world-event persistence, and a localized frontend model configuration page.

**Architecture:** Keep `DMService` as the orchestration boundary and add focused services for model config, model HTTP calls, context packing, and world events. The static frontend follows the existing view/state/i18n pattern and calls new `/api/models` endpoints.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, static HTML/CSS/JavaScript, standard-library `urllib.request` for OpenAI-compatible HTTP.

---

### Task 1: Model Config Storage and API

**Files:**
- Modify: `backend/src/db/sqlite.py`
- Create: `backend/src/schemas/llm.py`
- Create: `backend/src/services/llm_models.py`
- Create: `backend/src/api/models.py`
- Modify: `backend/src/main.py`
- Test: `test/test_llm_models.py`

- [ ] **Step 1: Write failing tests**

Add tests that create a model, verify masked API key output, update the model, activate it, and ensure activation is exclusive.

Run: `uv run pytest test/test_llm_models.py -q`

Expected: FAIL because `/api/models` does not exist.

- [ ] **Step 2: Implement schema and service**

Create Pydantic models with `provider="openai_compatible"`, key masking, and update validation. Add `llm_models` table to SQLite.

- [ ] **Step 3: Implement API router**

Expose:

- `GET /api/models`
- `POST /api/models`
- `PATCH /api/models/{model_id}`
- `DELETE /api/models/{model_id}`
- `POST /api/models/{model_id}/activate`

- [ ] **Step 4: Verify and commit**

Run:

```powershell
uv run pytest test/test_llm_models.py -q
```

Expected: all tests in `test_llm_models.py` pass.

Commit:

```powershell
git add backend/src/db/sqlite.py backend/src/schemas/llm.py backend/src/services/llm_models.py backend/src/api/models.py backend/src/main.py test/test_llm_models.py
git commit -m "feat: add llm model configuration api"
```

### Task 2: World Events and Context Summary

**Files:**
- Modify: `backend/src/db/sqlite.py`
- Create: `backend/src/schemas/world_event.py`
- Create: `backend/src/services/world_events.py`
- Create: `backend/src/services/context.py`
- Modify: `backend/src/services/adventures.py`
- Test: `test/test_context_world_events.py`

- [ ] **Step 1: Write failing tests**

Add tests that persist important world events for an adventure and update `adventures.summary` when estimated context exceeds a low token limit.

Run: `uv run pytest test/test_context_world_events.py -q`

Expected: FAIL because world-event and context services do not exist.

- [ ] **Step 2: Implement world event storage**

Add `world_events` table and service methods:

- `create(adventure_id, event)`
- `list_for_adventure(adventure_id, min_importance=0)`

- [ ] **Step 3: Implement context service**

Add `ContextService.estimate_tokens()`, `build_context()`, and `summarize_if_needed()` using adventure summary, recent messages, scene, character, story snapshot, and important world events.

- [ ] **Step 4: Verify and commit**

Run:

```powershell
uv run pytest test/test_context_world_events.py -q
```

Expected: all tests in `test_context_world_events.py` pass.

Commit:

```powershell
git add backend/src/db/sqlite.py backend/src/schemas/world_event.py backend/src/services/world_events.py backend/src/services/context.py backend/src/services/adventures.py test/test_context_world_events.py
git commit -m "feat: add adventure context tracking"
```

### Task 3: Model-Backed DM Agent

**Files:**
- Create: `backend/src/services/llm_client.py`
- Modify: `backend/src/services/dm.py`
- Modify: `backend/src/schemas/adventure.py`
- Test: `test/test_dm_agent.py`

- [ ] **Step 1: Write failing tests**

Add tests for a fake model response that:

- Requests a Wisdom check.
- Updates the scene.
- Persists an important world event.
- Falls back to template narration when the model client raises an exception.

Run: `uv run pytest test/test_dm_agent.py -q`

Expected: FAIL because model-backed DM provider and event persistence are missing.

- [ ] **Step 2: Implement OpenAI-compatible client**

Use `urllib.request` to POST to `{base_url.rstrip("/")}/chat/completions` with `Authorization: Bearer <api_key>`, messages, model, temperature, and JSON response request.

- [ ] **Step 3: Implement structured DM provider**

Build prompts from context and parse JSON response into:

- narration
- scene
- check
- npc actions
- world events

Server rolls any requested ability check using `CombatService.roll_check()` and stores the result in message metadata.

- [ ] **Step 4: Wire provider into DMService**

When an active model exists, call the model-backed path. If no active model exists or the call fails, call `TemplateDMProvider`.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
uv run pytest test/test_dm_agent.py -q
```

Expected: all tests in `test_dm_agent.py` pass.

Commit:

```powershell
git add backend/src/services/llm_client.py backend/src/services/dm.py backend/src/schemas/adventure.py test/test_dm_agent.py
git commit -m "feat: connect dm agent to active model"
```

### Task 4: Localized Frontend Model Page

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/app.js`
- Modify: `frontend/static/styles.css`
- Modify: `test/test_frontend_i18n.py`
- Create: `test/test_frontend_models_ui.py`

- [ ] **Step 1: Write failing tests**

Add tests that verify:

- A `model-config-view` exists.
- Navigation includes a localized Models button.
- `app.js` calls `/api/models`.
- New model-page i18n keys exist in English and Chinese.
- Existing Chinese translations use real UTF-8 Chinese text, not mojibake.

Run: `uv run pytest test/test_frontend_models_ui.py test/test_frontend_i18n.py -q`

Expected: FAIL because the page and keys do not exist.

- [ ] **Step 2: Implement HTML view**

Add the Models nav button and a model configuration page with list, edit form, and action buttons.

- [ ] **Step 3: Implement JavaScript state and API calls**

Add `models`, `selectedModelId`, `editingModelId`, `loadModels()`, `saveModel()`, `editModel()`, `activateModel()`, `deleteModel()`, `resetModelForm()`, and `renderModelList()`.

- [ ] **Step 4: Add localized strings**

Add English and Chinese translations for every new visible string and fix existing Chinese mojibake strings.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
uv run pytest test/test_frontend_models_ui.py test/test_frontend_i18n.py -q
node --check frontend/static/app.js
```

Expected: frontend tests pass and JavaScript syntax check exits 0.

Commit:

```powershell
git add frontend/static/index.html frontend/static/app.js frontend/static/styles.css test/test_frontend_i18n.py test/test_frontend_models_ui.py
git commit -m "feat: add localized model settings page"
```

### Task 5: Full Regression and Runtime Smoke

**Files:**
- No planned source changes unless verification exposes defects.

- [ ] **Step 1: Run full automated verification**

Run:

```powershell
uv run pytest -q
node --check frontend/static/app.js
```

Expected: pytest exits 0 and JavaScript syntax check exits 0.

- [ ] **Step 2: Run API smoke flow**

Start the service if needed:

```powershell
uv run python -m backend.src.main
```

Smoke:

- `GET /`
- `POST /api/models`
- `GET /api/models`
- `POST /api/characters`
- `POST /api/adventures`
- `POST /api/adventures/{id}/messages`

Expected: all API calls return 2xx, and adventure messaging remains playable without an active model.

- [ ] **Step 3: Commit verification fixes if needed**

If smoke exposes defects, add regression tests first, fix, rerun verification, and commit.
