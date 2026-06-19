# Story Template UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable story templates, a default DND story, a guided home page, and a custom story creation view.

**Architecture:** Backend adds a `stories` service/API and stores story snapshots on each adventure session. Frontend remains a static app with client-side views for home, story creation, and the existing game page.

**Tech Stack:** FastAPI, SQLite, Pydantic, static HTML/CSS/JavaScript, pytest, node syntax check.

---

## File Map

- Modify `backend/src/db/sqlite.py`: add `stories` table and idempotent migration for new adventure columns.
- Create `backend/src/schemas/story.py`: story request/response models.
- Create `backend/src/services/stories.py`: seed default story, CRUD-like listing/get/create.
- Create `backend/src/api/stories.py`: story routes.
- Modify `backend/src/main.py`: register story router and seed stories during store initialization.
- Modify `backend/src/schemas/adventure.py`: add `story_id` to create/out models.
- Modify `backend/src/services/adventures.py`: persist story id and snapshot.
- Modify `backend/src/services/dm.py`: build opening scene/message from selected story.
- Modify `frontend/static/index.html`: add home, story creation, and game views.
- Modify `frontend/static/app.js`: add story loading/creation, view switching, and adventure creation from selected story.
- Modify `frontend/static/styles.css`: add layout styles for new views.
- Add/modify tests under `test/`.

## Tasks

### Task 1: Backend Story Models and API

- [ ] Write failing tests in `test/test_stories.py` for default story listing, custom story creation, and story lookup.
- [ ] Run `uv run pytest test/test_stories.py -q` and confirm failure because API does not exist.
- [ ] Add `stories` schema/service/API and register the router.
- [ ] Run `uv run pytest test/test_stories.py -q` and confirm pass.
- [ ] Run `uv run pytest -q`.
- [ ] Commit with `feat: add story templates`.

### Task 2: Adventure Sessions From Story Templates

- [ ] Add failing tests in `test/test_story_adventure_flow.py` for creating two sessions from one story and checking opening message content.
- [ ] Run the new tests and confirm failure.
- [ ] Extend adventure schema/table/service/DM provider to use `story_id` and story snapshot.
- [ ] Run the new tests and confirm pass.
- [ ] Run `uv run pytest -q`.
- [ ] Commit with `feat: start adventures from story templates`.

### Task 3: Frontend Home and Story Creation Views

- [ ] Add failing static tests in `test/test_frontend_story_ui.py` for `home-view`, `story-create-view`, story form fields, and story selector.
- [ ] Run the new static tests and confirm failure.
- [ ] Update HTML/CSS/JS to add view navigation, tutorial cards, story creation form, story list, and story selector in game view.
- [ ] Run static tests, `node --check frontend/static/app.js`, and `uv run pytest -q`.
- [ ] Commit with `feat: add story home and creation views`.

### Task 4: End-to-End Verification

- [ ] Restart the local service on `127.0.0.1:5000`.
- [ ] Verify HTTP flow: create character, create story, start adventure with `story_id`, send player action.
- [ ] Verify `uv run pytest -q` returns all passing.
- [ ] Verify `node --check frontend/static/app.js` exits 0.
- [ ] Update handoff progress doc.
- [ ] Commit verification docs if changed.
