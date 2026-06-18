import json

from backend.src.schemas.adventure import AdventureCreate, MessageCreate
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.dm import DMService
from backend.src.services.llm_models import LLMModelService
from backend.src.services.world_events import WorldEventService


class FakeLLMClient:
    def __init__(self, response: dict):
        self.response = response
        self.messages = []

    def chat(self, model, messages):
        self.model = model
        self.messages = messages
        return json.dumps(self.response)


class FailingLLMClient:
    def chat(self, model, messages):
        raise RuntimeError("model offline")


def create_character_and_adventure(client, dm_service):
    character = client.post(
        "/api/characters",
        json={"name": "Seren", "race": "Elf", "class_name": "Ranger"},
    ).json()
    adventure = dm_service.create_adventure(AdventureCreate(title="Tower Door", character_id=character["id"]))
    return character, adventure


def activate_model(store):
    service = LLMModelService(store)
    model = service.create(
        LLMModelCreate(
            name="Local Agent",
            base_url="http://127.0.0.1:11434/v1",
            api_key="sk-local-secret",
            model_name="local-dm",
            temperature=0.2,
            max_context_tokens=2048,
        )
    )
    return service.activate(model.id)


def test_dm_agent_uses_active_model_response_and_records_world_events(client):
    activate_model(client.app.state.store)
    fake = FakeLLMClient(
        {
            "narration": "The hidden latch clicks, but the tower scout hears the scrape.",
            "scene": {
                "location": "Mistbell Tower Gate",
                "environment": "The gate stands half open under a cracked warning bell.",
                "important_objects": ["hidden latch", "cracked bell"],
                "npcs": ["Tower scout: nervous and ready to flee"],
                "current_objective": "Decide whether to stop the scout or enter quietly.",
                "world_changes": ["The gate latch has been discovered."],
            },
            "requires_check": True,
            "check": {"ability": "wisdom", "dc": 12, "reason": "Finding the hidden latch quietly"},
            "npc_actions": ["The tower scout backs toward the bell rope."],
            "world_events": [
                {
                    "event_type": "npc",
                    "title": "Scout warned",
                    "description": "The scout noticed the gate noise and moved toward the warning bell.",
                    "importance": 4,
                }
            ],
        }
    )
    dm_service = DMService(client.app.state.store, llm_client=fake)
    _, adventure = create_character_and_adventure(client, dm_service)

    response = dm_service.advance(adventure.id, MessageCreate(content="I inspect the gate latch quietly."))
    events = WorldEventService(client.app.state.store).list_for_adventure(adventure.id)

    assert response.dm_message.content.startswith("The hidden latch clicks")
    assert response.scene.location == "Mistbell Tower Gate"
    assert response.dice_result["ability"] == "wisdom"
    assert response.dice_result["reason"] == "Finding the hidden latch quietly"
    assert events[0].title == "Scout warned"
    assert fake.messages


def test_dm_agent_falls_back_to_template_when_model_call_fails(client):
    activate_model(client.app.state.store)
    dm_service = DMService(client.app.state.store, llm_client=FailingLLMClient())
    _, adventure = create_character_and_adventure(client, dm_service)

    response = dm_service.advance(adventure.id, MessageCreate(content="I move into the tower."))

    assert response.dm_message.content
    assert response.scene.current_objective
