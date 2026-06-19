# Script And Adventure Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the code with the updated “剧本与冒险模块” design: script templates are reusable adventure backgrounds with CRUD, and adventure sessions are separate playable windows that can be created, selected, and deleted.

**Architecture:** Keep the existing `/api/stories` storage/API as the script-template implementation to avoid breaking current adventure creation and tests. Add update behavior for custom scripts while locking the default script against modification and deletion. Update the static frontend to expose edit/delete controls for scripts, delete controls for adventures, and Chinese copy that distinguishes 剧本 from 冒险.

**Tech Stack:** FastAPI, Pydantic, SQLite, static HTML/CSS/JavaScript, pytest, Node syntax check.

---

### Task 1: Backend Script Update API

**Files:**
- Modify: `backend/src/schemas/story.py`
- Modify: `backend/src/services/stories.py`
- Modify: `backend/src/api/stories.py`
- Test: `test/test_stories.py`

- [ ] Add failing tests for `PATCH /api/stories/{story_id}` updating a custom script and rejecting default script updates with `default_story_locked`.
- [ ] Add `StoryUpdate` with optional fields for editable story properties.
- [ ] Add `StoryService.update(story_id, update)` that rejects `mistbell_tower`, validates the story exists, updates only provided fields, and returns `StoryOut`.
- [ ] Add `PATCH /api/stories/{story_id}` route.
- [ ] Run `uv run pytest test/test_stories.py -q`.

### Task 2: Frontend Script Editing And Adventure Deletion

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/app.js`
- Modify: `frontend/static/styles.css`
- Test: `test/test_frontend_story_ui.py`
- Test: `test/test_frontend_delete_ui.py`
- Test: `test/test_frontend_i18n.py`

- [ ] Add failing static tests for edit-script controls, `PATCH` usage, adventure delete controls, and Chinese copy using 剧本 for scripts and 冒险 for adventures.
- [ ] Add story form editing state, edit/cancel buttons, and `PATCH` submit behavior for custom scripts.
- [ ] Disable direct default-script editing and keep default-script delete disabled.
- [ ] Add adventure delete buttons that call `DELETE /api/adventures/{id}` and refresh the selected adventure state.
- [ ] Update visible Chinese copy from ambiguous 剧情 to 剧本 or 冒险 where appropriate.
- [ ] Run `uv run pytest test/test_frontend_story_ui.py test/test_frontend_delete_ui.py test/test_frontend_i18n.py -q` and `node --check frontend/static/app.js`.

### Task 3: Design Doc Alignment And Verification

**Files:**
- Modify: `docs/设计文档.md`

- [ ] Update the tracked design document section to use “剧本与冒险模块” and clarify script/adventure terminology.
- [ ] Run `uv run pytest -q`.
- [ ] Run `node --check frontend/static/app.js`.
- [ ] Commit with `feat: align script and adventure module`.
