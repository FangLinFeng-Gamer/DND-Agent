# Isekai World Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build adventure-local isekai world events that only display events the character has learned through a plausible in-world channel.

**Architecture:** Reuse the existing `world_events` table and `WorldEventService`, expose known events on `AdventureOut`, add focused isekai services for preference learning and event generation, then render `adventure.world_events` in the isekai room. DND mode keeps its existing world-state and world-event behavior.

**Tech Stack:** FastAPI/Pydantic backend, SQLite persistence, existing OpenAI-compatible LLM client, vanilla JS frontend, pytest and `node --check` verification.

---

## File Structure

- Modify `backend/src/schemas/adventure.py`
  - Add `world_events: list[WorldEventOut]` to `AdventureOut`.
- Modify `backend/src/services/world_events.py`
  - Remove the dependency on `AdventureService` to avoid a service cycle.
  - Validate adventure existence through a direct SQL query.
  - Add `list_known_for_adventure()` for known isekai event listing.
- Modify `backend/src/services/adventures.py`
  - Include known isekai world events when mapping adventure rows.
- Create `backend/src/services/isekai_preferences.py`
  - Owns adventure-local player preference learning cadence and LLM parsing.
- Create `backend/src/services/isekai_events.py`
  - Owns environment channel detection, scale-aware event selection, and world-event persistence.
- Modify `backend/src/services/isekai.py`
  - Increment isekai turn state, call preference learner, call event director, and return updated adventure data.
- Modify `frontend/static/js/game.js`
  - Render isekai events from `adventure.world_events`, not messages.
- Modify `frontend/static/styles.css`
  - Add compact metadata styling for event scope, channel, and source.
- Modify `frontend/static/js/locales/en.js`
  - Add event label strings.
- Modify `frontend/static/js/locales/zh-CN.js`
  - Add Chinese event label strings.
- Modify `test/backend/src/api/test_isekai_mode.py`
  - Cover API exposure and adventure isolation.
- Create `test/backend/src/services/test_isekai_events.py`
  - Cover event director behavior and player-triggered events.
- Create `test/backend/src/services/test_isekai_preferences.py`
  - Cover preference learner cadence and failure fallback.
- Modify `test/backend/src/services/test_isekai_survival.py`
  - Cover turn integration without breaking narration.
- Modify `test/frontend/static/js/test_frontend_isekai_mode.py`
  - Cover frontend rendering source and metadata labels.

## Task 1: Expose Known Isekai World Events On Adventure Responses

**Files:**
- Modify: `backend/src/schemas/adventure.py`
- Modify: `backend/src/services/world_events.py`
- Modify: `backend/src/services/adventures.py`
- Test: `test/backend/src/api/test_isekai_mode.py`

- [ ] **Step 1: Write failing API tests**

Append these tests to `test/backend/src/api/test_isekai_mode.py`:

```python
from backend.src.schemas.world_event import WorldEventCreate
from backend.src.services.world_events import WorldEventService
```

```python
def test_isekai_adventure_detail_includes_known_world_events(client):
    adventure = client.post(
        "/api/adventures",
        json={"title": "Known Events", "mode": "isekai_survival", "locale": "zh-CN"},
    ).json()
    WorldEventService(client.app.state.store).create(
        adventure["id"],
        WorldEventCreate(
            event_type="world",
            title="灰桥镇来了新香料商人",
            description="你从商队那里听说灰桥镇出现了出售异域香料的新商人。",
            importance=3,
            metadata={
                "mode": "isekai_survival",
                "scope": "settlement",
                "source": "preference_weighted",
                "knowledge_channel": "merchant_news",
                "known_to_character": True,
                "affected_area": "灰桥镇",
                "preference_tags": ["美食", "贸易"],
            },
        ),
    )

    response = client.get(f"/api/adventures/{adventure['id']}")

    assert response.status_code == 200
    events = response.json()["world_events"]
    assert len(events) == 1
    assert events[0]["title"] == "灰桥镇来了新香料商人"
    assert events[0]["metadata"]["knowledge_channel"] == "merchant_news"
    assert events[0]["metadata"]["scope"] == "settlement"


def test_isekai_world_events_are_isolated_per_adventure(client):
    first = client.post("/api/adventures", json={"title": "First", "mode": "isekai_survival"}).json()
    second = client.post("/api/adventures", json={"title": "Second", "mode": "isekai_survival"}).json()
    service = WorldEventService(client.app.state.store)
    service.create(
        first["id"],
        WorldEventCreate(
            event_type="world",
            title="只属于第一局",
            description="第一局角色听到的传闻。",
            importance=2,
            metadata={
                "mode": "isekai_survival",
                "scope": "local",
                "source": "random_world",
                "knowledge_channel": "environment_sign",
                "known_to_character": True,
            },
        ),
    )

    response = client.get(f"/api/adventures/{second['id']}")

    assert response.status_code == 200
    assert response.json()["world_events"] == []
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest test/backend/src/api/test_isekai_mode.py::test_isekai_adventure_detail_includes_known_world_events test/backend/src/api/test_isekai_mode.py::test_isekai_world_events_are_isolated_per_adventure
```

Expected: FAIL because `AdventureOut` does not expose `world_events`.

- [ ] **Step 3: Add `world_events` to the schema**

Modify `backend/src/schemas/adventure.py`:

```python
from backend.src.schemas.world_event import WorldEventOut
```

Add this field to `AdventureOut`:

```python
    world_events: list[WorldEventOut] = Field(default_factory=list)
```

- [ ] **Step 4: Remove the service cycle in world events**

Replace `backend/src/services/world_events.py` with direct adventure validation:

```python
from sqlite3 import Row

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.world_event import WorldEventCreate, WorldEventOut


class WorldEventService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def create(self, adventure_id: int, event: WorldEventCreate) -> WorldEventOut:
        self._ensure_adventure_exists(adventure_id)
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO world_events (
                    adventure_id, event_type, title, description, importance, metadata_json
                )
                VALUES (
                    :adventure_id, :event_type, :title, :description, :importance, :metadata_json
                )
                """,
                {
                    "adventure_id": adventure_id,
                    "event_type": event.event_type,
                    "title": event.title,
                    "description": event.description,
                    "importance": event.importance,
                    "metadata_json": encode_json(event.metadata),
                },
            )
            row = conn.execute("SELECT * FROM world_events WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._map_row(row)

    def list_for_adventure(self, adventure_id: int, min_importance: int = 0) -> list[WorldEventOut]:
        self._ensure_adventure_exists(adventure_id)
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM world_events
                WHERE adventure_id = ? AND importance >= ?
                ORDER BY id
                """,
                (adventure_id, min_importance),
            ).fetchall()
        return [self._map_row(row) for row in rows]

    def list_known_for_adventure(self, adventure_id: int, limit: int = 10) -> list[WorldEventOut]:
        events = self.list_for_adventure(adventure_id)
        known = [
            event
            for event in events
            if event.metadata.get("mode") == "isekai_survival"
            and event.metadata.get("known_to_character") is True
        ]
        return known[-limit:]

    def _ensure_adventure_exists(self, adventure_id: int) -> None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT id FROM adventures WHERE id = ?", (adventure_id,)).fetchone()
        if row is None:
            raise api_error(404, "adventure_not_found", "Adventure not found.")

    def _map_row(self, row: Row) -> WorldEventOut:
        return WorldEventOut(
            id=row["id"],
            adventure_id=row["adventure_id"],
            event_type=row["event_type"],
            title=row["title"],
            description=row["description"],
            importance=row["importance"],
            metadata=decode_json(row["metadata_json"], {}),
            created_at=row["created_at"],
        )
```

- [ ] **Step 5: Populate known events in adventure mapping**

Modify `backend/src/services/adventures.py` imports:

```python
from backend.src.services.world_events import WorldEventService
```

Inside `_map_adventure_row`, after `survival_state`:

```python
        world_events = (
            WorldEventService(self.store).list_known_for_adventure(row["id"])
            if mode == "isekai_survival"
            else []
        )
```

Pass the field into `AdventureOut(...)`:

```python
            world_events=world_events,
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
uv run pytest test/backend/src/api/test_isekai_mode.py::test_isekai_adventure_detail_includes_known_world_events test/backend/src/api/test_isekai_mode.py::test_isekai_world_events_are_isolated_per_adventure test/backend/src/services/test_context_world_events.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/schemas/adventure.py backend/src/services/world_events.py backend/src/services/adventures.py test/backend/src/api/test_isekai_mode.py
git commit -m "Expose isekai known world events"
```

## Task 2: Add The Isekai Event Director

**Files:**
- Create: `backend/src/services/isekai_events.py`
- Test: `test/backend/src/services/test_isekai_events.py`

- [ ] **Step 1: Write failing event director tests**

Create `test/backend/src/services/test_isekai_events.py`:

```python
from backend.src.schemas.adventure import AdventureCreate
from backend.src.services.isekai import IsekaiSurvivalService
from backend.src.services.isekai_events import IsekaiWorldEventDirector
from backend.src.services.world_events import WorldEventService


def create_isekai_adventure(store):
    return IsekaiSurvivalService(store).create_adventure(
        AdventureCreate(title="Event Road", mode="isekai_survival", locale="zh-CN")
    )


def test_player_triggered_event_is_recorded_with_action_and_direct_observation(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    turn = {
        "player_input": "我给路边营地的人做一锅热汤。",
        "action_type": "talk",
        "scene": adventure.current_scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(adventure.id, turn, {"turn_count": 1, "player_preferences": {}})

    assert len(events) == 1
    event = events[0]
    assert event.metadata["source"] == "player_triggered"
    assert event.metadata["knowledge_channel"] == "direct_observation"
    assert event.metadata["known_to_character"] is True
    assert event.metadata["triggering_action"] == "我给路边营地的人做一锅热汤。"
    persisted = WorldEventService(store).list_known_for_adventure(adventure.id)
    assert persisted[-1].id == event.id


def test_empty_wilderness_blocks_large_news_without_channel(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    turn = {
        "player_input": "我在无人的森林里继续前进。",
        "action_type": "explore",
        "scene": adventure.current_scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(
        adventure.id,
        turn,
        {
            "turn_count": 4,
            "player_preferences": {},
            "force_event_scope": "global",
        },
    )

    assert events == []
    assert WorldEventService(store).list_known_for_adventure(adventure.id) == []


def test_preference_weighted_event_uses_merchant_channel_when_channel_exists(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    scene = adventure.current_scene.model_copy(update={"location": "灰桥镇集市", "environment": "镇上的集市挤满商队、摊贩和旅人。"})
    turn = {
        "player_input": "我寻找适合开餐厅的食材。",
        "action_type": "forage",
        "scene": scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(
        adventure.id,
        turn,
        {
            "turn_count": 6,
            "player_preferences": {
                "themes": ["美食", "开餐厅", "贸易"],
                "playstyle": ["经营"],
                "goals": ["寻找食材"],
                "confidence": 0.8,
            },
            "force_event_scope": "settlement",
        },
    )

    assert len(events) == 1
    assert events[0].metadata["source"] == "preference_weighted"
    assert events[0].metadata["knowledge_channel"] == "merchant_news"
    assert "美食" in events[0].metadata["preference_tags"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_events.py
```

Expected: FAIL because `backend.src.services.isekai_events` does not exist.

- [ ] **Step 3: Implement deterministic event director**

Create `backend/src/services/isekai_events.py`:

```python
from __future__ import annotations

from typing import Any

from backend.src.schemas.world_event import WorldEventCreate, WorldEventOut
from backend.src.services.world_events import WorldEventService


SCOPE_IMPORTANCE = {
    "local": 1,
    "settlement": 3,
    "regional": 4,
    "national": 4,
    "global": 5,
}


class IsekaiWorldEventDirector:
    def __init__(self, store):
        self.events = WorldEventService(store)

    def evaluate_turn(
        self,
        adventure_id: int,
        turn: dict[str, Any],
        world_state: dict[str, Any],
    ) -> list[WorldEventOut]:
        candidate = self._player_triggered_candidate(turn)
        if candidate is None:
            candidate = self._preference_candidate(turn, world_state)
        if candidate is None:
            candidate = self._random_candidate(turn, world_state)
        if candidate is None:
            return []
        channel = (
            "direct_observation"
            if candidate["source"] == "player_triggered"
            else self._knowledge_channel(turn, candidate["scope"])
        )
        if channel is None:
            return []
        candidate["knowledge_channel"] = channel
        candidate["known_to_character"] = True
        event = self.events.create(adventure_id, self._to_create(candidate, turn))
        return [event]

    def _player_triggered_candidate(self, turn: dict[str, Any]) -> dict[str, Any] | None:
        text = str(turn.get("player_input") or "")
        if not any(keyword in text for keyword in ("做", "烹饪", "煮", "开餐厅", "偷", "帮助", "救", "交易")):
            return None
        if any(keyword in text for keyword in ("做", "烹饪", "煮", "开餐厅")):
            title = "营地记住了陌生料理的香味"
            description = "你亲眼看到周围的人被热食吸引，这件小事开始改变附近营地对你的态度。"
            tags = ["美食", "社交"]
        elif any(keyword in text for keyword in ("偷", "盗")):
            title = "附近商旅提高了警惕"
            description = "你的行动让附近商旅开始互相提醒，看管货物的人明显变多了。"
            tags = ["风险", "贸易"]
        else:
            title = "你的行动改变了附近人的态度"
            description = "你刚才的选择被周围的人看在眼里，附近的态度开始发生细微变化。"
            tags = ["声望"]
        return {
            "event_type": "world",
            "title": title,
            "description": description,
            "scope": "local",
            "source": "player_triggered",
            "affected_area": self._location(turn),
            "preference_tags": tags,
            "triggering_action": text,
        }

    def _preference_candidate(self, turn: dict[str, Any], world_state: dict[str, Any]) -> dict[str, Any] | None:
        preferences = world_state.get("player_preferences") or {}
        tags = [str(tag) for tag in preferences.get("themes", []) + preferences.get("goals", [])]
        if not tags:
            return None
        scope = str(world_state.get("force_event_scope") or "settlement")
        if scope not in SCOPE_IMPORTANCE:
            scope = "settlement"
        if not any(tag in " ".join(tags) for tag in ("美食", "餐厅", "食材", "贸易")):
            return None
        return {
            "event_type": "world",
            "title": "新食材传闻出现在商路上",
            "description": "你从可接触到的消息渠道得知，附近有人正在寻找懂得异域料理的人。",
            "scope": scope,
            "source": "preference_weighted",
            "affected_area": self._location(turn),
            "preference_tags": tags[:4],
            "triggering_action": "",
        }

    def _random_candidate(self, turn: dict[str, Any], world_state: dict[str, Any]) -> dict[str, Any] | None:
        turn_count = int(world_state.get("turn_count", 0))
        if not world_state.get("force_event_scope") and turn_count % 3 != 0:
            return None
        scope = str(world_state.get("force_event_scope") or "local")
        if scope not in SCOPE_IMPORTANCE:
            scope = "local"
        return {
            "event_type": "world",
            "title": "附近环境出现变化",
            "description": "你注意到附近的风向、足迹和生物活动发生了变化。",
            "scope": scope,
            "source": "random_world",
            "affected_area": self._location(turn),
            "preference_tags": [],
            "triggering_action": "",
        }

    def _knowledge_channel(self, turn: dict[str, Any], scope: str) -> str | None:
        scene = turn.get("scene")
        text = f"{getattr(scene, 'location', '')} {getattr(scene, 'environment', '')}".lower()
        if scope == "local":
            return "direct_observation" if turn.get("action_type") != "talk" else "environment_sign"
        if any(keyword in text for keyword in ("集市", "市场", "商队", "商人", "旅人", "酒馆", "城", "镇", "村", "market", "merchant", "town")):
            return "merchant_news"
        if any(keyword in text for keyword in ("神殿", "法师塔", "预言", "temple", "mage")):
            return "dream_omen"
        return None

    def _to_create(self, candidate: dict[str, Any], turn: dict[str, Any]) -> WorldEventCreate:
        scope = candidate["scope"]
        return WorldEventCreate(
            event_type=candidate["event_type"],
            title=candidate["title"],
            description=candidate["description"],
            importance=SCOPE_IMPORTANCE[scope],
            metadata={
                "mode": "isekai_survival",
                "scope": scope,
                "source": candidate["source"],
                "knowledge_channel": candidate["knowledge_channel"],
                "known_to_character": candidate["known_to_character"],
                "location": self._location(turn),
                "affected_area": candidate["affected_area"],
                "preference_tags": candidate["preference_tags"],
                "triggering_action": candidate["triggering_action"],
            },
        )

    def _location(self, turn: dict[str, Any]) -> str:
        scene = turn.get("scene")
        return str(getattr(scene, "location", "") or "未知地点")
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_events.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/isekai_events.py test/backend/src/services/test_isekai_events.py
git commit -m "Add isekai world event director"
```

## Task 3: Add Adventure-Local Preference Learning

**Files:**
- Create: `backend/src/services/isekai_preferences.py`
- Test: `test/backend/src/services/test_isekai_preferences.py`

- [ ] **Step 1: Write failing preference learner tests**

Create `test/backend/src/services/test_isekai_preferences.py`:

```python
import json

from backend.src.services.isekai_preferences import IsekaiPreferenceLearner


class FakePreferenceClient:
    def __init__(self):
        self.calls = []

    def chat(self, model, messages):
        self.calls.append({"model": model, "messages": messages})
        return json.dumps(
            {
                "themes": ["美食", "开餐厅", "贸易"],
                "playstyle": ["经营", "社交"],
                "goals": ["寻找食材"],
                "confidence": 0.82,
            },
            ensure_ascii=False,
        )


class FailingPreferenceClient:
    def chat(self, model, messages):
        raise RuntimeError("model unavailable")


class FakeModel:
    model_name = "preference-model"


def test_preference_learner_runs_on_fifth_effective_turn():
    client = FakePreferenceClient()
    learner = IsekaiPreferenceLearner(llm_client=client)
    world_state = {"turn_count": 5}
    messages = [
        {"role": "player", "content": "我想寻找食材，以后开一家餐厅。"},
        {"role": "dm", "content": "你闻到林间蘑菇的气味。"},
    ]

    updated = learner.maybe_update(world_state, messages, FakeModel())

    assert len(client.calls) == 1
    assert updated["player_preferences"]["themes"] == ["美食", "开餐厅", "贸易"]
    assert updated["player_preferences"]["updated_turn"] == 5
    assert updated["player_preferences"]["confidence"] == 0.82


def test_preference_learner_skips_non_cadence_turns():
    client = FakePreferenceClient()
    learner = IsekaiPreferenceLearner(llm_client=client)

    updated = learner.maybe_update({"turn_count": 4}, [], FakeModel())

    assert client.calls == []
    assert "player_preferences" not in updated


def test_preference_learner_keeps_previous_preferences_when_model_fails():
    learner = IsekaiPreferenceLearner(llm_client=FailingPreferenceClient())
    world_state = {
        "turn_count": 10,
        "player_preferences": {
            "themes": ["探索"],
            "playstyle": ["谨慎"],
            "goals": [],
            "confidence": 0.4,
            "updated_turn": 5,
        },
    }

    updated = learner.maybe_update(world_state, [], FakeModel())

    assert updated["player_preferences"]["themes"] == ["探索"]
    assert updated["player_preferences"]["updated_turn"] == 5
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_preferences.py
```

Expected: FAIL because `backend.src.services.isekai_preferences` does not exist.

- [ ] **Step 3: Implement the preference learner**

Create `backend/src/services/isekai_preferences.py`:

```python
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


class IsekaiPreferenceLearner:
    CADENCE = 5

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def maybe_update(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        model: Any | None,
    ) -> dict[str, Any]:
        updated = deepcopy(world_state)
        turn_count = int(updated.get("turn_count", 0))
        if turn_count <= 0 or turn_count % self.CADENCE != 0:
            return updated
        current = updated.get("player_preferences") or {}
        if int(current.get("updated_turn", 0)) == turn_count:
            return updated
        if not model or not self.llm_client or not hasattr(self.llm_client, "chat"):
            return updated
        try:
            raw = self.llm_client.chat(model, self._messages(messages, updated))
            payload = json.loads(raw)
        except Exception:
            return updated
        preferences = {
            "themes": self._string_list(payload.get("themes")),
            "playstyle": self._string_list(payload.get("playstyle")),
            "goals": self._string_list(payload.get("goals")),
            "confidence": max(0.0, min(1.0, float(payload.get("confidence", 0.5)))),
            "updated_turn": turn_count,
        }
        updated["player_preferences"] = preferences
        return updated

    def _messages(self, messages: list[dict[str, Any]], world_state: dict[str, Any]) -> list[dict[str, str]]:
        recent = [
            {
                "role": str(message.get("role") or ""),
                "content": str(message.get("content") or ""),
            }
            for message in messages[-12:]
        ]
        payload = {
            "role_boundaries": {
                "player": "用户控制的角色行动和目标。",
                "dm": "agent 生成的叙事，不等同于用户偏好。",
                "system_state": "后端记录的本局状态。",
            },
            "recent_messages": recent,
            "system_state": {"turn_count": world_state.get("turn_count", 0)},
        }
        return [
            {
                "role": "system",
                "content": (
                    "你负责总结异世界生存游戏中玩家当前的游玩偏好。"
                    "只根据玩家消息判断偏好，DM 消息只能作为上下文。"
                    "只输出 JSON：{\"themes\":[],\"playstyle\":[],\"goals\":[],\"confidence\":0.0}"
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()][:6]
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_preferences.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/isekai_preferences.py test/backend/src/services/test_isekai_preferences.py
git commit -m "Add isekai preference learning"
```

## Task 4: Integrate Events And Preferences Into Isekai Turns

**Files:**
- Modify: `backend/src/services/isekai.py`
- Modify: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing integration tests**

Append to `test/backend/src/services/test_isekai_survival.py`:

```python
def test_isekai_turn_records_known_world_events(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Event Turn", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我给路边营地的人做一锅热汤。", locale="zh-CN"))

    events = response.adventure.world_events
    assert events
    assert events[-1].metadata["source"] == "player_triggered"
    assert events[-1].metadata["known_to_character"] is True
    assert events[-1].metadata["triggering_action"] == "我给路边营地的人做一锅热汤。"


def test_isekai_turn_count_is_adventure_local(store):
    service = IsekaiSurvivalService(store)
    first = service.create_adventure(AdventureCreate(title="First Counter", mode="isekai_survival"))
    second = service.create_adventure(AdventureCreate(title="Second Counter", mode="isekai_survival"))

    first_response = service.advance(first.id, MessageCreate(content="我沿着旧猎径探索。", locale="zh-CN"))
    fresh_second = service.adventures.get(second.id)

    assert first_response.adventure.world_state["turn_count"] == 1
    assert fresh_second.world_state["turn_count"] == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_turn_records_known_world_events test/backend/src/services/test_isekai_survival.py::test_isekai_turn_count_is_adventure_local
```

Expected: FAIL because isekai turns do not call the event director or update `world_state.turn_count`.

- [ ] **Step 3: Wire services into `IsekaiSurvivalService`**

Modify imports in `backend/src/services/isekai.py`:

```python
from backend.src.services.isekai_events import IsekaiWorldEventDirector
from backend.src.services.isekai_preferences import IsekaiPreferenceLearner
```

Modify `__init__`:

```python
        self.event_director = IsekaiWorldEventDirector(store)
        self.preference_learner = IsekaiPreferenceLearner(llm_client=llm_client)
```

Add this method:

```python
    def advance_world_context(self, adventure_id: int, turn: dict[str, Any]) -> dict[str, Any]:
        world_state = self.adventures.get_world_state(adventure_id)
        world_state["turn_count"] = int(world_state.get("turn_count", 0)) + 1
        messages = [
            {"role": message.role, "content": message.content}
            for message in self.adventures.list_messages(adventure_id)
        ]
        world_state = self.preference_learner.maybe_update(world_state, messages, self.active_model())
        self.adventures.update_world_state(adventure_id, world_state)
        self.event_director.evaluate_turn(adventure_id, turn, world_state)
        return world_state
```

Call it at the end of `prepare_turn`, after `fallback` is built and before `return`:

```python
        turn = {
            "player_input": message.content,
            "player_message": player_message,
            "action_type": action_type,
            "delta": delta,
            "survival": survival,
            "scene": scene,
            "character": character,
            "fallback": fallback,
        }
        turn["world_state"] = self.advance_world_context(adventure_id, turn)
        return turn
```

Remove the old immediate dictionary return in `prepare_turn` so this new `turn` dictionary is returned once.

- [ ] **Step 4: Run integration tests to verify pass**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_turn_records_known_world_events test/backend/src/services/test_isekai_survival.py::test_isekai_turn_count_is_adventure_local
```

Expected: PASS.

- [ ] **Step 5: Run isekai backend test suite**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_events.py test/backend/src/services/test_isekai_preferences.py test/backend/src/api/test_isekai_mode.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/isekai.py test/backend/src/services/test_isekai_survival.py
git commit -m "Integrate isekai world events into turns"
```

## Task 5: Render Real World Events In The Isekai Frontend

**Files:**
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/styles.css`
- Modify: `frontend/static/js/locales/en.js`
- Modify: `frontend/static/js/locales/zh-CN.js`
- Modify: `test/frontend/static/js/test_frontend_isekai_mode.py`

- [ ] **Step 1: Write failing frontend tests**

Replace `test_isekai_world_events_use_event_cards_instead_of_stat_rows` in `test/frontend/static/js/test_frontend_isekai_mode.py` with:

```python
def test_isekai_world_events_render_adventure_world_events_not_messages():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
    text = frontend_text()

    detail_block = game_js.split("function renderIsekaiAdventureDetail", 1)[1].split("function renderIsekaiPanel", 1)[0]
    assert "renderIsekaiEvents(adventure.world_events || [])" in detail_block

    events_block = game_js.split("function renderIsekaiEvents", 1)[1].split("export function", 1)[0]
    assert "message.content" not in events_block
    assert "event.title" in events_block
    assert "event.description" in events_block
    assert "isekai-event-meta" in events_block
    assert "event.metadata?.scope" in events_block
    assert "event.metadata?.knowledge_channel" in events_block
    assert ".isekai-event-meta" in css
    assert '"eventScope": "Scope"' in text
    assert '"eventScope": "影响范围"' in text
    assert '"eventKnowledgeChannel": "Known by"' in text
    assert '"eventKnowledgeChannel": "得知途径"' in text
```

- [ ] **Step 2: Run frontend test to verify failure**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py::test_isekai_world_events_render_adventure_world_events_not_messages
```

Expected: FAIL because the frontend still passes messages into `renderIsekaiEvents`.

- [ ] **Step 3: Pass world events into the renderer**

Modify `renderIsekaiAdventureDetail` in `frontend/static/js/game.js`:

```javascript
  renderIsekaiEvents(adventure.world_events || []);
```

- [ ] **Step 4: Render event cards with metadata**

Replace `renderIsekaiEvents` in `frontend/static/js/game.js`:

```javascript
function renderIsekaiEvents(events) {
  const target = els.isekaiEventsPanel;
  if (!target) {
    return;
  }
  target.replaceChildren();
  const heading = document.createElement("h2");
  heading.textContent = t("isekaiWorldEvents");
  target.append(heading);

  const knownEvents = (events || []).slice(-10);
  if (!knownEvents.length) {
    target.append(emptyNode(t("isekaiNoKnownWorldEvents")));
    return;
  }

  const list = document.createElement("div");
  list.className = "isekai-event-list";
  knownEvents.forEach((event) => {
    const card = document.createElement("article");
    card.className = "isekai-event-card";
    const title = document.createElement("strong");
    title.className = "isekai-event-title";
    title.textContent = event.title || t("isekaiWorldEvents");
    const body = document.createElement("p");
    body.textContent = event.description || "";
    const meta = document.createElement("div");
    meta.className = "isekai-event-meta";
    const scope = document.createElement("span");
    scope.textContent = `${t("eventScope")}: ${localizeEventValue(event.metadata?.scope)}`;
    const channel = document.createElement("span");
    channel.textContent = `${t("eventKnowledgeChannel")}: ${localizeEventValue(event.metadata?.knowledge_channel)}`;
    meta.append(scope, channel);
    if (event.metadata?.source === "player_triggered" || event.metadata?.source === "preference_weighted") {
      const source = document.createElement("span");
      source.textContent = `${t("eventSource")}: ${localizeEventValue(event.metadata.source)}`;
      meta.append(source);
    }
    card.append(title, body, meta);
    list.append(card);
  });
  target.append(list);
}

function localizeEventValue(value) {
  if (!value) {
    return t("notSet");
  }
  return t(`eventValue.${value}`) || value;
}
```

- [ ] **Step 5: Add locale labels**

Add to `frontend/static/js/locales/en.js`:

```javascript
  "isekaiNoKnownWorldEvents": "No known world events yet",
  "eventScope": "Scope",
  "eventKnowledgeChannel": "Known by",
  "eventSource": "Source",
  "eventValue.local": "Local",
  "eventValue.settlement": "Settlement",
  "eventValue.regional": "Regional",
  "eventValue.national": "National",
  "eventValue.global": "Global",
  "eventValue.direct_observation": "Direct observation",
  "eventValue.environment_sign": "Environment signs",
  "eventValue.merchant_news": "Merchant news",
  "eventValue.npc_rumor": "NPC rumor",
  "eventValue.notice_board": "Notice board",
  "eventValue.tavern_gossip": "Tavern gossip",
  "eventValue.magic_message": "Magic message",
  "eventValue.dream_omen": "Dream omen",
  "eventValue.random_world": "World event",
  "eventValue.player_triggered": "Triggered by player",
  "eventValue.preference_weighted": "Preference-related",
```

Add to `frontend/static/js/locales/zh-CN.js`:

```javascript
  "isekaiNoKnownWorldEvents": "暂无已知世界事件",
  "eventScope": "影响范围",
  "eventKnowledgeChannel": "得知途径",
  "eventSource": "来源",
  "eventValue.local": "本地",
  "eventValue.settlement": "城镇",
  "eventValue.regional": "地区",
  "eventValue.national": "国家",
  "eventValue.global": "世界",
  "eventValue.direct_observation": "亲眼所见",
  "eventValue.environment_sign": "环境迹象",
  "eventValue.merchant_news": "商队消息",
  "eventValue.npc_rumor": "NPC 传闻",
  "eventValue.notice_board": "公告栏",
  "eventValue.tavern_gossip": "酒馆闲谈",
  "eventValue.magic_message": "魔法通讯",
  "eventValue.dream_omen": "梦境异兆",
  "eventValue.random_world": "随机世界事件",
  "eventValue.player_triggered": "玩家行动触发",
  "eventValue.preference_weighted": "偏好相关",
```

- [ ] **Step 6: Add metadata styling**

Append near existing `.isekai-event-card` styles in `frontend/static/styles.css`:

```css
.isekai-event-title {
  display: block;
  color: #f0e2bb;
  font-family: var(--font-display);
  font-size: 14px;
  line-height: 1.35;
}

.isekai-event-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
}

.isekai-event-meta span {
  border: 1px solid rgba(169, 140, 84, .24);
  border-radius: 999px;
  color: #bda878;
  font-size: 11px;
  line-height: 1.2;
  padding: 4px 7px;
}
```

- [ ] **Step 7: Run frontend checks**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py::test_isekai_world_events_render_adventure_world_events_not_messages
node --check frontend/static/js/game.js
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/static/js/game.js frontend/static/styles.css frontend/static/js/locales/en.js frontend/static/js/locales/zh-CN.js test/frontend/static/js/test_frontend_isekai_mode.py
git commit -m "Render isekai known world events"
```

## Task 6: End-To-End Verification

**Files:**
- Modify only if a verification failure exposes a bug in the files from Tasks 1-5.

- [ ] **Step 1: Run backend isekai and world-event tests**

Run:

```bash
uv run pytest test/backend/src/api/test_isekai_mode.py test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_events.py test/backend/src/services/test_isekai_preferences.py test/backend/src/services/test_context_world_events.py
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests and JS syntax check**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py
node --check frontend/static/js/game.js
```

Expected: PASS.

- [ ] **Step 3: Restart local service on port 5002**

If a previous server session is running, stop it with Ctrl-C. Then run:

```bash
uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 5002
```

Expected: Uvicorn reports it is running on `http://127.0.0.1:5002`.

- [ ] **Step 4: Manual browser verification**

Open:

```text
http://127.0.0.1:5002/game/30
```

Send:

```text
我给路边营地的人做一锅热汤。
```

Expected:

- Chat streams normally from the DM.
- The world events panel displays an event card, not the DM narration.
- The event card includes title, description, influence scope, knowledge channel, and source.
- The event source says it was triggered by player action.

- [ ] **Step 5: Commit verification fixes if any**

If no files changed, do not create a commit. If fixes were needed:

```bash
git add backend/src/services/isekai.py backend/src/services/isekai_events.py backend/src/services/isekai_preferences.py backend/src/services/adventures.py backend/src/services/world_events.py backend/src/schemas/adventure.py frontend/static/js/game.js frontend/static/styles.css frontend/static/js/locales/en.js frontend/static/js/locales/zh-CN.js test/backend/src/api/test_isekai_mode.py test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_events.py test/backend/src/services/test_isekai_preferences.py test/frontend/static/js/test_frontend_isekai_mode.py
git commit -m "Fix isekai world event verification issues"
```

Expected: commit only if verification required code changes.
