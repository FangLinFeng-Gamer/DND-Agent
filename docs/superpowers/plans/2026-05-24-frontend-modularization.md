# Frontend Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the oversized static frontend entrypoint into focused browser ES modules without changing user-visible behavior.

**Architecture:** `frontend/static/app.js` remains the startup and event-wiring entrypoint. Shared state, API, i18n, and UI helpers move into `frontend/static/js/`; story, model, race, and gameplay behavior move into feature modules.

**Tech Stack:** Static HTML/CSS/JavaScript, native browser ES modules, FastAPI backend tests with pytest, Node syntax checks.

---

### Task 1: Add Modularization Structure Test

**Files:**
- Create: `test/test_frontend_modularization.py`

- [x] **Step 1: Write the failing test**

Require `index.html` to load `app.js` as a module, require `app.js` to stay under 350 lines, and require focused files under `frontend/static/js/`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest test/test_frontend_modularization.py -q`

Expected: FAIL because the frontend still loads a classic script and has no split modules.

### Task 2: Split Static Frontend Code

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/app.js`
- Create: `frontend/static/js/state.js`
- Create: `frontend/static/js/api.js`
- Create: `frontend/static/js/i18n.js`
- Create: `frontend/static/js/ui.js`
- Create: `frontend/static/js/stories.js`
- Create: `frontend/static/js/models.js`
- Create: `frontend/static/js/races.js`
- Create: `frontend/static/js/game.js`

- [x] **Step 1: Move shared code**

Move state and element binding to `state.js`, API and stream parsing to `api.js`, translations/localization to `i18n.js`, and DOM/status helpers to `ui.js`.

- [x] **Step 2: Move feature code**

Move story, model, race, and gameplay functions into their matching feature modules. Export only functions used by `app.js` or other modules.

- [x] **Step 3: Thin the entrypoint**

Replace `app.js` with imports, locale rerender orchestration, event binding, capability loading, and startup.

### Task 3: Update Tests and Verify

**Files:**
- Modify: frontend string tests under `test/test_frontend_*.py`

- [x] **Step 1: Update tests to read all static JS**

Tests that previously inspected only `app.js` should use combined JS text from `app.js` plus `frontend/static/js/*.js`.

- [x] **Step 2: Run verification**

Run:

```powershell
uv run pytest -q
node --check frontend/static/app.js
Get-ChildItem frontend/static/js/*.js | ForEach-Object { node --check $_.FullName }
```

Expected: all tests pass and every frontend JS module parses.
