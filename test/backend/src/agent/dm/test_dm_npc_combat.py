import json

from backend.src.agent.dm.service import DMService
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.llm_models import LLMModelService


class FakeNPCDecisionLLM:
    def __init__(self):
        self.messages = []

    def chat(self, model, messages):
        self.messages = messages
        return json.dumps({"action_type": "dodge", "reason": "holding a defensive line"})


def activate_model(store):
    service = LLMModelService(store)
    model = service.create(
        LLMModelCreate(
            name="NPC Test Model",
            base_url="https://example.invalid/v1",
            api_key="test-key",
            model_name="npc-test",
        )
    )
    return service.activate(model.id)


def test_dm_service_uses_active_model_and_npc_context_for_npc_turn(client):
    character = client.post(
        "/api/characters",
        json={"name": "Iris", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post("/api/adventures", json={"title": "Model NPC", "character_id": character["id"]}).json()
    client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={
            "enemies": [
                {
                    "name": "Tactical Raider",
                    "hp": 8,
                    "ac": 11,
                    "attack_bonus": 2,
                    "damage": "1d4",
                    "initiative_bonus": 30,
                }
            ]
        },
    )
    activate_model(client.app.state.store)
    fake_llm = FakeNPCDecisionLLM()
    service = DMService(client.app.state.store, llm_client=fake_llm)

    result = service.resolve_npc_combat_turn(adventure["id"], locale="en")

    assert result["action_type"] == "dodge"
    assert result["decision_source"] == "model"
    assert result["decision_reason"] == "holding a defensive line"
    payload = json.loads(fake_llm.messages[1]["content"])
    assert payload["current_npc"]["name"] == "Tactical Raider"
    assert payload["scene"]["location"]
    assert payload["nearby_enemies"][0]["name"] == "Iris"
    assert any(skill["name"] == "npc-combat-tactics" for skill in payload["skills"])
