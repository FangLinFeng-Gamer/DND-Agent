import pytest
from fastapi import HTTPException

from backend.src.services.adventures import AdventureService


def test_playable_adventure_flow(client):
    character = client.post(
        "/api/characters",
        json={"name": "Nyx", "race": "Human", "class_name": "Fighter"},
    ).json()
    created = client.post("/api/adventures", json={"title": "Ruins of Dawn", "character_id": character["id"]})
    assert created.status_code == 200
    adventure = created.json()
    assert adventure["current_scene"]["location"]

    message = client.post(
        f"/api/adventures/{adventure['id']}/messages",
        json={"content": "I inspect the old door."},
    )
    assert message.status_code == 200
    data = message.json()
    assert data["dm_message"]["content"]
    assert data["scene"]["current_objective"]
    assert len(data["messages"]) >= 2


def test_start_combat_from_api(client):
    character = client.post(
        "/api/characters",
        json={"name": "Kara", "race": "Elf", "class_name": "Ranger"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Wolf Road", "character_id": character["id"]}).json()
    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Bandit", "hp": 9, "ac": 12, "attack_bonus": 3, "damage": "1d6+1"}]},
    )
    assert response.status_code == 200
    state = response.json()
    assert state["is_active"] is True
    assert len(state["participants"]) == 2


def test_create_adventure_accepts_party_character_ids(client):
    first = client.post(
        "/api/characters",
        json={"name": "Tav", "race": "Human", "class_name": "Druid"},
    ).json()
    second = client.post(
        "/api/characters",
        json={"name": "Dale", "race": "Human", "class_name": "Paladin"},
    ).json()

    response = client.post(
        "/api/adventures",
        json={
            "title": "Party Road",
            "party_character_ids": [first["id"], second["id"]],
        },
    )

    assert response.status_code == 200
    adventure = response.json()
    assert adventure["character_id"] == first["id"]
    assert adventure["party_character_ids"] == [first["id"], second["id"]]
    assert [character["name"] for character in adventure["party_characters"]] == ["Tav", "Dale"]


def test_create_adventure_rejects_invalid_party(client):
    character = client.post(
        "/api/characters",
        json={"name": "Loop", "race": "Human", "class_name": "Fighter"},
    ).json()

    duplicate = client.post(
        "/api/adventures",
        json={"title": "Duplicate Party", "party_character_ids": [character["id"], character["id"]]},
    )

    assert duplicate.status_code == 400
    assert duplicate.json()["detail"]["error"]["code"] == "party_duplicate_character"


def test_start_combat_includes_all_party_characters(client):
    first = client.post(
        "/api/characters",
        json={"name": "Rin", "race": "Human", "class_name": "Fighter"},
    ).json()
    second = client.post(
        "/api/characters",
        json={"name": "Lio", "race": "Elf", "class_name": "Wizard"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Party Combat", "party_character_ids": [first["id"], second["id"]]},
    ).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Bandit", "hp": 9, "ac": 12, "attack_bonus": 3, "damage": "1d6+1"}]},
    )

    assert response.status_code == 200
    names = {participant["name"] for participant in response.json()["participants"] if participant["side"] == "player"}
    assert names == {"Rin", "Lio"}


def test_get_combat_state_returns_existing_active_combat(client):
    character = client.post(
        "/api/characters",
        json={"name": "Lena", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Recover Combat", "character_id": character["id"]}).json()
    started = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Bandit", "hp": 9, "ac": 12, "attack_bonus": 3, "damage": "1d6+1"}]},
    ).json()

    response = client.get(f"/api/adventures/{adventure['id']}/combat")

    assert response.status_code == 200
    state = response.json()
    assert state["is_active"] is True
    assert state["round_number"] == started["round_number"]
    assert [participant["name"] for participant in state["participants"]] == [
        participant["name"] for participant in started["participants"]
    ]


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
    player = next(participant for participant in response.json()["participants"] if participant["side"] == "player")
    assert player["hp"] == 14
    assert player["hp_max"] == 14
    assert player["ac"] == 16
    assert player["initiative_bonus"] == 2
    assert player["attack_bonus"] >= 5
    assert player["damage"] == "1d8+3"


def test_player_at_zero_hp_cannot_attack_through_combat_api(client):
    character = client.post(
        "/api/characters",
        json={"name": "Vale", "race": "Human", "class_name": "Fighter"},
    ).json()
    client.patch(
        f"/api/characters/{character['id']}",
        json={"hp_current": 0, "hp_max": 10},
    )
    adventure = client.post("/api/adventures", json={"title": "Death Save Guard", "character_id": character["id"]}).json()
    state = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={
            "enemies": [
                {
                    "name": "Slow Bandit",
                    "hp": 9,
                    "ac": 12,
                    "attack_bonus": 3,
                    "damage": "1d6+1",
                    "initiative_bonus": -30,
                }
            ]
        },
    ).json()
    player = next(participant for participant in state["participants"] if participant["side"] == "player")
    target = next(participant for participant in state["participants"] if participant["side"] == "enemy")

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={"actor_name": player["name"], "action_type": "attack", "target_name": target["name"]},
    )

    assert state["participants"][state["turn_index"]]["name"] == player["name"]
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "validation_error"
    assert "cannot act at 0 hit points" in response.json()["detail"]["error"]["message"]


def test_missing_adventure_returns_structured_error(client):
    response = client.get("/api/adventures/999")

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "adventure_not_found"


def test_missing_adventure_messages_return_structured_error(client):
    service = AdventureService(client.app.state.store)

    with pytest.raises(HTTPException) as exc_info:
        service.list_messages(999)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "adventure_not_found"


def test_combat_action_persists_updated_state(client):
    character = client.post(
        "/api/characters",
        json={"name": "Bran", "race": "Dwarf", "class_name": "Cleric"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Shrine Vault", "character_id": character["id"]}).json()
    started = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={
            "enemies": [
                {
                    "name": "Cultist",
                    "hp": 1,
                    "ac": 1,
                    "attack_bonus": 100,
                    "damage": "1d4",
                    "initiative_bonus": -30,
                }
            ]
        },
    ).json()
    actor = started["participants"][started["turn_index"]]

    action = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={"actor_name": actor["name"], "action_type": "dodge"},
    )
    assert action.status_code == 200
    action_state = action.json()["state"]
    action_actor = action.json()["actor"]
    assert "dodge" in action_actor["conditions"]

    if action_state["is_active"]:
        ended = client.post(f"/api/adventures/{adventure['id']}/combat/end")
        assert ended.status_code == 200
        state = ended.json()
        persisted_actor = next(participant for participant in state["participants"] if participant["name"] == actor["name"])
        assert "dodge" in persisted_actor["conditions"]
    else:
        ended = client.post(f"/api/adventures/{adventure['id']}/combat/end")
        assert ended.status_code == 400
        assert ended.json()["detail"]["error"]["code"] == "combat_not_active"


def test_combat_action_accepts_new_dodge_payload(client):
    character = client.post(
        "/api/characters",
        json={"name": "Oren", "race": "Dwarf", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Dodge Test", "character_id": character["id"]}).json()
    started = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={
            "enemies": [
                {
                    "name": "Goblin",
                    "hp": 7,
                    "ac": 13,
                    "attack_bonus": 4,
                    "damage": "1d6+2",
                    "initiative_bonus": -30,
                }
            ]
        },
    ).json()
    current_actor = started["participants"][started["turn_index"]]

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={"actor_name": current_actor["name"], "action_type": "dodge"},
    )

    assert response.status_code == 200
    assert response.json()["action_type"] == "dodge"
    assert "dodge" in response.json()["actor"]["conditions"]


def test_combat_end_returns_inactive_state(client):
    character = client.post(
        "/api/characters",
        json={"name": "Mira", "race": "Halfling", "class_name": "Rogue"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Lantern Alley", "character_id": character["id"]}).json()
    client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Thug", "hp": 7, "ac": 11, "attack_bonus": 2, "damage": "1d6"}]},
    )

    response = client.post(f"/api/adventures/{adventure['id']}/combat/end")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_starting_active_combat_returns_structured_error(client):
    character = client.post(
        "/api/characters",
        json={"name": "Tamsin", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Bridge Fight", "character_id": character["id"]}).json()
    payload = {
        "enemies": [
            {
                "name": "Raider",
                "hp": 6,
                "ac": 10,
                "attack_bonus": 2,
                "damage": "1d6",
                "initiative_bonus": -30,
            }
        ]
    }
    first = client.post(f"/api/adventures/{adventure['id']}/combat/start", json=payload)
    first_state = first.json()
    current_actor = first_state["participants"][first_state["turn_index"]]
    original_target = next(
        participant
        for participant in first_state["participants"]
        if participant["name"] != current_actor["name"]
    )
    second = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Imposter", "hp": 6, "ac": 10, "attack_bonus": 2, "damage": "1d6"}]},
    )
    still_original = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={"attacker_name": current_actor["name"], "target_name": original_target["name"]},
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"]["error"]["code"] == "combat_already_active"
    assert still_original.status_code == 200
    assert still_original.json()["target"]["name"] == original_target["name"]


def test_combat_action_rejects_non_current_actor(client):
    character = client.post(
        "/api/characters",
        json={"name": "Iris", "race": "Elf", "class_name": "Ranger"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Ravine Ambush", "character_id": character["id"]}).json()
    state = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Scout", "hp": 8, "ac": 11, "attack_bonus": 2, "damage": "1d6"}]},
    ).json()
    current = state["participants"][state["turn_index"]]
    other = next(participant for participant in state["participants"] if participant["name"] != current["name"])
    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={"attacker_name": other["name"], "target_name": current["name"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "invalid_turn"


def test_player_combat_action_rejects_current_npc_turn(client):
    character = client.post(
        "/api/characters",
        json={"name": "Selene", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "NPC Turn Guard", "character_id": character["id"]}).json()
    state = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={
            "enemies": [
                {
                    "name": "Quick Raider",
                    "hp": 8,
                    "ac": 11,
                    "attack_bonus": 2,
                    "damage": "1d4",
                    "initiative_bonus": 30,
                }
            ]
        },
    ).json()
    current = state["participants"][state["turn_index"]]
    target = next(participant for participant in state["participants"] if participant["side"] == "player")

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={"actor_name": current["name"], "target_name": target["name"], "action_type": "attack"},
    )

    assert current["side"] == "enemy"
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "npc_turn_requires_agent"


def test_npc_turn_endpoint_resolves_current_npc_with_fallback(client):
    character = client.post(
        "/api/characters",
        json={"name": "Tarin", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "NPC Fallback", "character_id": character["id"]}).json()
    state = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={
            "enemies": [
                {
                    "name": "Quick Raider",
                    "hp": 8,
                    "ac": 11,
                    "attack_bonus": 20,
                    "damage": "1d4",
                    "initiative_bonus": 30,
                }
            ]
        },
    ).json()
    npc = state["participants"][state["turn_index"]]
    player = next(participant for participant in state["participants"] if participant["side"] == "player")

    response = client.post(f"/api/adventures/{adventure['id']}/combat/npc-turn", json={"locale": "en"})

    assert npc["side"] == "enemy"
    assert response.status_code == 200
    payload = response.json()
    assert payload["action_type"] == "attack"
    assert payload["actor"]["name"] == npc["name"]
    assert payload["target"]["name"] == player["name"]
    assert payload["decision_source"] == "fallback"
    assert payload["state"]["participants"][payload["state"]["turn_index"]]["side"] == "player"


def test_npc_turn_endpoint_rejects_player_turn(client):
    character = client.post(
        "/api/characters",
        json={"name": "Rowan", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Player Turn Guard", "character_id": character["id"]}).json()
    state = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={
            "enemies": [
                {
                    "name": "Slow Raider",
                    "hp": 8,
                    "ac": 11,
                    "attack_bonus": 2,
                    "damage": "1d4",
                    "initiative_bonus": -30,
                }
            ]
        },
    ).json()

    assert state["participants"][state["turn_index"]]["side"] == "player"
    response = client.post(f"/api/adventures/{adventure['id']}/combat/npc-turn", json={"locale": "en"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "not_npc_turn"


def test_combat_action_and_end_require_active_combat(client):
    character = client.post(
        "/api/characters",
        json={"name": "Oren", "race": "Dwarf", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Quiet Hall", "character_id": character["id"]}).json()

    action = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={"attacker_name": "Oren", "target_name": "Shadow"},
    )
    end = client.post(f"/api/adventures/{adventure['id']}/combat/end")

    assert action.status_code == 400
    assert action.json()["detail"]["error"]["code"] == "combat_not_active"
    assert end.status_code == 400
    assert end.json()["detail"]["error"]["code"] == "combat_not_active"


def test_ending_inactive_combat_returns_structured_error(client):
    character = client.post(
        "/api/characters",
        json={"name": "Perrin", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Gatehouse", "character_id": character["id"]}).json()
    client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Guard", "hp": 8, "ac": 11, "attack_bonus": 2, "damage": "1d6"}]},
    )
    first = client.post(f"/api/adventures/{adventure['id']}/combat/end")
    second = client.post(f"/api/adventures/{adventure['id']}/combat/end")

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"]["error"]["code"] == "combat_not_active"


def test_system_capabilities_and_image_stub(client):
    capabilities = client.get("/api/system/capabilities")
    assert capabilities.status_code == 200
    assert "characters" in capabilities.json()["features"]

    image = client.post("/api/assets/images", json={"kind": "character", "subject_id": "1", "description": "elf ranger"})
    assert image.status_code == 200
    data = image.json()
    assert data["status"] == "not_connected"
    assert "elf ranger" in data["prompt"]
