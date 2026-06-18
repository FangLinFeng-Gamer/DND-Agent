import json

from langgraph.graph.state import CompiledStateGraph

from backend.src.agent.dm.service import DMService
from backend.src.schemas.adventure import AdventureCreate, MessageCreate
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.llm_models import LLMModelService
from backend.src.services.world_events import WorldEventService


def test_dm_service_owns_compiled_langgraph_runner(client):
    service = DMService(client.app.state.store)

    assert isinstance(service.graph_runner.graph, CompiledStateGraph)


class ScriptedMultiAgentClient:
    def __init__(self):
        self.resolution_messages = []

    def chat_message(self, model, messages, tools=None, tool_choice=None):
        if tools:
            return {
                "content": (
                    '{"intent":"exploration","steps":['
                    '{"agent":"exploration_agent","instruction":"Inspect the gate."}]}'
                )
            }
        return {"content": '{"narration":"The gate yields with a low stone groan."}'}

    def chat(self, model, messages):
        self.resolution_messages = messages
        return json.dumps(
            {
                "narration": "Resolved gate facts.",
                "scene": {
                    "location": "Gate",
                    "environment": "The stone gate now stands open.",
                    "important_objects": ["open gate"],
                    "npcs": [],
                    "current_objective": "Cross the threshold.",
                    "world_changes": ["The gate was opened."],
                },
                "requires_check": False,
                "npc_actions": [],
                "world_events": [],
            }
        )

    def stream_chat(self, model, messages):
        yield '{"narration":"The gate'
        yield ' opens into a torchlit hall."}'


def test_active_model_uses_supervisor_plan_and_separate_narration_agent(client):
    character = client.post(
        "/api/characters",
        json={"name": "Graph Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    model = LLMModelService(client.app.state.store).create(
        LLMModelCreate(
            name="Graph Model",
            base_url="http://model.test/v1",
            api_key="sk-test",
            model_name="graph-model",
        )
    )
    LLMModelService(client.app.state.store).activate(model.id)
    scripted = ScriptedMultiAgentClient()
    service = DMService(client.app.state.store, llm_client=scripted)
    adventure = service.create_adventure(
        AdventureCreate(title="Graph Gate", character_id=character["id"])
    )

    response = service.advance(
        adventure.id,
        MessageCreate(content="I pick the locked gate."),
    )
    resolution_payload = json.loads(scripted.resolution_messages[-1]["content"])

    assert response.dm_message.content == "The gate yields with a low stone groan."
    assert resolution_payload["supervisor_plan"]["intent"] == "exploration"
    assert resolution_payload["skills"][0]["name"] == "lockpicking"


def test_active_model_streams_from_separate_narration_agent(client):
    character = client.post(
        "/api/characters",
        json={"name": "Stream Graph Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    model = LLMModelService(client.app.state.store).create(
        LLMModelCreate(
            name="Streaming Graph Model",
            base_url="http://model.test/v1",
            api_key="sk-test",
            model_name="graph-model",
        )
    )
    LLMModelService(client.app.state.store).activate(model.id)
    scripted = ScriptedMultiAgentClient()
    service = DMService(client.app.state.store, llm_client=scripted)
    adventure = service.create_adventure(
        AdventureCreate(title="Streaming Graph Gate", character_id=character["id"])
    )

    events = list(
        service.advance_stream(
            adventure.id,
            MessageCreate(content="I pick the locked gate."),
        )
    )
    deltas = "".join(event["content"] for event in events if event["type"] == "delta")
    resolution_payload = json.loads(scripted.resolution_messages[-1]["content"])

    assert deltas == "The gate opens into a torchlit hall."
    assert events[-1]["dm_message"].content == deltas
    assert resolution_payload["skills"][0]["name"] == "lockpicking"


class FailingNarrationClient(ScriptedMultiAgentClient):
    def chat_message(self, model, messages, tools=None, tool_choice=None):
        if tools:
            return super().chat_message(model, messages, tools, tool_choice)
        raise RuntimeError("narration unavailable")

    def chat(self, model, messages):
        payload = json.loads(super().chat(model, messages))
        payload["world_events"] = [
            {
                "event_type": "location",
                "title": "Gate opened",
                "description": "The gate was permanently opened.",
                "importance": 4,
            }
        ]
        return json.dumps(payload)


def test_narration_failure_does_not_partially_commit_world_events(client):
    character = client.post(
        "/api/characters",
        json={"name": "Fallback Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    model = LLMModelService(client.app.state.store).create(
        LLMModelCreate(
            name="Failing Narrator",
            base_url="http://model.test/v1",
            api_key="sk-test",
            model_name="graph-model",
        )
    )
    LLMModelService(client.app.state.store).activate(model.id)
    service = DMService(client.app.state.store, llm_client=FailingNarrationClient())
    adventure = service.create_adventure(
        AdventureCreate(title="Fallback Gate", character_id=character["id"])
    )

    response = service.advance(
        adventure.id,
        MessageCreate(content="I inspect the gate."),
    )
    events = WorldEventService(client.app.state.store).list_for_adventure(adventure.id)

    assert response.dm_message.content
    assert events == []
