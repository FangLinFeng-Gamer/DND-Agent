# Bilingual Race Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade race information from short English summaries to detailed bilingual race descriptions with structured creation mechanics.

**Architecture:** Keep `WorldEntryOut` and `/api/world/search` compatible by retaining `content` and `tags`, and add detailed bilingual data under `metadata`. Update seed behavior to refresh built-in entries in existing SQLite databases. Render race detail from `metadata.summary`, `metadata.traits`, and `metadata.mechanics` according to the selected frontend locale.

**Tech Stack:** FastAPI, SQLite seed data, static JavaScript UI, pytest, Node syntax check.

---

### Task 1: Backend Detailed Race Metadata

**Files:**
- Modify: `backend/src/services/world.py`
- Test: `test/test_world.py`

- [ ] Add failing tests requiring every base race to include `metadata.summary.en`, `metadata.summary.zh`, `metadata.traits.en`, `metadata.traits.zh`, and `metadata.mechanics`.
- [ ] Replace one-line race seed entries with detailed bilingual metadata.
- [ ] Change seed insertion to upsert built-in entries so existing local databases receive richer metadata.
- [ ] Run `uv run pytest test/test_world.py -q`.

### Task 2: Frontend Localized Race Detail Rendering

**Files:**
- Modify: `frontend/static/app.js`
- Test: `test/test_frontend_races_ui.py`

- [ ] Add failing static tests proving `renderRaceDetail()` reads `race.metadata.summary`, `race.metadata.traits`, `race.metadata.mechanics`, and `state.locale`.
- [ ] Update race detail rendering to choose Chinese or English content based on `state.locale`.
- [ ] Render mechanics fields as readable rows or compact sections, with fallback to `race.content`.
- [ ] Run `uv run pytest test/test_frontend_races_ui.py -q` and `node --check frontend/static/app.js`.

### Task 3: Verification And Commit

**Files:**
- Modify: `docs/设计文档.md`

- [ ] Update the design document to state race entries include bilingual descriptions and mechanics.
- [ ] Run `uv run pytest -q`.
- [ ] Run `node --check frontend/static/app.js`.
- [ ] Commit with `feat: add bilingual race details`.
