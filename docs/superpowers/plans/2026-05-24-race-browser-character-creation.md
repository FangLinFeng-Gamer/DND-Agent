# Race Browser And Character Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a race information page and a dedicated character creation page whose race selector is populated from DND race data.

**Architecture:** Reuse the existing `/api/world/search` world-data endpoint with `category=race`. Expand seeded race entries to the PHB base races, then add static frontend views that load those entries once and reuse them for race browsing and character creation.

**Tech Stack:** FastAPI, SQLite seed data, static HTML/CSS/JavaScript, pytest, Node syntax check.

---

### Task 1: Backend Race Data

**Files:**
- Modify: `backend/src/services/world.py`
- Test: `test/test_world.py`

- [ ] Add a failing test that `/api/world/search?category=race` returns the 9 PHB base races: Human, Elf, Dwarf, Halfling, Dragonborn, Gnome, Half-Elf, Half-Orc, Tiefling.
- [ ] Expand `SEED_ENTRIES` with those race entries and concise descriptions.
- [ ] Run `uv run pytest test/test_world.py -q`.

### Task 2: Frontend Race Browser And Character Creation Views

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/app.js`
- Modify: `frontend/static/styles.css`
- Test: create `test/test_frontend_races_ui.py`
- Test: update `test/test_frontend_i18n.py`

- [ ] Add failing static tests for `races-view`, `character-create-view`, `race-list`, `race-detail`, and `select id="character-race"`.
- [ ] Add navigation buttons for Races and Character Creation.
- [ ] Move character creation form to the new character creation page and replace the race input with a select.
- [ ] Load race entries from `/api/world/search?category=race`, render the race browser, and populate the character race select.
- [ ] Add English and Chinese UI copy.
- [ ] Run `uv run pytest test/test_frontend_races_ui.py test/test_frontend_i18n.py -q` and `node --check frontend/static/app.js`.

### Task 3: Verification And Commit

**Files:**
- Modify: `docs/设计文档.md`

- [ ] Update the design document with the race browser and character creation page.
- [ ] Run `uv run pytest -q`.
- [ ] Run `node --check frontend/static/app.js`.
- [ ] Commit with `feat: add race browser and character creation page`.
