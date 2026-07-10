# Isekai P0 Playability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the first playable survival loop for isekai mode by making resources, HP, status effects, non-action input, scene facts, and deletion cleanup trustworthy.

**Architecture:** Keep time/survival pressure in `IsekaiTimeService`, add a small `IsekaiResourceService` for character-bound inventory/HP/status consequences, and let `IsekaiSurvivalService` orchestrate the two. Scene facts stay in `current_scene` plus `world_state.confirmed_location`. Adventure deletion remains owned by `AdventureService`.

**Tech Stack:** FastAPI services, SQLite JSON fields, Pydantic schemas, pytest.

---

## File Structure

- Create `backend/src/services/isekai_resources.py`
  - Parse string inventory entries.
  - Consume dry rations and waterskin charges.
  - Apply HP/status consequences from survival pressure.
- Modify `backend/src/services/isekai.py`
  - Initialize water inventory as `水囊(3/3)`.
  - Run resource consequences after time/survival update.
  - Persist isekai character inventory, HP, and status effects.
  - Add scene fact reconciliation.
- Modify `backend/src/services/isekai_time.py`
  - Make action classification conservative.
  - Add more non-action/status query phrases.
  - Default unknown input to non-advancing `table_talk`.
- Modify `backend/src/services/adventures.py`
  - Delete `isekai_characters`, `isekai_survival_states`, and `world_events`.
- Tests:
  - Modify `test/backend/src/services/test_isekai_survival.py`.
  - Modify `test/backend/src/services/test_isekai_time.py`.
  - Modify `test/backend/src/api/test_isekai_mode.py`.

## Task 1: Resource Consumption And Consequences

- [ ] Write failing tests in `test/backend/src/services/test_isekai_survival.py`:
  - `test_isekai_eat_drink_consumes_inventory_and_records_resource_changes`
  - `test_isekai_high_survival_pressure_damages_hp_and_adds_status_effects`
  - `test_isekai_recovered_pressure_removes_status_effects`
- [ ] Run those tests and verify they fail.
- [ ] Create `backend/src/services/isekai_resources.py` with `IsekaiResourceService.apply()`.
- [ ] Modify `IsekaiSurvivalService` to persist resource results and include them in metadata.
- [ ] Run the three tests and verify they pass.

## Task 2: Non-Action Input Protection

- [ ] Add failing tests in `test/backend/src/services/test_isekai_time.py`:
  - `test_short_clarification_does_not_advance_time`
  - `test_money_query_does_not_advance_time`
  - `test_unknown_input_defaults_to_table_talk_without_time_cost`
- [ ] Run those tests and verify they fail.
- [ ] Modify `IsekaiTimeService.classify_action()` helpers so only explicit in-world actions advance time.
- [ ] Run the tests and verify they pass.

## Task 3: Scene Fact Locking

- [ ] Add failing tests in `test/backend/src/services/test_isekai_survival.py`:
  - `test_confirmed_location_overrides_contradictory_model_narration`
  - `test_non_action_scene_update_cannot_move_character`
- [ ] Run those tests and verify they fail.
- [ ] Modify `IsekaiSurvivalService` to initialize and update `world_state.confirmed_location`.
- [ ] Add narration reconciliation for obvious location contradictions.
- [ ] Prevent non-time-advancing turns from applying `scene_update.location`.
- [ ] Run the tests and verify they pass.

## Task 4: Delete Cleanup

- [ ] Add failing API test in `test/backend/src/api/test_isekai_mode.py`:
  - `test_delete_isekai_adventure_removes_mode_specific_rows_and_world_events`
- [ ] Run the test and verify it fails.
- [ ] Modify `AdventureService.delete()` to delete isekai rows and world events.
- [ ] Run the test and verify it passes.

## Task 5: Verification

- [ ] Run focused tests:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_time.py test/backend/src/api/test_isekai_mode.py -q
```

- [ ] Run full tests:

```bash
uv run pytest
```

- [ ] Restart local service on `127.0.0.1:5002`.
- [ ] Commit and push the branch.
