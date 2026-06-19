# DND-Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first playable offline DND-Agent MVP with FastAPI, SQLite, static UI, character/adventure management, DM narration, world lookup, and basic combat.

**Architecture:** Keep the app as a lightweight FastAPI monolith. Split behavior into thin API routes, focused service/tool classes, SQLite repositories, and static frontend assets served by FastAPI.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, pytest, FastAPI TestClient, static HTML/CSS/JavaScript.

---

## File Structure

Create or modify these files:

- Modify: `pyproject.toml` - add test dependencies.
- Modify: `backend/src/main.py` - app factory, routers, static UI mount, database initialization.
- Create: `backend/src/core/errors.py` - structured API errors.
- Create: `backend/src/core/settings.py` - local database and static paths.
- Create: `backend/src/db/sqlite.py` - SQLite connection, schema creation, JSON helpers.
- Create: `backend/src/schemas/common.py` - shared response models.
- Create: `backend/src/schemas/character.py` - character request/response models.
- Create: `backend/src/schemas/world.py` - world/rule models.
- Create: `backend/src/schemas/adventure.py` - adventure and message models.
- Create: `backend/src/schemas/combat.py` - combat request/response models.
- Create: `backend/src/schemas/assets.py` - image request/response models.
- Create: `backend/src/services/characters.py` - character CRUD and defaults.
- Create: `backend/src/services/world.py` - built-in DND MVP data and search.
- Create: `backend/src/services/combat.py` - dice, checks, initiative, attack, damage, turns.
- Create: `backend/src/services/adventures.py` - adventure CRUD, messages, scene state.
- Create: `backend/src/services/dm.py` - `LLMProvider`, `TemplateDMProvider`, DM loop.
- Create: `backend/src/services/assets.py` - image prompt records and not-connected response.
- Create: `backend/src/services/system.py` - capability response.
- Create: `backend/src/api/characters.py` - character endpoints.
- Create: `backend/src/api/world.py` - world search endpoint.
- Create: `backend/src/api/adventures.py` - adventure/message/combat endpoints.
- Create: `backend/src/api/assets.py` - image endpoint.
- Create: `backend/src/api/system.py` - capabilities endpoint.
- Create: `frontend/static/index.html` - static single-page UI.
- Create: `frontend/static/styles.css` - UI styling.
- Create: `frontend/static/app.js` - UI behavior and API calls.
- Create: `test/conftest.py` - test app/database fixtures.
- Create: `test/test_characters.py` - character service/API tests.
- Create: `test/test_world.py` - world service/API tests.
- Create: `test/test_combat.py` - combat service tests.
- Create: `test/test_adventure_flow.py` - full playable API flow test.

Existing draft files under `backend/src/agent` and `backend/src/infra` are not required for the MVP and should not be deleted in this plan.

---

### Task 1: Test Tooling and App Foundation

**Files:**
- Modify: `pyproject.toml`
- Modify: `backend/src/main.py`
- Create: `backend/src/core/settings.py`
- Create: `backend/src/core/errors.py`
- Create: `backend/src/db/sqlite.py`
- Create: `test/conftest.py`

- [ ] **Step 1: Add pytest dependencies**

Update `pyproject.toml` dependencies so tests can run with FastAPI TestClient:

```toml
dependencies = [
    "deepagents>=0.5.2",
    "fastapi>=0.135.3",
    "httpx>=0.28.1",
    "langchain>=1.2.15",
    "langgraph>=1.1.6",
    "pytest>=9.0.1",
    "uvicorn>=0.44.0",
]
```

- [ ] **Step 2: Write the failing app startup test fixture**

Create `test/conftest.py`:

```python
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.src.main import create_app


@pytest.fixture()
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        app = create_app(db_path=db_path, static_dir=None)
        with TestClient(app) as test_client:
            yield test_client
```

- [ ] **Step 3: Run the fixture import to verify it fails**

Run: `uv run pytest test/conftest.py -q`

Expected: FAIL because `create_app` does not exist yet.

- [ ] **Step 4: Add settings**

Create `backend/src/core/settings.py`:

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "dnd_agent.sqlite3"
DEFAULT_STATIC_DIR = PROJECT_ROOT / "frontend" / "static"
```

- [ ] **Step 5: Add structured error helpers**

Create `backend/src/core/errors.py`:

```python
from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )
```

- [ ] **Step 6: Add SQLite schema and helpers**

Create `backend/src/db/sqlite.py` with schema creation for `characters`, `world_entries`, `adventures`, `messages`, `combat_states`, and `generated_assets`. Use `sqlite3.Row` and a context manager returning a connection. Store JSON as text through `json.dumps(..., ensure_ascii=False)`.

```python
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        race TEXT NOT NULL,
        class_name TEXT NOT NULL,
        level INTEGER NOT NULL,
        background TEXT NOT NULL,
        alignment TEXT NOT NULL,
        hp_current INTEGER NOT NULL,
        hp_max INTEGER NOT NULL,
        armor_class INTEGER NOT NULL,
        strength INTEGER NOT NULL,
        dexterity INTEGER NOT NULL,
        constitution INTEGER NOT NULL,
        intelligence INTEGER NOT NULL,
        wisdom INTEGER NOT NULL,
        charisma INTEGER NOT NULL,
        skills_json TEXT NOT NULL,
        inventory_json TEXT NOT NULL,
        spells_json TEXT NOT NULL,
        notes TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS world_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        content TEXT NOT NULL,
        tags_json TEXT NOT NULL,
        source TEXT,
        page INTEGER,
        metadata_json TEXT NOT NULL,
        UNIQUE(category, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS adventures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        world_id TEXT NOT NULL,
        character_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        summary TEXT NOT NULL,
        current_scene_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS combat_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_id INTEGER NOT NULL UNIQUE,
        is_active INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        turn_index INTEGER NOT NULL,
        participants_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS generated_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        subject_id TEXT,
        prompt TEXT NOT NULL,
        status TEXT NOT NULL,
        result_uri TEXT,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


def encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def decode_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


class SQLiteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            for statement in SCHEMA:
                conn.execute(statement)
```

- [ ] **Step 7: Add the app factory**

Replace `backend/src/main.py` with:

```python
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.src.core.settings import DEFAULT_DB_PATH, DEFAULT_STATIC_DIR
from backend.src.db.sqlite import SQLiteStore


def create_app(db_path: str | Path | None = None, static_dir: str | Path | None = DEFAULT_STATIC_DIR) -> FastAPI:
    app = FastAPI(title="DND-Agent", root_path="/dnd-agent/v1")
    store = SQLiteStore(db_path or DEFAULT_DB_PATH)
    store.init_schema()
    app.state.store = store

    if static_dir:
        static_path = Path(static_dir)
        if static_path.exists():
            app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("backend.src.main:app", port=5000, log_level="info")
```

- [ ] **Step 8: Run foundation tests**

Run: `uv run pytest test/conftest.py -q`

Expected: PASS or "no tests ran" with no import error.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml backend/src/main.py backend/src/core backend/src/db test/conftest.py
git commit -m "feat: add app foundation and sqlite schema"
```

---

### Task 2: Character Models, Service, and API

**Files:**
- Create: `backend/src/schemas/character.py`
- Create: `backend/src/services/characters.py`
- Create: `backend/src/api/characters.py`
- Modify: `backend/src/main.py`
- Create: `test/test_characters.py`

- [ ] **Step 1: Write failing character tests**

Create `test/test_characters.py`:

```python
def test_create_character_defaults(client):
    response = client.post("/api/characters", json={"name": "Aria", "race": "Elf", "class_name": "Ranger"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Aria"
    assert data["level"] == 1
    assert data["hp_current"] == data["hp_max"]
    assert data["armor_class"] >= 10


def test_list_update_delete_character(client):
    created = client.post("/api/characters", json={"name": "Borin", "race": "Dwarf", "class_name": "Fighter"}).json()
    listed = client.get("/api/characters").json()
    assert any(item["id"] == created["id"] for item in listed)

    updated = client.patch(f"/api/characters/{created['id']}", json={"notes": "Carries an old map."})
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Carries an old map."

    deleted = client.delete(f"/api/characters/{created['id']}")
    assert deleted.status_code == 200
    missing = client.get(f"/api/characters/{created['id']}")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"]["code"] == "character_not_found"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest test/test_characters.py -q`

Expected: FAIL with 404 for missing character routes.

- [ ] **Step 3: Add character schemas**

Create `backend/src/schemas/character.py`:

```python
from pydantic import BaseModel, Field


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1)
    race: str = "Human"
    class_name: str = "Fighter"
    background: str = "Adventurer"
    alignment: str = "Neutral"
    notes: str = ""


class CharacterUpdate(BaseModel):
    name: str | None = None
    race: str | None = None
    class_name: str | None = None
    level: int | None = None
    background: str | None = None
    alignment: str | None = None
    hp_current: int | None = None
    hp_max: int | None = None
    armor_class: int | None = None
    strength: int | None = None
    dexterity: int | None = None
    constitution: int | None = None
    intelligence: int | None = None
    wisdom: int | None = None
    charisma: int | None = None
    skills: dict[str, int] | None = None
    inventory: list[str] | None = None
    spells: list[str] | None = None
    notes: str | None = None


class CharacterOut(BaseModel):
    id: int
    name: str
    race: str
    class_name: str
    level: int
    background: str
    alignment: str
    hp_current: int
    hp_max: int
    armor_class: int
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    skills: dict[str, int]
    inventory: list[str]
    spells: list[str]
    notes: str
```

- [ ] **Step 4: Add character service**

Create `backend/src/services/characters.py` with CRUD methods and row mapping. Defaults: level 1, ability scores 10 except class-sensitive primary score 14, HP 10, AC 12, starter inventory.

- [ ] **Step 5: Add character routes**

Create `backend/src/api/characters.py` with a FastAPI router at `/api/characters`. Use `request.app.state.store` to build `CharacterService`.

- [ ] **Step 6: Register character router**

Modify `backend/src/main.py`:

```python
from backend.src.api.characters import router as characters_router

# inside create_app after app.state.store assignment
app.include_router(characters_router)
```

- [ ] **Step 7: Run character tests**

Run: `uv run pytest test/test_characters.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/src/schemas/character.py backend/src/services/characters.py backend/src/api/characters.py backend/src/main.py test/test_characters.py
git commit -m "feat: add character management"
```

---

### Task 3: World and Rules Search

**Files:**
- Create: `backend/src/schemas/world.py`
- Create: `backend/src/services/world.py`
- Create: `backend/src/api/world.py`
- Modify: `backend/src/main.py`
- Create: `test/test_world.py`

- [ ] **Step 1: Write failing world tests**

Create `test/test_world.py`:

```python
def test_world_search_returns_seeded_entries(client):
    response = client.get("/api/world/search", params={"query": "initiative"})
    assert response.status_code == 200
    data = response.json()
    assert data["results"]
    assert any("initiative" in item["content"].lower() for item in data["results"])


def test_world_search_category_filter(client):
    response = client.get("/api/world/search", params={"category": "class", "query": "fighter"})
    assert response.status_code == 200
    names = [item["name"].lower() for item in response.json()["results"]]
    assert "fighter" in names
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest test/test_world.py -q`

Expected: FAIL with missing `/api/world/search`.

- [ ] **Step 3: Add world schemas**

Create `backend/src/schemas/world.py`:

```python
from pydantic import BaseModel


class WorldEntryOut(BaseModel):
    id: int
    category: str
    name: str
    content: str
    tags: list[str]
    source: str | None = None
    page: int | None = None
    metadata: dict = {}


class WorldSearchOut(BaseModel):
    query: str | None
    category: str | None
    results: list[WorldEntryOut]
    message: str
```

- [ ] **Step 4: Add world service**

Create `backend/src/services/world.py`. Seed at least these categories and names when the table is empty: `race/Human`, `race/Elf`, `race/Dwarf`, `class/Fighter`, `class/Wizard`, `class/Ranger`, `background/Soldier`, `equipment/Longsword`, `spell/Fire Bolt`, `condition/Prone`, `combat/Initiative`, `combat/Attack Roll`, `adventure/Ability Check`, `setting/Borderlands`.

- [ ] **Step 5: Add world route and register it**

Create `backend/src/api/world.py` with `GET /api/world/search`. Modify `backend/src/main.py` to call `WorldService(store).seed_defaults()` during app creation and include the router.

- [ ] **Step 6: Run world tests**

Run: `uv run pytest test/test_world.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/schemas/world.py backend/src/services/world.py backend/src/api/world.py backend/src/main.py test/test_world.py
git commit -m "feat: add world and rules search"
```

---

### Task 4: Combat Service

**Files:**
- Create: `backend/src/schemas/combat.py`
- Create: `backend/src/services/combat.py`
- Create: `test/test_combat.py`

- [ ] **Step 1: Write failing combat service tests**

Create `test/test_combat.py`:

```python
from backend.src.services.combat import CombatService


def test_d20_check_with_fixed_roll():
    service = CombatService(rng=lambda sides: 15)
    result = service.roll_check(modifier=2, dc=16)
    assert result["rolls"] == [15]
    assert result["total"] == 17
    assert result["success"] is True


def test_advantage_uses_higher_roll():
    rolls = iter([3, 18])
    service = CombatService(rng=lambda sides: next(rolls))
    result = service.roll_check(modifier=1, dc=15, mode="advantage")
    assert result["rolls"] == [3, 18]
    assert result["kept"] == 18
    assert result["success"] is True


def test_attack_damage_and_turn_order():
    rolls = iter([17, 4, 12, 8])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 12, "ac": 14, "attack_bonus": 5, "damage": "1d8+3"},
            {"name": "Goblin", "side": "enemy", "hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d6+2"},
        ]
    )
    assert state["is_active"] is True
    assert state["participants"][0]["name"] == "Hero"
    result = service.resolve_attack(state, attacker_name="Hero", target_name="Goblin")
    assert result["hit"] is True
    assert result["damage"] == 7
    assert result["target"]["hp"] == 0
    advanced = service.advance_turn(state)
    assert advanced["round_number"] >= 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest test/test_combat.py -q`

Expected: FAIL because `CombatService` does not exist.

- [ ] **Step 3: Add combat schemas**

Create `backend/src/schemas/combat.py` with Pydantic models for participants, start requests, action requests, and combat state responses.

- [ ] **Step 4: Add combat service**

Create `backend/src/services/combat.py`. Implement `roll_check`, `roll_damage`, `start_combat`, `resolve_attack`, `advance_turn`, and `end_combat`. The constructor accepts `rng: Callable[[int], int] | None`; default uses `random.randint(1, sides)`.

- [ ] **Step 5: Run combat tests**

Run: `uv run pytest test/test_combat.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/schemas/combat.py backend/src/services/combat.py test/test_combat.py
git commit -m "feat: add basic combat rules"
```

---

### Task 5: Adventures and DM Loop

**Files:**
- Create: `backend/src/schemas/adventure.py`
- Create: `backend/src/services/adventures.py`
- Create: `backend/src/services/dm.py`
- Create: `backend/src/api/adventures.py`
- Modify: `backend/src/main.py`
- Create: `test/test_adventure_flow.py`

- [ ] **Step 1: Write failing adventure flow test**

Create `test/test_adventure_flow.py`:

```python
def test_playable_adventure_flow(client):
    character = client.post("/api/characters", json={"name": "Nyx", "race": "Human", "class_name": "Fighter"}).json()
    created = client.post("/api/adventures", json={"title": "Ruins of Dawn", "character_id": character["id"]})
    assert created.status_code == 200
    adventure = created.json()
    assert adventure["current_scene"]["location"]

    message = client.post(f"/api/adventures/{adventure['id']}/messages", json={"content": "I inspect the old door."})
    assert message.status_code == 200
    data = message.json()
    assert data["dm_message"]["content"]
    assert data["scene"]["current_objective"]
    assert len(data["messages"]) >= 2


def test_start_combat_from_api(client):
    character = client.post("/api/characters", json={"name": "Kara", "race": "Elf", "class_name": "Ranger"}).json()
    adventure = client.post("/api/adventures", json={"title": "Wolf Road", "character_id": character["id"]}).json()
    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Bandit", "hp": 9, "ac": 12, "attack_bonus": 3, "damage": "1d6+1"}]},
    )
    assert response.status_code == 200
    state = response.json()
    assert state["is_active"] is True
    assert len(state["participants"]) == 2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest test/test_adventure_flow.py -q`

Expected: FAIL with missing adventure routes.

- [ ] **Step 3: Add adventure schemas**

Create `backend/src/schemas/adventure.py` with models for adventure create/out, message create/out, scene state, and DM advance response.

- [ ] **Step 4: Add adventure service**

Create `backend/src/services/adventures.py`. Implement create/list/get/delete adventures, append/list messages, get/update scene, get/save combat state.

- [ ] **Step 5: Add DM provider and service**

Create `backend/src/services/dm.py`:

- `LLMProvider` protocol with `opening_scene(character, world_entries)` and `advance(scene, player_input, dice_result, combat_state)`.
- `TemplateDMProvider` that returns deterministic offline narration.
- `DMService` that saves player messages, determines whether input suggests inspection/check/combat, calls `CombatService` for checks when needed, updates scene, saves DM message, and returns structured response.

- [ ] **Step 6: Add adventure routes**

Create `backend/src/api/adventures.py` with routes:

- `POST /api/adventures`
- `GET /api/adventures`
- `GET /api/adventures/{adventure_id}`
- `DELETE /api/adventures/{adventure_id}`
- `POST /api/adventures/{adventure_id}/messages`
- `POST /api/adventures/{adventure_id}/combat/start`
- `POST /api/adventures/{adventure_id}/combat/action`
- `POST /api/adventures/{adventure_id}/combat/end`

- [ ] **Step 7: Register adventure router**

Modify `backend/src/main.py` to include the adventure router.

- [ ] **Step 8: Run adventure tests**

Run: `uv run pytest test/test_adventure_flow.py -q`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/schemas/adventure.py backend/src/services/adventures.py backend/src/services/dm.py backend/src/api/adventures.py backend/src/main.py test/test_adventure_flow.py
git commit -m "feat: add adventure sessions and dm loop"
```

---

### Task 6: System Capabilities and Image Stub

**Files:**
- Create: `backend/src/schemas/assets.py`
- Create: `backend/src/services/assets.py`
- Create: `backend/src/services/system.py`
- Create: `backend/src/api/assets.py`
- Create: `backend/src/api/system.py`
- Modify: `backend/src/main.py`
- Extend: `test/test_adventure_flow.py`

- [ ] **Step 1: Add failing API tests**

Append to `test/test_adventure_flow.py`:

```python
def test_system_capabilities_and_image_stub(client):
    capabilities = client.get("/api/system/capabilities")
    assert capabilities.status_code == 200
    assert "characters" in capabilities.json()["features"]

    image = client.post("/api/assets/images", json={"kind": "character", "subject_id": "1", "description": "elf ranger"})
    assert image.status_code == 200
    data = image.json()
    assert data["status"] == "not_connected"
    assert "elf ranger" in data["prompt"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest test/test_adventure_flow.py::test_system_capabilities_and_image_stub -q`

Expected: FAIL with missing system/assets routes.

- [ ] **Step 3: Add asset schemas and service**

Create `backend/src/schemas/assets.py` and `backend/src/services/assets.py`. The service writes to `generated_assets` and returns `{id, kind, subject_id, prompt, status: "not_connected", result_uri: None}`.

- [ ] **Step 4: Add system service**

Create `backend/src/services/system.py` returning features: characters, adventures, dm_agent, world_search, combat, image_prompt_stub, offline_template_provider.

- [ ] **Step 5: Add and register routes**

Create `backend/src/api/assets.py` and `backend/src/api/system.py`. Include both routers in `backend/src/main.py`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest test/test_adventure_flow.py::test_system_capabilities_and_image_stub -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/schemas/assets.py backend/src/services/assets.py backend/src/services/system.py backend/src/api/assets.py backend/src/api/system.py backend/src/main.py test/test_adventure_flow.py
git commit -m "feat: add capabilities and image stub"
```

---

### Task 7: Static Web UI

**Files:**
- Create: `frontend/static/index.html`
- Create: `frontend/static/styles.css`
- Create: `frontend/static/app.js`
- Modify: `backend/src/main.py`

- [ ] **Step 1: Add static HTML**

Create `frontend/static/index.html` with top bar, left adventure/character panel, center chat panel, and right character/scene/combat/rules panel. Include `styles.css` and `app.js`.

- [ ] **Step 2: Add static styles**

Create `frontend/static/styles.css`. Use a dense app layout with CSS grid, restrained colors, stable panel dimensions, and no marketing hero.

- [ ] **Step 3: Add frontend behavior**

Create `frontend/static/app.js` with functions:

- `api(path, options)`
- `loadCapabilities()`
- `loadCharacters()`
- `createCharacter()`
- `loadAdventures()`
- `createAdventure()`
- `selectAdventure(id)`
- `sendMessage()`
- `startCombat()`
- `searchRules()`
- `renderMessages(messages)`
- `renderCharacter(character)`
- `renderScene(scene)`
- `renderCombat(combat)`

- [ ] **Step 4: Verify static mount manually**

Run: `uv run uvicorn backend.src.main:app --port 5000`

Open: `http://127.0.0.1:5000/`

Expected: The UI loads. Creating a character, creating an adventure, sending a message, starting combat, and searching rules work through the page.

- [ ] **Step 5: Commit**

```bash
git add frontend/static/index.html frontend/static/styles.css frontend/static/app.js backend/src/main.py
git commit -m "feat: add static web ui"
```

---

### Task 8: Full Verification and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run all backend tests**

Run: `uv run pytest -q`

Expected: All tests pass.

- [ ] **Step 2: Run app smoke test**

Run: `uv run uvicorn backend.src.main:app --port 5000`

Expected: Server starts without import errors and logs Uvicorn startup.

- [ ] **Step 3: Update README**

Replace `README.md` with concise local usage instructions:

```markdown
# DND-Agent

Offline-first DND-Agent MVP with FastAPI, SQLite, static UI, character management, adventure sessions, DM narration, world/rule lookup, and basic combat.

## Run

```bash
uv run uvicorn backend.src.main:app --port 5000
```

Open `http://127.0.0.1:5000/`.

## Test

```bash
uv run pytest -q
```
```

- [ ] **Step 4: Run tests after README update**

Run: `uv run pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add mvp run instructions"
```

---

## Self-Review

Spec coverage:

- Character CRUD is covered by Task 2.
- World/rule search and seeded MVP data are covered by Task 3.
- Basic combat loop is covered by Task 4 and API integration in Task 5.
- Adventure sessions, messages, scene state, and DM loop are covered by Task 5.
- Capabilities and image stub are covered by Task 6.
- Static UI is covered by Task 7.
- README and full verification are covered by Task 8.

Placeholder scan:

- No task contains unresolved marker words or unspecified "appropriate handling" language.
- Out-of-scope features remain out of implementation tasks.

Type consistency:

- Character fields match the spec's `characters` model.
- Adventure, message, combat, world, and asset names match API paths and services.
- Tests refer to route paths defined in the same task sequence.
