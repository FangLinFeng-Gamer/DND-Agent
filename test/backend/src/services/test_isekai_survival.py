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


class TimelineStreamingPreferenceClient:
    def __init__(self):
        self.timeline = []

    def chat(self, model, messages):
        self.timeline.append("chat")
        return json.dumps(
            {
                "themes": ["美食"],
                "playstyle": ["经营"],
                "goals": ["开餐厅"],
                "confidence": 0.8,
            }
        )

    def stream_chat(self, model, messages):
        self.timeline.append("stream_start")
        yield '{"narration":"第五回合流式回复：'
        self.timeline.append("stream_chunk")
        yield '你闻到远处营火上的炖汤香气。"}'


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


def test_isekai_stream_defers_preference_learning_until_after_narration(store):
    llm_client = TimelineStreamingPreferenceClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Stream Preference Wilds", mode="isekai_survival"))

    for index in range(4):
        service.advance(adventure.id, MessageCreate(content=f"我沿着旧猎径探索第{index + 1}段。", locale="zh-CN"))

    activate_test_model(store)

    events = list(service.advance_stream(adventure.id, MessageCreate(content="我继续寻找适合做汤的食材。", locale="zh-CN")))

    delta_text = "".join(event.get("content", "") for event in events if event["type"] == "delta")
    assert "第五回合流式回复" in delta_text
    assert llm_client.timeline.index("stream_start") < llm_client.timeline.index("chat")
    assert llm_client.timeline.index("stream_chunk") < llm_client.timeline.index("chat")
    assert service.adventures.get_world_state(adventure.id)["player_preferences"]["themes"] == ["美食"]


def test_isekai_turn_records_known_world_events(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Event Turn", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我给路边营地的人做一锅热汤。", locale="zh-CN"))

    events = response.adventure.world_events
    assert events
    assert events[-1].metadata["source"] == "player_triggered"
    assert events[-1].metadata["known_to_character"] is True
    assert events[-1].metadata["triggering_action"] == "我给路边营地的人做一锅热汤。"


def test_isekai_turn_count_is_adventure_local(store):
    service = IsekaiSurvivalService(store)
    first = service.create_adventure(AdventureCreate(title="First Counter", mode="isekai_survival"))
    second = service.create_adventure(AdventureCreate(title="Second Counter", mode="isekai_survival"))

    first_response = service.advance(first.id, MessageCreate(content="我沿着旧猎径探索。", locale="zh-CN"))
    fresh_second = service.adventures.get(second.id)

    assert first_response.adventure.world_state["turn_count"] == 1
    assert fresh_second.world_state["turn_count"] == 0


def test_isekai_status_question_does_not_advance_time_or_pressure(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Status", mode="isekai_survival"))
    before = adventure.survival_state

    response = service.advance(adventure.id, MessageCreate(content="我现在的状态怎么样？", locale="zh-CN"))

    after = response.adventure.survival_state
    assert after["day"] == before["day"]
    assert after["time_of_day"] == before["time_of_day"]
    assert after["hunger"] == before["hunger"]
    assert after["thirst"] == before["thirst"]
    assert after["fatigue"] == before["fatigue"]
    assert after["sleep_need"] == before["sleep_need"]
    assert after["state"]["last_time_delta_minutes"] == 0
    assert response.dm_message.metadata["time"]["advances_time"] is False
    assert response.adventure.world_events == []


def test_isekai_exploration_advances_time_and_pressure(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Road", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我前往远处火光所在的营地。", locale="zh-CN"))

    survival = response.adventure.survival_state
    assert survival["state"]["last_time_delta_minutes"] == 90
    assert survival["time_of_day"] == "夜晚"
    assert survival["thirst"] > adventure.survival_state["thirst"]
    assert survival["fatigue"] > adventure.survival_state["fatigue"]
    assert "时间推进了约" in response.dm_message.content


def test_isekai_sleep_rolls_to_next_day(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Sleep", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我睡觉过夜。", locale="zh-CN"))

    survival = response.adventure.survival_state
    assert survival["day"] == 2
    assert survival["time_of_day"] == "清晨"
    assert survival["fatigue"] < adventure.survival_state["fatigue"]
    assert survival["sleep_need"] < adventure.survival_state["sleep_need"]
