# Isekai P2 Pressure and Debug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit isekai town pressure goals and a hidden frontend DM debug panel for development validation.

**Architecture:** Backend exposes deterministic pressure goals and debug metadata through existing adventure/message payloads. Frontend renders a collapsed isekai-only debug panel from existing adventure/message state without changing DND mode.

**Tech Stack:** FastAPI/Python services, SQLite adventure state, vanilla JS frontend, pytest static and service tests.

---

### Task 1: Backend Pressure Goals

**Files:**
- Modify: `backend/src/services/isekai.py`
- Modify: `backend/src/services/isekai_worldview.py`
- Test: `test/backend/src/services/test_isekai_survival.py`

- [ ] Add failing tests asserting isekai model payload and adventure output include pressure goals: obtain lodging identity before sunset, outsider suspicion, alien tax, curfew patrol.
- [ ] Implement `isekai_pressure_goals()` and include it in system state, world state/debug metadata, and repaired scene objectives.
- [ ] Run focused backend tests.

### Task 2: Frontend Debug Panel

**Files:**
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/locales/zh-CN.js`
- Modify: `frontend/static/js/locales/en.js`
- Modify: `frontend/static/styles.css`
- Test: `test/frontend/static/js/test_frontend_isekai_mode.py`

- [ ] Add failing static tests for collapsed isekai DM debug panel and required fields.
- [ ] Implement isekai-only `<details>` debug panel using latest DM metadata and survival state.
- [ ] Style the panel as compact developer chrome without changing the main play layout.
- [ ] Run focused frontend tests.

### Task 3: Verification

**Files:**
- No new production files.

- [ ] Run `uv run pytest -q`.
- [ ] Restart `127.0.0.1:5002` with latest code.
- [ ] Smoke check `game/32` current scene/debug metadata through API.
