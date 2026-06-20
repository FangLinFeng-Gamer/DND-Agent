# World State Progression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add adventure-local world state progression so player actions can advance story pressure while status/rule/clarification questions do not.

**Architecture:** Store a compact `world_state` JSON object on each adventure, manage it through a focused `WorldStateService`, inject public state and pending deltas into DM prompts, and expose the public view through existing adventure and message APIs. The frontend renders a small world situation panel from the same payload.

**Tech Stack:** FastAPI, Pydantic, SQLite JSON columns, existing static ES modules, pytest, Node-based frontend smoke tests.

---

## File Structure

- Create `backend/src/services/world_state.py`: deterministic action classification, default story clocks, preview/commit progression, public view helpers.
- Modify `backend/src/db/sqlite.py`: add and migrate `adventures.world_state_json`.
- Modify `backend/src/schemas/adventure.py`: expose `world_state` on `AdventureOut` and `DMAdvanceResponse`.
- Modify `backend/src/services/adventures.py`: initialize, map, read, and save adventure world state.
- Modify `backend/src/agent/dm/prompts.py`: pass `world_state` and `action_classification` through `tool_context`.
- Modify `backend/src/agent/dm/service.py`: classify input, preview pending world delta, commit progression, include metadata and stream final world state.
- Modify `frontend/static/index.html`: add a compact world situation panel to the game room.
- Modify `frontend/static/js/state.js`: bind new DOM nodes.
- Modify `frontend/static/js/game.js`: render world state and update it from normal/streaming responses.
- Modify `frontend/static/js/locales/en.js` and `frontend/static/js/locales/zh-CN.js`: add world situation labels.
- Test with new backend tests in `test/backend/src/services/test_world_state.py`, API tests in `test/backend/src/api/test_world_state_progression.py`, prompt tests in `test/backend/src/agent/dm/test_dm_prompts.py`, and frontend static tests in `test/frontend/static/js/test_frontend_world_state.py`.

### Task 1: Backend Schema And Persistence

**Files:**
- Modify: `backend/src/db/sqlite.py`
- Modify: `backend/src/schemas/adventure.py`
- Modify: `backend/src/services/adventures.py`
- Create: `test/backend/src/api/test_world_state_progression.py`

- [ ] **Step 1: Write failing API tests**

Add tests asserting a new default-story adventure has `world_state.phase == "festival_evening"` and that two adventures have independent `world_state` objects.

Run: `uv run pytest test/backend/src/api/test_world_state_progression.py::test_adventure_creation_initializes_world_state`

Expected: FAIL because `world_state` is absent.

- [ ] **Step 2: Add database column and schema fields**

Add `world_state_json TEXT NOT NULL DEFAULT '{}'` to `adventures`, add `world_state: dict[str, Any] = Field(default_factory=dict)` to `AdventureOut`, and map it from decoded JSON.

- [ ] **Step 3: Initialize default world state**

Use `initial_world_state_for_story(story)` during adventure creation and add `AdventureService.update_world_state(adventure_id, state)`.

- [ ] **Step 4: Verify persistence tests**

Run: `uv run pytest test/backend/src/api/test_world_state_progression.py`

Expected: PASS for creation and isolation.

### Task 2: WorldStateService Classification And Progression

**Files:**
- Create: `backend/src/services/world_state.py`
- Create: `test/backend/src/services/test_world_state.py`

- [ ] **Step 1: Write failing service tests**

Cover these cases:

```python
def test_status_question_does_not_advance():
    service = WorldStateService(None)
    state = initial_world_state_for_story(default_story)
    classification = service.classify_action("equipment.steel-longsword是什么")
    assert classification["advance_world"] is False
    assert classification["message_type"] == "status_question"
```

Also test explicit actions such as `我去铁匠铺搜查后院` advance, and ambiguous actions such as `我看看有没有其他东西` request clarification.

Run: `uv run pytest test/backend/src/services/test_world_state.py`

Expected: FAIL because the service does not exist.

- [ ] **Step 2: Implement deterministic classifier**

Create `ActionClassification` as a plain dict return for the first implementation. Detect status/rule/clarification questions conservatively before detecting world actions.

- [ ] **Step 3: Implement preview and commit helpers**

`preview_advance` returns an unapplied delta. `commit_advance` applies clock changes once, updates phase labels, stores visible events, and clamps clocks to max.

- [ ] **Step 4: Verify service tests**

Run: `uv run pytest test/backend/src/services/test_world_state.py`

Expected: PASS.

### Task 3: DM Context And Message Flow

**Files:**
- Modify: `backend/src/agent/dm/prompts.py`
- Modify: `backend/src/agent/dm/service.py`
- Modify: `test/backend/src/agent/dm/test_dm_prompts.py`
- Modify: `test/backend/src/api/test_world_state_progression.py`

- [ ] **Step 1: Write failing prompt test**

Assert `build_dm_messages(..., world_state=..., action_classification=...)` places both values under `tool_context`, and `pending_visible_events` remains tool context rather than user input.

Run: `uv run pytest test/backend/src/agent/dm/test_dm_prompts.py::test_dm_prompt_includes_world_state_tool_context`

Expected: FAIL because the function signature lacks these inputs.

- [ ] **Step 2: Wire prompt inputs**

Add optional `world_state` and `action_classification` parameters to `build_dm_messages`, include them in `tool_context`, and update all call sites.

- [ ] **Step 3: Write failing DM flow tests**

Test:

- status question via `/messages` does not advance `moonwell_curse`.
- explicit action via `/messages` advances it.
- streamed final response includes `world_state`.

- [ ] **Step 4: Wire DMService**

In `advance` and `advance_stream`, classify before model/fallback generation, preview a pending delta, pass public world state plus pending delta into prompt/fallback context, commit after the DM content is resolved, and return the updated world state.

- [ ] **Step 5: Verify DM flow tests**

Run: `uv run pytest test/backend/src/agent/dm/test_dm_prompts.py test/backend/src/api/test_world_state_progression.py`

Expected: PASS.

### Task 4: Frontend World Situation Panel

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/js/state.js`
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/locales/en.js`
- Modify: `frontend/static/js/locales/zh-CN.js`
- Create: `test/frontend/static/js/test_frontend_world_state.py`

- [ ] **Step 1: Write failing frontend tests**

Assert the game room has world state DOM nodes, locale keys exist, and `renderAdventureDetail` renders phase, public clock, and visible events while hiding hidden events.

Run: `uv run pytest test/frontend/static/js/test_frontend_world_state.py`

Expected: FAIL because DOM and renderer do not exist.

- [ ] **Step 2: Add DOM and bindings**

Add a compact panel with IDs `world-state-phase`, `world-state-clocks`, and `world-state-events`, then bind them in `state.js`.

- [ ] **Step 3: Add renderer**

Add `renderWorldState(worldState)` in `game.js` and call it from `renderAdventureDetail`, message responses, and streaming final handling.

- [ ] **Step 4: Add translations and asset version bump**

Add bilingual labels for world situation and update static asset version consistently.

- [ ] **Step 5: Verify frontend tests**

Run: `uv run pytest test/frontend/static/js/test_frontend_world_state.py test/frontend/static/js/test_frontend_i18n_resources.py test/frontend/static/js/test_frontend_modularization.py test/frontend/static/js/test_frontend_routing.py`

Expected: PASS.

### Task 5: End-To-End Verification

**Files:**
- No new production files unless tests expose a gap.

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest`

Expected: PASS.

- [ ] **Step 2: Browser smoke test**

Open `http://127.0.0.1:5001/game/25`, send a status question and confirm the world clock does not advance. Send a clear in-world action and confirm the world situation panel updates and DM narration mentions the new pressure.

- [ ] **Step 3: Review diff**

Run: `git diff --stat` and inspect world-state-related files to ensure unrelated dirty work was not reverted.

---

## Self-Review Notes

- Spec coverage: persistence, classification, preview/commit, DM context, API, streaming, frontend, and tests are covered.
- Placeholder scan: no task depends on an undefined follow-up phase.
- Type consistency: the plan consistently uses `world_state`, `pending_world_delta`, `ActionClassification`, and `WorldStateService`.
