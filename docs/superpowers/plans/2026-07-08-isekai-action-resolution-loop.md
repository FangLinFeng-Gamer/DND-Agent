# Isekai Action Resolution Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make isekai survival mode understand small compound player actions and turn each choice into clear resources, risks, location, and interactable consequences.

**Architecture:** Keep the existing deterministic parser as the single-action classifier. Add a planner for splitting player input into at most three ordered sub-actions, a resolution engine to execute them through existing preconditions/time/resources/projector services, a risk service for noise/danger tradeoffs, and a narration composer for fixed feedback structure.

**Tech Stack:** Python service layer, Pydantic `SceneState`, SQLite-backed adventure persistence, pytest.

## Global Constraints

- Do not expand the action library without need; add only `approach`, `hide`, `avoid`, and `force_open`.
- `IsekaiActionParser` parses one action only; it must not become the compound execution engine.
- `IsekaiTimeService` remains the authority for time and survival deltas by action type.
- `observe` and `search` must not change main location.
- Location changes are only allowed for `travel`, `enter_location`, and `leave_location`; `approach` may change relative position only.
- Compound input executes at most three sub-actions in order; blockers stop later risky actions.
- Every action response must expose action result, time change, resource change, risk change, and new interactables.

---

### Task 1: Planner And New Core Actions

**Files:**
- Create: `backend/src/services/isekai_intent_planner.py`
- Modify: `backend/src/services/isekai_action_parser.py`
- Modify: `backend/src/services/isekai_time.py`
- Test: `test/backend/src/services/test_isekai_intent_planner.py`
- Test: `test/backend/src/services/test_isekai_action_parser.py`

- [ ] Write failing parser/planner tests for compound drink -> approach -> enter/no-search.
- [ ] Add action types `approach`, `hide`, `avoid`, `force_open`.
- [ ] Add style and constraint arguments without adding separate action types.
- [ ] Verify planner and parser tests pass.

### Task 2: Preconditions, Risk, And Physical Constraints

**Files:**
- Modify: `backend/src/services/isekai_action_preconditions.py`
- Create: `backend/src/services/isekai_risk.py`
- Test: `test/backend/src/services/test_isekai_action_preconditions.py`
- Test: `test/backend/src/services/test_isekai_risk.py`

- [ ] Write failing tests for blocked side-tipped carriage entry and force-open alternatives.
- [ ] Require `enter_location` targets to expose usable entry affordance/state.
- [ ] Add risk deltas for careful approach, quiet hide, force open, search, and night travel.
- [ ] Verify precondition and risk tests pass.

### Task 3: Deterministic Resolution Engine

**Files:**
- Create: `backend/src/services/isekai_action_resolution.py`
- Modify: `backend/src/services/isekai.py`
- Modify: `backend/src/services/isekai_interactables.py`
- Create: `backend/src/services/isekai_narration_composer.py`
- Test: `test/backend/src/services/test_isekai_action_resolution.py`
- Test: `test/backend/src/services/test_isekai_survival.py`

- [ ] Write failing 10-round-style tests for compound resolution, blocked entry, interactable refresh, and clear feedback.
- [ ] Execute sub-actions through parser, preconditions, time, resources, risk, and projector.
- [ ] Stop execution when a precondition fails and expose alternatives.
- [ ] Persist final survival, character resources, world risk metadata, and scene state.
- [ ] Use fixed feedback structure when deterministic resolution handles the turn.
- [ ] Verify targeted and service tests pass.

### Task 4: Final Verification

**Files:**
- Test: `test/backend/src/services`

- [ ] Run the targeted new tests.
- [ ] Run `uv run pytest test/backend/src/services -q`.
- [ ] Restart local service if needed and verify `/api/system/capabilities`.
