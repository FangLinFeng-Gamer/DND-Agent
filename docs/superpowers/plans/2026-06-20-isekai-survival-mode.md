# Isekai Survival Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent “异世界生成模拟器” survival mode without changing existing DND mode behavior.

**Architecture:** Keep `adventures` as the shared session/message shell and add `mode` routing. DND keeps using existing DM, story, party, combat, map, and dice flows. Isekai uses new backend schemas/services for random single-character creation, deterministic survival state changes, and independent frontend setup/room render paths.

**Tech Stack:** FastAPI, Pydantic, SQLite schema migration helpers, existing OpenAI-compatible LLM client, vanilla JS modules, static Python frontend tests, pytest.

---

## File Structure

- Modify `backend/src/db/sqlite.py`
  - Add `adventures.mode`.
  - Add `isekai_characters` and `isekai_survival_states` tables.
- Modify `backend/src/schemas/adventure.py`
  - Add `mode` to `AdventureCreate` and `AdventureOut`.
  - Add optional `isekai_character` and `survival_state` fields.
- Create `backend/src/schemas/isekai.py`
  - Define `IsekaiCharacterOut`, `IsekaiSurvivalStateOut`, and delta models.
- Modify `backend/src/services/adventures.py`
  - Add DND-compatible mode mapping.
  - Add `create_isekai_shell`.
  - Load isekai optional data when mapping adventures.
- Create `backend/src/services/isekai.py`
  - Generate random isekai character.
  - Initialize and update survival state.
  - Create isekai adventure and opening message.
  - Advance isekai messages with deterministic survival deltas and model/template narration.
- Modify `backend/src/agent/dm/service.py`
  - Route `create_adventure`, `advance`, and `advance_stream` to isekai service when `mode=isekai_survival`.
- Modify `backend/src/api/adventures.py`
  - Guard DND-only combat endpoints for isekai adventures.
- Modify `frontend/static/index.html`
  - Add mode switch near Game Start title.
  - Add isekai setup panel.
  - Add independent isekai room section.
  - Keep existing DND setup and DND room markup intact except adding IDs/classes needed to toggle.
- Modify `frontend/static/js/state.js`
  - Add `selectedGameMode`, `isekaiCreating`, and new element bindings.
- Modify `frontend/static/js/game.js`
  - Add mode switching, filtered adventure list, isekai creation, isekai setup render, and isekai room render.
  - Branch DND and isekai detail render paths by `adventure.mode`.
- Modify `frontend/static/js/locales/en.js` and `frontend/static/js/locales/zh-CN.js`
  - Add mode labels and isekai page strings.
- Modify `frontend/static/styles.css`
  - Add small mode switch styles and isekai setup/room layout styles.
- Tests:
  - Create `test/backend/src/api/test_isekai_mode.py`
  - Create `test/backend/src/services/test_isekai_survival.py`
  - Create `test/frontend/static/js/test_frontend_isekai_mode.py`
  - Update existing adventure/frontend tests only where they need the new `mode` field.

---

### Task 1: Adventure Mode Schema And DND Compatibility

**Files:**
- Modify: `backend/src/db/sqlite.py`
- Modify: `backend/src/schemas/adventure.py`
- Modify: `backend/src/services/adventures.py`
- Test: `test/backend/src/api/test_isekai_mode.py`

- [ ] **Step 1: Write failing backend mode compatibility tests**

Create `test/backend/src/api/test_isekai_mode.py` with:

```python
def test_existing_dnd_create_defaults_to_dnd_mode(client):
    character = client.post(
        "/api/characters",
        json={"name": "Mode Hero", "race": "Human", "class_name": "Fighter"},
    ).json()

    response = client.post("/api/adventures", json={"title": "Mode Road", "character_id": character["id"]})

    assert response.status_code == 200
    adventure = response.json()
    assert adventure["mode"] == "dnd"
    assert adventure["character_id"] == character["id"]
    assert adventure["party_characters"][0]["name"] == "Mode Hero"
    assert adventure["isekai_character"] is None
    assert adventure["survival_state"] is None


def test_list_adventures_exposes_mode_for_frontend_filtering(client):
    character = client.post(
        "/api/characters",
        json={"name": "List Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    created = client.post("/api/adventures", json={"title": "List Road", "character_id": character["id"]}).json()

    response = client.get("/api/adventures")

    assert response.status_code == 200
    listed = next(item for item in response.json() if item["id"] == created["id"])
    assert listed["mode"] == "dnd"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest test/backend/src/api/test_isekai_mode.py::test_existing_dnd_create_defaults_to_dnd_mode test/backend/src/api/test_isekai_mode.py::test_list_adventures_exposes_mode_for_frontend_filtering
```

Expected: FAIL because `mode`, `isekai_character`, and `survival_state` are missing.

- [ ] **Step 3: Add schema fields**

In `backend/src/schemas/adventure.py`:

```python
class AdventureCreate(BaseModel):
    title: str = Field(min_length=1)
    mode: str = "dnd"
    character_id: int | None = None
    party_character_ids: list[int] | None = None
    world_id: str = "default"
    story_id: str = "mistbell_tower"
    locale: str = "en"
```

Add optional payload fields on `AdventureOut` as generic dictionaries in Task 1; Task 2 keeps the same response shape while backing these fields with `IsekaiCharacterOut` and `IsekaiSurvivalStateOut` persistence:

```python
class AdventureOut(BaseModel):
    id: int
    title: str
    mode: str = "dnd"
    world_id: str
    story_id: str
    character_id: int
    party_character_ids: list[int] = Field(default_factory=list)
    party_characters: list[CharacterOut] = Field(default_factory=list)
    status: str
    summary: str
    current_scene: SceneState
    world_state: dict[str, Any] = Field(default_factory=dict)
    isekai_character: dict[str, Any] | None = None
    survival_state: dict[str, Any] | None = None
    messages: list[MessageOut] = Field(default_factory=list)
```

- [ ] **Step 4: Add SQLite mode column migration**

In `backend/src/db/sqlite.py`, add `mode` to the `adventures` table definition:

```sql
mode TEXT NOT NULL DEFAULT 'dnd',
```

In `init_schema`, add:

```python
self._ensure_column(conn, "adventures", "mode", "TEXT NOT NULL DEFAULT 'dnd'")
```

- [ ] **Step 5: Map mode in AdventureService**

In `AdventureService.create`, insert `mode`:

```python
INSERT INTO adventures (
    title, mode, world_id, story_id, character_id, status, summary,
    current_scene_json, story_snapshot_json, world_state_json
)
VALUES (
    :title, :mode, :world_id, :story_id, :character_id, :status, :summary,
    :current_scene_json, :story_snapshot_json, :world_state_json
)
```

Add `"mode": adventure.mode or "dnd"` to values.

In `_map_adventure_row`, include:

```python
mode=row["mode"] if "mode" in row.keys() else "dnd",
isekai_character=None,
survival_state=None,
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
uv run pytest test/backend/src/api/test_isekai_mode.py::test_existing_dnd_create_defaults_to_dnd_mode test/backend/src/api/test_isekai_mode.py::test_list_adventures_exposes_mode_for_frontend_filtering
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/db/sqlite.py backend/src/schemas/adventure.py backend/src/services/adventures.py test/backend/src/api/test_isekai_mode.py
git commit -m "Add adventure mode compatibility"
```

---

### Task 2: Isekai Persistence, Random Character, And Create Flow

**Files:**
- Create: `backend/src/schemas/isekai.py`
- Create: `backend/src/services/isekai.py`
- Modify: `backend/src/db/sqlite.py`
- Modify: `backend/src/services/adventures.py`
- Modify: `backend/src/agent/dm/service.py`
- Test: `test/backend/src/api/test_isekai_mode.py`
- Test: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing isekai create and isolation tests**

Append to `test/backend/src/api/test_isekai_mode.py`:

```python
def test_create_isekai_adventure_generates_independent_character_and_survival_state(client):
    response = client.post(
        "/api/adventures",
        json={"title": "Fog Border", "mode": "isekai_survival", "locale": "zh-CN"},
    )

    assert response.status_code == 200
    adventure = response.json()
    assert adventure["mode"] == "isekai_survival"
    assert adventure["story_id"] == "isekai_survival"
    assert adventure["party_characters"] == []
    assert adventure["party_character_ids"] == []
    assert adventure["isekai_character"]["name"]
    assert adventure["isekai_character"]["race"]
    assert adventure["isekai_character"]["class_name"]
    assert adventure["isekai_character"]["gold"] >= 0
    assert adventure["survival_state"]["hunger"] >= 0
    assert adventure["survival_state"]["thirst"] >= 0
    assert adventure["messages"][0]["metadata"]["mode"] == "isekai_survival"


def test_isekai_character_is_not_added_to_dnd_character_list(client):
    client.post("/api/adventures", json={"title": "No Character Leak", "mode": "isekai_survival"}).json()

    characters = client.get("/api/characters").json()

    assert all(character["name"] != "No Character Leak" for character in characters)
```

Create `test/backend/src/services/test_isekai_survival.py`:

```python
from backend.src.services.isekai import IsekaiSurvivalService


def test_random_isekai_character_has_survival_inventory_and_world_reaction_tags(store):
    service = IsekaiSurvivalService(store)

    character = service.generate_character()

    assert character.name
    assert character.race in {"Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Tiefling"}
    assert character.class_name in {"Fighter", "Ranger", "Rogue", "Wizard", "Cleric", "Druid"}
    assert character.gold >= 5
    assert character.inventory
    assert character.world_reaction_tags
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest test/backend/src/api/test_isekai_mode.py::test_create_isekai_adventure_generates_independent_character_and_survival_state test/backend/src/api/test_isekai_mode.py::test_isekai_character_is_not_added_to_dnd_character_list test/backend/src/services/test_isekai_survival.py::test_random_isekai_character_has_survival_inventory_and_world_reaction_tags
```

Expected: FAIL because `mode=isekai_survival` is not implemented and `backend.src.services.isekai` is missing.

- [ ] **Step 3: Add isekai schemas**

Create `backend/src/schemas/isekai.py`:

```python
from typing import Any

from pydantic import BaseModel, Field


class IsekaiCharacterOut(BaseModel):
    id: int | None = None
    adventure_id: int | None = None
    name: str
    race: str
    class_name: str
    background: str = "Wanderer"
    alignment: str = "Neutral"
    level: int = 1
    hp_current: int = 10
    hp_max: int = 10
    armor_class: int = 12
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    gold: int = 10
    inventory: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    world_reaction_tags: list[str] = Field(default_factory=list)
    status_effects: list[str] = Field(default_factory=list)


class IsekaiSurvivalStateOut(BaseModel):
    adventure_id: int | None = None
    day: int = 1
    time_of_day: str = "黄昏"
    hunger: int = 10
    thirst: int = 10
    fatigue: int = 15
    sleep_need: int = 20
    temperature_risk: int = 10
    morale: int = 70
    weather: str = "薄雾"
    location: str = "未知边境"
    shelter: str = "none"
    last_action_type: str = "start"
    state: dict[str, Any] = Field(default_factory=dict)


class IsekaiSurvivalDelta(BaseModel):
    hunger: int = 0
    thirst: int = 0
    fatigue: int = 0
    sleep_need: int = 0
    temperature_risk: int = 0
    morale: int = 0
    hp_delta: int = 0
    inventory_changes: list[str] = Field(default_factory=list)
    visible_events: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add SQLite tables**

In `backend/src/db/sqlite.py`, add SCHEMA entries:

```sql
CREATE TABLE IF NOT EXISTS isekai_characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adventure_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    race TEXT NOT NULL,
    class_name TEXT NOT NULL,
    background TEXT NOT NULL,
    alignment TEXT NOT NULL,
    level INTEGER NOT NULL,
    hp_current INTEGER NOT NULL,
    hp_max INTEGER NOT NULL,
    armor_class INTEGER NOT NULL,
    strength INTEGER NOT NULL,
    dexterity INTEGER NOT NULL,
    constitution INTEGER NOT NULL,
    intelligence INTEGER NOT NULL,
    wisdom INTEGER NOT NULL,
    charisma INTEGER NOT NULL,
    gold INTEGER NOT NULL,
    inventory_json TEXT NOT NULL,
    traits_json TEXT NOT NULL,
    world_reaction_tags_json TEXT NOT NULL,
    status_effects_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

```sql
CREATE TABLE IF NOT EXISTS isekai_survival_states (
    adventure_id INTEGER PRIMARY KEY,
    day INTEGER NOT NULL,
    time_of_day TEXT NOT NULL,
    hunger INTEGER NOT NULL,
    thirst INTEGER NOT NULL,
    fatigue INTEGER NOT NULL,
    sleep_need INTEGER NOT NULL,
    temperature_risk INTEGER NOT NULL,
    morale INTEGER NOT NULL,
    weather TEXT NOT NULL,
    location TEXT NOT NULL,
    shelter TEXT NOT NULL,
    last_action_type TEXT NOT NULL,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

- [ ] **Step 5: Add AdventureService isekai shell and data loading**

Add method:

```python
def create_isekai_shell(self, adventure: AdventureCreate, scene: SceneState) -> AdventureOut:
    with self.store.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO adventures (
                title, mode, world_id, story_id, character_id, status, summary,
                current_scene_json, story_snapshot_json, world_state_json
            )
            VALUES (
                :title, 'isekai_survival', :world_id, 'isekai_survival', 0, 'active', '',
                :current_scene_json, '{}', '{}'
            )
            """,
            {
                "title": adventure.title,
                "world_id": adventure.world_id,
                "current_scene_json": encode_json(scene.model_dump()),
            },
        )
        row = conn.execute("SELECT * FROM adventures WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return self._map_adventure_row(row)
```

Update `_party_for_adventure` so fallback `0` returns no DND party:

```python
if not rows and fallback_character_id <= 0:
    return [], []
```

Add private loaders `_isekai_character_for_adventure` and `_isekai_survival_state_for_adventure` in `AdventureService`:

```python
def _isekai_character_for_adventure(self, adventure_id: int) -> dict[str, Any] | None:
    with self.store.connect() as conn:
        row = conn.execute("SELECT * FROM isekai_characters WHERE adventure_id = ?", (adventure_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "adventure_id": row["adventure_id"],
        "name": row["name"],
        "race": row["race"],
        "class_name": row["class_name"],
        "background": row["background"],
        "alignment": row["alignment"],
        "level": row["level"],
        "hp_current": row["hp_current"],
        "hp_max": row["hp_max"],
        "armor_class": row["armor_class"],
        "strength": row["strength"],
        "dexterity": row["dexterity"],
        "constitution": row["constitution"],
        "intelligence": row["intelligence"],
        "wisdom": row["wisdom"],
        "charisma": row["charisma"],
        "gold": row["gold"],
        "inventory": decode_json(row["inventory_json"], []),
        "traits": decode_json(row["traits_json"], []),
        "world_reaction_tags": decode_json(row["world_reaction_tags_json"], []),
        "status_effects": decode_json(row["status_effects_json"], []),
    }


def _isekai_survival_state_for_adventure(self, adventure_id: int) -> dict[str, Any] | None:
    with self.store.connect() as conn:
        row = conn.execute("SELECT * FROM isekai_survival_states WHERE adventure_id = ?", (adventure_id,)).fetchone()
    if row is None:
        return None
    return {
        "adventure_id": row["adventure_id"],
        "day": row["day"],
        "time_of_day": row["time_of_day"],
        "hunger": row["hunger"],
        "thirst": row["thirst"],
        "fatigue": row["fatigue"],
        "sleep_need": row["sleep_need"],
        "temperature_risk": row["temperature_risk"],
        "morale": row["morale"],
        "weather": row["weather"],
        "location": row["location"],
        "shelter": row["shelter"],
        "last_action_type": row["last_action_type"],
        "state": decode_json(row["state_json"], {}),
    }
```

In `_map_adventure_row`, compute:

```python
mode = row["mode"] if "mode" in row.keys() else "dnd"
isekai_character = self._isekai_character_for_adventure(row["id"]) if mode == "isekai_survival" else None
survival_state = self._isekai_survival_state_for_adventure(row["id"]) if mode == "isekai_survival" else None
```

- [ ] **Step 6: Add IsekaiSurvivalService create flow**

Create `backend/src/services/isekai.py` with:

```python
from __future__ import annotations

import random

from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.adventure import AdventureCreate, AdventureOut, SceneState
from backend.src.schemas.isekai import IsekaiCharacterOut, IsekaiSurvivalStateOut
from backend.src.services.adventures import AdventureService


RACES = ["Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Tiefling"]
CLASSES = ["Fighter", "Ranger", "Rogue", "Wizard", "Cleric", "Druid"]
NAMES = ["艾瑞克", "莉娅", "诺恩", "米拉", "赛兰", "塔维"]


class IsekaiSurvivalService:
    def __init__(self, store: SQLiteStore, llm_client=None):
        self.store = store
        self.adventures = AdventureService(store)
        self.llm_client = llm_client

    def generate_character(self) -> IsekaiCharacterOut:
        race = random.choice(RACES)
        class_name = random.choice(CLASSES)
        inventory = ["干粮 x2", "水囊", "火绒盒", "旧斗篷"]
        if class_name == "Ranger":
            inventory.append("短弓")
        elif class_name == "Wizard":
            inventory.append("旅行法术书")
        else:
            inventory.append("匕首")
        return IsekaiCharacterOut(
            name=random.choice(NAMES),
            race=race,
            class_name=class_name,
            gold=random.randint(8, 24),
            inventory=inventory,
            traits=[race, class_name],
            world_reaction_tags=[race.lower(), class_name.lower(), "outsider"],
        )

    def initial_survival_state(self, scene: SceneState) -> IsekaiSurvivalStateOut:
        return IsekaiSurvivalStateOut(location=scene.location, weather="薄雾")

    def create_adventure(self, request: AdventureCreate) -> AdventureOut:
        character = self.generate_character()
        scene = SceneState(
            location="雾林边境",
            environment="你在一片潮湿针叶林边缘醒来，远处有微弱火光，脚下泥土留下陌生车辙。",
            important_objects=["潮湿脚印", "微弱火光", "旧猎径"],
            npcs=[],
            current_objective="找到夜间避难处，并确认附近是否有水源或食物。",
            world_changes=[],
        )
        survival = self.initial_survival_state(scene)
        adventure = self.adventures.create_isekai_shell(request, scene)
        self.save_character(adventure.id, character)
        self.save_survival_state(adventure.id, survival)
        self.adventures.append_message(
            adventure.id,
            "dm",
            self.opening_text(character, scene, survival),
            {"kind": "opening", "mode": "isekai_survival"},
        )
        return self.adventures.get(adventure.id)
```

Add `save_character`, `save_survival_state`, and `opening_text`:

```python
    def save_character(self, adventure_id: int, character: IsekaiCharacterOut) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO isekai_characters (
                    adventure_id, name, race, class_name, background, alignment, level,
                    hp_current, hp_max, armor_class, strength, dexterity, constitution,
                    intelligence, wisdom, charisma, gold, inventory_json, traits_json,
                    world_reaction_tags_json, status_effects_json
                )
                VALUES (
                    :adventure_id, :name, :race, :class_name, :background, :alignment, :level,
                    :hp_current, :hp_max, :armor_class, :strength, :dexterity, :constitution,
                    :intelligence, :wisdom, :charisma, :gold, :inventory_json, :traits_json,
                    :world_reaction_tags_json, :status_effects_json
                )
                """,
                {
                    **character.model_dump(exclude={"id", "adventure_id", "inventory", "traits", "world_reaction_tags", "status_effects"}),
                    "adventure_id": adventure_id,
                    "inventory_json": encode_json(character.inventory),
                    "traits_json": encode_json(character.traits),
                    "world_reaction_tags_json": encode_json(character.world_reaction_tags),
                    "status_effects_json": encode_json(character.status_effects),
                },
            )

    def save_survival_state(self, adventure_id: int, survival: IsekaiSurvivalStateOut) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO isekai_survival_states (
                    adventure_id, day, time_of_day, hunger, thirst, fatigue, sleep_need,
                    temperature_risk, morale, weather, location, shelter, last_action_type, state_json
                )
                VALUES (
                    :adventure_id, :day, :time_of_day, :hunger, :thirst, :fatigue, :sleep_need,
                    :temperature_risk, :morale, :weather, :location, :shelter, :last_action_type, :state_json
                )
                """,
                {
                    **survival.model_dump(exclude={"adventure_id", "state"}),
                    "adventure_id": adventure_id,
                    "state_json": encode_json(survival.state),
                },
            )

    def opening_text(self, character: IsekaiCharacterOut, scene: SceneState, survival: IsekaiSurvivalStateOut) -> str:
        return (
            f"{character.name}，{character.race} {character.class_name}，在{scene.location}醒来。"
            f"{scene.environment} 当前目标：{scene.current_objective}"
            f" 你的金币为 {character.gold}，饥饿 {survival.hunger}，口渴 {survival.thirst}，疲劳 {survival.fatigue}。"
        )
```

- [ ] **Step 7: Route DMService create by mode**

In `backend/src/agent/dm/service.py`, import `IsekaiSurvivalService` and at top of `create_adventure`:

```python
if request.mode == "isekai_survival":
    return IsekaiSurvivalService(self.store, llm_client=self.llm_client).create_adventure(request)
```

Keep existing DND create path unchanged for all other modes.

- [ ] **Step 8: Run create tests**

Run:

```bash
uv run pytest test/backend/src/api/test_isekai_mode.py test/backend/src/services/test_isekai_survival.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/db/sqlite.py backend/src/schemas/adventure.py backend/src/schemas/isekai.py backend/src/services/adventures.py backend/src/services/isekai.py backend/src/agent/dm/service.py test/backend/src/api/test_isekai_mode.py test/backend/src/services/test_isekai_survival.py
git commit -m "Add isekai survival adventure creation"
```

---

### Task 3: Isekai Survival Advancement And DND Combat Guard

**Files:**
- Modify: `backend/src/services/isekai.py`
- Modify: `backend/src/agent/dm/service.py`
- Modify: `backend/src/api/adventures.py`
- Test: `test/backend/src/api/test_isekai_mode.py`
- Test: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing survival advance tests**

Append to `test/backend/src/services/test_isekai_survival.py`:

```python
from backend.src.schemas.adventure import AdventureCreate, MessageCreate


def test_survival_rules_increase_pressure_for_exploration(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Rule Road", mode="isekai_survival"))
    before = adventure.survival_state

    response = service.advance(adventure.id, MessageCreate(content="我沿着旧猎径探索。", locale="zh-CN"))

    after = response.adventure.survival_state
    assert after["fatigue"] > before["fatigue"]
    assert after["thirst"] > before["thirst"]
    assert response.dm_message.metadata["mode"] == "isekai_survival"
    assert response.dm_message.metadata["survival_delta"]["fatigue"] > 0
```

Append to `test/backend/src/api/test_isekai_mode.py`:

```python
def test_isekai_message_stream_updates_survival_state(client):
    adventure = client.post(
        "/api/adventures",
        json={"title": "Stream Survival", "mode": "isekai_survival", "locale": "zh-CN"},
    ).json()
    before = adventure["survival_state"]["fatigue"]

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages",
        json={"content": "我寻找水源。", "locale": "zh-CN"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["adventure"]["survival_state"]["fatigue"] > before
    assert data["dm_message"]["metadata"]["mode"] == "isekai_survival"


def test_dnd_combat_api_rejects_isekai_adventure(client):
    adventure = client.post("/api/adventures", json={"title": "No Combat", "mode": "isekai_survival"}).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Wolf", "hp": 8, "ac": 12, "attack_bonus": 3, "damage": "1d6"}]},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "mode_not_supported"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py::test_survival_rules_increase_pressure_for_exploration test/backend/src/api/test_isekai_mode.py::test_isekai_message_stream_updates_survival_state test/backend/src/api/test_isekai_mode.py::test_dnd_combat_api_rejects_isekai_adventure
```

Expected: FAIL because advance routing/rules and combat guard are missing.

- [ ] **Step 3: Implement deterministic survival rules**

In `IsekaiSurvivalService`, add:

```python
def classify_action(self, content: str) -> str:
    text = content.lower()
    if any(word in text for word in ["休息", "睡", "camp", "rest"]):
        return "rest"
    if any(word in text for word in ["吃", "喝", "食物", "水", "food", "water"]):
        return "forage"
    if any(word in text for word in ["探索", "走", "寻找", "inspect", "explore", "move"]):
        return "explore"
    return "talk"


def survival_delta_for_action(self, action_type: str) -> dict:
    if action_type == "rest":
        return {"hunger": 2, "thirst": 2, "fatigue": -12, "sleep_need": -18, "visible_events": ["你短暂休整，疲劳有所缓解。"]}
    if action_type == "forage":
        return {"hunger": 1, "thirst": 2, "fatigue": 6, "sleep_need": 3, "visible_events": ["寻找资源消耗了体力。"]}
    if action_type == "explore":
        return {"hunger": 3, "thirst": 4, "fatigue": 8, "sleep_need": 4, "visible_events": ["探索让你更加疲惫和口渴。"]}
    return {"hunger": 0, "thirst": 1, "fatigue": 1, "sleep_need": 0, "visible_events": []}
```

Add `apply_delta`, clamping survival values 0 to 100:

```python
def apply_delta(self, adventure_id: int, action_type: str, delta: dict) -> dict:
    current = self.adventures.get(adventure_id).survival_state or {}
    updated = dict(current)
    for key in ["hunger", "thirst", "fatigue", "sleep_need", "temperature_risk", "morale"]:
        updated[key] = max(0, min(100, int(updated.get(key, 0)) + int(delta.get(key, 0))))
    updated["last_action_type"] = action_type
    with self.store.connect() as conn:
        conn.execute(
            """
            UPDATE isekai_survival_states
            SET hunger = :hunger, thirst = :thirst, fatigue = :fatigue, sleep_need = :sleep_need,
                temperature_risk = :temperature_risk, morale = :morale,
                last_action_type = :last_action_type, updated_at = CURRENT_TIMESTAMP
            WHERE adventure_id = :adventure_id
            """,
            {**updated, "adventure_id": adventure_id},
        )
    return updated
```

- [ ] **Step 4: Implement `advance` and `advance_stream`**

In `IsekaiSurvivalService`:

```python
def advance(self, adventure_id: int, message: MessageCreate) -> DMAdvanceResponse:
    player_message = self.adventures.append_message(adventure_id, "player", message.content, {"mode": "isekai_survival"})
    action_type = self.classify_action(message.content)
    delta = self.survival_delta_for_action(action_type)
    character = self.get_character(adventure_id)
    survival = self.apply_delta(adventure_id, action_type, delta)
    scene = self.adventures.get_scene(adventure_id)
    content = self.narrate(message.content, scene, character, survival, delta)
    dm_message = self.adventures.append_message(
        adventure_id,
        "dm",
        content,
        {"mode": "isekai_survival", "survival_delta": delta, "source": "survival_rules"},
    )
    updated = self.adventures.get(adventure_id)
    return DMAdvanceResponse(
        adventure=updated,
        dm_message=dm_message,
        scene=updated.current_scene,
        messages=updated.messages,
        world_state=updated.world_state,
        combat_state=None,
        dice_result=None,
    )
```

Add stream version yielding status, player_message, chunked deltas, and final:

```python
def advance_stream(self, adventure_id: int, message: MessageCreate):
    yield {"type": "status", "message": "dm_thinking"}
    response = self.advance(adventure_id, message)
    player_message = response.messages[-2] if len(response.messages) >= 2 else None
    if player_message:
        yield {"type": "player_message", "message": player_message}
    for chunk in chunk_text(response.dm_message.content):
        yield {"type": "delta", "content": chunk}
    yield {
        "type": "final",
        "adventure": response.adventure,
        "dm_message": response.dm_message,
        "scene": response.scene,
        "messages": response.messages,
        "world_state": response.world_state,
        "combat_state": None,
        "dice_result": None,
    }
```

Import `chunk_text` from `backend.src.agent.dm.output`.

- [ ] **Step 5: Route DMService advance and stream by mode**

At the top of `DMService.advance` after fetching adventure:

```python
if adventure.mode == "isekai_survival":
    return IsekaiSurvivalService(self.store, llm_client=self.llm_client).advance(adventure_id, message)
```

At the top of `DMService.advance_stream` after fetching adventure:

```python
if adventure.mode == "isekai_survival":
    yield from IsekaiSurvivalService(self.store, llm_client=self.llm_client).advance_stream(adventure_id, message)
    return
```

- [ ] **Step 6: Add DND combat mode guard**

In `backend/src/api/adventures.py`, add:

```python
def require_dnd_adventure(adventure_id: int, request: Request) -> AdventureOut:
    adventure = adventure_service(request).get(adventure_id, include_messages=False)
    if adventure.mode != "dnd":
        raise api_error(400, "mode_not_supported", "This endpoint only supports DND adventures.")
    return adventure
```

Call it at the start of combat start/action/npc-turn/end/get endpoints.

- [ ] **Step 7: Run survival and combat guard tests**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py test/backend/src/api/test_isekai_mode.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/src/services/isekai.py backend/src/agent/dm/service.py backend/src/api/adventures.py test/backend/src/api/test_isekai_mode.py test/backend/src/services/test_isekai_survival.py
git commit -m "Add isekai survival advancement"
```

---

### Task 4: Frontend Mode Switch And Isekai Setup Page

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/js/state.js`
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/locales/en.js`
- Modify: `frontend/static/js/locales/zh-CN.js`
- Modify: `frontend/static/styles.css`
- Test: `test/frontend/static/js/test_frontend_isekai_mode.py`

- [ ] **Step 1: Write failing frontend setup tests**

Create `test/frontend/static/js/test_frontend_isekai_mode.py`:

```python
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def frontend_text():
    files = [FRONTEND_DIR / "index.html", FRONTEND_DIR / "styles.css", *sorted((FRONTEND_DIR / "js").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_setup_has_mode_switch_and_isekai_setup_without_removing_dnd_setup():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    text = frontend_text()

    assert 'id="game-mode-switch"' in html
    assert 'data-game-mode="dnd"' in html
    assert 'data-game-mode="isekai_survival"' in html
    assert 'id="dnd-setup-content"' in html
    assert 'id="isekai-setup-content"' in html
    assert 'id="game-story-choice-list"' in html
    assert 'id="character-list"' in html
    assert 'id="isekai-adventure-form"' in html
    assert "selectedGameMode" in text
    assert "renderGameModeSetup" in text
    assert "createIsekaiAdventure" in text
    assert '"isekaiMode": "Isekai Generator"' in text
    assert '"isekaiMode": "异世界生成模拟器"' in text


def test_frontend_filters_adventure_list_by_selected_mode():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")

    assert "adventure.mode || \"dnd\"" in game_js
    assert "state.selectedGameMode" in game_js
    assert ".filter((adventure) => adventureMode(adventure) === state.selectedGameMode)" in game_js
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py
```

Expected: FAIL because setup mode switch and isekai setup are missing.

- [ ] **Step 3: Add setup markup**

In `frontend/static/index.html`, add mode switch inside `game-screen-title` title block:

```html
<div class="game-setup-title-row">
  <h1 data-i18n="gameSetupTitle">Game Start</h1>
  <div id="game-mode-switch" class="game-mode-switch" aria-label="Game mode">
    <button type="button" data-game-mode="dnd" data-i18n="dndMode">DND Mode</button>
    <button type="button" data-game-mode="isekai_survival" data-i18n="isekaiMode">Isekai Generator</button>
  </div>
</div>
```

Wrap the existing DND setup layout by changing the current setup layout opener from:

```html
<div class="setup-layout">
```

to:

```html
<div id="dnd-setup-content">
  <div class="setup-layout">
</div>
```

Move the new `</div>` closing tag so it appears immediately after the existing setup layout closing `</div>` and before the new isekai setup sibling. Do not remove or reorder the existing DND story, party, or create-adventure markup.

Add sibling after `#dnd-setup-content`:

```html
<div id="isekai-setup-content" class="isekai-setup-content hidden">
  <section class="panel setup-choice-panel">
    <div class="panel-inner">
      <div class="section-head">
        <div>
          <h2 data-i18n="isekaiCreateAdventure">Create Isekai Adventure</h2>
          <p class="field-hint" data-i18n="isekaiCreateHint">Only title is needed. Character and world are generated.</p>
        </div>
      </div>
      <form id="isekai-adventure-form" class="compact-form setup-adventure-form">
        <label>
          <span data-i18n="title">Title</span>
          <input id="isekai-adventure-title" autocomplete="off" required>
        </label>
        <div id="isekai-create-status" class="map-action-message detail-empty"></div>
        <div id="isekai-generated-character" class="selected-summary"></div>
        <button id="isekai-create-button" type="submit" data-i18n="isekaiCreateAndEnter">Generate and Enter</button>
      </form>
    </div>
  </section>
  <section class="panel existing-adventures-panel">
    <div class="panel-inner">
      <div class="section-head"><h2 data-i18n="existingAdventures">Existing Adventures</h2></div>
      <div id="isekai-adventure-list" class="adventure-list adventure-room-list" role="list"></div>
    </div>
  </section>
</div>
```

- [ ] **Step 4: Add state and bindings**

In `frontend/static/js/state.js`, add:

```js
selectedGameMode: "dnd",
isekaiCreating: false,
```

Add element IDs:

```js
"game-mode-switch",
"dnd-setup-content",
"isekai-setup-content",
"isekai-adventure-form",
"isekai-adventure-title",
"isekai-create-status",
"isekai-generated-character",
"isekai-create-button",
"isekai-adventure-list",
```

- [ ] **Step 5: Add frontend mode functions**

In `frontend/static/js/game.js`, add:

```js
function adventureMode(adventure) {
  return adventure?.mode || "dnd";
}

export function setSelectedGameMode(mode) {
  state.selectedGameMode = mode === "isekai_survival" ? "isekai_survival" : "dnd";
  renderGameModeSetup();
  renderAdventureList();
  renderAdventureDetail();
}

export function renderGameModeSetup() {
  const isIsekai = state.selectedGameMode === "isekai_survival";
  els.dndSetupContent?.classList.toggle("hidden", isIsekai);
  els.isekaiSetupContent?.classList.toggle("hidden", !isIsekai);
  els.gameModeSwitch?.querySelectorAll("[data-game-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.gameMode === state.selectedGameMode);
  });
}
```

In `renderAdventureList`, filter:

```js
const adventures = state.adventures.filter((adventure) => adventureMode(adventure) === state.selectedGameMode);
```

Render into `els.isekaiAdventureList` when selected mode is isekai, otherwise existing `els.adventureList`.

- [ ] **Step 6: Add isekai create frontend flow**

In `game.js`:

```js
export async function createIsekaiAdventure() {
  const title = els.isekaiAdventureTitle.value.trim();
  if (!title) {
    setStatus(t("adventureTitleRequired"), "error");
    return;
  }
  state.isekaiCreating = true;
  els.isekaiCreateButton.disabled = true;
  els.isekaiCreateStatus.textContent = t("isekaiCharacterCreating");
  try {
    const adventure = await api("/api/adventures", {
      method: "POST",
      body: JSON.stringify({ title, mode: "isekai_survival", locale: state.locale }),
    });
    renderIsekaiGeneratedCharacter(adventure.isekai_character, adventure.survival_state);
    state.selectedAdventureId = adventure.id;
    state.selectedAdventure = adventure;
    state.gameMode = "room";
    await loadAdventures();
    await selectAdventure(adventure.id);
  } catch (error) {
    showError(error);
  } finally {
    state.isekaiCreating = false;
    els.isekaiCreateButton.disabled = false;
  }
}
```

Wire in `frontend/static/app.js`:

```js
els.gameModeSwitch.addEventListener("click", (event) => {
  const button = event.target.closest("[data-game-mode]");
  if (button) setSelectedGameMode(button.dataset.gameMode);
});
els.isekaiAdventureForm.addEventListener("submit", (event) => {
  event.preventDefault();
  createIsekaiAdventure();
});
```

- [ ] **Step 7: Add i18n and styles**

Add translations for:

```js
"dndMode": "DND Mode",
"isekaiMode": "Isekai Generator",
"isekaiCreateAdventure": "Create Isekai Adventure",
"isekaiCreateHint": "Only title is needed. Character and world are generated.",
"isekaiCreateAndEnter": "Generate and Enter",
"isekaiCharacterCreating": "Character is being created...",
"isekaiGeneratedCharacter": "Generated Character"
```

Chinese equivalents:

```js
"dndMode": "DND 模式",
"isekaiMode": "异世界生成模拟器",
"isekaiCreateAdventure": "创建异世界冒险",
"isekaiCreateHint": "只需要标题，角色和世界会随机生成。",
"isekaiCreateAndEnter": "随机生成并进入冒险",
"isekaiCharacterCreating": "角色正在创建中...",
"isekaiGeneratedCharacter": "生成角色"
```

Add `.game-setup-title-row`, `.game-mode-switch`, `.game-mode-switch button.active`, `.isekai-setup-content`.

- [ ] **Step 8: Run frontend setup tests**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/static/index.html frontend/static/js/state.js frontend/static/js/game.js frontend/static/app.js frontend/static/js/locales/en.js frontend/static/js/locales/zh-CN.js frontend/static/styles.css test/frontend/static/js/test_frontend_isekai_mode.py
git commit -m "Add isekai setup mode switch"
```

---

### Task 5: Frontend Isekai Room Page

**Files:**
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/js/state.js`
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/locales/en.js`
- Modify: `frontend/static/js/locales/zh-CN.js`
- Modify: `frontend/static/styles.css`
- Test: `test/frontend/static/js/test_frontend_isekai_mode.py`

- [ ] **Step 1: Write failing isekai room tests**

Append:

```python
def test_isekai_room_is_independent_from_dnd_room():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'id="isekai-room"' in html
    assert 'id="isekai-character-panel"' in html
    assert 'id="isekai-survival-panel"' in html
    assert 'id="isekai-inventory-panel"' in html
    assert 'id="isekai-environment-panel"' in html
    assert 'id="isekai-events-panel"' in html
    assert "renderIsekaiAdventureDetail" in game_js
    assert 'adventureMode(adventure) === "isekai_survival"' in game_js
    assert "renderCombat(null)" not in game_js.split("function renderIsekaiAdventureDetail", 1)[1].split("function", 1)[0]
    assert ".isekai-room-layout" in css
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py::test_isekai_room_is_independent_from_dnd_room
```

Expected: FAIL because isekai room does not exist.

- [ ] **Step 3: Add isekai room markup**

Add sibling after existing `#game-room`:

```html
<section id="isekai-room" class="isekai-room hidden" aria-label="Isekai survival room">
  <header class="screen-title game-screen-title">
    <div>
      <span class="room-kicker" data-i18n="isekaiMode">Isekai Generator</span>
      <h1 id="isekai-room-title" data-i18n="selectAdventure">Select an adventure</h1>
      <p id="isekai-room-subtitle" data-i18n="isekaiRoomSubtitle">Survive the generated world.</p>
    </div>
    <span id="isekai-route-tag" class="route-tag">/game</span>
  </header>
  <div class="isekai-room-layout">
    <aside id="isekai-character-panel" class="compact-panel"></aside>
    <section id="isekai-environment-panel" class="panel"></section>
    <aside id="isekai-survival-panel" class="compact-panel"></aside>
    <aside id="isekai-inventory-panel" class="compact-panel"></aside>
    <section class="chat-panel room-chat-panel isekai-chat-panel">
      <div id="isekai-messages" class="messages" aria-live="polite"></div>
      <form id="isekai-message-form" class="message-form">
        <textarea id="isekai-message-input" rows="3" required data-i18n-placeholder="messagePlaceholder"></textarea>
        <button id="isekai-message-send" type="submit" data-i18n="askDm">Ask the DM</button>
      </form>
    </section>
    <aside id="isekai-events-panel" class="compact-panel"></aside>
  </div>
</section>
```

- [ ] **Step 4: Add bindings and mode display toggles**

Bind new IDs in `state.js`.

Update `renderGameMode`:

```js
const isRoom = state.gameMode === "room" && Boolean(state.selectedAdventureId);
const isIsekaiRoom = isRoom && adventureMode(state.selectedAdventure) === "isekai_survival";
gameView.classList.toggle("room-mode", isRoom && !isIsekaiRoom);
gameView.classList.toggle("isekai-room-mode", isIsekaiRoom);
els.gameRoom?.classList.toggle("hidden", !isRoom || isIsekaiRoom);
els.isekaiRoom?.classList.toggle("hidden", !isIsekaiRoom);
```

- [ ] **Step 5: Implement isekai room render**

In `renderAdventureDetail`, branch before DND rendering:

```js
if (adventureMode(adventure) === "isekai_survival") {
  renderIsekaiAdventureDetail(adventure, messages);
  return;
}
```

Implement:

```js
function renderIsekaiAdventureDetail(adventure, messages) {
  renderGameMode();
  els.isekaiRoomTitle.textContent = adventure.title;
  els.isekaiRoomSubtitle.textContent = [adventure.survival_state?.day && `第 ${adventure.survival_state.day} 天`, adventure.survival_state?.time_of_day, adventure.survival_state?.location].filter(Boolean).join(" · ");
  els.isekaiRouteTag.textContent = `/game/${adventure.id}`;
  renderIsekaiCharacter(adventure.isekai_character);
  renderIsekaiSurvival(adventure.survival_state);
  renderIsekaiInventory(adventure.isekai_character);
  renderIsekaiEnvironment(adventure);
  renderIsekaiEvents(adventure.messages || []);
  renderMessagesInto(els.isekaiMessages, messages || adventure.messages || []);
}
```

If existing `renderMessages` is tightly coupled to `els.messages`, extract `renderMessageList(target, messages)` and have DND `renderMessages` call it.

- [ ] **Step 6: Wire isekai chat to existing send flow**

Add `sendIsekaiMessage()` that calls `readStreamingResponse` and renders into isekai messages. Keep DND `sendMessage` unchanged for the DND form:

```js
export async function sendIsekaiMessage() {
  if (state.dmBusy) {
    setStatus(t("dmStillResponding"), "error");
    return;
  }
  const content = els.isekaiMessageInput.value.trim();
  if (!content || !state.selectedAdventureId) {
    return;
  }
  const currentMessages = state.selectedAdventure?.messages || [];
  const pendingDm = {
    id: `pending-isekai-dm-${Date.now()}`,
    adventure_id: state.selectedAdventureId,
    role: "dm",
    content: "",
    metadata: { pending: true, mode: "isekai_survival" },
    created_at: "",
  };
  const optimisticMessages = [
    ...currentMessages,
    {
      id: `pending-isekai-player-${Date.now()}`,
      adventure_id: state.selectedAdventureId,
      role: "player",
      content,
      metadata: { mode: "isekai_survival" },
      created_at: "",
    },
    pendingDm,
  ];
  renderMessageList(els.isekaiMessages, optimisticMessages);
  setDmBusy(true);
  try {
    const response = await readStreamingResponse(
      state.selectedAdventureId,
      content,
      state.locale,
      (delta) => {
        pendingDm.content += delta;
        pendingDm.metadata.pending = !pendingDm.content;
        renderMessageList(els.isekaiMessages, optimisticMessages);
      },
    );
    els.isekaiMessageInput.value = "";
    state.selectedAdventure = response.adventure;
    renderIsekaiAdventureDetail(response.adventure, response.messages);
    setStatus(t("messageSent"), "ok");
  } catch (error) {
    showError(error);
  } finally {
    setDmBusy(false);
  }
}
```

- [ ] **Step 7: Add CSS and i18n**

Add `.workspace.isekai-room-mode`, `.isekai-room`, `.isekai-room-layout`, `.isekai-chat-panel`.

Add translation keys:

```js
"isekaiRoomSubtitle": "Survive the generated world.",
"isekaiSurvivalState": "Survival",
"isekaiInventory": "Inventory",
"isekaiWorldEvents": "World Events",
"isekaiCurrentEnvironment": "Current Environment"
```

Chinese equivalents.

- [ ] **Step 8: Run frontend room tests**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/static/index.html frontend/static/js/state.js frontend/static/js/game.js frontend/static/js/locales/en.js frontend/static/js/locales/zh-CN.js frontend/static/styles.css test/frontend/static/js/test_frontend_isekai_mode.py
git commit -m "Add isekai survival room UI"
```

---

### Task 6: Integration Verification

**Files:**
- Modify tests only if regressions reveal missing mode compatibility.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
uv run pytest test/backend/src/api/test_isekai_mode.py test/backend/src/services/test_isekai_survival.py test/backend/src/api/test_adventure_flow.py test/backend/src/api/test_dm_streaming.py
```

Expected: PASS.

- [ ] **Step 2: Run targeted frontend tests**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py test/frontend/static/js/test_frontend_game_room_layout.py test/frontend/static/js/test_frontend_streaming_ui.py test/frontend/static/js/test_frontend_modularization.py
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

- [ ] **Step 4: Browser verification**

Start or restart service:

```bash
uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 5001
```

Verify in browser:

- `/game` defaults to DND mode and existing DND setup appears.
- Toggle to “异世界生成模拟器”; DND story and character selection disappear.
- Create isekai adventure with a title; “角色正在创建中...” appears.
- Generated adventure opens to isekai room.
- Isekai room shows random character, survival values, inventory, environment, chat, and events.
- DND adventure still opens to existing DND room.

- [ ] **Step 5: Commit any verification fixes**

If verification requires fixes:

```bash
git status --short
git add backend/src/db/sqlite.py backend/src/schemas/adventure.py backend/src/schemas/isekai.py backend/src/services/adventures.py backend/src/services/isekai.py backend/src/agent/dm/service.py backend/src/api/adventures.py frontend/static/index.html frontend/static/js/state.js frontend/static/js/game.js frontend/static/app.js frontend/static/js/locales/en.js frontend/static/js/locales/zh-CN.js frontend/static/styles.css test/backend/src/api/test_isekai_mode.py test/backend/src/services/test_isekai_survival.py test/frontend/static/js/test_frontend_isekai_mode.py
git commit -m "Fix isekai mode integration"
```

Only run the `git add` command after checking `git status --short`; it intentionally lists the files owned by this feature so unrelated files remain unstaged. If no fixes are needed, do not create an empty commit.
