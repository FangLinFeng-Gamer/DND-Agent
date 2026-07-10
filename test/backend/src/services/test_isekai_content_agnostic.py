import json
from pathlib import Path

from backend.src.schemas.adventure import AdventureCreate, MessageCreate, SceneState
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.isekai import IsekaiSurvivalService
from backend.src.services.isekai_action_grounder import IsekaiActionGrounder
from backend.src.services.isekai_interactables import IsekaiInteractableProjector
from backend.src.services.isekai_intent_schema import IsekaiIntentSchema
from backend.src.services.isekai_locations import IsekaiLocationService
from backend.src.services.isekai_time import IsekaiTimeService
from backend.src.services.llm_models import LLMModelService


class PayloadLLMClient:
    supports_intent_interpretation = False

    def __init__(self, payload: dict):
        self.payload = payload
        self.last_messages: list[dict[str, str]] = []

    def chat(self, model, messages):
        import json

        self.last_messages = messages
        system = messages[0]["content"]
        if "异世界开局生成器" in system:
            return "{invalid opening payload"
        return json.dumps(self.payload, ensure_ascii=False)


class IntentPlanLLMClient:
    supports_intent_interpretation = True

    def __init__(self, plan: dict):
        self.plan = plan

    def chat(self, model, messages):
        import json

        system = messages[0]["content"]
        if "异世界开局生成器" in system:
            return "{invalid opening payload"
        if "异世界玩家意图解析器" in system:
            return json.dumps(self.plan, ensure_ascii=False)
        raise AssertionError("content-agnostic resolved turns should not ask DM model for final narration")


def activate_test_model(store):
    service = LLMModelService(store)
    model = service.create(
        LLMModelCreate(
            name="Isekai DM",
            provider="openai_compatible",
            base_url="https://api.example.test",
            api_key="sk-test-1234567890",
            model_name="isekai-dm-model",
        )
    )
    service.activate(model.id)
    return model


def test_empty_isekai_world_state_does_not_activate_legacy_p1_content():
    from backend.src.services.isekai_content import IsekaiContentService

    service = IsekaiContentService()
    state = service.ensure_world_state({})

    assert state["isekai_content"]["active_packs"] == []
    assert service.location_nodes(state) == {}
    assert service.merchant_offers(state) == {}
    assert service.discovery_tables(state) == {}
    assert service.allowed_active_quest_ids(state) == set()
    assert service.destination_template("铁炉镇外的旧矿道入口", state) == {}


def test_empty_isekai_world_state_does_not_create_night_wolf_quest():
    from backend.src.services.isekai_quests import IsekaiQuestService

    state = IsekaiQuestService().initial_world_state({})

    assert state["isekai_quest"]["active_quest_id"] is None
    assert state["isekai_quest"]["stage"] == "none"
    assert state["isekai_quest"]["flags"] == {}


def test_legacy_default_content_packs_are_removed_from_unrelated_save(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="旧默认包清理", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="铁炉镇外的旧矿道入口",
            environment="旧矿道入口被冷雾压住，碎石坡旁只有矿车残骸和一条黑暗矿缝。",
            important_objects=["矿车残骸", "黑暗矿缝"],
            npcs=[],
            current_objective="确认旧矿道入口是否安全。",
            interactables=[],
            suggested_actions=[],
        ),
    )
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["isekai_content"] = {
        "active_packs": ["old_furnace_inn_p1", "baseline_exploration_discoveries"],
    }
    world_state["isekai_quest"] = {"active_quest_id": "night_wolf_line", "stage": "not_started", "flags": {}}
    service.adventures.update_world_state(adventure.id, world_state)

    output = service.adventures.get(adventure.id, include_messages=False)
    cleaned_world_state = service.adventures.get_world_state(adventure.id)

    assert cleaned_world_state["isekai_content"]["active_packs"] == []
    assert output.world_state["isekai_quest"] == {"active_quest_id": None, "stage": "none", "flags": {}}
    rendered = json.dumps(output.current_scene.model_dump(mode="json"), ensure_ascii=False)
    assert "旧炉旅店" not in rendered
    assert "街边旅店" not in rendered
    assert "镇门口告示板" not in rendered


def test_unrelated_wilderness_save_does_not_expose_legacy_quest_or_city_pressure_templates(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="硫磺岗哨", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="黑松林废弃岗哨",
            environment="岗哨木墙半塌，沟渠里积着带硫磺味的黄水，附近没有城镇灯火。",
            important_objects=["半塌岗哨", "硫磺污染水沟", "黑松林"],
            npcs=[],
            current_objective="确认污染和夜间庇护风险。",
            interactables=[],
            suggested_actions=[],
        ),
    )
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["isekai_content"] = {"active_packs": ["old_furnace_inn_p1"]}
    world_state["isekai_quest"] = {"active_quest_id": "night_wolf_line", "stage": "not_started", "flags": {}}
    world_state["isekai_pressure_goals"] = [
        {"id": "lodging_identity", "label": "日落前取得落脚身份"},
        {"id": "alien_tax", "label": "异族食宿价格翻倍"},
        {"id": "curfew_patrol", "label": "夜晚宵禁巡逻"},
    ]
    service.adventures.update_world_state(adventure.id, world_state)

    output = service.adventures.get(adventure.id, include_messages=False)
    rendered = json.dumps(output.world_state, ensure_ascii=False)

    assert "旧炉旅店" not in rendered
    assert "梦魇草" not in rendered
    assert "暗夜狼" not in rendered
    assert "日落前取得落脚身份" not in rendered
    assert "异族食宿价格翻倍" not in rendered
    assert "夜晚宵禁巡逻" not in rendered
    assert any(goal["id"] == "environmental_hazard" for goal in output.world_state["isekai_pressure_goals"])
    assert "污染" in rendered


def test_unrelated_wilderness_save_removes_progressed_implicit_legacy_quest(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="旧任务推进残留", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="幽暗森林深处",
            environment="黑色蕨叶遮住湿软地面，远处只有不成节律的虫鸣，没有城镇和旅店。",
            important_objects=["黑色蕨叶", "断裂猎径", "潮湿树洞"],
            npcs=[],
            current_objective="确认森林中的危险和可用庇护。",
            interactables=[],
            suggested_actions=[],
        ),
    )
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["isekai_content"] = {"active_packs": ["old_furnace_inn_p1"]}
    world_state["isekai_quest"] = {
        "active_quest_id": "night_wolf_line",
        "stage": "rumor_heard",
        "flags": {"rumor_source": "old_furnace_keeper"},
    }
    service.adventures.update_world_state(adventure.id, world_state)

    output = service.adventures.get(adventure.id, include_messages=False)
    rendered = json.dumps(output.world_state, ensure_ascii=False)

    assert output.world_state["isekai_quest"] == {"active_quest_id": None, "stage": "none", "flags": {}}
    assert "旧炉旅店" not in rendered
    assert "梦魇草" not in rendered
    assert "暗夜狼" not in rendered


def test_unrelated_wilderness_save_filters_stale_city_pressure_clocks(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="旧压力时钟残留", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="艾尔文森林边缘的废弃岗哨",
            environment="岗哨木墙焦黑，地上散着硫磺粉末和旧骸骨徽记，周围没有城镇灯火。",
            important_objects=["焦黑墙面", "硫磺粉末", "骸骨徽记"],
            npcs=[],
            current_objective="确认污染、危险和可休息位置。",
            interactables=[],
            suggested_actions=[],
        ),
    )
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["pressure_clocks"] = [
        {"id": "sunset", "label": "日落倒计时", "value": 61, "max": 100, "visible": True},
        {"id": "outsider_suspicion", "label": "外来者怀疑", "value": 20, "max": 100, "visible": True},
        {"id": "curfew_patrol", "label": "宵禁巡逻", "value": 13, "max": 100, "visible": True},
        {"id": "beast_activity", "label": "野兽活动", "value": 15, "max": 100, "visible": True},
        {"id": "weather_thirst", "label": "天气与口渴", "value": 24, "max": 100, "visible": True},
    ]
    service.adventures.update_world_state(adventure.id, world_state)

    output = service.adventures.get(adventure.id, include_messages=False)
    rendered = json.dumps(output.world_state.get("pressure_clocks"), ensure_ascii=False)

    assert "外来者怀疑" not in rendered
    assert "宵禁巡逻" not in rendered
    assert "庇护安全" in rendered
    assert "污染风险" in rendered
    assert {clock["id"] for clock in output.world_state["pressure_clocks"]} >= {
        "sunset",
        "beast_activity",
        "weather_thirst",
        "shelter_security",
        "environmental_hazard",
    }


def test_wilderness_pressure_goals_sent_to_model_are_scene_contextual(store):
    activate_test_model(store)
    payload = {"narration": "你压低呼吸，确认黄水的刺鼻气味来自岗哨沟渠。"}
    service = IsekaiSurvivalService(store, llm_client=PayloadLLMClient(payload))
    adventure = service.create_adventure(AdventureCreate(title="硫磺模型上下文", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="黑松林废弃岗哨",
            environment="岗哨周围有硫磺污染的黄水，黑松林里没有商路和旅店。",
            important_objects=["硫磺污染水沟", "倒塌木墙"],
            npcs=[],
            current_objective="确认水源污染和扎营风险。",
            interactables=[],
            suggested_actions=[],
        ),
    )

    service.advance(adventure.id, MessageCreate(content="我观察硫磺污染的水沟", locale="zh-CN"))

    request_payload = json.loads(service.llm_client.last_messages[-1]["content"])
    pressure_text = json.dumps(request_payload["system_state"]["pressure_goals"], ensure_ascii=False)
    assert "日落前取得落脚身份" not in pressure_text
    assert "异族食宿价格翻倍" not in pressure_text
    assert "夜晚宵禁巡逻" not in pressure_text
    assert "硫磺" in pressure_text or "污染" in pressure_text


def test_legacy_default_pack_location_transition_is_rolled_back(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="旧默认地点回滚", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="街边旅店",
            environment="街边旅店内部光线复杂，能看见几处尚未确认的物件。",
            important_objects=[],
            npcs=[],
            current_objective="确认街边旅店内有哪些可用资源和危险。",
            world_changes=["位置从铁炉镇外的旧矿道入口推进到街边旅店。"],
            interactables=[{"id": "surroundings_01", "type": "place", "name": "周围环境", "affordances": ["观察", "搜索"]}],
            suggested_actions=["观察周围环境", "搜索周围环境"],
        ),
    )
    world_state = service.adventures.get_world_state(adventure.id)
    world_state["isekai_content"] = {
        "active_packs": ["old_furnace_inn_p1", "baseline_exploration_discoveries"],
    }
    world_state["isekai_quest"] = {"active_quest_id": "night_wolf_line", "stage": "not_started", "flags": {}}
    world_state["location_history"] = [
        {
            "from": "铁炉镇外的旧矿道入口",
            "to": "街边旅店",
            "triggering_action": "进入街边旅店",
            "summary": "你进入街边旅店。",
        }
    ]
    world_state["confirmed_location"] = "街边旅店"
    service.adventures.update_world_state(adventure.id, world_state)

    output = service.adventures.get(adventure.id, include_messages=False)

    assert output.current_scene.location == "铁炉镇外的旧矿道入口"
    assert output.world_state["confirmed_location"] == "铁炉镇外的旧矿道入口"
    rendered = json.dumps(output.current_scene.model_dump(mode="json"), ensure_ascii=False)
    assert "街边旅店" not in rendered
    assert "旧炉旅店" not in rendered


def test_old_furnace_pack_exposes_locations_offers_and_discoveries():
    from backend.src.services.isekai_content import IsekaiContentService

    service = IsekaiContentService()
    state = service.ensure_world_state({"isekai_content": {"active_packs": ["old_furnace_inn_p1"]}})
    nodes = service.location_nodes(state)
    offers = service.merchant_offers(state)
    discoveries = service.discovery_tables(state)

    assert "inn_front_hall" in nodes
    assert "inn_bed" in {offer["offer_id"] for offer in offers["innkeeper_01"]}
    assert "broken_pot_handle" in discoveries


def test_location_service_loads_nodes_from_content_pack():
    locations = IsekaiLocationService(world_state={"isekai_content": {"active_packs": ["old_furnace_inn_p1"]}})

    scene = locations.scene_for("inn_front_hall")

    assert scene.location_path["node_id"] == "inn_front_hall"
    assert {entry["id"] for entry in scene.interactables} >= {"innkeeper_01", "kitchen_door"}


def test_model_scene_objects_materialize_without_keyword_projector(store):
    activate_test_model(store)
    payload = {
        "narration": "你看见蓝盐水洼旁有一只虫蚀皮袋。",
        "scene_objects": {
            "add": [
                {
                    "type": "resource",
                    "name": "蓝盐水洼",
                    "aliases": ["水洼"],
                    "description": "水面泛着淡蓝盐霜。",
                    "suggested_affordances": ["observe", "search"],
                },
                {
                    "type": "container",
                    "name": "虫蚀皮袋",
                    "aliases": ["皮袋"],
                    "description": "袋口被虫咬出细洞。",
                    "suggested_affordances": ["observe", "search", "open"],
                },
            ]
        },
        "suggested_actions": ["搜索虫蚀皮袋"],
    }
    service = IsekaiSurvivalService(store, llm_client=PayloadLLMClient(payload))
    adventure = service.create_adventure(AdventureCreate(title="随机对象测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="雾盐渡口",
            environment="雾气压着渡口，地面有陌生盐霜。",
            important_objects=[],
            npcs=[],
            current_objective="确认渡口是否安全。",
            interactables=[],
            suggested_actions=[],
        ),
    )

    response = service.advance(adventure.id, MessageCreate(content="观察渡口周围", locale="zh-CN"))

    names = {entry["name"] for entry in response.adventure.current_scene.interactables}
    assert {"蓝盐水洼", "虫蚀皮袋"}.issubset(names)
    assert "搜索虫蚀皮袋" in response.adventure.current_scene.suggested_actions
    assert response.dm_message.metadata["scene_object_source"] == "llm_proposal"


def test_interactable_projector_does_not_create_generic_surroundings_fallback():
    scene = SceneState(
        location="雾盐渡口",
        environment="雾气压着渡口，但结构化对象还没有生成。",
        important_objects=[],
        npcs=[],
        current_objective="确认渡口是否安全。",
        interactables=[],
        suggested_actions=[],
    )

    interactables, suggestions = IsekaiInteractableProjector().project(scene, "search")

    assert interactables == []
    assert suggestions == []


def test_grounder_matches_random_object_alias_without_parser_token():
    schema = IsekaiIntentSchema()
    scene = SceneState(
        location="雾盐渡口",
        environment="地上有一只虫蚀皮袋。",
        important_objects=[],
        npcs=[],
        current_objective="检查可疑容器。",
        interactables=[
            {
                "id": "random_bag_01",
                "type": "container",
                "name": "虫蚀皮袋",
                "aliases": ["盐蚀袋"],
                "affordances": ["观察", "搜索", "打开"],
            }
        ],
    )
    plan = schema.validate(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "搜索皮袋",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [{"step_id": "s1", "action_type": "search", "target_text": "盐蚀袋"}],
        },
        raw_text="搜索盐蚀袋",
    )

    grounded = IsekaiActionGrounder(IsekaiTimeService()).ground(plan, scene)

    assert grounded.steps[0].action.target_id == "random_bag_01"
    assert grounded.steps[0].action.target_name == "虫蚀皮袋"


def test_discovery_table_reveals_random_object_without_resolution_branch(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(
        store,
        llm_client=IntentPlanLLMClient(
            {
                "schema_version": "isekai_intent_v1",
                "raw_text": "搜索盐蚀袋",
                "requires_clarification": False,
                "confidence": "high",
                "steps": [{"step_id": "s1", "action_type": "search", "target_text": "盐蚀袋"}],
            }
        ),
    )
    adventure = service.create_adventure(AdventureCreate(title="随机发现测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="雾盐渡口",
            environment="雾气里有一只虫蚀皮袋。",
            important_objects=[],
            npcs=[],
            current_objective="检查可疑容器。",
            interactables=[
                {
                    "id": "random_bag_01",
                    "type": "container",
                    "name": "虫蚀皮袋",
                    "aliases": ["盐蚀袋"],
                    "affordances": ["观察", "搜索", "打开"],
                }
            ],
        ),
    )
    world_state = dict(adventure.world_state)
    content = dict(world_state.get("isekai_content") or {})
    content["discovery_tables"] = {
        "random_bag_01": [
            {
                "entry_id": "bone_flute_01",
                "trigger": {"action_type": "search"},
                "result": {
                    "narration_fact": "袋底藏着一支骨笛，孔洞里还残留着蓝盐粉末。",
                    "reveal_objects": [
                        {
                            "id": "bone_flute_01",
                            "type": "item",
                            "name": "骨笛",
                            "aliases": ["小骨笛"],
                            "suggested_affordances": ["observe", "take"],
                        }
                    ],
                    "clues": ["骨笛孔洞里残留蓝盐粉末"],
                },
            }
        ]
    }
    world_state["isekai_content"] = content
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(adventure.id, MessageCreate(content="搜索盐蚀袋", locale="zh-CN"))

    assert "骨笛" in response.dm_message.content
    names = {entry["name"] for entry in response.adventure.current_scene.interactables}
    assert "骨笛" in names
    assert "骨笛孔洞里残留蓝盐粉末" in response.dm_message.metadata["clues"]


def test_content_pack_offer_purchase_updates_currency_and_inventory_without_price_constant(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(
        store,
        llm_client=IntentPlanLLMClient(
            {
                "schema_version": "isekai_intent_v1",
                "raw_text": "向渡口商人买一段干蜡绳",
                "requires_clarification": False,
                "confidence": "high",
                "steps": [
                    {
                        "step_id": "s1",
                        "action_type": "purchase",
                        "target_text": "渡口商人",
                        "arguments": {"offer_id": "dry_wax_rope"},
                    }
                ],
            }
        ),
    )
    adventure = service.create_adventure(AdventureCreate(title="随机报价测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="雾盐渡口",
            environment="一名披盐布的渡口商人守着木摊。",
            important_objects=[],
            npcs=["渡口商人"],
            current_objective="补齐渡河前的工具。",
            interactables=[
                {
                    "id": "dock_merchant_01",
                    "type": "merchant",
                    "name": "渡口商人",
                    "affordances": ["交谈", "询问价格", "支付"],
                }
            ],
        ),
    )
    world_state = dict(adventure.world_state)
    world_state["isekai_economy"] = service.economy.initial_state(12)
    content = dict(world_state.get("isekai_content") or {})
    content["merchant_offers"] = {
        "dock_merchant_01": [
            {
                "offer_id": "dry_wax_rope",
                "kind": "item",
                "name": "干蜡绳",
                "price_copper": 4,
                "grants": {"items": ["干蜡绳"]},
            }
        ]
    }
    world_state["isekai_content"] = content
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(adventure.id, MessageCreate(content="向渡口商人买一段干蜡绳", locale="zh-CN"))

    economy = response.adventure.world_state["isekai_economy"]
    assert economy["currency"]["copper_total"] == 8
    assert {"lost": "4 铜", "gained": "干蜡绳", "reason": "购买干蜡绳"} in economy["transaction_log"]
    assert "干蜡绳" in response.adventure.isekai_character["inventory"]
    assert "干蜡绳" in response.dm_message.metadata["rewards"]


def test_random_fixture_names_are_not_hardcoded_in_generic_services():
    forbidden = ["蓝盐水洼", "虫蚀皮袋", "骨笛", "干蜡绳"]
    service_paths = [
        Path("backend/src/services/isekai_interactables.py"),
        Path("backend/src/services/isekai_action_parser.py"),
        Path("backend/src/services/isekai_action_resolution.py"),
        Path("backend/src/services/isekai_economy.py"),
        Path("backend/src/services/isekai_locations.py"),
    ]
    for path in service_paths:
        text = path.read_text()
        assert not any(term in text for term in forbidden), f"{path} contains content fixture names"


def test_legacy_exploration_discoveries_are_not_hardcoded_in_resolution_engine():
    text = Path("backend/src/services/isekai_action_resolution.py").read_text()
    forbidden = [
        "锁链女神",
        "麋鹿骸骨",
        "铁头箭",
        "松动锅把",
        "二楼三号房",
        "热炖菜",
        "货袋",
        "暗夜狼",
        "灰橡镇",
        "小屋",
        "哨塔",
    ]

    assert not any(term in text for term in forbidden)


def test_interactable_projector_is_state_based_not_keyword_catalog():
    text = Path("backend/src/services/isekai_interactables.py").read_text()
    forbidden = ["灰橡镇", "旧炉旅店", "麋鹿骸骨", "货袋", "木箱", "雨水桶", "坍塌的石砌哨塔"]

    assert not any(term in text for term in forbidden)


def test_interactable_projector_projects_existing_scene_objects_generically():
    scene = SceneState(
        location="任意地点",
        environment="任意环境。",
        important_objects=[],
        npcs=[],
        current_objective="测试通用投影。",
        interactables=[
            {"id": "object_a", "type": "container", "name": "星砂匣", "affordances": ["观察", "搜索", "打开"]},
            {"id": "object_b", "type": "water_source", "name": "银叶泉", "affordances": ["观察", "装水"]},
        ],
    )

    interactables, suggestions = IsekaiInteractableProjector().project(scene, "search")

    assert [entry["id"] for entry in interactables] == ["object_a", "object_b"]
    assert {"观察星砂匣", "搜索星砂匣", "打开星砂匣", "用水囊在银叶泉装水"}.issubset(set(suggestions))


def test_quest_service_uses_content_pack_not_quest_text_literals():
    text = Path("backend/src/services/isekai_quests.py").read_text()
    forbidden = ["旧炉旅店店主提到", "夜里狼嚎来自", "梦魇草燃烟", "北坡泥地", "暗夜狼"]

    assert not any(term in text for term in forbidden)


def test_survival_service_does_not_hardcode_quest_rewards():
    text = Path("backend/src/services/isekai.py").read_text()
    forbidden = ["暗夜狼牙 x1", "暗夜狼任务线", "暗夜狼惧怕梦魇草燃烟"]

    assert not any(term in text for term in forbidden)


def test_economy_service_uses_content_offers_not_product_literals():
    text = Path("backend/src/services/isekai_economy.py").read_text()
    forbidden = ["二楼三号房", "热炖菜", "帮后厨修锅把", "店主", "旧炉旅店"]

    assert not any(term in text for term in forbidden)


def test_generic_isekai_services_do_not_embed_legacy_content_terms():
    forbidden = [
        "灰石镇",
        "灰橡镇",
        "旧炉旅店",
        "松动锅把",
        "二楼三号房",
        "热炖菜",
        "暗夜狼",
        "梦魇草",
        "麋鹿骸骨",
        "铁头箭",
        "货袋",
        "小屋",
        "哨塔",
        "木箱",
        "雨水桶",
        "后厨",
        "前厅",
        "客房",
        "马厩",
        "店主",
    ]
    service_paths = [
        Path("backend/src/services/isekai_action_parser.py"),
        Path("backend/src/services/isekai_action_grounder.py"),
        Path("backend/src/services/isekai_locations.py"),
        Path("backend/src/services/isekai_action_resolution.py"),
        Path("backend/src/services/isekai_interactables.py"),
        Path("backend/src/services/isekai_pressure_events.py"),
        Path("backend/src/services/adventures.py"),
    ]
    for path in service_paths:
        text = path.read_text()
        assert not any(term in text for term in forbidden), f"{path} contains legacy content terms"
