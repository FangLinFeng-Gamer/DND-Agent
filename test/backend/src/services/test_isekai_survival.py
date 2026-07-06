import json

from backend.src.db.sqlite import encode_json
from backend.src.schemas.adventure import AdventureCreate, MessageCreate
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.llm_models import LLMModelService
from backend.src.services.isekai import IsekaiSurvivalService


def is_opening_prompt(messages):
    return "异世界开局生成器" in messages[0]["content"]


class FakeIsekaiLLMClient:
    def __init__(self):
        self.chat_calls = []

    def chat(self, model, messages):
        self.chat_calls.append({"model": model, "messages": messages})
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        return json.dumps({"narration": "模型异世界回复：雾中的猎径传来铃声。"})


class OpeningIsekaiLLMClient:
    def __init__(self):
        self.chat_calls = []

    def chat(self, model, messages):
        self.chat_calls.append({"model": model, "messages": messages})
        if is_opening_prompt(messages):
            return json.dumps(
                {
                    "location": "灰桥镇废弃马厩",
                    "environment": "冷雨敲打着塌了一角的马厩屋顶，泥地上有新鲜车辙和散落燕麦。",
                    "important_objects": ["破马灯", "新鲜车辙", "散落燕麦"],
                    "current_objective": "弄清是谁刚刚离开马厩，并找到可以过夜的干燥角落。",
                    "weather": "冷雨",
                    "opening_narration": "你在灰桥镇废弃马厩醒来，雨水顺着木梁滴落，远处传来马车轮声。",
                },
                ensure_ascii=False,
            )
        return json.dumps({"narration": "模型异世界回复：雨声遮住了远处脚步。"}, ensure_ascii=False)


class InvalidOpeningIsekaiLLMClient:
    def chat(self, model, messages):
        if is_opening_prompt(messages):
            return "{not-json"
        return json.dumps({"narration": "模型异世界回复：你继续前进。"}, ensure_ascii=False)


class OutOfSettingIsekaiLLMClient:
    def chat(self, model, messages):
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        return json.dumps(
            {
                "narration": "你来到商业街，看见一家烤饼铺子正在卖早餐套餐。",
                "scene_update": {
                    "location": "商业街",
                    "environment": "烤饼铺子旁边有便利店。",
                    "important_objects": ["广告牌", "热销菜单"],
                    "current_objective": "询问烤饼铺子老板。",
                },
            },
            ensure_ascii=False,
        )


class ContradictoryLocationLLMClient:
    def chat(self, model, messages):
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        return json.dumps(
            {"narration": "你并未抵达任何村落，仍在雾林边境。"},
            ensure_ascii=False,
        )


class NonActionSceneMoveLLMClient:
    def chat(self, model, messages):
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        return json.dumps(
            {
                "narration": "你查看状态时，周围景象又变回了雾林边境。",
                "scene_update": {
                    "location": "雾林边境",
                    "environment": "你又站在最初醒来的针叶林边缘。",
                },
            },
            ensure_ascii=False,
        )


class SceneUpdateIsekaiLLMClient:
    def __init__(self):
        self.chat_calls = []
        self.advance_calls = 0

    def chat(self, model, messages):
        self.chat_calls.append({"model": model, "messages": messages})
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        self.advance_calls += 1
        if self.advance_calls == 1:
            return json.dumps(
                {
                    "narration": "你沿着旧猎径前进，抵达白石镇外的木质哨站。",
                    "scene_update": {
                        "location": "白石镇外木质哨站",
                        "environment": "晨雾中的木质哨站立在旧猎径尽头，路牌指向白石镇。",
                        "important_objects": ["木质哨站", "指向白石镇的路牌", "披斗篷的守卫"],
                        "current_objective": "确认哨站守卫的态度，并决定是否进入白石镇。",
                    },
                },
                ensure_ascii=False,
            )
        payload = json.loads(messages[-1]["content"])
        recent_text = "\n".join(message["content"] for message in payload["recent_messages"])
        assert "抵达白石镇外的木质哨站" in recent_text
        assert payload["system_state"]["scene"]["location"] == "白石镇外木质哨站"
        assert payload["system_state"]["world_state"]["location_history"][-1]["to"] == "白石镇外木质哨站"
        return json.dumps({"narration": "你确实已经抵达白石镇外木质哨站。"}, ensure_ascii=False)


class FakeStreamingIsekaiLLMClient:
    def __init__(self):
        self.stream_calls = 0
        self.chat_calls = 0

    def chat(self, model, messages):
        self.chat_calls += 1
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        raise AssertionError("streaming isekai replies should not wait for chat()")

    def stream_chat(self, model, messages):
        self.stream_calls += 1
        yield '{"narration":"模型流式异世界回复：'
        yield '树影中出现了陌生路标。"}'


class FailingIsekaiLLMClient:
    def chat(self, model, messages):
        raise RuntimeError("deepseek request failed")


class FailingStreamingIsekaiLLMClient:
    def stream_chat(self, model, messages):
        raise RuntimeError("deepseek stream failed")
        yield ""

    def chat(self, model, messages):
        raise RuntimeError("deepseek chat failed")


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


def activate_test_model(store, max_context_tokens: int = 4096):
    model_service = LLMModelService(store)
    model = model_service.create(
        LLMModelCreate(
            name="Isekai DM",
            provider="openai_compatible",
            base_url="https://api.example.test",
            api_key="sk-test-1234567890",
            model_name="isekai-dm-model",
            max_context_tokens=max_context_tokens,
        )
    )
    model_service.activate(model.id)
    return model


def set_survival_pressure(store, adventure_id: int, **values):
    with store.connect() as conn:
        assignments = ", ".join(f"{key} = :{key}" for key in values)
        conn.execute(
            f"""
            UPDATE isekai_survival_states
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE adventure_id = :adventure_id
            """,
            {"adventure_id": adventure_id, **values},
        )


def set_character_state(store, adventure_id: int, **values):
    payload = dict(values)
    if "inventory" in payload:
        payload["inventory_json"] = encode_json(payload.pop("inventory"))
    if "status_effects" in payload:
        payload["status_effects_json"] = encode_json(payload.pop("status_effects"))
    with store.connect() as conn:
        assignments = ", ".join(f"{key} = :{key}" for key in payload)
        conn.execute(
            f"""
            UPDATE isekai_characters
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE adventure_id = :adventure_id
            """,
            {"adventure_id": adventure_id, **payload},
        )


def test_random_isekai_character_has_survival_inventory_and_world_reaction_tags(store):
    service = IsekaiSurvivalService(store)

    character = service.generate_character()

    assert character.name
    assert character.race in {"Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Tiefling"}
    assert character.class_name in {"Fighter", "Ranger", "Rogue", "Wizard", "Cleric", "Druid"}
    assert character.gold >= 5
    assert character.inventory
    assert character.world_reaction_tags


def test_isekai_create_uses_active_model_for_opening_scene(store):
    activate_test_model(store)
    llm_client = OpeningIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)

    adventure = service.create_adventure(AdventureCreate(title="Opening Road", mode="isekai_survival", locale="zh-CN"))

    assert llm_client.chat_calls[0]["model"].model_name == "isekai-dm-model"
    assert adventure.current_scene.location == "灰桥镇废弃马厩"
    assert adventure.current_scene.important_objects == ["破马灯", "新鲜车辙", "散落燕麦"]
    assert adventure.current_scene.current_objective == "弄清是谁刚刚离开马厩，并找到可以过夜的干燥角落。"
    assert adventure.survival_state["location"] == "灰桥镇废弃马厩"
    assert adventure.survival_state["weather"] == "冷雨"
    assert adventure.world_state["confirmed_location"] == "灰桥镇废弃马厩"
    assert "灰桥镇废弃马厩" in adventure.messages[0].content
    assert adventure.messages[0].metadata["opening_source"] == "active_model"


def test_isekai_opening_falls_back_when_model_payload_is_invalid(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=InvalidOpeningIsekaiLLMClient())

    adventure = service.create_adventure(AdventureCreate(title="Fallback Opening", mode="isekai_survival", locale="zh-CN"))

    assert adventure.current_scene.location
    assert adventure.current_scene.location != "雾林边境"
    assert adventure.survival_state["location"] == adventure.current_scene.location
    assert adventure.survival_state["weather"]
    assert adventure.messages[0].metadata["opening_source"] == "fallback_template"


def test_isekai_eat_drink_consumes_inventory_and_records_resource_changes(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Resource Road", mode="isekai_survival"))
    before_inventory = adventure.isekai_character["inventory"]

    response = service.advance(adventure.id, MessageCreate(content="我吃干粮并喝水。", locale="zh-CN"))

    after_inventory = response.adventure.isekai_character["inventory"]
    changes = response.dm_message.metadata["survival_delta"]["inventory_changes"]
    assert before_inventory != after_inventory
    assert any("消耗干粮" in change for change in changes)
    assert any("饮用水囊" in change for change in changes)
    assert "干粮 x2" not in after_inventory
    assert response.dm_message.metadata["survival_delta"]["hp_delta"] == 0


def test_isekai_high_survival_pressure_damages_hp_and_adds_status_effects(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Pressure Road", mode="isekai_survival"))
    set_survival_pressure(store, adventure.id, hunger=95, thirst=95, fatigue=95, sleep_need=95)
    set_character_state(store, adventure.id, hp_current=10, status_effects=[])

    response = service.advance(adventure.id, MessageCreate(content="我继续前进。", locale="zh-CN"))

    character = response.adventure.isekai_character
    delta = response.dm_message.metadata["survival_delta"]
    assert character["hp_current"] < 10
    assert delta["hp_delta"] < 0
    assert {"饥饿虚弱", "脱水", "极度疲劳"} <= set(character["status_effects"])
    assert {"饥饿虚弱", "脱水", "极度疲劳"} <= set(delta["status_effects_added"])


def test_isekai_recovered_pressure_removes_status_effects(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Recovery Road", mode="isekai_survival"))
    set_survival_pressure(store, adventure.id, hunger=20, thirst=20, fatigue=20, sleep_need=20)
    set_character_state(store, adventure.id, status_effects=["饥饿虚弱", "脱水", "极度疲劳"])

    response = service.advance(adventure.id, MessageCreate(content="我现在的状态怎么样？", locale="zh-CN"))

    character = response.adventure.isekai_character
    delta = response.dm_message.metadata["survival_delta"]
    assert "饥饿虚弱" not in character["status_effects"]
    assert "脱水" not in character["status_effects"]
    assert "极度疲劳" not in character["status_effects"]
    assert {"饥饿虚弱", "脱水", "极度疲劳"} <= set(delta["status_effects_removed"])


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

    assert len(llm_client.chat_calls) == 2
    assert llm_client.chat_calls[-1]["model"].model_name == "isekai-dm-model"
    assert response.dm_message.content == "模型异世界回复：雾中的猎径传来铃声。"
    assert response.dm_message.metadata["source"] == "active_model"


def test_isekai_model_context_uses_active_model_context_window(store):
    activate_test_model(store, max_context_tokens=40960)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Long Memory Wilds", mode="isekai_survival"))
    for index in range(8):
        service.adventures.append_message(adventure.id, "player", f"历史玩家行动 {index}", {"mode": "isekai_survival"})
        service.adventures.append_message(adventure.id, "dm", f"历史模型回复 {index}", {"mode": "isekai_survival"})

    service.advance(adventure.id, MessageCreate(content="现在根据完整历史继续。", locale="zh-CN"))

    payload = json.loads(llm_client.chat_calls[-1]["messages"][-1]["content"])
    recent_messages = payload["recent_messages"]
    assert len(recent_messages) > 12
    assert recent_messages[-1]["content"] == "现在根据完整历史继续。"


def test_isekai_model_output_is_normalized_to_fantasy_world_terms(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=OutOfSettingIsekaiLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="Worldview Road", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我去镇上找食物。", locale="zh-CN"))

    assert "烤饼铺子" not in response.dm_message.content
    assert "早餐套餐" not in response.dm_message.content
    assert "炉饼摊" in response.dm_message.content
    assert response.adventure.current_scene.location == "集市街"
    assert response.adventure.current_scene.environment == "炉饼摊旁边有杂货铺。"
    assert response.adventure.current_scene.important_objects == ["告示牌", "招牌菜单"]


def test_isekai_prompt_includes_worldview_style_guidance(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Prompt Road", mode="isekai_survival"))

    service.advance(adventure.id, MessageCreate(content="我寻找食物。", locale="zh-CN"))

    system_prompt = llm_client.chat_calls[-1]["messages"][0]["content"]
    assert "DND 风格奇幻世界" in system_prompt
    assert "烤饼铺子" not in system_prompt
    assert "炉饼摊" in system_prompt


def test_isekai_active_model_failure_records_fallback_reason(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=FailingIsekaiLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="Model Failure", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我观察雾气。", locale="zh-CN"))

    assert response.dm_message.metadata["source"] == "survival_rules"
    assert response.dm_message.metadata["model_errors"] == [
        {"stage": "chat", "message": "deepseek request failed"}
    ]


def test_isekai_model_scene_update_persists_location_and_history(store):
    activate_test_model(store)
    llm_client = SceneUpdateIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Memory Road", mode="isekai_survival"))
    starting_location = adventure.current_scene.location

    first = service.advance(adventure.id, MessageCreate(content="去白石镇", locale="zh-CN"))

    assert first.adventure.current_scene.location == "白石镇外木质哨站"
    assert first.adventure.survival_state["location"] == "白石镇外木质哨站"
    assert first.adventure.world_state["location_history"][-1]["from"] == starting_location
    assert first.adventure.world_state["location_history"][-1]["to"] == "白石镇外木质哨站"
    assert first.adventure.world_state["location_history"][-1]["triggering_action"] == "去白石镇"

    second = service.advance(adventure.id, MessageCreate(content="我不是已经到木质哨站了吗", locale="zh-CN"))

    assert "确实已经抵达" in second.dm_message.content
    assert second.adventure.current_scene.location == "白石镇外木质哨站"


def test_confirmed_location_overrides_contradictory_model_narration(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=ContradictoryLocationLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="Fact Lock Road", mode="isekai_survival"))
    locked_scene = adventure.current_scene.model_copy(update={"location": "白石镇外木质哨站"})
    service.adventures.update_scene(adventure.id, locked_scene)
    service.update_world_location_history(
        adventure.id,
        {
            "from": "雾林边境",
            "to": "白石镇外木质哨站",
            "triggering_action": "去白石镇",
            "day": 1,
            "time_of_day": "夜晚",
            "summary": "你已经抵达白石镇外木质哨站。",
        },
    )
    service.update_survival_location(
        adventure.id,
        "白石镇外木质哨站",
        {
            "from": "雾林边境",
            "to": "白石镇外木质哨站",
            "triggering_action": "去白石镇",
            "day": 1,
            "time_of_day": "夜晚",
            "summary": "你已经抵达白石镇外木质哨站。",
        },
    )

    response = service.advance(adventure.id, MessageCreate(content="我不是已经到木质哨站了吗？", locale="zh-CN"))

    assert "白石镇外木质哨站" in response.dm_message.content
    assert "并未抵达" not in response.dm_message.content
    assert "仍在雾林边境" not in response.dm_message.content
    assert response.adventure.current_scene.location == "白石镇外木质哨站"
    assert response.adventure.world_state["confirmed_location"] == "白石镇外木质哨站"


def test_non_action_scene_update_cannot_move_character(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=NonActionSceneMoveLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="No Move Road", mode="isekai_survival"))
    locked_scene = adventure.current_scene.model_copy(update={"location": "白石镇外木质哨站"})
    service.adventures.update_scene(adventure.id, locked_scene)
    service.update_world_location_history(
        adventure.id,
        {
            "from": "雾林边境",
            "to": "白石镇外木质哨站",
            "triggering_action": "去白石镇",
            "day": 1,
            "time_of_day": "夜晚",
            "summary": "你已经抵达白石镇外木质哨站。",
        },
    )
    service.update_survival_location(
        adventure.id,
        "白石镇外木质哨站",
        {
            "from": "雾林边境",
            "to": "白石镇外木质哨站",
            "triggering_action": "去白石镇",
            "day": 1,
            "time_of_day": "夜晚",
            "summary": "你已经抵达白石镇外木质哨站。",
        },
    )

    response = service.advance(adventure.id, MessageCreate(content="我现在在哪？", locale="zh-CN"))

    assert response.adventure.current_scene.location == "白石镇外木质哨站"
    assert response.adventure.survival_state["location"] == "白石镇外木质哨站"
    assert response.dm_message.metadata["time"]["advances_time"] is False


def test_isekai_stream_uses_active_model_streaming(store):
    activate_test_model(store)
    llm_client = FakeStreamingIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Stream Wilds", mode="isekai_survival"))
    opening_chat_calls = llm_client.chat_calls

    events = list(service.advance_stream(adventure.id, MessageCreate(content="我继续前进。", locale="zh-CN")))

    delta_text = "".join(event.get("content", "") for event in events if event["type"] == "delta")
    assert llm_client.stream_calls == 1
    assert llm_client.chat_calls == opening_chat_calls
    assert "模型流式异世界回复" in delta_text
    assert events[-1]["type"] == "final"
    assert events[-1]["dm_message"].metadata["source"] == "active_model"


def test_isekai_stream_model_failure_records_fallback_reason(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=FailingStreamingIsekaiLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="Stream Failure", mode="isekai_survival"))

    events = list(service.advance_stream(adventure.id, MessageCreate(content="我继续前进。", locale="zh-CN")))

    assert events[-1]["dm_message"].metadata["source"] == "survival_rules"
    assert events[-1]["dm_message"].metadata["model_errors"] == [
        {"stage": "stream_chat", "message": "deepseek stream failed"},
        {"stage": "chat", "message": "deepseek chat failed"},
    ]


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


def test_isekai_event_impacts_are_persisted_and_sent_to_model_context(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Impact Road", mode="isekai_survival"))

    for index in range(3):
        response = service.advance(adventure.id, MessageCreate(content=f"我沿着猎径继续前进第{index + 1}段。", locale="zh-CN"))

    impacts = response.adventure.world_state["event_impacts"]
    assert impacts
    assert impacts[-1]["dm_context"]
    payload = json.loads(llm_client.chat_calls[-1]["messages"][-1]["content"])
    context_impacts = payload["system_state"]["world_state"]["event_impacts"]
    assert context_impacts[-1]["dm_context"] == impacts[-1]["dm_context"]


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
