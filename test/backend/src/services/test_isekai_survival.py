import json

from backend.src.schemas.adventure import AdventureCreate, MessageCreate
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.llm_models import LLMModelService
from backend.src.services.isekai import IsekaiSurvivalService


class FakeIsekaiLLMClient:
    def __init__(self):
        self.chat_calls = []

    def chat(self, model, messages):
        self.chat_calls.append({"model": model, "messages": messages})
        return json.dumps({"narration": "模型异世界回复：雾中的猎径传来铃声。"})


class FakeStreamingIsekaiLLMClient:
    def __init__(self):
        self.stream_calls = 0
        self.chat_calls = 0

    def chat(self, model, messages):
        self.chat_calls += 1
        raise AssertionError("streaming isekai replies should not wait for chat()")

    def stream_chat(self, model, messages):
        self.stream_calls += 1
        yield '{"narration":"模型流式异世界回复：'
        yield '树影中出现了陌生路标。"}'


def activate_test_model(store):
    model_service = LLMModelService(store)
    model = model_service.create(
        LLMModelCreate(
            name="Isekai DM",
            provider="openai_compatible",
            base_url="https://api.example.test",
            api_key="sk-test-1234567890",
            model_name="isekai-dm-model",
        )
    )
    model_service.activate(model.id)
    return model


def test_random_isekai_character_has_survival_inventory_and_world_reaction_tags(store):
    service = IsekaiSurvivalService(store)

    character = service.generate_character()

    assert character.name
    assert character.race in {"Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Tiefling"}
    assert character.class_name in {"Fighter", "Ranger", "Rogue", "Wizard", "Cleric", "Druid"}
    assert character.gold >= 5
    assert character.inventory
    assert character.world_reaction_tags


def test_survival_rules_increase_pressure_for_exploration(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Rule Road", mode="isekai_survival"))
    before = adventure.survival_state

    response = service.advance(adventure.id, MessageCreate(content="我沿着旧猎径探索。", locale="zh-CN"))

    after = response.adventure.survival_state
    assert after["fatigue"] > before["fatigue"]
    assert after["thirst"] > before["thirst"]
    assert response.dm_message.metadata["mode"] == "isekai_survival"
    assert response.dm_message.metadata["survival_delta"]["fatigue"] > 0


def test_isekai_advance_uses_active_model_for_narration(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Model Wilds", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我观察雾气。", locale="zh-CN"))

    assert len(llm_client.chat_calls) == 1
    assert llm_client.chat_calls[0]["model"].model_name == "isekai-dm-model"
    assert response.dm_message.content == "模型异世界回复：雾中的猎径传来铃声。"
    assert response.dm_message.metadata["source"] == "active_model"


def test_isekai_stream_uses_active_model_streaming(store):
    activate_test_model(store)
    llm_client = FakeStreamingIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Stream Wilds", mode="isekai_survival"))

    events = list(service.advance_stream(adventure.id, MessageCreate(content="我继续前进。", locale="zh-CN")))

    delta_text = "".join(event.get("content", "") for event in events if event["type"] == "delta")
    assert llm_client.stream_calls == 1
    assert llm_client.chat_calls == 0
    assert "模型流式异世界回复" in delta_text
    assert events[-1]["type"] == "final"
    assert events[-1]["dm_message"].metadata["source"] == "active_model"
