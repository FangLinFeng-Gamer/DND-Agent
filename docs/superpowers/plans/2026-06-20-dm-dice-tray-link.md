# DM Dice Tray Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect DM-requested ability checks to the existing frontend dice tray so players roll checks before the DM resolves the outcome.

**Architecture:** Backend DM responses create adventure-message `pending_check` metadata instead of immediately rolling player ability checks. A new resolve endpoint accepts a raw d20 result, validates it against the adventure-local character state, stores `dice_result`, and asks the DM service to continue from a tool-originated check result. The frontend renders pending checks under DM messages, rolls through `dice.js`, submits the result, and refreshes the game state.

**Tech Stack:** FastAPI, Pydantic schemas, SQLite message metadata, existing DMService, vanilla ES modules, existing static frontend tests, pytest.

---

## File Structure

- `backend/src/schemas/adventure.py`: add `AbilityCheckResolveRequest`.
- `backend/src/services/adventures.py`: add message lookup and metadata update helpers.
- `backend/src/agent/dm/service.py`: create pending checks, resolve player check results, and continue narration from tool context.
- `backend/src/agent/dm/prompts.py`: teach DM prompt about tool-originated ability check results.
- `backend/src/api/adventures.py`: add `POST /api/adventures/{adventure_id}/checks/{check_id}/resolve`.
- `frontend/static/js/dice.js`: expose Promise-based dice rolling while preserving button clicks.
- `frontend/static/js/api.js`: add check resolve API helper.
- `frontend/static/js/game.js`: render pending/resolved check controls and call dice resolve flow.
- `frontend/static/js/locales/en.js`, `frontend/static/js/locales/zh-CN.js`: add check UI labels.
- `frontend/static/styles.css`: style compact check controls.
- Tests:
  - `test/backend/src/agent/dm/test_dm_pending_checks.py`
  - `test/backend/src/api/test_dm_check_resolution.py`
  - `test/frontend/static/js/test_frontend_dice_checks.py`

## Task 1: Backend Pending Check Instead Of Auto Roll

**Files:**
- Modify: `backend/src/agent/dm/service.py`
- Test: `test/backend/src/agent/dm/test_dm_pending_checks.py`

- [ ] **Step 1: Write failing tests**

Create `test/backend/src/agent/dm/test_dm_pending_checks.py`:

```python
import json

from backend.src.schemas.adventure import AdventureCreate, MessageCreate
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.dm import DMService
from backend.src.services.llm_models import LLMModelService


class FakeLLMClient:
    def __init__(self, response: dict):
        self.response = response

    def chat(self, model, messages):
        return json.dumps(self.response)


def activate_model(store):
    service = LLMModelService(store)
    model = service.create(
        LLMModelCreate(
            name="Check Model",
            base_url="http://127.0.0.1:11434/v1",
            api_key="sk-local",
            model_name="local-dm",
        )
    )
    return service.activate(model.id)


def create_adventure(client, dm_service):
    character = client.post(
        "/api/characters",
        json={"name": "Check Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = dm_service.create_adventure(AdventureCreate(title="Check Gate", character_id=character["id"]))
    return character, adventure


def test_model_requested_player_check_creates_pending_check_without_dice_result(client):
    activate_model(client.app.state.store)
    fake = FakeLLMClient(
        {
            "narration": "The wall is slick; you need a Dexterity check to climb it.",
            "scene": {
                "location": "Yard",
                "environment": "A slick wooden wall blocks the alley.",
                "important_objects": ["wooden wall"],
                "npcs": [],
                "current_objective": "Climb the wall.",
                "world_changes": [],
            },
            "requires_check": True,
            "check": {"ability": "dexterity", "dc": 12, "reason": "Climb the slick wall"},
            "npc_actions": [],
            "world_events": [],
        }
    )
    dm_service = DMService(client.app.state.store, llm_client=fake)
    character, adventure = create_adventure(client, dm_service)

    response = dm_service.advance(adventure.id, MessageCreate(content="I climb the wall.", character_id=character["id"]))

    assert response.dice_result is None
    pending = response.dm_message.metadata["pending_check"]
    assert pending["status"] == "pending"
    assert pending["ability"] == "dexterity"
    assert pending["dc"] == 12
    assert pending["character_id"] == character["id"]
    assert pending["source_message_id"] == response.dm_message.id
    assert "dice_result" not in response.dm_message.metadata
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest test/backend/src/agent/dm/test_dm_pending_checks.py::test_model_requested_player_check_creates_pending_check_without_dice_result`

Expected: FAIL because `dice_result` is still populated and `pending_check` is missing.

- [ ] **Step 3: Implement minimal backend pending check**

Add helper methods in `DMService`:

```python
    def _pending_check_from_payload(
        self,
        payload: dict[str, Any],
        character: CharacterOut,
        message_id: int | None = None,
    ) -> dict[str, Any] | None:
        if not payload.get("requires_check") or not payload.get("check"):
            return None
        check = dict(payload.get("check") or {})
        ability = str(check.get("ability") or "strength").lower()
        dc = int(check.get("dc") or 10)
        reason = str(check.get("reason") or "")
        source_id = int(message_id or 0)
        return {
            "id": f"check_{source_id}_{ability}_{dc}",
            "status": "pending",
            "ability": ability,
            "dc": dc,
            "reason": reason,
            "character_id": character.id,
            "character_name": character.name,
            "source_message_id": source_id,
        }
```

Change `_model_payload_to_response` to return `pending_check` instead of rolling. Update `advance` and `advance_stream` metadata after appending the DM message, then update the check id/source message id once the row id exists.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest test/backend/src/agent/dm/test_dm_pending_checks.py`

Expected: PASS.

## Task 2: Resolve Check API

**Files:**
- Modify: `backend/src/schemas/adventure.py`
- Modify: `backend/src/services/adventures.py`
- Modify: `backend/src/agent/dm/service.py`
- Modify: `backend/src/api/adventures.py`
- Test: `test/backend/src/api/test_dm_check_resolution.py`

- [ ] **Step 1: Write failing API tests**

Create `test/backend/src/api/test_dm_check_resolution.py`:

```python
from backend.src.services.adventures import AdventureService


def test_resolve_pending_check_calculates_result_and_updates_message(client):
    character = client.post(
        "/api/characters",
        json={"name": "Resolver", "race": "Human", "class_name": "Fighter", "dexterity": 14},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Resolve Check", "character_id": character["id"]},
    ).json()
    service = AdventureService(client.app.state.store)
    dm_message = service.append_message(
        adventure["id"],
        "dm",
        "Make a Dexterity check.",
        {
            "pending_check": {
                "id": "check_1_dexterity_12",
                "status": "pending",
                "ability": "dexterity",
                "dc": 12,
                "reason": "Climb the wall",
                "character_id": character["id"],
                "character_name": character["name"],
                "source_message_id": 0,
            }
        },
    )
    metadata = dict(dm_message.metadata)
    metadata["pending_check"]["source_message_id"] = dm_message.id
    service.update_message_metadata(dm_message.id, metadata)

    response = client.post(
        f"/api/adventures/{adventure['id']}/checks/check_1_dexterity_12/resolve",
        json={"message_id": dm_message.id, "roll": 10, "locale": "zh-CN"},
    )

    assert response.status_code == 200
    data = response.json()
    resolved = next(message for message in data["messages"] if message["id"] == dm_message.id)
    assert resolved["metadata"]["pending_check"]["status"] == "resolved"
    result = resolved["metadata"]["dice_result"]
    assert result["rolls"] == [10]
    assert result["modifier"] == 2
    assert result["total"] == 12
    assert result["success"] is True
    assert result["source"] == "player_dice_tray"


def test_resolve_pending_check_rejects_duplicate_submission(client):
    character = client.post(
        "/api/characters",
        json={"name": "Duplicate", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Duplicate Check", "character_id": character["id"]},
    ).json()
    service = AdventureService(client.app.state.store)
    dm_message = service.append_message(
        adventure["id"],
        "dm",
        "Make a Strength check.",
        {
            "pending_check": {
                "id": "check_dup_strength_10",
                "status": "resolved",
                "ability": "strength",
                "dc": 10,
                "reason": "Force the door",
                "character_id": character["id"],
                "character_name": character["name"],
                "source_message_id": 0,
            },
            "dice_result": {"rolls": [12], "kept": 12, "modifier": 0, "total": 12, "dc": 10, "success": True},
        },
    )

    response = client.post(
        f"/api/adventures/{adventure['id']}/checks/check_dup_strength_10/resolve",
        json={"message_id": dm_message.id, "roll": 15},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "check_already_resolved"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest test/backend/src/api/test_dm_check_resolution.py`

Expected: FAIL because the schema, service helper, and route do not exist.

- [ ] **Step 3: Implement schema and service helpers**

Add to `backend/src/schemas/adventure.py`:

```python
class AbilityCheckResolveRequest(BaseModel):
    message_id: int
    roll: int = Field(ge=1, le=20)
    locale: str = "en"
```

Add to `AdventureService`:

```python
    def get_message(self, message_id: int) -> MessageOut:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            raise api_error(404, "message_not_found", "Message not found.")
        return self._map_message_row(row)

    def update_message_metadata(self, message_id: int, metadata: dict[str, Any]) -> MessageOut:
        with self.store.connect() as conn:
            result = conn.execute(
                "UPDATE messages SET metadata_json = :metadata_json WHERE id = :message_id",
                {"message_id": message_id, "metadata_json": encode_json(metadata)},
            )
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if result.rowcount == 0 or row is None:
            raise api_error(404, "message_not_found", "Message not found.")
        return self._map_message_row(row)
```

- [ ] **Step 4: Implement resolve logic and API route**

Add `DMService.resolve_pending_check(adventure_id, check_id, request)` that validates message ownership, check id, status, roll range, and character state. It updates metadata, appends a short DM continuation message from deterministic text for now, and returns `DMAdvanceResponse` with refreshed adventure/messages.

Add route:

```python
@router.post("/{adventure_id}/checks/{check_id}/resolve", response_model=DMAdvanceResponse)
def resolve_check(adventure_id: int, check_id: str, payload: AbilityCheckResolveRequest, request: Request) -> DMAdvanceResponse:
    return dm_service(request).resolve_pending_check(adventure_id, check_id, payload)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest test/backend/src/api/test_dm_check_resolution.py test/backend/src/agent/dm/test_dm_pending_checks.py`

Expected: PASS.

## Task 3: Frontend Dice API And Pending Check UI

**Files:**
- Modify: `frontend/static/js/dice.js`
- Modify: `frontend/static/js/api.js`
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/locales/en.js`
- Modify: `frontend/static/js/locales/zh-CN.js`
- Modify: `frontend/static/styles.css`
- Test: `test/frontend/static/js/test_frontend_dice_checks.py`

- [ ] **Step 1: Write failing frontend tests**

Create `test/frontend/static/js/test_frontend_dice_checks.py` with static checks:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def read(path):
    return (ROOT / path).read_text()


def test_dice_module_exposes_promise_roll_api_for_checks():
    dice = read("frontend/static/js/dice.js")
    assert "export function rollDie" in dice
    assert "return new Promise" in dice
    assert "export function rollD20ForCheck" in dice


def test_game_renders_pending_check_and_resolves_through_dice_tray():
    game = read("frontend/static/js/game.js")
    assert "renderPendingCheck" in game
    assert "rollD20ForCheck" in game
    assert "resolvePendingCheck" in game
    assert "pending_check" in game


def test_check_labels_are_localized():
    zh = read("frontend/static/js/locales/zh-CN.js")
    en = read("frontend/static/js/locales/en.js")
    assert '"rollCheck": "掷 d20"' in zh
    assert '"rollCheck": "Roll d20"' in en
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest test/frontend/static/js/test_frontend_dice_checks.py`

Expected: FAIL because the exports and UI helpers are missing.

- [ ] **Step 3: Refactor dice.js minimally**

Change `rollDie` to an exported Promise-returning function while keeping click handlers:

```javascript
export function rollDie(sides, options = {}) {
  return new Promise((resolve) => {
    // existing animation body
    // resolve(entry) after history update and renderDiceTray()
  });
}

export function rollD20ForCheck(check) {
  return rollDie(20, { label: check?.ability ? t(`ability.${check.ability}`) : t("abilityCheck") });
}
```

Update `initDiceTray` click listener to ignore the returned Promise.

- [ ] **Step 4: Add frontend API and message UI**

Add to `api.js`:

```javascript
export async function resolvePendingCheck(adventureId, checkId, payload) {
  return api(`/api/adventures/${adventureId}/checks/${encodeURIComponent(checkId)}/resolve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
```

In `game.js`, import `rollD20ForCheck` and `resolvePendingCheck`, render a check block below DM messages, and on click:

```javascript
const roll = await rollD20ForCheck(check);
const response = await resolvePendingCheck(state.selectedAdventureId, check.id, {
  message_id: message.id,
  roll: roll.value,
  locale: state.locale,
});
state.selectedAdventure = response.adventure;
state.combat = response.combat_state;
renderAdventureDetail(response.messages, response.scene, response.combat_state);
```

- [ ] **Step 5: Add labels and styles**

Add labels:

```javascript
"rollCheck": "Roll d20",
"pendingCheckTitle": "Ability Check",
"resolvedCheckTitle": "Check Result"
```

Chinese:

```javascript
"rollCheck": "掷 d20",
"pendingCheckTitle": "能力检定",
"resolvedCheckTitle": "检定结果"
```

Add `.message-check`, `.message-check button`, and `.message-check-result` styles near message styles.

- [ ] **Step 6: Run frontend tests**

Run: `uv run pytest test/frontend/static/js/test_frontend_dice_checks.py test/frontend/static/js/test_frontend_streaming_ui.py test/frontend/static/js/test_frontend_game_room_layout.py`

Expected: PASS.

## Task 4: Integration Verification

**Files:**
- Existing backend and frontend files from prior tasks.

- [ ] **Step 1: Run targeted backend tests**

Run:

`uv run pytest test/backend/src/agent/dm/test_dm_pending_checks.py test/backend/src/api/test_dm_check_resolution.py test/backend/src/agent/dm/test_dm_agent.py test/backend/src/api/test_dm_streaming.py`

Expected: PASS. Update older tests that asserted automatic player ability checks to expect `pending_check` instead of `dice_result`.

- [ ] **Step 2: Run targeted frontend tests**

Run:

`uv run pytest test/frontend/static/js/test_frontend_dice_checks.py test/frontend/static/js/test_frontend_i18n_resources.py test/frontend/static/js/test_frontend_modularization.py test/frontend/static/js/test_frontend_routing.py`

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run: `uv run pytest`

Expected: PASS, with only the existing Starlette deprecation warning.

- [ ] **Step 4: Restart service and browser check**

Run:

`uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 5001`

Open `/game/25`, create or inspect a pending check, click `掷 d20`, and confirm the dice tray animates and the message refreshes to a resolved check.
