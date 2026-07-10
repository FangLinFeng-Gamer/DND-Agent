import json

from backend.src.db.sqlite import encode_json
from backend.src.schemas.adventure import AdventureCreate, MessageCreate, SceneState
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.adventures import AdventureService
from backend.src.services.llm_models import LLMModelService
from backend.src.services.isekai import IsekaiSurvivalService


def set_content_packs(service, adventure_id: int, packs: list[str]):
    world_state = service.adventures.get_world_state(adventure_id)
    world_state["isekai_content"] = {"active_packs": packs, "activation": "explicit"}
    world_state = service.quests.initial_world_state(world_state)
    service.adventures.update_world_state(adventure_id, world_state)
    return world_state


def test_scene_state_accepts_structured_isekai_interactables():
    scene = SceneState(
        location="伐木营地",
        environment="雨后的木棚旁有猎犬低吼。",
        important_objects=[],
        npcs=[],
        current_objective="找到可以过夜的庇护点。",
        interactables=[
            {
                "id": "lumberjack_01",
                "type": "npc",
                "name": "戒备的伐木工",
                "state": "戒备",
                "affordances": ["交涉", "请求借宿"],
                "risk": "态度恶化可能引来猎犬",
            }
        ],
        suggested_actions=["向伐木工说明来意"],
        npc_states=[
            {
                "id": "lumberjack_01",
                "name": "伐木工",
                "attitude": "suspicious",
                "trust": 20,
                "known_facts": ["玩家是外来者"],
            }
        ],
    )

    assert scene.interactables[0]["name"] == "戒备的伐木工"
    assert scene.suggested_actions == ["向伐木工说明来意"]
    assert scene.npc_states[0]["trust"] == 20


def test_isekai_model_payload_parses_structured_fields(store):
    service = IsekaiSurvivalService(store)
    raw = json.dumps(
        {
            "narration": "你拿起猎网和燧石碎片。",
            "scene_update": {"important_objects": ["旧木棚"]},
            "interactables": [{"id": "net_01", "type": "item", "name": "猎网"}],
            "suggested_actions": ["检查猎网是否还能使用"],
            "state_changes": {"add_items": ["猎网", "燧石碎片"]},
        },
        ensure_ascii=False,
    )

    payload = service.parse_model_payload(raw, "fallback")

    assert payload["narration"] == "你拿起猎网和燧石碎片。"
    assert payload["interactables"][0]["name"] == "猎网"
    assert payload["suggested_actions"] == ["检查猎网是否还能使用"]
    assert payload["state_changes"]["add_items"] == ["猎网", "燧石碎片"]


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


class ContradictoryOpeningInventoryLLMClient:
    def chat(self, model, messages):
        if is_opening_prompt(messages):
            return json.dumps(
                {
                    "location": "迷踪森林边缘",
                    "environment": "树冠遮住天空，泥地上留着仓促逃亡的脚印。",
                    "important_objects": ["断裂树枝", "湿苔", "兽类足迹"],
                    "current_objective": "确认水源方向，并检查还能使用的随身物资。",
                    "weather": "阴冷薄雾",
                    "opening_narration": "你在树根下醒来，水囊已在昨夜逃亡时遗失，只剩干粮压在旧斗篷下。",
                },
                ensure_ascii=False,
            )
        return json.dumps({"narration": "模型异世界回复：你继续前进。"}, ensure_ascii=False)


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


class HungryOrdinaryTradeLLMClient:
    def __init__(self):
        self.chat_calls = []

    def chat(self, model, messages):
        self.chat_calls.append({"model": model, "messages": messages})
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        return json.dumps(
            {
                "narration": "你肚子饿得发慌，只能和普通小贩讨价还价。",
                "scene_update": {
                    "environment": "白石镇炉饼摊旁边，人们像普通集市一样买卖。",
                    "important_objects": ["普通小贩", "菜单牌"],
                    "current_objective": "买点吃的。",
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


class StructuredStateChangeIsekaiLLMClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.chat_calls = []

    def chat(self, model, messages):
        self.chat_calls.append({"model": model, "messages": messages})
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        return json.dumps(self.payload, ensure_ascii=False)


class SequenceIsekaiLLMClient:
    def __init__(self, payloads: list[dict]):
        self.payloads = list(payloads)
        self.chat_calls = []

    def chat(self, model, messages):
        self.chat_calls.append({"model": model, "messages": messages})
        if is_opening_prompt(messages):
            return "{invalid opening payload"
        if self.payloads:
            return json.dumps(self.payloads.pop(0), ensure_ascii=False)
        return json.dumps({"narration": "你继续确认周围环境。"}, ensure_ascii=False)


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
    assert character.gold == 0
    assert character.inventory
    assert character.world_reaction_tags


def test_isekai_create_initializes_copper_economy_separate_from_character_gold(store):
    service = IsekaiSurvivalService(store)

    adventure = service.create_adventure(AdventureCreate(title="Copper Economy", mode="isekai_survival", locale="zh-CN"))

    economy = adventure.world_state["isekai_economy"]
    copper_total = economy["currency"]["copper_total"]
    assert set(economy["currency"].keys()) == {"copper_total"}
    assert 20 <= copper_total <= 80
    assert adventure.isekai_character["gold"] == 0
    assert "金币" not in adventure.messages[-1].content
    assert "铜" in adventure.messages[-1].content


def test_isekai_old_adventure_read_migrates_missing_copper_economy(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Legacy Missing Economy", mode="isekai_survival"))
    world_state = service.adventures.get_world_state(adventure.id)
    world_state.pop("isekai_economy", None)
    service.adventures.update_world_state(adventure.id, world_state)

    migrated = AdventureService(store).get(adventure.id, include_messages=False)

    economy = migrated.world_state["isekai_economy"]
    assert set(economy["currency"].keys()) == {"copper_total"}
    assert 20 <= economy["currency"]["copper_total"] <= 80


def test_isekai_create_uses_active_model_for_opening_scene(store):
    activate_test_model(store)
    llm_client = OpeningIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)

    adventure = service.create_adventure(AdventureCreate(title="Opening Road", mode="isekai_survival", locale="zh-CN"))

    assert llm_client.chat_calls[0]["model"].model_name == "isekai-dm-model"
    opening_messages = llm_client.chat_calls[0]["messages"]
    assert "character.inventory 是后端权威背包" in opening_messages[0]["content"]
    assert "水囊(3/3)" in opening_messages[-1]["content"]
    assert adventure.current_scene.location == "灰桥镇废弃马厩"
    assert adventure.current_scene.important_objects == ["破马灯", "新鲜车辙", "散落燕麦"]
    assert adventure.current_scene.current_objective == "弄清是谁刚刚离开马厩，并找到可以过夜的干燥角落。"
    assert adventure.survival_state["location"] == "灰桥镇废弃马厩"
    assert adventure.survival_state["weather"] == "冷雨"
    assert adventure.world_state["confirmed_location"] == "灰桥镇废弃马厩"
    assert "灰桥镇废弃马厩" in adventure.messages[0].content
    assert adventure.messages[0].metadata["opening_source"] == "active_model"


def test_isekai_opening_repairs_model_inventory_contradictions(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=ContradictoryOpeningInventoryLLMClient())

    adventure = service.create_adventure(AdventureCreate(title="Opening Inventory Guard", mode="isekai_survival", locale="zh-CN"))

    opening = adventure.messages[0].content
    assert "水囊(3/3)" in adventure.isekai_character["inventory"]
    assert "水囊已在昨夜逃亡时遗失" not in opening
    assert "水囊" in opening
    assert "随身物品" in opening
    assert adventure.messages[0].metadata["opening_source"] == "active_model"


def test_isekai_search_can_apply_confirmed_item_gain_from_model(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(
        store,
        llm_client=StructuredStateChangeIsekaiLLMClient(
            {
                "narration": "你拨开冷灰烬堆，找到一枚烧焦铜币。",
                "state_changes": {"add_items": ["烧焦铜币 x1"]},
                "interactables": [{"id": "campfire", "type": "place", "name": "小火堆"}],
                "suggested_actions": ["继续检查墙壁符文"],
            }
        ),
    )
    adventure = service.create_adventure(AdventureCreate(title="Ash Coin", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "废弃瞭望塔底层",
            "environment": "底层圆形大厅里有冷灰烬堆和兽骨。",
            "important_objects": ["冷灰烬堆", "兽骨"],
            "interactables": [
                {
                    "id": "cold_ashes",
                    "type": "place",
                    "name": "冷灰烬堆",
                    "affordances": ["检查", "翻找"],
                }
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="检查冷灰烬堆和兽骨", locale="zh-CN"))

    assert response.dm_message.metadata["parsed_action"]["action_type"] == "search"
    assert "烧焦铜币" in response.adventure.isekai_character["inventory"]
    assert response.dm_message.metadata["state_changes_applied"]["inventory_added"] == ["烧焦铜币 x1"]
    assert response.dm_message.metadata["state_changes_applied"]["blocked"] == {}


def test_isekai_compound_rest_and_eat_food_consumes_ration(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Rest Eat", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["干粮 x2", "水囊(2/3)"])

    response = service.advance(
        adventure.id,
        MessageCreate(content="在火堆旁休息一小时，吃半份干粮，尽量恢复体力。", locale="zh-CN"),
    )

    assert response.dm_message.metadata["source"] == "action_resolution"
    assert response.dm_message.metadata["parsed_action"]["action_type"] == "compound"
    assert "干粮 x1" in response.adventure.isekai_character["inventory"]
    assert "消耗干粮 x1" in response.dm_message.metadata["survival_delta"]["inventory_changes"]


def test_isekai_otherworld_signal_uses_scene_update_location(store):
    service = IsekaiSurvivalService(store)
    old_scene = SceneState(
        location="废弃瞭望塔塔基",
        environment="塔门外雨声很密。",
        important_objects=["塔门"],
        current_objective="进入塔内。",
    )
    turn = {
        "survival": {"hunger": 10, "thirst": 10, "fatigue": 10, "sleep_need": 10},
        "visible_survival": service.visible_survival_state({"hunger": 10, "thirst": 10, "fatigue": 10, "sleep_need": 10}),
        "character": {"race": "Half-Elf"},
        "scene": old_scene,
        "world_state": {},
        "action_type": "enter_location",
        "model_payload": {"scene_update": {"location": "废弃瞭望塔底层"}},
    }

    repaired = service.repair_narration_for_turn(turn, "你踏入塔内，火光照亮圆形大厅。")

    assert "废弃瞭望塔底层" in repaired
    assert "废弃瞭望塔塔基的空气" not in repaired


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


def test_isekai_eat_drink_reports_one_total_time_change(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Resource Time Road", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我喝一口水，然后吃一点干粮。", locale="zh-CN"))

    content = response.dm_message.content
    visible_events = response.dm_message.metadata["survival_delta"]["visible_events"]
    assert response.dm_message.metadata["survival_delta"]["time_cost_minutes"] == 15
    assert visible_events == ["时间推进了约 15 分钟。"]
    assert content.count("时间推进了约") == 1
    assert "时间推进了约 5 分钟" not in content
    assert "时间推进了约 10 分钟" not in content


def test_isekai_drinking_skips_empty_waterskin_and_normalizes_charges(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Waterskin Road", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["水囊(0/3)", "水囊(2/3)", "干粮 x2"])

    response = service.advance(adventure.id, MessageCreate(content="我喝水。", locale="zh-CN"))

    inventory = response.adventure.isekai_character["inventory"]
    changes = response.dm_message.metadata["survival_delta"]["inventory_changes"]
    waterskins = [item for item in inventory if "水囊" in item]
    assert waterskins == ["水囊(1/6)"]
    assert "干粮 x2" in inventory
    assert "饮用水囊 1 份" in changes
    assert "水囊已经空了" not in changes


def test_drink_water_only_reduces_thirst_and_consumes_water(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Drink Split", mode="isekai_survival"))
    set_survival_pressure(store, adventure.id, hunger=40, thirst=50, fatigue=10, sleep_need=10)
    set_character_state(store, adventure.id, inventory=["水囊(2/3)", "干粮 x2"])

    response = service.advance(adventure.id, MessageCreate(content="我喝一口水", locale="zh-CN"))

    survival = response.adventure.survival_state
    inventory = response.adventure.isekai_character["inventory"]
    assert response.dm_message.metadata["parsed_action"]["action_type"] == "drink_water"
    assert survival["hunger"] == 40
    assert survival["thirst"] < 50
    assert "水囊(1/3)" in inventory
    assert "干粮 x2" in inventory


def test_eat_food_only_reduces_hunger_and_consumes_ration(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Eat Split", mode="isekai_survival"))
    set_survival_pressure(store, adventure.id, hunger=50, thirst=40, fatigue=10, sleep_need=10)
    set_character_state(store, adventure.id, inventory=["水囊(2/3)", "干粮 x2"])

    response = service.advance(adventure.id, MessageCreate(content="我吃一份干粮", locale="zh-CN"))

    survival = response.adventure.survival_state
    inventory = response.adventure.isekai_character["inventory"]
    assert response.dm_message.metadata["parsed_action"]["action_type"] == "eat_food"
    assert survival["hunger"] < 50
    assert survival["thirst"] == 40
    assert "水囊(2/3)" in inventory
    assert "干粮 x1" in inventory
    assert "干粮 x2" not in inventory


def test_refill_water_with_source_fills_waterskin(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Refill Water", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["水囊(0/3)", "干粮 x2"])
    scene = adventure.current_scene.model_copy(
        update={
            "location": "小屋屋檐下",
            "environment": "屋檐下有一只接满雨水的木桶。",
            "important_objects": ["雨水桶"],
            "interactables": [
                {"id": "rain_barrel_01", "type": "water_source", "name": "雨水桶", "affordances": ["装水", "观察"]}
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="用水囊在雨水桶装水", locale="zh-CN"))

    inventory = response.adventure.isekai_character["inventory"]
    assert response.dm_message.metadata["parsed_action"]["action_type"] == "refill_water"
    assert response.dm_message.metadata["parsed_action"]["target_id"] == "rain_barrel_01"
    assert "水囊(3/3)" in inventory
    assert "装满水囊" in "".join(response.dm_message.metadata["survival_delta"]["inventory_changes"])


def test_search_can_reveal_water_source_then_refill_succeeds(store):
    activate_test_model(store)
    llm_client = SequenceIsekaiLLMClient(
        [
            {
                "narration": "你搜索木箱旁的阴影，发现屋檐漏水接进一只雨水桶。",
                "scene_update": {
                    "environment": "小屋内昏暗潮湿，木箱旁有一只接雨水的木桶。",
                    "important_objects": ["木箱", "雨水桶"],
                },
                "interactables": [
                    {"id": "wooden_crate_01", "type": "object", "name": "木箱", "affordances": ["搜索", "观察"]},
                    {"id": "rain_barrel_01", "type": "water_source", "name": "雨水桶", "affordances": ["装水", "观察"]},
                ],
            }
        ]
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Search Then Refill", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["水囊(0/3)", "干粮 x2"])
    scene = adventure.current_scene.model_copy(
        update={
            "location": "小屋",
            "environment": "小屋内昏暗潮湿，角落里有一个旧木箱。",
            "important_objects": ["木箱"],
            "interactables": [{"id": "wooden_crate_01", "type": "object", "name": "木箱", "affordances": ["搜索", "观察"]}],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    searched = service.advance(adventure.id, MessageCreate(content="搜索木箱", locale="zh-CN"))
    refilled = service.advance(adventure.id, MessageCreate(content="装水", locale="zh-CN"))

    assert searched.adventure.current_scene.location == "小屋"
    assert any(entry["id"] == "rain_barrel_01" for entry in searched.adventure.current_scene.interactables)
    assert refilled.dm_message.metadata["parsed_action"]["action_type"] == "refill_water"
    assert refilled.dm_message.metadata["parsed_action"]["target_id"] == "rain_barrel_01"
    assert "水囊(3/3)" in refilled.adventure.isekai_character["inventory"]


def test_isekai_fallback_narration_is_readable_dm_text(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Fallback Narrator", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "小屋",
            "environment": "小屋内昏暗潮湿，角落里有一个旧木箱。",
            "important_objects": ["木箱"],
            "interactables": [{"id": "wooden_crate_01", "type": "object", "name": "木箱", "affordances": ["搜索", "观察"]}],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="搜索木箱", locale="zh-CN"))

    content = response.dm_message.content
    assert response.dm_message.metadata["source"] == "survival_rules"
    assert "行动结果" in content
    assert "时间消耗" in content
    assert "环境反馈" in content
    assert "生存变化" in content
    assert "可互动对象" in content
    assert "当前饥饿" not in content


def test_model_state_changes_add_items_to_isekai_inventory(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你拿起猎网和燧石碎片。",
            "state_changes": {"add_items": ["猎网", "燧石碎片"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Item Sync", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="拿起猎网和燧石碎片", locale="zh-CN"))

    inventory = response.adventure.isekai_character["inventory"]
    assert "猎网" in inventory
    assert "燧石碎片" in inventory
    assert response.dm_message.metadata["state_changes_applied"]["inventory_added"] == ["猎网", "燧石碎片"]


def test_status_check_blocks_model_inventory_state_changes(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你查看状态时发现背包里多了一颗红浆果。",
            "state_changes": {"add_items": ["红浆果"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Blocked Status Change", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我现在的状态怎么样？", locale="zh-CN"))

    assert "红浆果" not in response.adventure.isekai_character["inventory"]
    assert response.dm_message.metadata["state_changes_applied"]["blocked"]["add_items"] == ["红浆果"]


def test_status_check_blocks_model_money_entitlement_and_relationship_state_changes(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "模型试图直接给你钥匙和铜币。",
            "state_changes": {
                "money_changes": [{"copper_delta": 99, "reason": "状态查询"}],
                "entitlement_changes": [{"id": "inn_room_3_bed", "name": "二楼三号房床位"}],
                "relationship_changes": [{"npc_id": "innkeeper_01", "attitude": "信任"}],
            },
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Blocked Economy State", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我现在的状态怎么样？", locale="zh-CN"))

    blocked = response.dm_message.metadata["state_changes_applied"]["blocked"]
    assert blocked["money_changes"] == [{"copper_delta": 99, "reason": "状态查询"}]
    assert blocked["entitlement_changes"] == [{"id": "inn_room_3_bed", "name": "二楼三号房床位"}]
    assert blocked["relationship_changes"] == [{"npc_id": "innkeeper_01", "attitude": "信任"}]


def test_observe_blocks_model_add_items_even_when_target_matches(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你观察红浆果，模型却试图直接把它放入背包。",
            "state_changes": {"add_items": ["红浆果"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Blocked Observe Item", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "interactables": [
                {
                    "id": "red_berries_01",
                    "type": "item",
                    "name": "红浆果",
                    "affordances": ["观察", "采集"],
                }
            ]
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="观察红浆果", locale="zh-CN"))

    assert "红浆果" not in response.adventure.isekai_character["inventory"]
    assert response.dm_message.metadata["state_changes_applied"]["blocked"]["add_items"] == ["红浆果"]


def test_gather_allows_compatible_target_item_addition(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你避开刺，摘下几颗红浆果。",
            "state_changes": {"add_items": ["红浆果"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Gather Allows Item", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "interactables": [
                {
                    "id": "red_berries_01",
                    "type": "item",
                    "name": "红浆果",
                    "affordances": ["观察", "采集"],
                }
            ]
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="摘点红浆果", locale="zh-CN"))

    assert "红浆果" in response.adventure.isekai_character["inventory"]
    assert response.dm_message.metadata["state_changes_applied"]["inventory_added"] == ["红浆果"]


def test_model_state_changes_merge_waterskin_charges_in_inventory(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你找到一只还剩两份清水的水囊。",
            "state_changes": {"add_items": ["水囊(2/3)"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Waterskin Sync", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["水囊(0/3)", "干粮 x2"])

    response = service.advance(adventure.id, MessageCreate(content="拿起水囊", locale="zh-CN"))

    inventory = response.adventure.isekai_character["inventory"]
    assert [item for item in inventory if "水囊" in item] == ["水囊(2/6)"]
    assert "干粮 x2" in inventory


def test_isekai_suggested_actions_include_classifier_details(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你可以重新躺下，安心入睡，等待真正的天亮。",
            "suggested_actions": ["重新躺下，安心入睡，等待真正的天亮"],
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Suggested Sleep", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我观察睡袋。", locale="zh-CN"))

    detail = response.dm_message.metadata["suggested_action_details"][0]
    assert detail["text"] == "重新躺下，安心入睡，等待真正的天亮"
    assert detail["action_type"] == "sleep"
    assert detail["advances_time"] is True
    assert detail["time_cost_minutes"] > 0


def test_model_state_changes_remove_items_from_isekai_inventory(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你扔掉红浆果。",
            "state_changes": {"remove_items": ["红浆果"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Drop Sync", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["红浆果", "干粮 x2"])

    response = service.advance(adventure.id, MessageCreate(content="扔掉红浆果", locale="zh-CN"))

    assert "红浆果" not in response.adventure.isekai_character["inventory"]
    assert "红浆果" in response.dm_message.metadata["state_changes_applied"]["inventory_removed"]


def test_isekai_advance_records_scene_aware_parsed_action_metadata(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Parsed Action", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "溪边荆棘丛",
            "environment": "荆棘藤上结着几簇颜色不同的浆果。",
            "important_objects": ["红浆果"],
            "interactables": [
                {
                    "id": "red_berries_01",
                    "type": "item",
                    "name": "红浆果",
                    "affordances": ["观察", "采集"],
                    "risk": "误食可能中毒",
                }
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="摘点红浆果", locale="zh-CN"))

    parsed = response.dm_message.metadata["parsed_action"]
    assert parsed["action_type"] == "gather"
    assert parsed["target_id"] == "red_berries_01"
    assert parsed["target_name"] == "红浆果"
    assert parsed["confidence"] == "high"
    assert "affordance_match:gather" in parsed["confidence_reasons"]


def test_ambiguous_target_requires_clarification_and_blocks_scene_and_state_changes(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你采下了一把浆果。",
            "scene_update": {"environment": "你已经采过这里的浆果，荆棘藤变得稀疏。"},
            "state_changes": {"add_items": ["红浆果"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Ambiguous Berries", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "溪边荆棘丛",
            "environment": "荆棘藤上同时有红浆果和紫浆果。",
            "important_objects": ["红浆果", "紫浆果"],
            "interactables": [
                {"id": "red_berries_01", "type": "item", "name": "红浆果", "affordances": ["观察", "采集"]},
                {"id": "purple_berries_01", "type": "item", "name": "紫浆果", "affordances": ["观察", "采集"]},
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)
    before_survival = adventure.survival_state

    response = service.advance(adventure.id, MessageCreate(content="摘点浆果", locale="zh-CN"))

    parsed = response.dm_message.metadata["parsed_action"]
    assert parsed["action_type"] == "clarification"
    assert parsed["requires_clarification"] is True
    assert [candidate["id"] for candidate in parsed["candidates"]] == ["red_berries_01", "purple_berries_01"]
    assert response.dm_message.metadata["time"]["advances_time"] is False
    assert response.adventure.survival_state["state"]["last_time_delta_minutes"] == 0
    assert response.adventure.survival_state["day"] == before_survival["day"]
    assert response.adventure.current_scene.environment == "荆棘藤上同时有红浆果和紫浆果。"
    assert "红浆果" not in response.adventure.isekai_character["inventory"]
    assert response.dm_message.metadata["source"] == "action_parser"
    assert "你指的是红浆果、紫浆果中的哪一个" in response.dm_message.content


def test_refill_water_without_water_source_blocks_model_state_and_scene_changes(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你发现一个水桶并把水囊装满。",
            "scene_update": {"environment": "干草旁多出一个清水桶。", "important_objects": ["清水桶"]},
            "state_changes": {"add_items": ["水囊(3/3)"]},
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="No Water Refill", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["水囊(0/3)", "干粮 x2"])
    scene = adventure.current_scene.model_copy(
        update={
            "location": "干燥小屋",
            "environment": "屋内只有木箱和干草，没有任何水源。",
            "important_objects": ["木箱", "干草"],
            "interactables": [{"id": "crate_01", "type": "object", "name": "木箱", "affordances": ["搜索"]}],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="装水", locale="zh-CN"))

    parsed = response.dm_message.metadata["parsed_action"]
    assert parsed["action_type"] == "condition_failed"
    assert parsed["arguments"]["failed_precondition"] == "missing_water_source"
    assert response.dm_message.metadata["time"]["advances_time"] is False
    assert response.adventure.current_scene.environment == "屋内只有木箱和干草，没有任何水源。"
    assert response.adventure.isekai_character["inventory"] == ["水囊(0/3)", "干粮 x2"]
    assert "没有可用水源" in response.dm_message.content


def test_observe_does_not_apply_model_location_change(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你观察小屋，模型试图把你推进屋内。",
            "scene_update": {
                "location": "小屋内",
                "environment": "屋内黑暗潮湿。",
                "important_objects": ["木箱"],
            },
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Observe No Move", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "小屋外",
            "environment": "你站在低矮小屋门口。",
            "important_objects": ["小屋"],
            "interactables": [{"id": "hut_01", "type": "place", "name": "小屋", "affordances": ["进入", "观察"]}],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="观察小屋", locale="zh-CN"))

    assert response.dm_message.metadata["parsed_action"]["action_type"] == "observe"
    assert response.adventure.current_scene.location == "小屋外"
    assert response.dm_message.metadata["scene_update_blocked_reason"] == "location_change_requires_movement_action"


def test_enter_location_changes_location_and_projects_new_interactables(store):
    activate_test_model(store)
    llm_client = StructuredStateChangeIsekaiLLMClient(
        {
            "narration": "你进入小屋，先站在门边适应昏暗。",
            "scene_update": {
                "location": "小屋",
                "environment": "小屋内昏暗潮湿，角落里有木箱和接雨水的木桶。",
                "important_objects": ["木箱", "雨水桶"],
                "current_objective": "确认屋内是否安全，并寻找可用补给。",
            },
        }
    )
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Enter Projects", mode="isekai_survival"))
    set_content_packs(service, adventure.id, ["baseline_exploration_discoveries"])
    scene = adventure.current_scene.model_copy(
        update={
            "location": "小屋外",
            "environment": "你站在低矮小屋门口。",
            "important_objects": ["小屋"],
            "interactables": [{"id": "hut_01", "type": "place", "name": "小屋", "affordances": ["进入", "观察"]}],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="进入小屋后不急着翻东西", locale="zh-CN"))

    assert response.dm_message.metadata["parsed_action"]["action_type"] == "enter_location"
    assert response.adventure.current_scene.location == "小屋"
    interactable_ids = [entry["id"] for entry in response.adventure.current_scene.interactables]
    assert "hut_01" not in interactable_ids
    assert {"wooden_crate_01", "rain_barrel_01"} <= set(interactable_ids)


def test_isekai_navigation_blocks_unconnected_location_jump(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="No Jump", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "铁炉镇外 / 旧矿道入口",
            "location_path": {"node_id": "mine_entrance", "display_name": "铁炉镇外 / 旧矿道入口"},
            "environment": "旧矿道入口只有通向外层矿道的铁栅栏。",
            "important_objects": ["铁栅栏"],
            "interactables": [
                {
                    "id": "outer_tunnel_gate",
                    "type": "entrance",
                    "name": "铁栅栏",
                    "affordances": ["进入", "观察"],
                    "target_node_id": "mine_outer_tunnel",
                }
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["scene_graph"] = {
        "nodes": [
            {"node_id": "mine_entrance", "name": "旧矿道入口"},
            {"node_id": "mine_outer_tunnel", "name": "外层矿道"},
            {"node_id": "street_inn", "name": "街边旅店"},
        ],
        "edges": [
            {
                "id": "edge_mine_to_outer",
                "from_node_id": "mine_entrance",
                "to_node_id": "mine_outer_tunnel",
                "access": "open",
            }
        ],
    }
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(adventure.id, MessageCreate(content="进入街边旅店", locale="zh-CN"))

    assert response.adventure.current_scene.location_path["node_id"] == "mine_entrance"
    assert response.dm_message.metadata["time"]["advances_time"] is False
    assert response.dm_message.metadata["resolved_steps"][0]["navigation"]["status"] == "known_target_unknown_route"
    assert "没有合法连接路径" in response.dm_message.content or "寻找道路" in response.dm_message.content


def test_isekai_navigation_returns_to_known_settlement_from_history(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Return Town", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "铁炉镇外 / 旧矿道入口",
            "location_path": {"node_id": "mine_entrance", "display_name": "铁炉镇外 / 旧矿道入口"},
            "environment": "旧矿道入口还能看见来时踩出的泥印。",
            "important_objects": ["来路泥印"],
            "interactables": [
                {
                    "id": "old_track",
                    "type": "place",
                    "name": "来路泥印",
                    "affordances": ["观察", "离开"],
                }
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["known_locations"] = [{"node_id": "grey_oak_gate", "name": "灰橡镇", "type": "settlement"}]
    world_state["scene_graph"] = {
        "nodes": [
            {
                "node_id": "grey_oak_gate",
                "name": "灰橡镇",
                "location_path": {"node_id": "grey_oak_gate", "region": "灰橡镇", "site": "镇门", "display_name": "灰橡镇 / 镇门"},
                "environment": "镇门外有泥泞车辙和警惕的守卫。",
                "current_objective": "决定是否进镇或在门外打听消息。",
                "interactables": [{"id": "town_gate_guard", "type": "npc", "name": "守卫", "affordances": ["交谈", "观察"]}],
                "suggested_actions": ["和守卫说明来意"],
            },
            {"node_id": "forest_path", "name": "林间小路"},
            {"node_id": "mine_entrance", "name": "旧矿道入口"},
        ],
        "edges": [],
    }
    world_state["location_history"] = [
        {"from_node_id": "grey_oak_gate", "to_node_id": "forest_path", "edge_id": "edge_town_to_path"},
        {"from_node_id": "forest_path", "to_node_id": "mine_entrance", "edge_id": "edge_path_to_mine"},
    ]
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(adventure.id, MessageCreate(content="回到城镇", locale="zh-CN"))

    assert response.adventure.current_scene.location_path["node_id"] == "grey_oak_gate"
    assert response.adventure.current_scene.location == "灰橡镇 / 镇门"
    assert response.dm_message.metadata["resolved_steps"][0]["navigation"]["status"] == "resolved"


def test_isekai_navigation_leave_current_scene_uses_back_edge(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Leave Scene", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "铁炉镇外 / 旧矿道 / 外层矿道",
            "location_path": {"node_id": "mine_outer_tunnel", "display_name": "铁炉镇外 / 旧矿道 / 外层矿道"},
            "environment": "外层矿道潮湿阴暗，入口的光在身后。",
            "important_objects": ["入口光线"],
            "interactables": [{"id": "exit_light", "type": "place", "name": "入口光线", "affordances": ["离开", "观察"]}],
        }
    )
    service.adventures.update_scene(adventure.id, scene)
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["scene_graph"] = {
        "nodes": [
            {
                "node_id": "mine_entrance",
                "name": "旧矿道入口",
                "location_path": {"node_id": "mine_entrance", "region": "铁炉镇外", "site": "旧矿道入口", "display_name": "铁炉镇外 / 旧矿道入口"},
                "environment": "旧矿道入口有冷雾和碎石坡。",
                "interactables": [{"id": "rubble_slope", "type": "place", "name": "碎石坡", "affordances": ["观察", "搜索"]}],
                "suggested_actions": ["搜索碎石坡"],
            },
            {"node_id": "mine_outer_tunnel", "name": "外层矿道"},
        ],
        "edges": [
            {
                "id": "edge_outer_to_entrance",
                "from_node_id": "mine_outer_tunnel",
                "to_node_id": "mine_entrance",
                "kind": "back",
                "access": "open",
            }
        ],
    }
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(adventure.id, MessageCreate(content="离开这里", locale="zh-CN"))

    assert response.adventure.current_scene.location_path["node_id"] == "mine_entrance"
    assert response.dm_message.metadata["resolved_steps"][0]["navigation"]["navigation_intent"] == "leave_current_scene"


def test_compound_turn_executes_drink_approach_enter_without_searching(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Compound Carriage", mode="isekai_survival"))
    set_character_state(store, adventure.id, inventory=["水囊(3/3)", "干粮 x2"])
    scene = adventure.current_scene.model_copy(
        update={
            "location": "泥泞旧路",
            "environment": "雨后的旧路旁有一辆侧翻马车，车厢有一道勉强能钻入的破口。",
            "important_objects": ["侧翻马车", "车厢", "狭窄破口"],
            "interactables": [
                {
                    "id": "wagon_01",
                    "type": "place",
                    "name": "侧翻马车",
                    "state": "半陷在泥里",
                    "affordances": ["靠近", "观察"],
                    "risk": "靠得太快可能踩入泥坑或惊动附近东西",
                },
                {
                    "id": "carriage_01",
                    "type": "place",
                    "name": "车厢",
                    "state": "破口勉强可进入",
                    "affordances": ["进入", "观察"],
                    "risk": "内部可能有陷阱或寄生虫",
                    "destination_environment": "侧翻车厢内部潮湿狭窄，座椅下压着货袋，破损木箱旁有黑暗角落。",
                    "destination_objects": ["货袋", "破损木箱", "黑暗角落", "狭窄破口"],
                },
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(
        adventure.id,
        MessageCreate(content="喝水，然后小心靠近马车，进入车厢后不急着翻东西。", locale="zh-CN"),
    )

    metadata = response.dm_message.metadata
    assert metadata["source"] == "action_resolution"
    assert metadata["parsed_action"]["action_type"] == "compound"
    assert [step["action_type"] for step in metadata["resolved_steps"]] == ["drink_water", "approach", "enter_location"]
    assert metadata["resolved_steps"][1]["risk"]["deltas"]["danger"] == -1
    assert response.adventure.current_scene.location == "车厢"
    assert response.adventure.survival_state["state"]["last_time_delta_minutes"] == 30
    assert "水囊(2/3)" in response.adventure.isekai_character["inventory"]
    assert "潮湿干粮" not in response.adventure.isekai_character["inventory"]
    interactable_names = [entry["name"] for entry in response.adventure.current_scene.interactables]
    assert {"货袋", "破损木箱", "黑暗角落"} <= set(interactable_names)
    assert "行动结果" in response.dm_message.content
    assert "时间变化" in response.dm_message.content
    assert "资源变化" in response.dm_message.content
    assert "风险变化" in response.dm_message.content
    assert "新的可互动内容" in response.dm_message.content


def test_blocked_carriage_entry_stops_plan_and_offers_physical_alternatives(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Blocked Carriage", mode="isekai_survival"))
    scene = adventure.current_scene.model_copy(
        update={
            "location": "泥泞旧路",
            "environment": "侧翻马车陷在泥里，车门被泥土压住，破口太窄。",
            "important_objects": ["侧翻马车", "车厢", "车厢门", "狭窄破口"],
            "interactables": [
                {
                    "id": "carriage_01",
                    "type": "place",
                    "name": "车厢",
                    "state": "车门被泥土压住，破口太窄",
                    "affordances": ["观察", "听动静"],
                    "risk": "强行进入可能卡住或制造声响",
                }
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="尝试进入车厢但不翻东西", locale="zh-CN"))

    metadata = response.dm_message.metadata
    assert metadata["source"] == "action_resolution"
    assert metadata["resolved_steps"][0]["action_type"] == "condition_failed"
    assert metadata["resolved_steps"][0]["blocked"] is True
    assert metadata["resolved_steps"][0]["alternatives"] == [
        "从破损处探身查看",
        "撬开木板或车门",
        "绕到另一侧找入口",
        "先听听里面有没有动静",
    ]
    assert response.adventure.current_scene.location == "泥泞旧路"
    assert response.adventure.survival_state["state"]["last_time_delta_minutes"] == 0
    assert "从破损处探身查看" in response.dm_message.content
    assert "强行进入" not in response.dm_message.content


def test_searching_cargo_bag_adds_real_item_and_risk_feedback(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Cargo Search", mode="isekai_survival"))
    set_content_packs(service, adventure.id, ["baseline_exploration_discoveries"])
    set_character_state(store, adventure.id, inventory=["水囊(2/3)", "干粮 x1"])
    scene = adventure.current_scene.model_copy(
        update={
            "location": "车厢",
            "environment": "侧翻车厢内部潮湿狭窄，座椅下压着货袋。",
            "important_objects": ["货袋", "破损木箱", "黑暗角落"],
            "interactables": [
                {
                    "id": "cargo_bag_01",
                    "type": "item",
                    "name": "货袋",
                    "affordances": ["搜索", "观察"],
                    "risk": "翻动可能制造声响",
                }
            ],
        }
    )
    service.adventures.update_scene(adventure.id, scene)

    response = service.advance(adventure.id, MessageCreate(content="搜索货袋", locale="zh-CN"))

    metadata = response.dm_message.metadata
    assert metadata["source"] == "action_resolution"
    assert metadata["parsed_action"]["action_type"] == "search"
    assert "潮湿干粮 x1" in response.adventure.isekai_character["inventory"]
    assert "获得潮湿干粮 x1" in metadata["survival_delta"]["inventory_changes"]
    assert metadata["risk_change"]["noise"] > 0
    assert "风险变化" in response.dm_message.content


def test_overnight_travel_uses_resolution_risk_feedback(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Night Travel", mode="isekai_survival"))
    set_survival_pressure(store, adventure.id, hunger=20, thirst=20, fatigue=20, sleep_need=20)
    with store.connect() as conn:
        conn.execute(
            """
            UPDATE isekai_survival_states
            SET time_of_day = '夜晚', state_json = :state_json
            WHERE adventure_id = :adventure_id
            """,
            {"adventure_id": adventure.id, "state_json": encode_json({"elapsed_minutes": 21 * 60})},
        )

    response = service.advance(adventure.id, MessageCreate(content="连夜赶路", locale="zh-CN"))

    metadata = response.dm_message.metadata
    assert metadata["source"] == "action_resolution"
    assert metadata["parsed_action"]["action_type"] == "travel"
    assert metadata["risk_change"]["danger"] >= 2
    assert "夜间赶路" in response.dm_message.content


def test_graystone_inn_facility_loop_tracks_location_money_entitlements_and_time(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Graystone Inn Loop", mode="isekai_survival"))
    set_character_state(store, adventure.id, gold=0, inventory=["水囊(2/3)", "干粮 x1"])
    outside = adventure.current_scene.model_copy(
        update={
            "location": "灰石镇外泥路",
            "location_path": {
                "region": "灰石镇外",
                "site": "泥路",
                "sublocation": "",
                "node_id": "graystone_outskirts",
                "parent_id": "graystone_region",
                "display_name": "灰石镇外 / 泥路",
            },
            "environment": "雨后的泥路通向灰石镇，镇门内能看见旧炉旅店冒烟的招牌。",
            "important_objects": ["灰石镇", "旧炉旅店招牌"],
            "interactables": [{"id": "graystone_town", "type": "place", "name": "灰石镇", "affordances": ["进入", "观察"]}],
            "suggested_actions": ["进入灰石镇"],
        }
    )
    service.adventures.update_scene(adventure.id, outside)
    world_state = dict(adventure.world_state)
    world_state["isekai_content"] = {"active_packs": ["old_furnace_inn_p1"], "activation": "explicit"}
    world_state["isekai_economy"] = {"currency": {"copper_total": 5}, "entitlements": [], "transaction_log": []}
    world_state = service.quests.initial_world_state(world_state)
    service.adventures.update_world_state(adventure.id, world_state)

    town = service.advance(adventure.id, MessageCreate(content="进入灰石镇", locale="zh-CN"))
    inn = service.advance(adventure.id, MessageCreate(content="进入旧炉旅店前厅", locale="zh-CN"))
    negotiated = service.advance(adventure.id, MessageCreate(content="和店主讨价还价，打听住宿价格", locale="zh-CN"))
    repaired = service.advance(adventure.id, MessageCreate(content="去后厨修锅把", locale="zh-CN"))
    claimed = service.advance(adventure.id, MessageCreate(content="回前厅领取住宿权", locale="zh-CN"))
    paid = service.advance(adventure.id, MessageCreate(content="支付铜币买床位", locale="zh-CN"))
    room = service.advance(adventure.id, MessageCreate(content="进入二楼三号房查看钥匙和床位", locale="zh-CN"))
    meal = service.advance(adventure.id, MessageCreate(content="吃已购买的热炖菜", locale="zh-CN"))
    listened = service.advance(adventure.id, MessageCreate(content="夜里听见暗夜狼动静，我从小窗观察", locale="zh-CN"))
    track = service.advance(adventure.id, MessageCreate(content="第二天准备追踪", locale="zh-CN"))

    assert town.adventure.current_scene.location_path["node_id"] == "graystone_town"
    assert inn.adventure.current_scene.location_path["node_id"] == "inn_front_hall"
    assert {entry["id"] for entry in inn.adventure.current_scene.interactables} >= {"innkeeper_01", "kitchen_door"}

    assert negotiated.dm_message.metadata["parsed_action"]["action_type"] == "negotiate"
    assert negotiated.dm_message.metadata["survival_delta"]["time_cost_minutes"] == 12
    assert negotiated.adventure.world_state["isekai_economy"]["quotes"]["inn_bed"] == 3
    assert negotiated.adventure.world_state["isekai_economy"]["entitlements"] == []

    assert repaired.adventure.current_scene.location_path["node_id"] == "inn_kitchen"
    assert repaired.dm_message.metadata["outcome_level"] == "key_success"
    assert "修好松动锅把" in repaired.dm_message.content

    economy = claimed.adventure.world_state["isekai_economy"]
    assert claimed.adventure.current_scene.location_path["node_id"] == "inn_front_hall"
    assert economy["entitlements"][-1]["id"] == "inn_room_3_bed"
    assert economy["entitlements"][-1]["identity"] == "旧炉旅店临时住客"
    assert economy["transaction_log"][-1]["lost"] == "0 铜"
    assert economy["relationship_changes"][-1]["attitude"] == "愿意交易"
    assert "二楼三号房钥匙" in claimed.adventure.isekai_character["inventory"]

    assert paid.adventure.world_state["isekai_economy"]["currency"]["copper_total"] == 2
    assert paid.adventure.world_state["isekai_economy"]["transaction_log"][-1]["lost"] == "3 铜"
    assert room.adventure.current_scene.location_path["node_id"] == "inn_room_3"
    assert {entry["id"] for entry in room.adventure.current_scene.interactables} >= {"inn_room_3_bed", "small_window"}

    assert meal.dm_message.metadata["parsed_action"]["action_type"] == "eat_meal"
    assert meal.dm_message.metadata["survival_delta"]["time_cost_minutes"] == 20
    assert "热炖菜" in meal.dm_message.content

    assert listened.dm_message.metadata["outcome_level"] in {"normal_success", "partial_success"}
    assert any("暗夜狼" in clue for clue in listened.dm_message.metadata["clues"])
    assert track.dm_message.metadata["parsed_action"]["action_type"] in {"observe", "travel", "table_talk"}
    assert track.adventure.current_scene.location_path["display_name"]


def test_purchase_bed_fails_with_shortfall_and_alternatives(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="No Copper Bed", mode="isekai_survival"))
    from backend.src.services.isekai_locations import IsekaiLocationService

    world_state = set_content_packs(service, adventure.id, ["old_furnace_inn_p1"])
    locations = IsekaiLocationService(world_state=world_state)
    service.adventures.update_scene(adventure.id, locations.scene_for("inn_front_hall"))
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["isekai_economy"] = {"currency": {"copper_total": 1}, "entitlements": [], "transaction_log": []}
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(adventure.id, MessageCreate(content="支付铜币买床位", locale="zh-CN"))

    assert response.dm_message.metadata["source"] == "action_resolution"
    assert response.dm_message.metadata["outcome_level"] == "failure"
    assert response.dm_message.metadata["shortfall_copper"] == 2
    assert response.adventure.world_state["isekai_economy"]["currency"]["copper_total"] == 1
    assert "还差 2 铜" in response.dm_message.content
    assert "帮后厨修锅把换取床位" in response.dm_message.content


def test_model_npc_updates_enter_scene_state(store):
    activate_test_model(store)
    payload = {
        "narration": "伐木工放低斧头，但仍盯着你的短弓。",
        "interactables": [
            {
                "id": "lumberjack_01",
                "type": "npc",
                "name": "戒备的伐木工",
                "affordances": ["交涉"],
                "risk": "可能引来猎犬",
            }
        ],
        "suggested_actions": ["和伐木工说明来意"],
        "state_changes": {
            "npc_updates": [
                {
                    "id": "lumberjack_01",
                    "name": "伐木工",
                    "attitude": "wary",
                    "trust_delta": 10,
                    "known_facts": ["玩家主动说明来意"],
                }
            ]
        },
    }
    service = IsekaiSurvivalService(store, llm_client=StructuredStateChangeIsekaiLLMClient(payload))
    adventure = service.create_adventure(AdventureCreate(title="NPC Sync", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="和伐木工说明来意", locale="zh-CN"))

    scene = response.adventure.current_scene
    assert scene.interactables[0]["id"] == "lumberjack_01"
    assert scene.suggested_actions == ["和伐木工说明来意"]
    assert scene.npc_states[0]["name"] == "伐木工"
    assert scene.npc_states[0]["trust"] == 30
    assert "玩家主动说明来意" in scene.npc_states[0]["known_facts"]
    assert "伐木工" in scene.npcs


def test_isekai_location_change_clears_present_npcs_but_keeps_npc_memory(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(
        store,
        llm_client=StructuredStateChangeIsekaiLLMClient(
            {
                "narration": "你离开伐木营地，来到溪边荆棘丛后的小岩洞。",
                "scene_update": {
                    "location": "溪边荆棘丛后的小岩洞",
                    "environment": "岩洞里没有人声，只有溪水和潮湿石壁。",
                    "important_objects": ["湿冷石壁"],
                    "current_objective": "确认岩洞是否安全。",
                },
                "interactables": [{"id": "cave_wall", "type": "place", "name": "湿冷石壁"}],
                "suggested_actions": ["检查岩洞深处"],
            }
        ),
    )
    adventure = service.create_adventure(AdventureCreate(title="NPC Memory", mode="isekai_survival"))
    camp_scene = adventure.current_scene.model_copy(
        update={
            "location": "伐木营地",
            "environment": "营地里有伐木工头领和磨坊主。",
            "npcs": ["伐木工头领", "磨坊主"],
            "npc_states": [
                {"id": "foreman_01", "name": "伐木工头领", "trust": 25, "known_facts": ["见过玩家"]},
                {"id": "miller_01", "name": "磨坊主", "trust": 40, "known_facts": ["向玩家报价"]},
            ],
            "interactables": [{"id": "foreman_01", "type": "npc", "name": "伐木工头领"}],
            "suggested_actions": ["询问伐木工头领"],
        }
    )
    service.adventures.update_scene(adventure.id, camp_scene)

    response = service.advance(
        adventure.id,
        MessageCreate(content="我离开营地，去溪边荆棘丛后的小岩洞。", locale="zh-CN"),
    )

    scene = response.adventure.current_scene
    assert scene.location == "溪边荆棘丛后的小岩洞"
    assert scene.npcs == []
    assert [npc["name"] for npc in scene.npc_states] == ["伐木工头领", "磨坊主"]
    assert scene.interactables == [{"id": "cave_wall", "type": "place", "name": "湿冷石壁"}]
    assert scene.suggested_actions == ["检查岩洞深处"]


def test_isekai_world_state_initializes_pressure_clocks(store):
    service = IsekaiSurvivalService(store)

    adventure = service.create_adventure(AdventureCreate(title="Clock Start", mode="isekai_survival"))

    clocks = adventure.world_state["pressure_clocks"]
    assert {clock["id"] for clock in clocks} >= {
        "sunset",
        "outsider_suspicion",
        "curfew_patrol",
        "beast_activity",
        "weather_thirst",
    }


def test_isekai_action_advances_pressure_clocks(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Advance", mode="isekai_survival"))
    before = {clock["id"]: clock["value"] for clock in adventure.world_state["pressure_clocks"]}

    response = service.advance(adventure.id, MessageCreate(content="我摘点红浆果。", locale="zh-CN"))

    after = {clock["id"]: clock["value"] for clock in response.adventure.world_state["pressure_clocks"]}
    assert after["sunset"] > before["sunset"]
    assert response.dm_message.metadata["pressure_clocks"]


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
    assert response.dm_message.content.startswith("模型异世界回复：雾中的猎径传来铃声。")
    assert any(signal in response.dm_message.content for signal in ["异界", "异族", "外来者", "禁忌", "税", "预兆", "法则"])
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


def test_isekai_prompt_requires_otherworld_survival_signals(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Signal Prompt Road", mode="isekai_survival"))

    service.advance(adventure.id, MessageCreate(content="我和摊主说话。", locale="zh-CN"))

    system_prompt = llm_client.chat_calls[-1]["messages"][0]["content"]
    assert "异界来客" in system_prompt
    assert "文化隔阂" in system_prompt
    assert "资源稀缺" in system_prompt
    assert "每轮至少体现一个异世界信号" in system_prompt
    assert "普通小镇日常" in system_prompt


def test_isekai_prompt_requires_structured_playability_fields(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Structured Prompt Road", mode="isekai_survival"))

    service.advance(adventure.id, MessageCreate(content="我拿起猎网。", locale="zh-CN"))

    system_prompt = llm_client.chat_calls[-1]["messages"][0]["content"]
    assert "interactables" in system_prompt
    assert "suggested_actions" in system_prompt
    assert "state_changes" in system_prompt
    assert "add_items" in system_prompt
    assert "npc_updates" in system_prompt


def test_isekai_model_payload_uses_player_visible_survival_terms(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Visible Survival Road", mode="isekai_survival"))
    set_survival_pressure(store, adventure.id, hunger=26, thirst=53, fatigue=21, sleep_need=4)

    service.advance(adventure.id, MessageCreate(content="我现在的状态怎么样？", locale="zh-CN"))

    payload = json.loads(llm_client.chat_calls[-1]["messages"][-1]["content"])
    visible = payload["system_state"]["visible_survival"]
    assert visible["satiety"] == 74
    assert visible["hydration"] == 47
    assert visible["energy"] == 79
    assert visible["sleep_sufficiency"] == 96
    assert "饱腹度较高" in visible["status_summary"]
    assert "水分偏低" in visible["status_summary"]


def test_isekai_pressure_goals_are_public_and_sent_to_model(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Pressure Goal Road", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我观察镇上的规矩。", locale="zh-CN"))

    public_goals = response.adventure.world_state["isekai_pressure_goals"]
    public_text = json.dumps(public_goals, ensure_ascii=False)
    assert "日落前取得落脚身份" in public_text
    assert "外来者身份被怀疑" in public_text
    assert "异族食宿价格翻倍" in public_text
    assert "夜晚宵禁巡逻" in public_text

    payload = json.loads(llm_client.chat_calls[-1]["messages"][-1]["content"])
    payload_text = json.dumps(payload["system_state"]["pressure_goals"], ensure_ascii=False)
    assert "日落前取得落脚身份" in payload_text
    assert "异族食宿价格翻倍" in payload_text


def test_isekai_narration_guard_adds_otherworld_signal_and_removes_hunger_contradiction(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=HungryOrdinaryTradeLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="Guard Road", mode="isekai_survival"))
    set_survival_pressure(store, adventure.id, hunger=8, thirst=25, fatigue=18, sleep_need=10)
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="白石镇炉饼摊",
            environment="白石镇烤饼铺子里，一个胖女人说这只是小本生意。",
            important_objects=["烤饼铺子", "热销菜单"],
            npcs=["炉饼摊主"],
            current_objective="买点吃的。",
        ),
    )

    response = service.advance(adventure.id, MessageCreate(content="你是什么种族的？", locale="zh-CN"))

    assert "肚子饿" not in response.dm_message.content
    assert "普通小贩" not in response.dm_message.content
    assert any(signal in response.dm_message.content for signal in ["异族", "异界", "外来者", "禁忌", "税", "预兆", "法则"])
    assert response.dm_message.metadata["time"]["advances_time"] is True
    assert response.dm_message.metadata["time"]["survival_intent"] == "social"


def test_isekai_wilderness_signal_avoids_town_template_even_with_stale_npcs(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Cave Signal Road", mode="isekai_survival"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="溪边荆棘丛后的小岩洞",
            environment="岩洞里没有人声，只有溪水和潮湿石壁。",
            important_objects=["湿冷石壁"],
            npcs=["伐木工头领"],
            current_objective="确认岩洞是否安全。",
        ),
    )

    response = service.advance(adventure.id, MessageCreate(content="我观察岩洞。", locale="zh-CN"))

    assert "镇民" not in response.dm_message.content
    assert "异族税" not in response.dm_message.content
    assert "宵禁" not in response.dm_message.content
    assert any(signal in response.dm_message.content for signal in ["异界法则", "符文", "魔物", "陌生星象", "身体"])


def test_isekai_dm_metadata_records_scene_update_applied(store):
    activate_test_model(store)
    llm_client = SceneUpdateIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Scene Debug Road", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="去白石镇", locale="zh-CN"))

    assert response.dm_message.metadata["scene_update_applied"] is True
    assert response.dm_message.metadata["action_type"] == "travel"
    assert response.dm_message.metadata["debug"]["raw_survival"]["hunger"] == response.adventure.survival_state["hunger"]
    assert response.dm_message.metadata["debug"]["visible_survival"]["satiety"] == 100 - response.adventure.survival_state["hunger"]


def test_isekai_repairs_legacy_scene_before_model_context(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Legacy Scene Road", mode="isekai_survival"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="白石镇烤饼铺子",
            environment="胖女人在烤饼铺子里说这只是小本生意。",
            important_objects=["热销菜单", "烤饼铺子"],
            npcs=["胖女人"],
            current_objective="继续普通买卖。",
        ),
    )

    service.advance(adventure.id, MessageCreate(content="我观察这里。", locale="zh-CN"))

    payload = json.loads(llm_client.chat_calls[-1]["messages"][-1]["content"])
    scene = payload["system_state"]["scene"]
    scene_text = json.dumps(scene, ensure_ascii=False)
    assert "烤饼铺子" not in scene_text
    assert "胖女人" not in scene_text
    assert "小本生意" not in scene_text
    assert any(signal in scene_text for signal in ["异族税", "外来者", "灾厄征兆", "宵禁"])


def test_isekai_legacy_scene_is_repaired_for_adventure_output(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Legacy Output Road", mode="isekai_survival"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="白石镇街尾烤饼铺",
            environment="街尾一间简陋的烤饼铺，一个胖女摊主说这只是小本生意。",
            important_objects=["烤饼炉", "胖女摊主"],
            npcs=[],
            current_objective="购买烤饼。",
            world_changes=["位置推进到白石镇街尾烤饼铺。"],
        ),
    )

    repaired = service.adventures.get(adventure.id)
    scene_text = json.dumps(repaired.current_scene.model_dump(), ensure_ascii=False)

    assert "烤饼" not in scene_text
    assert "胖女摊主" not in scene_text
    assert "小本生意" not in scene_text
    assert any(signal in scene_text for signal in ["异族税", "外来者", "灾厄征兆", "宵禁"])


def test_isekai_recent_survival_rules_context_is_normalized_and_downweighted(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Legacy Message Road", mode="isekai_survival"))
    service.adventures.append_message(
        adventure.id,
        "dm",
        "你在烤饼铺子里和胖女人聊小本生意。",
        {"mode": "isekai_survival", "source": "survival_rules"},
    )

    service.advance(adventure.id, MessageCreate(content="我继续和摊主说话。", locale="zh-CN"))

    payload = json.loads(llm_client.chat_calls[-1]["messages"][-1]["content"])
    recent = payload["recent_messages"]
    legacy = [message for message in recent if message["metadata"].get("source") == "survival_rules"]
    assert legacy
    legacy_text = json.dumps(legacy, ensure_ascii=False)
    assert "烤饼铺子" not in legacy_text
    assert "胖女人" not in legacy_text
    assert "小本生意" not in legacy_text
    assert legacy[-1]["metadata"]["context_weight"] == "low"
    assert legacy[-1]["metadata"]["context_note"] == "legacy_survival_rules_downweighted"


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


def test_non_action_scene_update_cannot_change_time_of_day_content(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(
        store,
        llm_client=StructuredStateChangeIsekaiLLMClient(
            {
                "narration": "你没有动作，但洞外已经天亮。",
                "scene_update": {
                    "environment": "清晨的阳光照进岩洞，夜晚已经结束。",
                    "current_objective": "在天亮后离开岩洞。",
                    "important_objects": ["晨光", "清晨露水"],
                },
                "interactables": [{"id": "dawn_exit", "type": "place", "name": "天亮后的洞口"}],
                "suggested_actions": ["迎着清晨阳光离开岩洞"],
            }
        ),
    )
    adventure = service.create_adventure(AdventureCreate(title="No Dawn Drift", mode="isekai_survival"))
    locked_scene = adventure.current_scene.model_copy(
        update={
            "location": "溪边荆棘丛后的小岩洞",
            "environment": "夜晚的小岩洞潮湿昏暗，洞口被荆棘挡住。",
            "important_objects": ["湿冷石壁"],
            "current_objective": "在夜晚保持安静，确认是否安全。",
            "interactables": [{"id": "cave_wall", "type": "place", "name": "湿冷石壁"}],
            "suggested_actions": ["继续听洞外动静"],
        }
    )
    service.adventures.update_scene(adventure.id, locked_scene)

    response = service.advance(adventure.id, MessageCreate(content="什么意思？", locale="zh-CN"))

    scene = response.adventure.current_scene
    assert response.dm_message.metadata["time"]["advances_time"] is False
    assert scene.environment == "夜晚的小岩洞潮湿昏暗，洞口被荆棘挡住。"
    assert scene.current_objective == "在夜晚保持安静，确认是否安全。"
    assert scene.important_objects == ["湿冷石壁"]
    assert scene.interactables == [{"id": "cave_wall", "type": "place", "name": "湿冷石壁"}]
    assert scene.suggested_actions == ["继续听洞外动静"]


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


def test_isekai_sleep_resets_overnight_pressure_clocks(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Reset", mode="isekai_survival"))
    world_state = dict(adventure.world_state)
    for clock in world_state["pressure_clocks"]:
        if clock["id"] == "sunset":
            clock["value"] = 87
        if clock["id"] == "curfew_patrol":
            clock["value"] = 82
        if clock["id"] == "shelter_security":
            clock["value"] = 82
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(
        adventure.id,
        MessageCreate(content="重新躺下，安心入睡，等待真正的天亮。", locale="zh-CN"),
    )

    clocks = {clock["id"]: clock["value"] for clock in response.adventure.world_state["pressure_clocks"]}
    assert response.adventure.survival_state["time_of_day"] == "清晨"
    assert clocks["sunset"] <= 15
    if "curfew_patrol" in clocks:
        assert clocks["curfew_patrol"] <= 10
    else:
        assert clocks["shelter_security"] <= 25
    assert response.adventure.world_state["last_pressure_advance"]["overnight_reset"] is True


def test_isekai_pressure_clock_threshold_creates_visible_consequence(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Consequence", mode="isekai_survival"))
    world_state = dict(adventure.world_state)
    for clock in world_state["pressure_clocks"]:
        if clock["id"] == "beast_activity":
            clock["value"] = 99
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(adventure.id, MessageCreate(content="我摘点红浆果。", locale="zh-CN"))

    advance = response.adventure.world_state["last_pressure_advance"]
    visible_events = response.adventure.world_state["visible_events"]
    assert any(event["id"] == "beast_activity" for event in advance["threshold_events"])
    assert any("野兽" in event for event in visible_events)
