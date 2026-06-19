import json

from backend.src.schemas.adventure import AdventureCreate, MessageCreate
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.adventure_locks import AdventureLockService
from backend.src.services.dm import DMService
from backend.src.services.llm_models import LLMModelService


class FakeStreamingLLMClient:
    def stream_chat(self, model, messages):
        yield '{"narration":"The lantern flares'
        yield ' and reveals wet footprints.","scene":'
        yield '{"location":"Gate","environment":"Rainy","important_objects":["lantern"],'
        yield '"npcs":[],"current_objective":"Follow the footprints.","world_changes":[]}}'


def create_adventure(client):
    character = client.post(
        "/api/characters",
        json={"name": "Stream Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    return client.post("/api/adventures", json={"title": "Streaming Gate", "character_id": character["id"]}).json()


def parse_ndjson(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_streaming_message_endpoint_emits_status_delta_and_final(client):
    adventure = create_adventure(client)

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages/stream",
        json={"content": "I inspect the old door."},
    )
    events = parse_ndjson(response)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert events[0] == {"type": "status", "message": "dm_thinking"}
    assert any(event["type"] == "player_message" for event in events)
    assert any(event["type"] == "delta" and event["content"] for event in events)
    final = events[-1]
    assert final["type"] == "final"
    assert final["dm_message"]["content"]
    assert final["adventure"]["id"] == adventure["id"]


def test_streaming_message_final_includes_dm_triggered_combat(client):
    character = client.post(
        "/api/characters",
        json={"name": "Stream Blade", "race": "Human", "class_name": "Fighter"},
    ).json()
    story = client.post(
        "/api/stories",
        json={
            "title": "Streaming Mill Fight",
            "description": "A scripted encounter for stream verification.",
            "world_background": "The mill is bound to a cold well.",
            "main_quest": "Recover the silver bell.",
            "opening_location": "Mill Road",
            "opening_environment": "Wet footprints cross the road toward the old mill.",
            "opening_objective": "Find the stolen bell.",
            "important_objects": ["wet footprints"],
            "npcs": [],
            "encounters": [
                {
                    "id": "mill_guardian",
                    "title": "Mill Guardian",
                    "description": "A guardian rises when the old mill door opens.",
                    "trigger_keywords": ["old mill", "door"],
                    "enemies": [
                        {
                            "name": "Mill Guardian",
                            "hp": 11,
                            "ac": 13,
                            "attack_bonus": 3,
                            "damage": "1d6+1",
                        }
                    ],
                }
            ],
        },
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Streaming Combat", "character_id": character["id"], "story_id": story["id"]},
    ).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages/stream",
        json={"content": "I reach the old mill and force the door open."},
    )
    events = parse_ndjson(response)

    assert response.status_code == 200
    final = events[-1]
    assert final["type"] == "final"
    assert final["combat_state"]["is_active"] is True
    assert any(participant["name"] == "Mill Guardian" for participant in final["combat_state"]["participants"])


def test_streaming_message_endpoint_rejects_second_request_while_dm_is_busy(client):
    adventure = create_adventure(client)
    locks = AdventureLockService()

    with locks.acquire(adventure["id"]):
        response = client.post(
            f"/api/adventures/{adventure['id']}/messages/stream",
            json={"content": "I try to speak over the DM."},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "dm_busy"


def test_model_streaming_deltas_show_narration_not_raw_json(client):
    character = client.post(
        "/api/characters",
        json={"name": "Stream Mage", "race": "Human", "class_name": "Wizard"},
    ).json()
    model = LLMModelService(client.app.state.store).create(
        LLMModelCreate(
            name="Fake Stream",
            base_url="http://model.test/v1",
            api_key="sk-test",
            model_name="fake",
        )
    )
    LLMModelService(client.app.state.store).activate(model.id)
    service = DMService(client.app.state.store, llm_client=FakeStreamingLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="Model Stream", character_id=character["id"]))

    events = list(service.advance_stream(adventure.id, MessageCreate(content="Look around.")))
    deltas = [event["content"] for event in events if event["type"] == "delta"]

    assert "".join(deltas) == "The lantern flares and reveals wet footprints."
    assert not any('"narration"' in delta or "{" in delta for delta in deltas)
