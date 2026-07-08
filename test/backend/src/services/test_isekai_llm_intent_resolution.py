import json

from backend.src.schemas.adventure import AdventureCreate, MessageCreate, SceneState
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.isekai import IsekaiSurvivalService
from backend.src.services.isekai_action_grounder import IsekaiActionGrounder
from backend.src.services.isekai_intent_schema import IsekaiIntentSchema
from backend.src.services.isekai_time import IsekaiTimeService
from backend.src.services.llm_models import LLMModelService


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


def carriage_scene():
    return SceneState(
        location="泥泞旧路",
        environment="雨后的旧路旁有一辆侧翻马车，车厢门被泥土压住。",
        important_objects=["侧翻马车", "车厢", "车厢门"],
        npcs=[],
        current_objective="确认马车里是否有可用补给，同时避免制造太大声响。",
        interactables=[
            {
                "id": "wagon_01",
                "type": "place",
                "name": "侧翻马车",
                "state": "半陷在泥里",
                "affordances": ["靠近", "观察", "绕行"],
            },
            {
                "id": "carriage_01",
                "type": "place",
                "name": "车厢",
                "state": "破口勉强可进入",
                "affordances": ["进入", "观察", "搜索"],
            },
            {
                "id": "carriage_door_01",
                "type": "obstacle",
                "name": "车厢门",
                "state": "被泥土压住",
                "affordances": ["撬开", "观察"],
            },
        ],
    )


def temple_scene():
    return SceneState(
        location="埃尔德伍德镇外的废弃神庙",
        environment="一座半坍塌的石砌神庙，被常春藤和苔藓覆盖，内部阴暗潮湿。",
        important_objects=[
            "祭坛上的破损圣徽",
            "角落里的旧木箱",
            "墙上的模糊壁画（描绘一位被锁链缠绕的女神）",
        ],
        npcs=[],
        current_objective="探索神庙，寻找可用的补给或线索。",
        interactables=[
            {
                "id": "wooden_crate_01",
                "type": "container",
                "name": "旧木箱",
                "affordances": ["搜索", "观察", "打开"],
            }
        ],
    )


def gray_oak_gate_scene():
    return SceneState(
        location="灰橡镇西门外",
        environment="土路延伸向灰橡镇西门，镇门口有告示板，门内能看见避雨的屋檐。",
        important_objects=["灰橡镇西门", "镇门口的告示板", "一截断裂的马车轮"],
        npcs=[],
        current_objective="进入灰橡镇，寻找安全的歇脚处并打听消息。",
        interactables=[],
    )


def forest_clue_scene():
    return SceneState(
        location="迷雾森林的边界",
        environment="林地里有麋鹿骸骨，肋骨间插着折断的铁头箭；血迹拖向坍塌的石砌哨塔，旁边能听见溪流声。",
        important_objects=["麋鹿骸骨", "折断的铁头箭", "血迹方向", "坍塌的石砌哨塔", "溪流方向"],
        npcs=[],
        current_objective="判断附近是否安全，并确认哨塔能否作为临时落脚点。",
        interactables=[],
    )


def collapsed_watchtower_scene():
    return SceneState(
        location="坍塌的石砌哨塔",
        environment="哨塔内部半截墙壁挡住夜风，墙角堆着旧火堆灰，地基缝隙里有潮湿冷风。",
        important_objects=["墙角", "地基缝隙", "旧火堆", "避风角落", "墙体缺口"],
        npcs=[],
        current_objective="确认哨塔内部是否适合扎营，同时避免夜里暴露。",
        interactables=[],
    )


def gray_oak_inn_scene():
    return SceneState(
        location="灰橡镇街边旅店前厅",
        environment="前厅有街边旅店店主、冒着热气的炖菜锅和一串二楼房间钥匙。",
        important_objects=["街边旅店店主", "炖菜锅", "二楼房间钥匙", "床位报价 3 铜"],
        npcs=[],
        current_objective="用有限铜币换到今晚床位。",
        interactables=[
            {
                "id": "innkeeper_01",
                "type": "npc",
                "name": "街边旅店店主",
                "affordances": ["交谈", "询问价格", "购买"],
            }
        ],
    )


class IntentPlanLLMClient:
    supports_intent_interpretation = True

    def __init__(self, plan: dict):
        self.plan = plan
        self.chat_calls = []

    def chat(self, model, messages):
        self.chat_calls.append({"model": model, "messages": messages})
        system = messages[0]["content"]
        if "异世界开局生成器" in system:
            return "{invalid opening payload"
        if "异世界玩家意图解析器" in system:
            return json.dumps(self.plan, ensure_ascii=False)
        raise AssertionError("resolved intent turns must not ask the DM model for final state")


class FailingIntentLLMClient:
    supports_intent_interpretation = True

    def chat(self, model, messages):
        system = messages[0]["content"]
        if "异世界开局生成器" in system:
            return "{invalid opening payload"
        if "异世界玩家意图解析器" in system:
            raise RuntimeError("intent model unavailable")
        return json.dumps({"narration": "模型回复不应执行高风险复合 fallback。"}, ensure_ascii=False)


def test_intent_schema_rejects_unknown_action_as_clarification():
    schema = IsekaiIntentSchema()

    plan = schema.validate(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "打开传送门",
            "requires_clarification": False,
            "steps": [{"step_id": "s1", "action_type": "open_portal", "target_text": "传送门"}],
        },
        raw_text="打开传送门",
    )

    assert plan.requires_clarification is True
    assert plan.steps == []
    assert "未登记动作" in plan.clarification_question


def test_llm_intent_grounder_binds_targets_and_preserves_negation_constraints():
    schema = IsekaiIntentSchema()
    grounder = IsekaiActionGrounder(IsekaiTimeService())
    plan = schema.validate(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "喝水，然后小心靠近马车，看看里面但先别翻。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [
                {"step_id": "s1", "action_type": "drink_water"},
                {"step_id": "s2", "action_type": "approach", "target_text": "马车", "style": "careful"},
                {
                    "step_id": "s3",
                    "action_type": "observe",
                    "target_text": "车厢",
                    "constraints": ["no_search", "no_loot"],
                },
            ],
        },
        raw_text="喝水，然后小心靠近马车，看看里面但先别翻。",
    )

    grounded = grounder.ground(plan, carriage_scene())

    assert [step.action.action_type for step in grounded.steps] == ["drink_water", "approach", "observe"]
    assert grounded.steps[1].action.target_id == "wagon_01"
    assert grounded.steps[1].action.arguments["style"] == "careful"
    assert grounded.steps[2].action.target_id == "carriage_01"
    assert grounded.steps[2].action.arguments["constraints"] == ["no_search", "no_loot"]


def test_llm_intent_path_executes_structured_compound_plan(store):
    activate_test_model(store)
    client = IntentPlanLLMClient(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "喝水，然后小心靠近马车，看看里面但先别翻。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [
                {"step_id": "s1", "action_type": "drink_water"},
                {"step_id": "s2", "action_type": "approach", "target_text": "马车", "style": "careful"},
                {
                    "step_id": "s3",
                    "action_type": "observe",
                    "target_text": "车厢",
                    "constraints": ["no_search", "no_loot"],
                },
            ],
        }
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="意图测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(adventure.id, carriage_scene())

    response = service.advance(
        adventure.id,
        MessageCreate(content="喝水，然后小心靠近马车，看看里面但先别翻。", locale="zh-CN"),
    )

    metadata = response.dm_message.metadata
    assert metadata["source"] == "action_resolution"
    assert metadata["intent_source"] == "active_model"
    assert metadata["action_type"] == "compound"
    assert [step["action_type"] for step in metadata["resolved_steps"]] == ["drink_water", "approach", "observe"]
    assert metadata["resolved_steps"][2]["arguments"]["constraints"] == ["no_search", "no_loot"]


def test_llm_intent_failure_blocks_high_risk_compound_fallback(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=FailingIntentLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="意图失败测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(adventure.id, carriage_scene())

    response = service.advance(
        adventure.id,
        MessageCreate(content="喝水，然后强行撬开车厢门。", locale="zh-CN"),
    )

    metadata = response.dm_message.metadata
    assert metadata["action_type"] == "clarification"
    assert metadata["time"]["advances_time"] is False
    assert metadata["time"]["time_cost_minutes"] == 0
    assert metadata["intent_source"] == "fallback_blocked"
    assert "resolved_steps" not in metadata


def test_temple_search_produces_specific_discovery_and_refreshes_interactables(store):
    activate_test_model(store)
    client = IntentPlanLLMClient(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "搜索木箱。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [{"step_id": "s1", "action_type": "search", "target_text": "木箱"}],
        }
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="神庙搜索测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(adventure.id, temple_scene())

    response = service.advance(adventure.id, MessageCreate(content="搜索木箱。", locale="zh-CN"))

    assert "行动结果：" not in response.dm_message.content
    assert "空香瓶" in response.dm_message.content
    assert "锁链女神" in response.dm_message.content
    names = {entry["name"] for entry in response.adventure.current_scene.interactables}
    assert {"旧木箱", "祭坛", "破损圣徽", "模糊壁画"}.issubset(names)


def test_enter_town_from_gate_scene_uses_named_town_target(store):
    activate_test_model(store)
    client = IntentPlanLLMClient(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "进入灰橡镇。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [{"step_id": "s1", "action_type": "enter_location", "target_text": "灰橡镇"}],
        }
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="灰橡镇入口测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(adventure.id, gray_oak_gate_scene())

    response = service.advance(adventure.id, MessageCreate(content="进入灰橡镇。", locale="zh-CN"))

    metadata = response.dm_message.metadata
    assert metadata["action_type"] == "enter_location"
    assert metadata["time"]["advances_time"] is True
    assert "需要先明确可进入的地点" not in response.dm_message.content
    assert response.adventure.current_scene.location == "灰橡镇"
    names = {entry["name"] for entry in response.adventure.current_scene.interactables}
    assert "旧炉旅店" in names or "街边旅店" in names


def test_isekai_output_repairs_stale_interactables_from_scene_facts(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="旧存档展示修复", mode="isekai_survival", locale="zh-CN"))
    stale_temple = temple_scene().model_copy(
        update={
            "interactables": [
                {"id": "wooden_crate_01", "type": "object", "name": "木箱", "affordances": ["搜索", "观察"]}
            ],
            "suggested_actions": ["搜索木箱"],
        }
    )
    service.adventures.update_scene(adventure.id, stale_temple)

    output = service.adventures.get(adventure.id)

    names = {entry["name"] for entry in output.current_scene.interactables}
    assert {"旧木箱", "祭坛", "破损圣徽", "模糊壁画"}.issubset(names)


def test_isekai_output_repairs_stale_gate_door_interactable(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="旧镇门展示修复", mode="isekai_survival", locale="zh-CN"))
    stale_gate = gray_oak_gate_scene().model_copy(
        update={
            "interactables": [{"id": "door_01", "type": "object", "name": "门口", "affordances": ["堵门", "离开", "观察"]}],
            "suggested_actions": ["用门口堵门"],
        }
    )
    service.adventures.update_scene(adventure.id, stale_gate)

    output = service.adventures.get(adventure.id)

    names = {entry["name"] for entry in output.current_scene.interactables}
    assert "灰橡镇" in names
    assert "镇门口告示板" in names
    assert "门口" not in names


def test_forest_clue_observation_produces_specific_findings(store):
    activate_test_model(store)
    client = IntentPlanLLMClient(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "搜索麋鹿骸骨、折断箭和血迹，再看溪流方向。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [
                {"step_id": "s1", "action_type": "observe", "target_text": "麋鹿骸骨和折断的箭"},
                {"step_id": "s2", "action_type": "observe", "target_text": "溪流方向，检查脚印和水源安全性"},
            ],
        }
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="森林线索测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(adventure.id, forest_clue_scene())

    response = service.advance(
        adventure.id,
        MessageCreate(content="搜索麋鹿骸骨、折断箭和血迹，再看溪流方向。", locale="zh-CN"),
    )

    assert "角色快速观察周围" not in response.dm_message.content
    assert "铁头箭" in response.dm_message.content
    assert "血迹" in response.dm_message.content
    names = {entry["name"] for entry in response.adventure.current_scene.interactables}
    assert {"麋鹿骸骨", "折断的铁头箭", "血迹方向", "坍塌的石砌哨塔"}.issubset(names)


def test_watchtower_search_produces_specific_camp_findings(store):
    activate_test_model(store)
    client = IntentPlanLLMClient(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "搜索哨塔内部，看看墙角、旧火堆和地基缝隙有什么。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [{"step_id": "s1", "action_type": "search", "target_text": "哨塔内部"}],
        }
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="哨塔搜索测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(adventure.id, collapsed_watchtower_scene())

    response = service.advance(
        adventure.id,
        MessageCreate(content="搜索哨塔内部，看看墙角、旧火堆和地基缝隙有什么。", locale="zh-CN"),
    )

    assert "角色仔细搜索附近区域" not in response.dm_message.content
    assert "旧火堆" in response.dm_message.content
    assert "地基缝隙" in response.dm_message.content
    names = {entry["name"] for entry in response.adventure.current_scene.interactables}
    assert {"旧火堆", "地基缝隙", "避风角落", "墙体缺口"}.issubset(names)


def test_wilderness_camp_setup_does_not_trigger_inn_repair_rewards(store):
    activate_test_model(store)
    client = IntentPlanLLMClient(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "用旧斗篷挡住缺口，清理一块避风角落，用火绒盒点小火，把哨塔当作临时营地休息半小时。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [
                {"step_id": "s1", "action_type": "repair", "target_text": "用旧斗篷挡住缺口"},
                {"step_id": "s2", "action_type": "search", "target_text": "清理一块避风角落"},
                {"step_id": "s3", "action_type": "rest_short", "target_text": "用火绒盒点小火，把哨塔当作临时营地休息半小时"},
            ],
        }
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="野外扎营测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(adventure.id, collapsed_watchtower_scene())

    response = service.advance(
        adventure.id,
        MessageCreate(
            content="用旧斗篷挡住缺口，清理一块避风角落，用火绒盒点小火，把哨塔当作临时营地休息半小时。",
            locale="zh-CN",
        ),
    )

    payload = json.dumps(response.dm_message.metadata, ensure_ascii=False)
    assert "锅把" not in response.dm_message.content
    assert "店主" not in response.dm_message.content
    assert "住宿" not in response.dm_message.content
    assert "锅把" not in payload
    assert "innkeeper_01" not in payload
    assert "旧斗篷" in response.dm_message.content or "临时营地" in response.dm_message.content


def test_llm_purchase_bed_arguments_infer_item_id_and_spend_copper(store):
    activate_test_model(store)
    client = IntentPlanLLMClient(
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "我支付 3 铜买下今晚的床位。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [
                {
                    "step_id": "s1",
                    "action_type": "purchase",
                    "target_text": "街边旅店店主",
                    "arguments": {"item": "床位", "cost": "3铜"},
                }
            ],
        }
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="床位支付测试", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(adventure.id, gray_oak_inn_scene())
    world_state = dict(adventure.world_state)
    world_state["isekai_economy"] = {
        "currency": {"copper_total": 26},
        "quotes": {"inn_bed": 3},
        "entitlements": [],
        "transaction_log": [],
    }
    service.adventures.update_world_state(adventure.id, world_state)

    response = service.advance(
        adventure.id,
        MessageCreate(content="我支付 3 铜买下今晚的床位。", locale="zh-CN"),
    )

    assert "铜币不够" not in response.dm_message.content
    assert "还差 0 铜" not in response.dm_message.content
    economy = response.adventure.world_state["isekai_economy"]
    assert economy["currency"]["copper_total"] == 23
    assert economy["transaction_log"][-1]["lost"] == "3 铜"
    assert any(item["id"] == "inn_room_3_bed" for item in economy["entitlements"])


def test_legacy_watchtower_save_clears_false_inn_reward_pollution(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="旧哨塔污染修复", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="坍塌的石砌哨塔",
            environment="坍塌的石砌哨塔内部光线复杂，能看见几处尚未确认的物件。",
            important_objects=["周围环境"],
            npcs=[],
            current_objective="确认坍塌的石砌哨塔内有哪些可用资源和危险。",
            interactables=[{"id": "surroundings_01", "type": "place", "name": "周围环境", "affordances": ["观察", "搜索"]}],
        ),
    )
    world_state = dict(adventure.world_state)
    world_state.update(
        {
            "pending_lodging_reward": True,
            "isekai_clues": ["店主提到夜里镇墙外有异常低嚎", "旧炉旅店店主提到夜里镇墙外有异常低嚎"],
            "isekai_quest": {
                "active_quest_id": "night_wolf_line",
                "stage": "rumor_heard",
                "flags": {"rumor_source": "old_furnace_keeper"},
            },
            "isekai_economy": {"currency": {"copper_total": 25}, "entitlements": [], "transaction_log": []},
        }
    )
    service.adventures.update_world_state(adventure.id, world_state)

    output = service.adventures.get(adventure.id)

    assert output.world_state.get("pending_lodging_reward") is not True
    assert output.world_state["isekai_quest"]["stage"] == "not_started"
    assert output.world_state["isekai_clues"] == []
    assert "旧火堆" in output.current_scene.important_objects
    names = {entry["name"] for entry in output.current_scene.interactables}
    assert {"旧火堆", "地基缝隙", "避风角落", "墙体缺口"}.issubset(names)
