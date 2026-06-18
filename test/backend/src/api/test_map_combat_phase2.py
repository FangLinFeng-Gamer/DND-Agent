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
    adventure, scene, _state = create_mapped_adventure(client)

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


def test_player_melee_attack_rejects_target_beyond_reach_on_map(client):
    character = client.post(
        "/api/characters",
        json={"name": "Reach Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    client.patch(
        f"/api/characters/{character['id']}",
        json={"inventory": [{"item_id": "equipment.battleaxe", "quantity": 1}]},
    )
    adventure = client.post(
        "/api/adventures",
        json={"title": "Reach Matters", "character_id": character["id"]},
    ).json()
    asset = client.post(
        "/api/map-assets?asset_type=map&name=ReachGrid&filename=reach-grid.png",
        content=b"grid",
        headers={"content-type": "image/png"},
    ).json()
    scene = client.post(
        "/api/map-scenes",
        json={
            "name": "Reach Grid",
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
                    "name": "Reach Goblin",
                    "hp": 7,
                    "ac": 13,
                    "attack_bonus": 4,
                    "damage": "1d6+2",
                    "initiative_bonus": -30,
                }
            ]
        },
    ).json()
    tokens = client.get(f"/api/map-scenes/{scene['id']}/combat-tokens").json()
    hero = next(token for token in tokens if token["participant_name"] == "Reach Hero")
    goblin = next(token for token in tokens if token["participant_name"] == "Reach Goblin")
    client.patch(f"/api/map-scenes/{scene['id']}/combat-tokens/{hero['id']}", json={"x": 70, "y": 70})
    client.patch(f"/api/map-scenes/{scene['id']}/combat-tokens/{goblin['id']}", json={"x": 210, "y": 70})

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={
            "actor_name": state["participants"][state["turn_index"]]["name"],
            "target_name": "Reach Goblin",
            "action_type": "attack",
            "attack_id": "equipment.battleaxe",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "attack_out_of_range"
    assert "10" in response.json()["detail"]["error"]["message"]


def test_player_ranged_attack_uses_weapon_range_on_map(client):
    character = client.post(
        "/api/characters",
        json={"name": "Bow Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    client.patch(
        f"/api/characters/{character['id']}",
        json={"inventory": [{"item_id": "equipment.longbow", "quantity": 1}]},
    )
    adventure = client.post(
        "/api/adventures",
        json={"title": "Range Matters", "character_id": character["id"]},
    ).json()
    asset = client.post(
        "/api/map-assets?asset_type=map&name=RangeGrid&filename=range-grid.png",
        content=b"grid",
        headers={"content-type": "image/png"},
    ).json()
    scene = client.post(
        "/api/map-scenes",
        json={
            "name": "Range Grid",
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
                    "name": "Range Goblin",
                    "hp": 7,
                    "ac": 13,
                    "attack_bonus": 4,
                    "damage": "1d6+2",
                    "initiative_bonus": -30,
                }
            ]
        },
    ).json()
    tokens = client.get(f"/api/map-scenes/{scene['id']}/combat-tokens").json()
    hero = next(token for token in tokens if token["participant_name"] == "Bow Hero")
    goblin = next(token for token in tokens if token["participant_name"] == "Range Goblin")
    client.patch(f"/api/map-scenes/{scene['id']}/combat-tokens/{hero['id']}", json={"x": 70, "y": 70})
    client.patch(f"/api/map-scenes/{scene['id']}/combat-tokens/{goblin['id']}", json={"x": 910, "y": 70})

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/action",
        json={
            "actor_name": state["participants"][state["turn_index"]]["name"],
            "target_name": "Range Goblin",
            "action_type": "attack",
            "attack_id": "equipment.longbow",
        },
    )

    assert response.status_code == 200
    assert response.json()["map_range"]["distance_ft"] == 60
    assert response.json()["map_range"]["attack_kind"] == "ranged"
    assert response.json()["map_range"]["normal_range_ft"] == 150
    assert response.json()["map_range"]["long_range_ft"] == 600


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
        token
        for token in client.get(f"/api/map-scenes/{scene['id']}/combat-tokens").json()
        if token["participant_name"] == "Map Goblin"
    )

    assert state["participants"][state["turn_index"]]["name"] == "Map Goblin"
    assert response.status_code == 200
    assert response.json()["action_type"] == "dash"
    assert response.json()["map_movement"]["from"]["x"] == 910
    assert moved_goblin["x"] < 910
