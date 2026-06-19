# Combat UI Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users verify PHB combat from the game page without opening DevTools, and make first-level app routes load directly.

**Architecture:** Keep the existing static frontend and FastAPI backend. Add explicit SPA route fallback on the backend, add frontend route helpers for `home`, `character-create`, `stories`, and `game`, and extend the existing combat panel with deterministic API-backed actions.

**Tech Stack:** FastAPI, static ES modules, pytest, Node-based frontend module tests.

---

### Task 1: Route Contract

**Files:**
- Modify: `test/backend/src/test_static_routes.py`
- Modify: `test/frontend/static/js/test_frontend_routing.py`
- Modify: `backend/src/main.py`
- Modify: `frontend/static/js/ui.js`
- Modify: `frontend/static/js/state.js`
- Modify: `frontend/static/app.js`

- [ ] **Step 1: Write failing tests for direct app routes**

Assert `/home`, `/character-create`, `/stories`, `/game`, and `/models` return `index.html`, while `/` redirects to `/home`.

- [ ] **Step 2: Write failing frontend routing expectations**

Assert `routeForView("game")` returns `/game`, old `/play` still maps to the game view for compatibility, and `showView` updates history.

- [ ] **Step 3: Implement backend fallback and frontend route helpers**

Serve static assets normally, return `index.html` for app routes, and initialize `state.view` from `window.location.pathname`.

### Task 2: Combat Action UI

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/js/state.js`
- Modify: `frontend/static/js/api.js`
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/i18n.js`
- Modify: `frontend/static/styles.css`

- [ ] **Step 1: Add combat action controls**

Add attack, dodge, dash, disengage, and end-combat buttons inside the existing combat section.

- [ ] **Step 2: Add API functions and state rendering**

Wire buttons to `/api/adventures/{id}/combat/action` and `/api/adventures/{id}/combat/end`, using the current turn actor and first enemy/player target as needed.

- [ ] **Step 3: Render battle participants and action results**

Show `角色 vs 敌人`, current actor, HP/AC/initiative, condition tags, and latest roll or action result.

### Task 3: Verification

**Files:**
- Test: `test/backend/src/test_static_routes.py`
- Test: `test/frontend/static/js/test_frontend_routing.py`
- Test: `test/backend/src/api/test_adventure_flow.py`

- [ ] **Step 1: Run targeted route tests**

Run `python -m pytest test/backend/src/test_static_routes.py test/frontend/static/js/test_frontend_routing.py`.

- [ ] **Step 2: Run combat API regression tests**

Run `python -m pytest test/backend/src/api/test_adventure_flow.py test/backend/src/services/test_combat.py`.

- [ ] **Step 3: Verify running server endpoints**

Check `http://127.0.0.1:5000/game` returns HTML and combat API still accepts page-driven actions.
