# Isekai P1 World Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add replayable isekai openings and richer world events with persistent impacts.

**Architecture:** Add a focused opening generator service for model/fallback opening scenes and an event catalog for deterministic event seeds. `IsekaiSurvivalService` owns orchestration and persistence; `IsekaiWorldEventDirector` owns event selection and impact generation. Core survival resources remain backend-controlled.

**Tech Stack:** FastAPI service layer, SQLite JSON state, Pydantic scene models, pytest.

---

## File Structure

- Create `backend/src/services/isekai_opening.py`
  - Generate opening payloads from active model or fallback templates.
  - Validate and normalize `SceneState`, weather, and opening narration.
- Create `backend/src/services/isekai_event_catalog.py`
  - Provide deterministic event seeds with impact payloads.
- Modify `backend/src/services/isekai.py`
  - Use opening generator in `create_adventure`.
  - Include event impacts in existing model payload through `world_state`.
- Modify `backend/src/services/isekai_events.py`
  - Use event catalog instead of generic random event text.
  - Add event impact metadata.
  - Mutate/persist `world_state.event_impacts` through caller.
- Modify `test/backend/src/services/test_isekai_survival.py`
  - Add opening generation and event-impact context tests.
  - Adjust tests that assumed no model call during creation.
- Modify `test/backend/src/services/test_isekai_events.py`
  - Add event catalog and impact tests.

## Task 1: Random Opening Generation

- [ ] Write failing tests:
  - `test_isekai_create_uses_active_model_for_opening_scene`
  - `test_isekai_opening_falls_back_when_model_payload_is_invalid`
- [ ] Run those tests and verify they fail.
- [ ] Create `IsekaiOpeningGenerator`.
- [ ] Wire it into `IsekaiSurvivalService.create_adventure`.
- [ ] Run the opening tests and verify they pass.

## Task 2: Event Catalog And Impact Metadata

- [ ] Write failing event tests:
  - `test_random_event_uses_specific_catalog_entry`
  - `test_known_event_records_impact_metadata`
- [ ] Run those tests and verify they fail.
- [ ] Create `IsekaiEventCatalog`.
- [ ] Wire catalog into `IsekaiWorldEventDirector._random_candidate`.
- [ ] Add `impact` to event metadata.
- [ ] Run the event tests and verify they pass.

## Task 3: Event Impact Persistence And Context Injection

- [ ] Write failing service test:
  - `test_isekai_event_impacts_are_persisted_and_sent_to_model_context`
- [ ] Run the test and verify it fails.
- [ ] Have event director append known event impacts to `world_state.event_impacts`.
- [ ] Persist world state after event evaluation in `IsekaiSurvivalService.advance_world_context`.
- [ ] Run the service test and verify it passes.

## Task 4: Verification

- [ ] Run focused tests:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_events.py test/backend/src/api/test_isekai_mode.py -q
```

- [ ] Run full tests:

```bash
uv run pytest
```

- [ ] Restart `127.0.0.1:5002`.
- [ ] Commit and push.
