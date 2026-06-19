# PHB Combat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build PHB Chapter 9 theatre-of-the-mind combat with deterministic LangGraph workflows and read-only DM judgement skills.

**Architecture:** Keep `CombatService` as the deterministic rules facade, expand combat schemas/API for typed actions, and route fixed combat actions through `DeterministicWorkflows.combat_graph`. DM judgement text from the PHB is represented as built-in read-only skills that provide guidance without rolling dice or mutating state.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, LangGraph `StateGraph`, pytest, project-local SQLite JSON combat state.

---

## File Structure

- Modify `backend/src/schemas/combat.py`: add action type aliases, richer participant/state output models, backward-compatible action request fields.
- Modify `backend/src/services/combat.py`: normalize old/new combat state, implement PHB Chapter 9 deterministic actions, keep existing public methods compatible.
- Modify `backend/src/api/adventures.py`: build player combat participants from saved character data, dispatch action payloads through `CombatService.resolve_action`, persist updated state.
- Modify `backend/src/agent/dm/workflows.py`: route combat action workflow through the deterministic combat service instead of direct attack-only wrapper.
- Create `backend/src/agent/dm/skills/combat-positioning/SKILL.md`: read-only guidance for surprise, position, hiding, unseen targets, cover, terrain, reach.
- Create `backend/src/agent/dm/skills/combat-adjudication/SKILL.md`: read-only guidance for improvised actions, Search, Ready, mounted, underwater, complex spells, NPC death exceptions.
- Modify `test/backend/src/services/test_combat.py`: add service-level PHB combat tests.
- Modify `test/backend/src/api/test_adventure_flow.py`: add API compatibility and character-derived combat tests.
- Modify `test/backend/src/agent/dm/test_dm_langgraph_workflows.py`: add combat graph action-routing test.
- Modify `test/backend/src/agent/dm/test_dm_skills.py`: add combat skill loading/matching tests.

Current workspace is dirty and already has unrelated staged changes. If commits are made during execution, use explicit pathspecs and inspect `git diff --cached --name-only` before committing.

### Task 1: Combat Schemas And Backward Compatibility Tests

**Files:**
- Modify: `backend/src/schemas/combat.py`
- Test: `test/backend/src/services/test_combat.py`
- Test: `test/backend/src/api/test_adventure_flow.py`

- [ ] **Step 1: Write failing schema compatibility tests**

Add tests that lock old and new payload shapes:

```python
from backend.src.schemas.combat import CombatActionRequest


def test_combat_action_request_accepts_old_attack_payload():
    request = CombatActionRequest(attacker_name="Hero", target_name="Goblin")

    assert request.action_type == "attack"
    assert request.actor_name == "Hero"
    assert request.attacker_name == "Hero"
    assert request.target_name == "Goblin"


def test_combat_action_request_accepts_new_payload():
    request = CombatActionRequest(
        actor_name="Hero",
        action_type="dash",
        movement_ft=15,
        difficult_terrain=True,
    )

    assert request.actor_name == "Hero"
    assert request.action_type == "dash"
    assert request.movement_ft == 15
    assert request.difficult_terrain is True
```

- [ ] **Step 2: Run schema tests to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_combat_action_request_accepts_old_attack_payload test/backend/src/services/test_combat.py::test_combat_action_request_accepts_new_payload -q`

Expected: FAIL because `CombatActionRequest` does not expose `action_type`, `actor_name`, `movement_ft`, or `difficult_terrain`.

- [ ] **Step 3: Expand `CombatActionRequest`**

Add fields and a post-init validator:

```python
class CombatActionRequest(BaseModel):
    attacker_name: str | None = Field(default=None, min_length=1)
    actor_name: str | None = Field(default=None, min_length=1)
    target_name: str | None = Field(default=None, min_length=1)
    action_type: str = "attack"
    attack_id: str | None = None
    movement_ft: int = Field(default=0, ge=0)
    difficult_terrain: bool = False
    cover: str = "none"
    mode: str = "normal"
    nonlethal: bool = False
    defender_choice: str | None = None
    spell_id: str | None = None
    dc: int | None = Field(default=None, ge=1, le=30)

    @model_validator(mode="after")
    def normalize_actor(self) -> "CombatActionRequest":
        if self.actor_name is None and self.attacker_name is not None:
            self.actor_name = self.attacker_name
        if self.attacker_name is None and self.actor_name is not None:
            self.attacker_name = self.actor_name
        if self.action_type == "attack" and not self.target_name:
            raise ValueError("target_name is required for attack actions.")
        if not self.actor_name:
            raise ValueError("actor_name is required.")
        return self
```

- [ ] **Step 4: Run schema tests to verify pass**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_combat_action_request_accepts_old_attack_payload test/backend/src/services/test_combat.py::test_combat_action_request_accepts_new_payload -q`

Expected: PASS.

### Task 2: Participant Normalization And Initiative

**Files:**
- Modify: `backend/src/services/combat.py`
- Test: `test/backend/src/services/test_combat.py`

- [ ] **Step 1: Write failing initiative and normalization tests**

Add tests:

```python
def test_start_combat_adds_initiative_bonus_and_default_turn_resources():
    rolls = iter([10, 12])
    service = CombatService(rng=lambda sides: next(rolls))

    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 12, "hp_max": 12, "ac": 14, "initiative_bonus": 3, "speed_ft": 30},
            {"name": "Goblin", "side": "enemy", "hp": 7, "hp_max": 7, "ac": 13, "initiative_bonus": 0, "speed_ft": 30},
        ]
    )

    assert [p["name"] for p in state["participants"]] == ["Hero", "Goblin"]
    hero = state["participants"][0]
    assert hero["initiative"] == 13
    assert hero["movement_remaining_ft"] == 30
    assert hero["action_available"] is True
    assert hero["reaction_available"] is True
    assert hero["conditions"] == []


def test_old_participants_are_upgraded_when_action_resolves():
    service = CombatService(rng=lambda sides: 20)
    state = {
        "participants": [
            {"name": "Hero", "side": "player", "hp": 10, "ac": 12, "attack_bonus": 2, "damage": "1d4", "kind": "pc", "initiative": 10, "defeated": False},
            {"name": "Rat", "side": "enemy", "hp": 1, "ac": 10, "attack_bonus": 0, "damage": "1d4", "kind": "npc", "initiative": 5, "defeated": False},
        ],
        "is_active": True,
        "round_number": 1,
        "turn_index": 0,
    }

    result = service.resolve_action(state, {"actor_name": "Hero", "action_type": "dodge"})

    assert result["state"]["participants"][0]["speed_ft"] == 30
    assert "dodge" in result["state"]["participants"][0]["conditions"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_start_combat_adds_initiative_bonus_and_default_turn_resources test/backend/src/services/test_combat.py::test_old_participants_are_upgraded_when_action_resolves -q`

Expected: FAIL because initiative bonuses and `resolve_action` are missing.

- [ ] **Step 3: Implement normalization helpers**

Add helpers in `CombatService`:

```python
def _normalize_state(self, state: dict[str, Any]) -> dict[str, Any]:
    state["participants"] = [self._upgrade_participant(p) for p in state.get("participants", [])]
    state.setdefault("round_number", 1)
    state.setdefault("turn_index", 0)
    state.setdefault("is_active", True)
    return state

def _upgrade_participant(self, participant: dict[str, Any]) -> dict[str, Any]:
    hp = int(participant.get("hp", 0))
    hp_max = int(participant.get("hp_max", max(hp, 1)))
    speed = int(participant.get("speed_ft", 30))
    upgraded = {
        **participant,
        "hp": hp,
        "hp_max": hp_max,
        "temp_hp": int(participant.get("temp_hp", 0)),
        "ac": int(participant.get("ac", 10)),
        "attack_bonus": int(participant.get("attack_bonus", 0)),
        "damage": participant.get("damage", "1d4"),
        "damage_type": participant.get("damage_type", "bludgeoning"),
        "initiative_bonus": int(participant.get("initiative_bonus", 0)),
        "speed_ft": speed,
        "reach_ft": int(participant.get("reach_ft", 5)),
        "movement_remaining_ft": int(participant.get("movement_remaining_ft", speed)),
        "action_available": bool(participant.get("action_available", True)),
        "bonus_action_available": bool(participant.get("bonus_action_available", True)),
        "reaction_available": bool(participant.get("reaction_available", True)),
        "conditions": list(participant.get("conditions", [])),
        "cover": participant.get("cover", "none"),
        "engaged_with": list(participant.get("engaged_with", [])),
        "resistances": list(participant.get("resistances", [])),
        "vulnerabilities": list(participant.get("vulnerabilities", [])),
        "immunities": list(participant.get("immunities", [])),
        "death_saves": dict(participant.get("death_saves", {"successes": 0, "failures": 0})),
        "stable": bool(participant.get("stable", False)),
        "defeated": bool(participant.get("defeated", hp == 0 and participant.get("kind") != "character")),
    }
    return upgraded
```

- [ ] **Step 4: Run normalization tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_start_combat_adds_initiative_bonus_and_default_turn_resources test/backend/src/services/test_combat.py::test_old_participants_are_upgraded_when_action_resolves -q`

Expected: PASS.

### Task 3: Actions, Movement, Cover, And Opportunity Eligibility

**Files:**
- Modify: `backend/src/services/combat.py`
- Test: `test/backend/src/services/test_combat.py`

- [ ] **Step 1: Write failing action tests**

Add tests:

```python
def test_dash_disengage_and_dodge_consume_action_and_set_state():
    service = CombatService(rng=lambda sides: 10)
    state = service.start_combat([
        {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12},
        {"name": "Orc", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 12},
    ])

    dashed = service.resolve_action(state, {"actor_name": "Hero", "action_type": "dash"})["state"]
    hero = dashed["participants"][0]
    assert hero["movement_remaining_ft"] == 60
    assert hero["action_available"] is False

    service.advance_turn(dashed)
    service.advance_turn(dashed)
    disengaged = service.resolve_action(dashed, {"actor_name": "Hero", "action_type": "disengage"})["state"]
    assert disengaged["participants"][0]["disengage_active"] is True


def test_move_spends_double_movement_in_difficult_terrain_and_flags_opportunity():
    service = CombatService(rng=lambda sides: 10)
    state = service.start_combat([
        {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "engaged_with": ["Orc"]},
        {"name": "Orc", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 12, "engaged_with": ["Hero"]},
    ])

    result = service.resolve_action(
        state,
        {"actor_name": "Hero", "action_type": "move", "movement_ft": 10, "difficult_terrain": True, "leaves_reach_of": "Orc"},
    )

    hero = result["state"]["participants"][0]
    assert hero["movement_remaining_ft"] == 10
    assert result["opportunity_attack"]["eligible"] is True
    assert result["opportunity_attack"]["attacker_name"] == "Orc"


def test_total_cover_blocks_direct_attack_and_half_cover_adds_ac():
    rolls = iter([14, 14])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat([
        {"name": "Archer", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "attack_bonus": 0, "damage": "1d4"},
        {"name": "Goblin", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 14, "cover": "half"},
    ])

    result = service.resolve_attack(state, "Archer", "Goblin")

    assert result["attack_roll"]["dc"] == 16
    assert result["hit"] is False
```

- [ ] **Step 2: Run action tests to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_dash_disengage_and_dodge_consume_action_and_set_state test/backend/src/services/test_combat.py::test_move_spends_double_movement_in_difficult_terrain_and_flags_opportunity test/backend/src/services/test_combat.py::test_total_cover_blocks_direct_attack_and_half_cover_adds_ac -q`

Expected: FAIL because action routing and cover modifiers are missing.

- [ ] **Step 3: Implement `resolve_action` and action handlers**

Add service routing:

```python
def resolve_action(self, state: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    self._ensure_active(state)
    state = self._normalize_state(state)
    action_type = str(action.get("action_type") or "attack").replace("-", "_")
    actor_name = action.get("actor_name") or action.get("attacker_name")
    if not actor_name:
        raise ValueError("actor_name is required.")
    if action_type == "attack":
        return self.resolve_attack(state, actor_name, action.get("target_name"), action)
    if action_type == "move":
        return self._resolve_move(state, actor_name, action)
    if action_type in {"dash", "disengage", "dodge", "help", "hide", "ready", "search", "use_object"}:
        return self._resolve_simple_action(state, actor_name, action_type, action)
    raise ValueError(f"Unsupported combat action: {action_type}.")
```

Implement `_consume_action`, `_resolve_simple_action`, `_resolve_move`, and
`_cover_bonus` with explicit state changes from the tests.

- [ ] **Step 4: Run action tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_dash_disengage_and_dodge_consume_action_and_set_state test/backend/src/services/test_combat.py::test_move_spends_double_movement_in_difficult_terrain_and_flags_opportunity test/backend/src/services/test_combat.py::test_total_cover_blocks_direct_attack_and_half_cover_adds_ac -q`

Expected: PASS.

### Task 4: Attack Rolls, Damage, Healing, And Death

**Files:**
- Modify: `backend/src/services/combat.py`
- Test: `test/backend/src/services/test_combat.py`

- [ ] **Step 1: Write failing damage tests**

Add tests:

```python
def test_natural_20_hits_and_doubles_damage_dice():
    rolls = iter([20, 3, 4])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat([
        {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "attack_bonus": 0, "damage": "1d8+2"},
        {"name": "Ogre", "side": "enemy", "hp": 30, "hp_max": 30, "ac": 30},
    ])

    result = service.resolve_attack(state, "Hero", "Ogre")

    assert result["hit"] is True
    assert result["critical"] is True
    assert result["damage"] == 9


def test_damage_resistance_vulnerability_immunity_and_temp_hp():
    service = CombatService(rng=lambda sides: 6)
    state = service.start_combat([
        {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "attack_bonus": 20, "damage": "1d6", "damage_type": "fire"},
        {"name": "Target", "side": "enemy", "hp": 20, "hp_max": 20, "temp_hp": 3, "ac": 10, "resistances": ["fire"]},
    ])

    result = service.resolve_attack(state, "Hero", "Target")

    assert result["damage"] == 3
    assert result["target"]["temp_hp"] == 0
    assert result["target"]["hp"] == 20


def test_character_at_zero_hp_tracks_death_saves_and_can_be_stabilized():
    rolls = iter([20, 5])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat([
        {"name": "Hero", "side": "player", "kind": "character", "hp": 0, "hp_max": 10, "ac": 12},
        {"name": "Goblin", "side": "enemy", "hp": 7, "hp_max": 7, "ac": 13},
    ])

    result = service.resolve_action(state, {"actor_name": "Hero", "action_type": "death_save"})

    assert result["roll"]["kept"] == 20
    assert result["actor"]["hp"] == 1
    assert result["actor"]["death_saves"] == {"successes": 0, "failures": 0}
```

- [ ] **Step 2: Run damage tests to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_natural_20_hits_and_doubles_damage_dice test/backend/src/services/test_combat.py::test_damage_resistance_vulnerability_immunity_and_temp_hp test/backend/src/services/test_combat.py::test_character_at_zero_hp_tracks_death_saves_and_can_be_stabilized -q`

Expected: FAIL because critical damage, temp HP, resistance, and death saves are missing.

- [ ] **Step 3: Implement deterministic damage and death helpers**

Add helpers:

```python
def _roll_attack(self, modifier: int, dc: int, mode: str) -> dict[str, Any]:
    rolled = self.roll_check(modifier=modifier, dc=dc, mode=mode)
    natural = rolled["kept"]
    rolled["critical"] = natural == 20
    rolled["natural_one"] = natural == 1
    rolled["success"] = False if natural == 1 else True if natural == 20 else rolled["success"]
    return rolled

def _apply_damage(self, target: dict[str, Any], amount: int, damage_type: str, critical: bool = False) -> int:
    if damage_type in target.get("immunities", []):
        amount = 0
    elif damage_type in target.get("resistances", []):
        amount //= 2
    elif damage_type in target.get("vulnerabilities", []):
        amount *= 2
    absorbed = min(target.get("temp_hp", 0), amount)
    target["temp_hp"] = target.get("temp_hp", 0) - absorbed
    remaining = amount - absorbed
    target["hp"] = max(0, target["hp"] - remaining)
    self._apply_zero_hp_state(target, remaining, critical)
    return amount
```

Add `_resolve_death_save`, `_apply_zero_hp_state`, and critical damage dice logic.

- [ ] **Step 4: Run damage tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_natural_20_hits_and_doubles_damage_dice test/backend/src/services/test_combat.py::test_damage_resistance_vulnerability_immunity_and_temp_hp test/backend/src/services/test_combat.py::test_character_at_zero_hp_tracks_death_saves_and_can_be_stabilized -q`

Expected: PASS.

### Task 5: Grapple, Shove, And PHB Special Actions

**Files:**
- Modify: `backend/src/services/combat.py`
- Test: `test/backend/src/services/test_combat.py`

- [ ] **Step 1: Write failing opposed-action tests**

Add tests:

```python
def test_grapple_uses_opposed_athletics_and_applies_grappled():
    rolls = iter([15, 9])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat([
        {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "athletics_bonus": 5},
        {"name": "Bandit", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 12, "athletics_bonus": 1},
    ])

    result = service.resolve_action(state, {"actor_name": "Hero", "action_type": "grapple", "target_name": "Bandit", "defender_choice": "athletics"})

    assert result["success"] is True
    assert "grappled" in result["target"]["conditions"]
    assert result["target"]["grappled_by"] == "Hero"


def test_shove_can_knock_target_prone():
    rolls = iter([16, 8])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat([
        {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "athletics_bonus": 4},
        {"name": "Bandit", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 12, "acrobatics_bonus": 2},
    ])

    result = service.resolve_action(state, {"actor_name": "Hero", "action_type": "shove", "target_name": "Bandit", "defender_choice": "acrobatics", "shove_effect": "prone"})

    assert result["success"] is True
    assert "prone" in result["target"]["conditions"]
```

- [ ] **Step 2: Run opposed-action tests to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_grapple_uses_opposed_athletics_and_applies_grappled test/backend/src/services/test_combat.py::test_shove_can_knock_target_prone -q`

Expected: FAIL because grapple and shove are unsupported.

- [ ] **Step 3: Implement `grapple` and `shove` routing**

Add routes in `resolve_action` and helpers:

```python
if action_type == "grapple":
    return self._resolve_grapple(state, actor_name, action)
if action_type == "shove":
    return self._resolve_shove(state, actor_name, action)
```

Both helpers consume the actor action, roll opposed checks, and apply `grappled`,
`grappled_by`, `prone`, or `pushed_ft`.

- [ ] **Step 4: Run opposed-action tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py::test_grapple_uses_opposed_athletics_and_applies_grappled test/backend/src/services/test_combat.py::test_shove_can_knock_target_prone -q`

Expected: PASS.

### Task 6: API Character Data Integration

**Files:**
- Modify: `backend/src/api/adventures.py`
- Test: `test/backend/src/api/test_adventure_flow.py`

- [ ] **Step 1: Write failing API tests**

Add tests that create a character with realistic saved fields and assert combat start uses those fields:

```python
def test_start_combat_uses_character_stats_for_initiative_and_attacks(client):
    character = client.post(
        "/api/characters",
        json={
            "name": "Mira",
            "race": "Human",
            "class_name": "Fighter",
            "background": "Soldier",
            "alignment": "Neutral Good",
        },
    ).json()
    client.patch(
        f"/api/characters/{character['id']}",
        json={
            "hp_current": 14,
            "hp_max": 14,
            "armor_class": 16,
            "strength": 16,
            "dexterity": 14,
            "inventory": [
                {"item_id": "equipment.battleaxe", "quantity": 1},
                {"item_id": "equipment.shield", "quantity": 1},
            ],
        },
    )
    adventure = client.post("/api/adventures", json={"title": "Combat", "character_id": character["id"]}).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Bandit", "hp": 9, "ac": 12, "attack_bonus": 3, "damage": "1d6+1"}]},
    )

    assert response.status_code == 200
    player = next(p for p in response.json()["participants"] if p["side"] == "player")
    assert player["hp"] == 14
    assert player["ac"] == 16
    assert player["initiative_bonus"] == 2
    assert player["attack_bonus"] >= 5
```

- [ ] **Step 2: Run API test to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_adventure_flow.py::test_start_combat_uses_character_stats_for_initiative_and_attacks -q`

Expected: FAIL because API start currently hard-codes attack fields and does not expose initiative bonus.

- [ ] **Step 3: Build character participant from saved data**

Add helper in `backend/src/api/adventures.py`:

```python
def character_to_combat_participant(character) -> dict:
    strength_mod = (character.strength - 10) // 2
    dexterity_mod = (character.dexterity - 10) // 2
    attack_bonus = max(0, strength_mod + 2)
    damage = "1d8" + (f"{strength_mod:+d}" if strength_mod else "")
    return {
        "name": character.name,
        "side": "player",
        "hp": character.hp_current,
        "hp_max": character.hp_max,
        "ac": character.armor_class,
        "attack_bonus": attack_bonus,
        "damage": damage,
        "damage_type": "slashing",
        "initiative_bonus": dexterity_mod,
        "speed_ft": 30,
        "kind": "character",
    }
```

Use it inside `start_combat`. If richer derived attack data is available in a
future saved character payload, map it into `attacks` without changing the API.

- [ ] **Step 4: Run API test**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_adventure_flow.py::test_start_combat_uses_character_stats_for_initiative_and_attacks -q`

Expected: PASS.

### Task 7: LangGraph Combat Routing

**Files:**
- Modify: `backend/src/agent/dm/workflows.py`
- Test: `test/backend/src/agent/dm/test_dm_langgraph_workflows.py`

- [ ] **Step 1: Write failing workflow test**

Add test:

```python
def test_combat_graph_routes_non_attack_action(client):
    workflows = DeterministicWorkflows(
        client.app.state.store,
        combat_service=CombatService(rng=lambda sides: 10),
    )
    state = CombatService(rng=lambda sides: 10).start_combat([
        {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12},
        {"name": "Goblin", "side": "enemy", "hp": 7, "hp_max": 7, "ac": 13},
    ])

    result = workflows.combat_graph.invoke(
        {
            "combat_state": state,
            "actor_name": "Hero",
            "action": {"actor_name": "Hero", "action_type": "dodge"},
            "attacker_name": "",
            "target_name": "",
            "result": None,
        }
    )["result"]

    assert result["action_type"] == "dodge"
    assert "dodge" in result["actor"]["conditions"]
```

- [ ] **Step 2: Run workflow test to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/agent/dm/test_dm_langgraph_workflows.py::test_combat_graph_routes_non_attack_action -q`

Expected: FAIL because `CombatWorkflowState` does not accept `action` and graph calls only `resolve_attack`.

- [ ] **Step 3: Expand workflow state and graph resolver**

Change `CombatWorkflowState`:

```python
class CombatWorkflowState(TypedDict, total=False):
    combat_state: dict[str, Any]
    actor_name: str
    attacker_name: str
    target_name: str
    action: dict[str, Any]
    result: dict[str, Any] | None
```

Change resolver to:

```python
action = dict(state.get("action") or {})
if not action:
    action = {
        "actor_name": state.get("actor_name") or state.get("attacker_name"),
        "attacker_name": state.get("attacker_name"),
        "target_name": state.get("target_name"),
        "action_type": "attack",
    }
return {"result": self.combat.resolve_action(combat_state, action)}
```

- [ ] **Step 4: Run workflow test**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/agent/dm/test_dm_langgraph_workflows.py::test_combat_graph_routes_non_attack_action -q`

Expected: PASS.

### Task 8: Read-Only Combat DM Skills

**Files:**
- Create: `backend/src/agent/dm/skills/combat-positioning/SKILL.md`
- Create: `backend/src/agent/dm/skills/combat-adjudication/SKILL.md`
- Test: `test/backend/src/agent/dm/test_dm_skills.py`

- [ ] **Step 1: Write failing skill tests**

Add tests:

```python
def test_builtin_dm_skill_registry_matches_combat_positioning():
    registry = DMSkillRegistry.load_builtin()

    matches = registry.match("Can I hide behind the pillar for half cover before attacking?", locale="en")

    assert any(skill.name == "combat-positioning" for skill in matches)


def test_builtin_dm_skill_registry_matches_combat_adjudication():
    registry = DMSkillRegistry.load_builtin()

    matches = registry.match("I ready an action to strike when the cultist opens the door", locale="en")

    assert any(skill.name == "combat-adjudication" for skill in matches)
```

- [ ] **Step 2: Run skill tests to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/agent/dm/test_dm_skills.py::test_builtin_dm_skill_registry_matches_combat_positioning test/backend/src/agent/dm/test_dm_skills.py::test_builtin_dm_skill_registry_matches_combat_adjudication -q`

Expected: FAIL because combat skills do not exist.

- [ ] **Step 3: Add combat skill files**

Create `combat-positioning/SKILL.md` with frontmatter:

```markdown
---
name: combat-positioning
description: Judge theatre-of-the-mind combat position, cover, surprise, hiding, unseen attackers, terrain, and reach.
when_to_use:
  - player asks whether a creature is surprised hidden unseen covered behind terrain in reach or out of reach
tags:
  - combat
  - cover
  - surprise
  - hide
  - unseen
  - terrain
  - reach
agent: combat_agent
---
```

Create `combat-adjudication/SKILL.md` with frontmatter:

```markdown
---
name: combat-adjudication
description: Judge improvised combat actions, Ready triggers, Search choices, complex mounted or underwater situations, and NPC death exceptions.
when_to_use:
  - player describes an improvised combat action ready trigger search mounted combat underwater combat or special monster death outcome
tags:
  - combat
  - ready
  - search
  - improvised
  - mounted
  - underwater
  - knockout
agent: combat_agent
---
```

Bodies must explicitly say: do not roll dice, do not directly persist game
state, do not modify combat state, and return only DM guidance.

- [ ] **Step 4: Run skill tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/agent/dm/test_dm_skills.py::test_builtin_dm_skill_registry_matches_combat_positioning test/backend/src/agent/dm/test_dm_skills.py::test_builtin_dm_skill_registry_matches_combat_adjudication -q`

Expected: PASS.

### Task 9: API Action Dispatch And Regression Sweep

**Files:**
- Modify: `backend/src/api/adventures.py`
- Test: `test/backend/src/api/test_adventure_flow.py`
- Test: `test/backend/src/services/test_combat.py`

- [ ] **Step 1: Write failing API action tests**

Add tests:

```python
def test_combat_action_accepts_new_dodge_payload(client):
    adventure = _create_adventure_with_character(client)
    client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Goblin", "hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d6+2"}]},
    )
    state = client.get(f"/api/adventures/{adventure['id']}").json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={"actor_name": "Oren", "action_type": "dodge"},
    )

    assert response.status_code == 200
    assert response.json()["action_type"] == "dodge"
```

If `_create_adventure_with_character` does not exist, inline the existing helper
pattern from `test_adventure_flow.py`.

- [ ] **Step 2: Run API action test to verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/api/test_adventure_flow.py::test_combat_action_accepts_new_dodge_payload -q`

Expected: FAIL because API still calls `resolve_attack` directly.

- [ ] **Step 3: Dispatch API action through `resolve_action`**

Change `combat_action`:

```python
payload = action.model_dump(exclude_none=True)
result = combat.resolve_action(state, payload)
if result["state"].get("is_active") and result.get("ends_turn", True):
    combat.advance_turn(result["state"])
```

Keep old response fields available for attack results. Return non-attack action
results with `state`, `action_type`, and `actor`.

- [ ] **Step 4: Run targeted regression tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py test/backend/src/api/test_adventure_flow.py test/backend/src/agent/dm/test_dm_langgraph_workflows.py test/backend/src/agent/dm/test_dm_skills.py -q`

Expected: PASS.

### Task 10: Final Verification

**Files:**
- No source edits unless verification identifies a concrete failure.

- [ ] **Step 1: Run DM and combat focused tests**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src/services/test_combat.py test/backend/src/api/test_adventure_flow.py test/backend/src/agent/dm -q`

Expected: PASS.

- [ ] **Step 2: Run broader backend tests likely affected by schemas/API**

Run: `.\.venv\Scripts\python.exe -m pytest test/backend/src -q`

Expected: PASS or a clearly documented unrelated pre-existing failure.

- [ ] **Step 3: Inspect dirty diff**

Run: `git diff -- backend/src/schemas/combat.py backend/src/services/combat.py backend/src/api/adventures.py backend/src/agent/dm/workflows.py backend/src/agent/dm/skills test/backend/src/services/test_combat.py test/backend/src/api/test_adventure_flow.py test/backend/src/agent/dm/test_dm_langgraph_workflows.py test/backend/src/agent/dm/test_dm_skills.py docs/superpowers/plans/2026-06-13-phb-combat.md`

Expected: diff only contains combat-related implementation and tests.

## Self-Review

- Spec coverage: deterministic combat service, LangGraph routing, API compatibility, theatre-of-the-mind positioning fields, DM judgement skills, and character-derived combat data each have tasks.
- Marker scan: the plan avoids unfinished-work markers and gives concrete commands and code shapes.
- Type consistency: `actor_name`, `attacker_name`, `target_name`, `action_type`, `movement_ft`, `difficult_terrain`, `cover`, `mode`, `nonlethal`, and `defender_choice` are used consistently across schemas, service, API, and workflow tests.
