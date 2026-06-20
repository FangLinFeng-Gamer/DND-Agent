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

    response = dm_service.advance(
        adventure.id,
        MessageCreate(content="I climb the wall.", character_id=character["id"]),
    )

    assert response.dice_result is None
    pending = response.dm_message.metadata["pending_check"]
    assert pending["status"] == "pending"
    assert pending["ability"] == "dexterity"
    assert pending["dc"] == 12
    assert pending["reason"] == "Climb the slick wall"
    assert pending["character_id"] == character["id"]
    assert pending["source_message_id"] == response.dm_message.id
    assert "dice_result" not in response.dm_message.metadata
