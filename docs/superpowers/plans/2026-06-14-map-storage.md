# Map Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build local-first map asset storage and reusable scene metadata for DND-Agent.

**Architecture:** Store uploaded map/token/prop media as local files addressed by SHA-256 hash, and store only metadata, placements, walls, lights, and fog shapes in SQLite. Expose the feature through FastAPI service/router/schema layers and add a compact game-page map panel for upload, scene creation, preview, and adventure binding.

**Tech Stack:** FastAPI, SQLite, Pydantic, local filesystem, static ES modules.

---

### File Structure

- Create: `backend/src/schemas/maps.py` for Pydantic API models.
- Create: `backend/src/services/maps.py` for asset file handling, scene CRUD, and adventure binding.
- Create: `backend/src/api/maps.py` for `/api/map-assets` and `/api/map-scenes` routes.
- Modify: `backend/src/db/sqlite.py` to add map tables.
- Modify: `backend/src/main.py` to register the router.
- Create: `test/backend/src/api/test_maps.py` for red-green API coverage.
- Modify: `frontend/static/index.html` to add the map panel to the game page.
- Modify: `frontend/static/js/state.js`, `frontend/static/js/game.js`, `frontend/static/app.js`, and `frontend/static/js/i18n.js` for frontend behavior.
- Modify: `frontend/static/styles.css` for compact map preview styling.
- Create: `test/frontend/static/js/test_frontend_maps_ui.py` for static frontend assertions.

### Task 1: Design Documents

- [x] **Step 1: Save implementation plan**

Create this file with exact scope, files, and verification steps.

- [x] **Step 2: Save product/architecture design**

Create `docs/地图存储设计.md` describing local media storage, SQLite metadata, API shape, and next-phase boundaries.

### Task 2: Backend Red Tests

- [ ] **Step 1: Write failing API tests**

Add tests that prove:

```python
def test_upload_map_asset_stores_file_metadata_and_file(client):
    response = client.post(
        "/api/map-assets?asset_type=map&name=Old%20Keep&filename=keep.png",
        content=b"fake-png",
        headers={"content-type": "image/png"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["asset_type"] == "map"
    assert payload["mime_type"] == "image/png"
    assert payload["sha256"]
    file_response = client.get(f"/api/map-assets/{payload['id']}/file")
    assert file_response.status_code == 200
    assert file_response.content == b"fake-png"
```

Also add scene CRUD and adventure-binding tests.

- [ ] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_maps.py -q
```

Expected: FAIL because `/api/map-assets` does not exist.

### Task 3: Backend Implementation

- [ ] **Step 1: Add SQLite tables**

Add `map_assets`, `map_scenes`, `map_scene_items`, `map_walls`, `map_lights`, and `map_fog_shapes` to `SCHEMA`.

- [ ] **Step 2: Add map schemas**

Define response/request models for assets, scenes, scene items, walls, lights, fog shapes, and scene binding.

- [ ] **Step 3: Add map service**

Implement upload validation, hash-addressed file writes, asset listing, safe file lookup, scene CRUD, item placement, and active scene binding.

- [ ] **Step 4: Add map API router**

Register multipart upload and JSON scene endpoints. Use `FileResponse` for safe file serving.

- [ ] **Step 5: Run backend map tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_maps.py -q
```

Expected: PASS.

### Task 4: Frontend Verification Panel

- [ ] **Step 1: Write failing static UI tests**

Assert the game page contains map panel IDs, i18n keys, and the app imports map functions.

- [ ] **Step 2: Add game-page map panel**

Add upload controls, asset list, scene name input, scene list, and preview area.

- [ ] **Step 3: Wire JS behavior**

Load assets/scenes on adventure selection, upload selected image, create a scene from an asset, bind a scene to current adventure, and render preview.

- [ ] **Step 4: Add compact CSS**

Use existing parchment/detail-card styling, with fixed preview dimensions to prevent layout shifts.

### Task 5: Verification

- [ ] **Step 1: Run focused backend tests**

```powershell
.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_maps.py -q
```

- [ ] **Step 2: Run full test suite**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- [ ] **Step 3: Syntax-check frontend modules**

```powershell
node --check frontend/static/app.js
node --check frontend/static/js/game.js
node --check frontend/static/js/state.js
node --check frontend/static/js/i18n.js
```

- [ ] **Step 4: Report exact verification output**

Report passing/failing command outputs before claiming completion.
