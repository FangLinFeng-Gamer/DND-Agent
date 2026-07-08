# Isekai Structured Playability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make isekai survival turns produce reliable action classification, structured scene objects, validated inventory/NPC state changes, visible interaction prompts, and adventure-local pressure clocks.

**Architecture:** Keep deterministic rules authoritative. `IsekaiTimeService` classifies actions and advances survival pressure; `IsekaiSurvivalService` asks the model for structured JSON; a focused state-change layer sanitizes model proposals before applying them to `isekai_characters`, `current_scene`, and `world_state`. Frontend rendering reads structured metadata/current scene and gives the player non-sending suggested-action buttons.

**Tech Stack:** Python 3.12, FastAPI/Pydantic models, SQLite JSON columns, pytest, vanilla JS modules, static CSS/i18n.

---

## File Map

- Modify `backend/src/services/isekai_time.py`: add `gather`, `seek_shelter`, and `manage_inventory` classification and survival deltas.
- Modify `backend/src/schemas/adventure.py`: extend `SceneState` with `interactables`, `suggested_actions`, and `npc_states` while preserving old fields.
- Create `backend/src/services/isekai_state_changes.py`: sanitize model structured fields, apply inventory changes, NPC updates, interactables, suggested actions, and pressure clock updates.
- Modify `backend/src/services/isekai.py`: require structured JSON, parse new fields, apply state changes after narration generation, include metadata and pressure clocks.
- Modify `backend/src/services/adventures.py`: ensure isekai scene output normalizes new fields and public world state includes pressure clocks.
- Modify `frontend/static/js/game.js`: render isekai interactables/actions below DM messages and pressure clocks in the world info panel.
- Modify `frontend/static/js/locales/en.js` and `frontend/static/js/locales/zh-CN.js`: labels for interactables, suggestions, pressure clocks.
- Modify `frontend/static/styles.css`: compact styling for interaction cards, action chips, and pressure clock bars.
- Test `test/backend/src/services/test_isekai_time.py`: action classification.
- Test `test/backend/src/services/test_isekai_survival.py`: model state changes, NPC sync, pressure clocks.
- Test `test/frontend/static/js/test_frontend_isekai_mode.py`: frontend rendering hooks.

## Task 1: Action Classification

**Files:**
- Modify: `test/backend/src/services/test_isekai_time.py`
- Modify: `backend/src/services/isekai_time.py`

- [ ] **Step 1: Write failing classification tests**

Add tests:

```python
def test_gather_action_advances_time_without_table_talk():
    service = IsekaiTimeService()

    action = service.classify_action("我摘点红浆果。")

    assert action.action_type == "gather"
    assert action.advances_time is True
    assert action.time_cost_minutes == 30
    assert action.survival_intent == "gather"


def test_seek_shelter_does_not_trigger_sleep():
    service = IsekaiTimeService()

    action = service.classify_action("我找个可以过夜的地方。")

    assert action.action_type == "seek_shelter"
    assert action.advances_time is True
    assert action.time_cost_minutes == 45
    assert action.survival_intent == "shelter"


def test_explicit_overnight_sleep_still_sleeps_until_morning():
    service = IsekaiTimeService()

    action = service.classify_action("我在这里睡觉过夜。")

    assert action.action_type == "sleep"
    assert action.advances_time is True


def test_manage_inventory_action_is_not_status_check():
    service = IsekaiTimeService()

    action = service.classify_action("我扔掉红浆果。")

    assert action.action_type == "manage_inventory"
    assert action.advances_time is True
    assert action.time_cost_minutes == 5
```

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest test/backend/src/services/test_isekai_time.py::test_gather_action_advances_time_without_table_talk test/backend/src/services/test_isekai_time.py::test_seek_shelter_does_not_trigger_sleep test/backend/src/services/test_isekai_time.py::test_manage_inventory_action_is_not_status_check -q`

Expected: FAIL because new action types are missing.

- [ ] **Step 3: Implement minimal classification and deltas**

Add checks before generic search/travel/sleep:

```python
if self._is_seek_shelter(text):
    return IsekaiActionResolution("seek_shelter", 45, True, "shelter", "角色寻找可过夜或避险的庇护点。")
if self._is_manage_inventory(text):
    return IsekaiActionResolution("manage_inventory", 5, True, "inventory", "角色整理、取出或丢弃物品。")
if self._is_gather(text):
    return IsekaiActionResolution("gather", 30, True, "gather", "角色采集或拾取附近物品。")
```

Add extras:

```python
"gather": {"fatigue": 2, "thirst": 1},
"seek_shelter": {"fatigue": 1, "morale": 1},
"manage_inventory": {"fatigue": 0},
```

- [ ] **Step 4: Run focused tests GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_time.py -q`

Expected: PASS.

## Task 2: Scene Schema

**Files:**
- Modify: `backend/src/schemas/adventure.py`
- Modify: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing schema test**

Add:

```python
def test_scene_state_accepts_structured_isekai_interactables():
    scene = SceneState(
        location="伐木营地",
        environment="雨后的木棚旁有猎犬低吼。",
        important_objects=[],
        npcs=[],
        current_objective="找到可以过夜的庇护点。",
        interactables=[
            {
                "id": "lumberjack_01",
                "type": "npc",
                "name": "戒备的伐木工",
                "state": "戒备",
                "affordances": ["交涉", "请求借宿"],
                "risk": "态度恶化可能引来猎犬",
            }
        ],
        suggested_actions=["向伐木工说明来意"],
        npc_states=[
            {
                "id": "lumberjack_01",
                "name": "伐木工",
                "attitude": "suspicious",
                "trust": 20,
                "known_facts": ["玩家是外来者"],
            }
        ],
    )

    assert scene.interactables[0]["name"] == "戒备的伐木工"
    assert scene.suggested_actions == ["向伐木工说明来意"]
    assert scene.npc_states[0]["trust"] == 20
```

- [ ] **Step 2: Run test RED**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_scene_state_accepts_structured_isekai_interactables -q`

Expected: FAIL because fields are not on `SceneState`.

- [ ] **Step 3: Add fields**

Add to `SceneState`:

```python
interactables: list[dict[str, Any]] = Field(default_factory=list)
suggested_actions: list[str] = Field(default_factory=list)
npc_states: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Run schema test GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_scene_state_accepts_structured_isekai_interactables -q`

Expected: PASS.

## Task 3: Structured Model Payload Parsing

**Files:**
- Modify: `test/backend/src/services/test_isekai_survival.py`
- Modify: `backend/src/services/isekai.py`

- [ ] **Step 1: Write failing parser test**

Add:

```python
def test_isekai_model_payload_parses_structured_fields(store):
    service = IsekaiSurvivalService(store)
    raw = json.dumps(
        {
            "narration": "你拿起猎网和燧石碎片。",
            "scene_update": {"important_objects": ["旧木棚"]},
            "interactables": [{"id": "net_01", "type": "item", "name": "猎网"}],
            "suggested_actions": ["检查猎网是否还能使用"],
            "state_changes": {"add_items": ["猎网", "燧石碎片"]},
        },
        ensure_ascii=False,
    )

    payload = service.parse_model_payload(raw, "fallback")

    assert payload["narration"] == "你拿起猎网和燧石碎片。"
    assert payload["interactables"][0]["name"] == "猎网"
    assert payload["suggested_actions"] == ["检查猎网是否还能使用"]
    assert payload["state_changes"]["add_items"] == ["猎网", "燧石碎片"]
```

- [ ] **Step 2: Run parser test RED**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_model_payload_parses_structured_fields -q`

Expected: FAIL because parser drops new fields.

- [ ] **Step 3: Extend parser with conservative pass-through**

In `parse_model_payload`, when values are dict/list, include `interactables`, `suggested_actions`, and `state_changes` for the later state-change layer:

```python
for key in ["interactables", "suggested_actions", "state_changes"]:
    if key in payload:
        result[key] = payload[key]
```

- [ ] **Step 4: Run parser test GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_model_payload_parses_structured_fields -q`

Expected: PASS.

## Task 4: State Change Service

**Files:**
- Create: `backend/src/services/isekai_state_changes.py`
- Modify: `test/backend/src/services/test_isekai_survival.py`
- Modify: `backend/src/services/isekai.py`

- [ ] **Step 1: Write failing state-change tests**

Add tests using fake LLM payloads:

```python
def test_model_state_changes_add_items_to_isekai_inventory(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你拿起猎网和燧石碎片。",
            "state_changes": {"add_items": ["猎网", "燧石碎片"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Item Sync", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="拿起猎网和燧石碎片", locale="zh-CN"))

    inventory = response.adventure.isekai_character["inventory"]
    assert "猎网" in inventory
    assert "燧石碎片" in inventory
    assert response.dm_message.metadata["state_changes_applied"]["inventory_added"] == ["猎网", "燧石碎片"]
```

```python
def test_model_state_changes_remove_items_from_isekai_inventory(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=StructuredStateChangeIsekaiLLMClient({"narration": "你扔掉红浆果。", "state_changes": {"remove_items": ["红浆果"]}}))
    adventure = service.create_adventure(AdventureCreate(title="Drop Sync", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["红浆果", "干粮 x2"])

    response = service.advance(adventure.id, MessageCreate(content="扔掉红浆果", locale="zh-CN"))

    assert "红浆果" not in response.adventure.isekai_character["inventory"]
    assert "红浆果" in response.dm_message.metadata["state_changes_applied"]["inventory_removed"]
```

- [ ] **Step 2: Run tests RED**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_model_state_changes_add_items_to_isekai_inventory test/backend/src/services/test_isekai_survival.py::test_model_state_changes_remove_items_from_isekai_inventory -q`

Expected: FAIL because no state-change service is connected.

- [ ] **Step 3: Implement `IsekaiStateChangeService`**

Create methods:

```python
class IsekaiStateChangeService:
    def apply(self, adventure_id: int, character: dict[str, Any], scene: SceneState, world_state: dict[str, Any], payload: dict[str, Any]) -> IsekaiStateChangeResult:
        ...
```

The implementation sanitizes `add_items` and `remove_items`, updates `isekai_characters.inventory_json`, and returns metadata:

```python
{
    "inventory_added": added,
    "inventory_removed": removed,
    "npc_updates": applied_npcs,
    "pressure_updates": applied_clocks,
    "errors": errors,
}
```

- [ ] **Step 4: Connect service in `IsekaiSurvivalService`**

Call the service after narration generation and before DM metadata append. Update turn with `state_changes_applied` and refreshed character/world state.

- [ ] **Step 5: Run state-change tests GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_model_state_changes_add_items_to_isekai_inventory test/backend/src/services/test_isekai_survival.py::test_model_state_changes_remove_items_from_isekai_inventory -q`

Expected: PASS.

## Task 5: NPC And Interactable Sync

**Files:**
- Modify: `backend/src/services/isekai_state_changes.py`
- Modify: `backend/src/services/isekai.py`
- Modify: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing NPC sync test**

Add:

```python
def test_model_npc_updates_enter_scene_state(store):
    activate_test_model(store)
    payload = {
        "narration": "伐木工放低斧头，但仍盯着你的短弓。",
        "interactables": [{"id": "lumberjack_01", "type": "npc", "name": "戒备的伐木工", "affordances": ["交涉"], "risk": "可能引来猎犬"}],
        "suggested_actions": ["和伐木工说明来意"],
        "state_changes": {
            "npc_updates": [
                {"id": "lumberjack_01", "name": "伐木工", "attitude": "wary", "trust_delta": 10, "known_facts": ["玩家主动说明来意"]}
            ]
        },
    }
    service = IsekaiSurvivalService(store, llm_client=StructuredStateChangeIsekaiLLMClient(payload))
    adventure = service.create_adventure(AdventureCreate(title="NPC Sync", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="和伐木工说明来意", locale="zh-CN"))

    scene = response.adventure.current_scene
    assert scene.interactables[0]["id"] == "lumberjack_01"
    assert scene.suggested_actions == ["和伐木工说明来意"]
    assert scene.npc_states[0]["name"] == "伐木工"
    assert scene.npc_states[0]["trust"] == 30
    assert "伐木工" in scene.npcs
```

- [ ] **Step 2: Run NPC test RED**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_model_npc_updates_enter_scene_state -q`

Expected: FAIL because scene fields are not applied.

- [ ] **Step 3: Implement scene merge**

Sanitize interactables and suggested actions, merge NPC updates by `id`, clamp trust, and call `AdventureService.update_scene()`.

- [ ] **Step 4: Run NPC test GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_model_npc_updates_enter_scene_state -q`

Expected: PASS.

## Task 6: Pressure Clocks

**Files:**
- Modify: `backend/src/services/isekai_state_changes.py`
- Modify: `backend/src/services/isekai.py`
- Modify: `backend/src/services/adventures.py`
- Modify: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing pressure clock tests**

Add:

```python
def test_isekai_world_state_initializes_pressure_clocks(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Start", mode="isekai_survival"))

    clocks = adventure.world_state["pressure_clocks"]

    assert {clock["id"] for clock in clocks} >= {"sunset", "outsider_suspicion", "curfew_patrol", "beast_activity", "weather_thirst"}
```

```python
def test_isekai_action_advances_pressure_clocks(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Advance", mode="isekai_survival"))
    before = {clock["id"]: clock["value"] for clock in adventure.world_state["pressure_clocks"]}

    response = service.advance(adventure.id, MessageCreate(content="我摘点红浆果。", locale="zh-CN"))

    after = {clock["id"]: clock["value"] for clock in response.adventure.world_state["pressure_clocks"]}
    assert after["sunset"] > before["sunset"]
    assert response.dm_message.metadata["pressure_clocks"]
```

- [ ] **Step 2: Run clock tests RED**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_world_state_initializes_pressure_clocks test/backend/src/services/test_isekai_survival.py::test_isekai_action_advances_pressure_clocks -q`

Expected: FAIL because pressure clocks are not initialized.

- [ ] **Step 3: Implement pressure clocks**

Add default clocks during `initialize_scene_facts()`. Advance clock values based on time cost and action type. Store in `world_state["pressure_clocks"]` and metadata.

- [ ] **Step 4: Run clock tests GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_world_state_initializes_pressure_clocks test/backend/src/services/test_isekai_survival.py::test_isekai_action_advances_pressure_clocks -q`

Expected: PASS.

## Task 7: Frontend Interaction Rendering

**Files:**
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/locales/en.js`
- Modify: `frontend/static/js/locales/zh-CN.js`
- Modify: `frontend/static/styles.css`
- Modify: `test/frontend/static/js/test_frontend_isekai_mode.py`

- [ ] **Step 1: Write failing frontend static tests**

Add tests that assert:

```python
assert "renderIsekaiMessageExtras" in game_js
assert "isekai-interactables" in game_js
assert "isekai-suggested-actions" in game_js
assert "addEventListener(\"click\"" in game_js
assert "isekai-pressure-clock" in game_js
assert ".isekai-pressure-clock" in css
assert '"isekaiInteractables": "Interactables"' in i18n
assert '"isekaiInteractables": "可互动内容"' in i18n
```

- [ ] **Step 2: Run frontend tests RED**

Run: `uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py::test_isekai_dm_messages_render_interactables_and_suggestions test/frontend/static/js/test_frontend_isekai_mode.py::test_isekai_world_panel_renders_pressure_clocks -q`

Expected: FAIL because render helpers and labels are missing.

- [ ] **Step 3: Implement message extras**

In `renderMessageList`, append extras for isekai DM messages:

```javascript
const extras = renderIsekaiMessageExtras(message);
if (extras) {
  article.append(extras);
}
```

Suggested action buttons set `els.isekaiMessageInput.value = suggestion` and focus the input.

- [ ] **Step 4: Implement pressure clock rendering**

In the isekai world/environment panel, read `adventure.world_state.pressure_clocks` and render compact bars.

- [ ] **Step 5: Run frontend tests GREEN**

Run: `uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py -q`

Expected: PASS.

## Task 8: Integration Verification

**Files:**
- Existing backend and frontend files touched above.

- [ ] **Step 1: Run focused backend suite**

Run: `uv run pytest test/backend/src/services/test_isekai_time.py test/backend/src/services/test_isekai_survival.py -q`

Expected: PASS.

- [ ] **Step 2: Run focused frontend suite**

Run: `uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py -q`

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run: `uv run pytest -q`

Expected: PASS.

- [ ] **Step 4: Restart verification server**

Run: `uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 5002`

Expected: `Uvicorn running on http://127.0.0.1:5002`.

