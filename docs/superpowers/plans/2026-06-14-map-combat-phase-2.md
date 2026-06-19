# Map Combat Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make active map scenes usable during combat through combat tokens, distance context, NPC tactical decisions, and a basic frontend board.

**Architecture:** Add a dedicated `map_combat_tokens` table and keep uploaded assets/scene items separate. `MapService` owns token sync, movement, and context; combat start and DM NPC turns call into it. The frontend consumes the same APIs to render a grid board and move selected tokens.

**Tech Stack:** FastAPI, SQLite, Pydantic, pytest, vanilla frontend modules.

---

### Task 1: Backend Combat Token Schema and API Tests

**Files:**
- Create: `test/backend/src/api/test_map_combat_phase2.py`
- Modify later: `backend/src/db/sqlite.py`
- Modify later: `backend/src/schemas/maps.py`
- Modify later: `backend/src/services/maps.py`
- Modify later: `backend/src/api/maps.py`

- [ ] **Step 1: Write failing API tests**

```python
import json

from backend.src.agent.dm.service import DMService
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.llm_models import LLMModelService


class CapturingNPCMapLLM:
    def __init__(self):
        self.messages = []

    def chat(self, model, messages):
        self.messages = messages
        return json.dumps({"action_type": "dodge", "reason": "hold position with map awareness"})


def create_mapped_adventure(client, *, enemy_initiative=-30):
    character = client.post(
        "/api/characters",
        json={"name": "Map Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Mapped Fight", "character_id": character["id"]},
    ).json()
    asset = client.post(
        "/api/map-assets?asset_type=map&name=Grid&filename=grid.png",
        content=b"grid",
        headers={"content-type": "image/png"},
    ).json()
    scene = client.post(
        "/api/map-scenes",
        json={
            "name": "Grid Hall",
            "adventure_id": adventure["id"],
            "background_asset_id": asset["id"],
            "grid_size": 70,
            "scale": 5,
        },
    ).json()
    client.post(f"/api/map-scenes/{scene['id']}/activate")
    state = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={
            "enemies": [
                {
                    "name": "Map Goblin",
                    "hp": 7,
                    "ac": 13,
                    "attack_bonus": 4,
                    "damage": "1d6+2",
                    "initiative_bonus": enemy_initiative,
                    "speed_ft": 30,
                    "reach_ft": 5,
                }
            ]
        },
    ).json()
    return adventure, scene, state


def activate_model(store):
    service = LLMModelService(store)
    model = service.create(
        LLMModelCreate(
            name="Map NPC Model",
            base_url="https://example.invalid/v1",
            api_key="test-key",
            model_name="map-npc-test",
        )
    )
    return service.activate(model.id)


def test_start_combat_creates_tokens_for_active_scene(client):
    adventure, scene, state = create_mapped_adventure(client)

    response = client.get(f"/api/map-scenes/{scene['id']}/combat-tokens")

    assert response.status_code == 200
    tokens = response.json()
    assert {token["participant_name"] for token in tokens} == {"Map Hero", "Map Goblin"}
    assert {token["side"] for token in tokens} == {"player", "enemy"}
    assert all(token["scene_id"] == scene["id"] for token in tokens)
    assert all(token["adventure_id"] == adventure["id"] for token in tokens)
    assert all(token["size"] == 70 for token in tokens)


def test_move_token_updates_position_and_map_context_distance(client):
    adventure, scene, _state = create_mapped_adventure(client)
    tokens = client.get(f"/api/map-scenes/{scene['id']}/combat-tokens").json()
    hero = next(token for token in tokens if token["participant_name"] == "Map Hero")
    goblin = next(token for token in tokens if token["participant_name"] == "Map Goblin")

    moved = client.patch(
        f"/api/map-scenes/{scene['id']}/combat-tokens/{hero['id']}",
        json={"x": 70, "y": 70},
    )
    client.patch(
        f"/api/map-scenes/{scene['id']}/combat-tokens/{goblin['id']}",
        json={"x": 210, "y": 70},
    )
    context = client.get(f"/api/adventures/{adventure['id']}/map-context").json()

    assert moved.status_code == 200
    assert moved.json()["x"] == 70
    assert context["active_scene"]["id"] == scene["id"]
    assert context["distances"]["Map Hero"]["Map Goblin"] == 10


def test_npc_model_context_includes_map_tokens_and_distances(client):
    adventure, scene, _state = create_mapped_adventure(client, enemy_initiative=30)
    tokens = client.get(f"/api/map-scenes/{scene['id']}/combat-tokens").json()
    hero = next(token for token in tokens if token["participant_name"] == "Map Hero")
    goblin = next(token for token in tokens if token["participant_name"] == "Map Goblin")
    client.patch(f"/api/map-scenes/{scene['id']}/combat-tokens/{hero['id']}", json={"x": 70, "y": 70})
    client.patch(f"/api/map-scenes/{scene['id']}/combat-tokens/{goblin['id']}", json={"x": 210, "y": 70})
    activate_model(client.app.state.store)
    fake_llm = CapturingNPCMapLLM()

    result = DMService(client.app.state.store, llm_client=fake_llm).resolve_npc_combat_turn(adventure["id"])

    payload = json.loads(fake_llm.messages[1]["content"])
    assert result["decision_source"] == "model"
    assert payload["map"]["active_scene"]["name"] == "Grid Hall"
    assert payload["map"]["distances"]["Map Goblin"]["Map Hero"] == 10
    assert payload["nearby_enemies"][0]["distance_ft"] == 10


def test_fallback_npc_dashes_toward_distant_target_on_map(client):
    adventure, scene, state = create_mapped_adventure(client, enemy_initiative=30)
    tokens = client.get(f"/api/map-scenes/{scene['id']}/combat-tokens").json()
    hero = next(token for token in tokens if token["participant_name"] == "Map Hero")
    goblin = next(token for token in tokens if token["participant_name"] == "Map Goblin")
    client.patch(f"/api/map-scenes/{scene['id']}/combat-tokens/{hero['id']}", json={"x": 70, "y": 70})
    client.patch(f"/api/map-scenes/{scene['id']}/combat-tokens/{goblin['id']}", json={"x": 910, "y": 70})

    response = client.post(f"/api/adventures/{adventure['id']}/combat/npc-turn", json={"locale": "en"})
    moved_goblin = next(
        token for token in client.get(f"/api/map-scenes/{scene['id']}/combat-tokens").json()
        if token["participant_name"] == "Map Goblin"
    )

    assert state["participants"][state["turn_index"]]["name"] == "Map Goblin"
    assert response.status_code == 200
    assert response.json()["action_type"] == "dash"
    assert response.json()["map_movement"]["from"]["x"] == 910
    assert moved_goblin["x"] < 910
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_map_combat_phase2.py -q`

Expected: failures because combat-token endpoints, schemas, and map context do not exist yet.

### Task 2: Implement Backend Combat Tokens

**Files:**
- Modify: `backend/src/db/sqlite.py`
- Modify: `backend/src/schemas/maps.py`
- Modify: `backend/src/services/maps.py`
- Modify: `backend/src/api/maps.py`
- Modify: `backend/src/api/adventures.py`
- Modify: `backend/src/schemas/adventure.py`

- [ ] **Step 1: Add `map_combat_tokens` schema**

Add the table and indexes in `SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS map_combat_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    adventure_id INTEGER NOT NULL,
    participant_name TEXT NOT NULL,
    side TEXT NOT NULL,
    kind TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    size REAL NOT NULL,
    speed_ft REAL NOT NULL,
    reach_ft REAL NOT NULL,
    visible INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scene_id, participant_name)
)
```

- [ ] **Step 2: Add schemas**

Add `MapCombatTokenOut`, `MapCombatTokenUpdate`, and `MapContextOut` to `backend/src/schemas/maps.py`, plus optional `map_movement` to `AdventureCombatActionResponse`.

- [ ] **Step 3: Add service methods**

Implement active scene lookup, token sync, token list/update, map context, distance calculation, and movement toward a target in `MapService`.

- [ ] **Step 4: Add API routes**

Expose token listing, token sync, token update, and adventure map context routes from `backend/src/api/maps.py`.

- [ ] **Step 5: Wire combat start**

After combat state is saved in `backend/src/api/adventures.py`, call `MapService.ensure_combat_tokens`.

- [ ] **Step 6: Run backend tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_map_combat_phase2.py -q`

Expected: map token and map context tests pass; DM map tests fail until Task 3.

### Task 3: DM/NPC Map Context and Fallback Movement

**Files:**
- Modify: `backend/src/agent/dm/service.py`
- Modify: `backend/src/agent/dm/prompts.py`
- Test: `test/backend/src/api/test_map_combat_phase2.py`
- Test: `test/backend/src/agent/dm/test_dm_npc_combat.py`

- [ ] **Step 1: Inject `MapService` into `DMService`**

Construct `self.maps = MapService(store)` and pass `adventure_id` into NPC decision helpers.

- [ ] **Step 2: Enrich model payload**

Include `map` context in `_npc_combat_context` and add `distance_ft` to nearby enemies where available.

- [ ] **Step 3: Add fallback map movement**

When no model decision is available and the nearest hostile is outside reach, move the NPC token toward the target and resolve `dash`; otherwise keep existing attack/dodge/disengage behavior.

- [ ] **Step 4: Run DM tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_map_combat_phase2.py test/backend/src/agent/dm/test_dm_npc_combat.py -q`

Expected: all selected tests pass.

### Task 4: Frontend Map Board

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/js/state.js`
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/i18n.js`
- Modify: `frontend/static/styles.css`
- Test: `test/frontend/static/js/test_frontend_maps_ui.py`

- [ ] **Step 1: Write failing frontend static tests**

Add assertions for `map-token-list`, `sync-map-tokens`, `map-token-layer`, `combat-tokens`, `loadMapTokens`, and click-to-move wiring.

- [ ] **Step 2: Run frontend static tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/frontend/static/js/test_frontend_maps_ui.py -q`

Expected: failures because the token board controls and JS functions do not exist.

- [ ] **Step 3: Add DOM controls**

Add token sync button, token list, and board token layer to the map panel.

- [ ] **Step 4: Add JS state and API calls**

Add `mapTokens`, `selectedMapTokenId`, `loadMapTokens`, `syncMapTokens`, `moveMapToken`, token rendering, and click-to-move handlers.

- [ ] **Step 5: Add i18n and styles**

Add Chinese and English labels and stable CSS dimensions for the map board, grid overlay, and tokens.

- [ ] **Step 6: Verify frontend**

Run: `.\.venv\Scripts\python.exe -m pytest test/frontend/static/js/test_frontend_maps_ui.py -q`

Expected: frontend static tests pass.

### Task 5: Full Verification

**Files:**
- All modified files.

- [ ] **Step 1: Run all Python tests**

Run: `.\.venv\Scripts\python.exe -m pytest`

Expected: all tests pass.

- [ ] **Step 2: Run JS syntax checks**

Run: `node --check frontend/static/app.js`

Run: `node --check frontend/static/js/game.js`

Run: `node --check frontend/static/js/state.js`

Run: `node --check frontend/static/js/i18n.js`

Expected: exit code 0 for each command.

- [ ] **Step 3: Browser smoke check**

Start the local service with a temporary DB if the default DB has local I/O problems, open the game page, confirm the map panel shows the board, and verify token controls exist after starting combat.

Expected: the board is visible, tokens render, and clicking the board moves the selected token without a console-visible route failure.
