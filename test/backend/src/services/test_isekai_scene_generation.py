import json

from backend.src.schemas.adventure import AdventureCreate, MessageCreate, SceneState
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.isekai import IsekaiSurvivalService
from backend.src.services.isekai_scene_generation import IsekaiSceneGenerationAgent, IsekaiSceneValidator
from backend.src.services.llm_models import LLMModelService


class SceneGenerationLLMClient:
    supports_intent_interpretation = False

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, model, messages):
        self.calls.append(messages)
        system = messages[0]["content"]
        if "异世界开局生成器" in system:
            return "{invalid opening payload"
        if "异世界场景生成子 Agent" in system:
            return json.dumps(self.payload, ensure_ascii=False)
        return json.dumps({"narration": "你继续观察。"}, ensure_ascii=False)


class SequencedSceneGenerationLLMClient(SceneGenerationLLMClient):
    def __init__(self, payloads: list[dict]):
        super().__init__(payloads[0])
        self.payloads = list(payloads)
        self.index = 0

    def chat(self, model, messages):
        self.calls.append(messages)
        system = messages[0]["content"]
        if "异世界开局生成器" in system:
            return "{invalid opening payload"
        if "异世界场景生成子 Agent" in system:
            payload = self.payloads[min(self.index, len(self.payloads) - 1)]
            self.index += 1
            return json.dumps(payload, ensure_ascii=False)
        return json.dumps({"narration": "你继续观察。"}, ensure_ascii=False)


class SceneGenerationIntentLLMClient(SceneGenerationLLMClient):
    supports_intent_interpretation = True

    def __init__(self, payload: dict, intent_plan: dict):
        super().__init__(payload)
        self.intent_plan = intent_plan

    def chat(self, model, messages):
        self.calls.append(messages)
        system = messages[0]["content"]
        if "异世界开局生成器" in system:
            return "{invalid opening payload"
        if "异世界场景生成子 Agent" in system:
            return json.dumps(self.payload, ensure_ascii=False)
        if "异世界玩家意图解析器" in system:
            return json.dumps(self.intent_plan, ensure_ascii=False)
        return json.dumps({"narration": "你继续观察。"}, ensure_ascii=False)

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


def valid_scene_payload():
    return {
        "schema_version": "isekai_scene_node_v1",
        "node": {
            "node_id": "old_mine_entrance",
            "location_path": {
                "region": "铁炉镇外",
                "site": "旧矿道入口",
                "sublocation": "",
                "display_name": "铁炉镇外 / 旧矿道入口",
            },
            "environment": "冷雾压着旧矿道入口，碎石坡旁有一截锈蚀轨道。",
            "current_objective": "确认入口是否安全，并找出可进入的路线。",
        },
        "visible_objects": [
            {"id": "rusted_gate", "type": "entrance", "name": "生锈铁栅栏", "affordances": ["观察", "进入"], "target_node_id": "mine_outer_tunnel"},
            {"id": "rubble_slope", "type": "place", "name": "碎石坡", "affordances": ["观察", "搜索"]},
        ],
        "hidden_objects": [
            {"id": "covered_side_crack", "type": "entrance", "name": "被碎石遮住的侧缝", "affordances": ["观察", "进入"], "visibility": "hidden"}
        ],
        "visible_edges": [
            {"id": "edge_gate_to_outer", "from_node_id": "old_mine_entrance", "to_node_id": "mine_outer_tunnel", "via_object_id": "rusted_gate", "access": "open", "known_to_player": True}
        ],
        "hidden_edges": [
            {"id": "edge_slope_to_drainage", "from_node_id": "old_mine_entrance", "to_node_id": "hidden_drainage", "via_object_id": "covered_side_crack", "access": "hidden", "known_to_player": False}
        ],
        "node_stubs": [
            {"node_id": "mine_outer_tunnel", "parent_node_id": "old_mine_entrance", "connected_from": "rusted_gate", "generation_status": "stub", "known_to_player": True},
            {"node_id": "hidden_drainage", "parent_node_id": "old_mine_entrance", "connected_from": "covered_side_crack", "generation_status": "stub", "known_to_player": False},
        ],
        "discovery_tables": [
            {
                "target_object_id": "rubble_slope",
                "entries": [
                    {
                        "entry_id": "reveal_side_crack",
                        "trigger": {"action_type": "search"},
                        "result": {
                            "narration_fact": "你拨开碎石，发现一条被遮住的侧缝。",
                            "reveal_objects": ["covered_side_crack"],
                            "reveal_edges": ["edge_slope_to_drainage"],
                        },
                    }
                ],
            }
        ],
        "suggested_actions": ["观察生锈铁栅栏", "搜索碎石坡", "进入生锈铁栅栏"],
    }


def hidden_drainage_payload():
    return {
        "schema_version": "isekai_scene_node_v1",
        "node": {
            "node_id": "hidden_drainage",
            "parent_node_id": "old_mine_entrance",
            "location_path": {
                "region": "铁炉镇外",
                "site": "旧矿道入口",
                "sublocation": "隐藏排水道",
                "display_name": "铁炉镇外 / 旧矿道入口 / 隐藏排水道",
            },
            "environment": "狭窄排水道里有冷湿气流，墙上长着发白苔藓。",
            "current_objective": "确认排水道是否通向矿道深处。",
        },
        "visible_objects": [
            {"id": "pale_moss", "type": "resource", "name": "发白苔藓", "affordances": ["观察", "采集"]},
            {"id": "narrow_exit", "type": "entrance", "name": "返回侧缝", "affordances": ["离开"], "target_node_id": "old_mine_entrance"},
        ],
        "hidden_objects": [],
        "visible_edges": [
            {"id": "edge_drainage_back", "from_node_id": "hidden_drainage", "to_node_id": "old_mine_entrance", "via_object_id": "narrow_exit", "kind": "back", "access": "open", "known_to_player": True}
        ],
        "hidden_edges": [],
        "node_stubs": [
            {"node_id": "old_mine_entrance", "parent_node_id": "old_mine_entrance", "connected_from": "narrow_exit", "generation_status": "stub", "known_to_player": True}
        ],
        "discovery_tables": [],
        "suggested_actions": ["观察发白苔藓", "离开这里"],
    }


def sulfur_outpost_payload():
    return {
        "schema_version": "isekai_scene_node_v1",
        "node": {
            "node_id": "sulfur_watchpost",
            "location_path": {
                "region": "艾尔文森林边缘",
                "site": "废弃岗哨",
                "sublocation": "门洞内",
                "display_name": "艾尔文森林边缘 / 废弃岗哨 / 门洞内",
            },
            "environment": "岗哨门洞内有焦黑墙面、硫磺粉末和带徽记的骸骨。",
            "current_objective": "确认污染源和仪式性质。",
        },
        "visible_objects": [
            {"id": "scorched_wall", "type": "clue", "name": "焦黑墙面", "affordances": ["观察", "搜索"], "description": "焦痕从墙内侧向外炸开。"},
            {"id": "sulfur_powder", "type": "clue", "name": "硫磺粉末", "affordances": ["观察", "搜索"], "description": "粉末沿墙根聚成断续弧线。"},
            {"id": "bone_emblem", "type": "clue", "name": "骸骨徽记", "affordances": ["观察", "搜索"], "description": "徽记被烧裂但仍能看出螺旋角图案。"},
            {"id": "travel_spellbook", "type": "item", "name": "旅行法术书", "affordances": ["观察", "解读"], "description": "边注记录了召唤污染的常见残留。"},
        ],
        "hidden_objects": [],
        "visible_edges": [],
        "hidden_edges": [],
        "node_stubs": [],
        "discovery_tables": [
            {
                "target_object_id": "scorched_wall",
                "target_aliases": ["焦黑墙面", "墙面焦黑"],
                "entries": [
                    {
                        "entry_id": "read_scorch_pattern",
                        "trigger": {"action_type": "observe"},
                        "result": {
                            "narration_fact": "焦黑墙面的纹路由内向外炸开，不像普通火灾。",
                            "clues": ["焦黑墙面显示爆发点在岗哨内部"],
                        },
                    }
                ],
            },
            {
                "target_object_id": "sulfur_powder",
                "target_aliases": ["硫磺粉末"],
                "entries": [
                    {
                        "entry_id": "read_sulfur_powder",
                        "trigger": {"action_type": "observe"},
                        "result": {
                            "narration_fact": "硫磺粉末沿墙根形成断续弧线，像是仪式边界残留。",
                            "clues": ["硫磺粉末疑似召唤仪式边界"],
                        },
                    }
                ],
            },
            {
                "target_object_id": "bone_emblem",
                "target_aliases": ["骸骨徽记", "徽记"],
                "entries": [
                    {
                        "entry_id": "read_bone_emblem",
                        "trigger": {"action_type": "observe"},
                        "result": {
                            "narration_fact": "骸骨徽记上的螺旋角图案与旅行法术书里召唤污染的附图相近。",
                            "clues": ["骸骨徽记与召唤污染记录相符"],
                        },
                    }
                ],
            },
        ],
        "suggested_actions": ["观察焦黑墙面", "观察硫磺粉末", "解读旅行法术书"],
    }


def druid_grove_payload():
    return {
        "schema_version": "isekai_scene_node_v1",
        "node": {
            "node_id": "druid_thunder_oak",
            "location_path": {
                "region": "幽暗森林",
                "site": "雷击巨橡",
                "sublocation": "裂树根旁",
                "display_name": "幽暗森林 / 雷击巨橡 / 裂树根旁",
            },
            "environment": "雷劈裂的巨橡旁有德鲁伊符文、树皮裂缝和潮湿的自然节点痕迹。",
            "current_objective": "确认符文含义、自然节点状态和附近营地危险。",
        },
        "visible_objects": [
            {"id": "druid_runes", "type": "clue", "name": "德鲁伊符文", "affordances": ["观察", "解读"], "description": "符文不是警告，而是在标记一处被强行扭曲的自然节点。"},
            {"id": "bark_crack", "type": "clue", "name": "树皮裂缝", "affordances": ["观察", "搜索"], "description": "裂缝里有发绿的树脂，摸上去微微发热。"},
            {"id": "nature_node", "type": "clue", "name": "自然节点", "affordances": ["观察"], "description": "节点的气息被抽走一半，残留方向指向废弃猎人营地。"},
            {"id": "hunter_embers", "type": "clue", "name": "猎人营地余烬", "affordances": ["观察", "搜索"], "description": "余烬还温着，但灰里混着非木炭的黑色粉末。"},
            {"id": "broken_trap", "type": "hazard", "name": "破损捕兽夹", "affordances": ["观察", "搜索"], "description": "夹齿被从内侧撑弯，像有什么东西挣脱过。"},
            {"id": "gnawed_bones", "type": "clue", "name": "啃过的兽骨", "affordances": ["观察", "搜索"], "description": "兽骨断口整齐，附近留下细长爪痕。"},
            {"id": "camp_tracks", "type": "clue", "name": "营地周围脚印", "affordances": ["观察", "追踪"], "description": "脚印绕开巨橡，最后消失在背风灌木后。"},
        ],
        "hidden_objects": [],
        "visible_edges": [],
        "hidden_edges": [],
        "node_stubs": [],
        "discovery_tables": [
            {
                "target_object_id": "druid_runes",
                "target_aliases": ["德鲁伊符文", "符文"],
                "entries": [
                    {
                        "entry_id": "druid_runes_meaning",
                        "trigger": {"action_type": "observe"},
                        "result": {
                            "narration_fact": "德鲁伊符文不是普通警告，它在标记一处被强行扭曲的自然节点。",
                            "clues": ["德鲁伊符文指向被扭曲的自然节点"],
                        },
                    }
                ],
            },
            {
                "target_object_id": "bark_crack",
                "target_aliases": ["树皮裂缝", "裂缝"],
                "entries": [
                    {
                        "entry_id": "warm_green_resin",
                        "trigger": {"action_type": "search"},
                        "result": {
                            "narration_fact": "树皮裂缝里有发绿的树脂，触感微热，像刚被抽走自然之力。",
                            "clues": ["树皮裂缝残留微热绿树脂"],
                        },
                    }
                ],
            },
            {
                "target_object_id": "nature_node",
                "target_aliases": ["自然节点", "节点"],
                "entries": [
                    {
                        "entry_id": "node_points_to_camp",
                        "trigger": {"action_type": "observe"},
                        "result": {
                            "narration_fact": "自然节点的气息被抽走一半，残留方向指向废弃猎人营地。",
                            "clues": ["自然节点残留方向指向猎人营地"],
                        },
                    }
                ],
            },
        ],
        "suggested_actions": ["解读德鲁伊符文", "搜索树皮裂缝", "检查猎人营地余烬"],
    }


def test_scene_validator_accepts_connected_hidden_stubs():
    result = IsekaiSceneValidator().validate(valid_scene_payload(), source_node_id="")

    assert result.valid is True
    assert result.errors == []


def test_scene_validator_rejects_edge_without_stub():
    payload = valid_scene_payload()
    payload["node_stubs"] = []

    result = IsekaiSceneValidator().validate(payload, source_node_id="")

    assert result.valid is False
    assert "edge.to_node_id missing node stub: mine_outer_tunnel" in result.errors


def test_scene_generation_agent_parses_and_validates_model_output(store):
    model = activate_test_model(store)
    client = SceneGenerationLLMClient(valid_scene_payload())
    service = IsekaiSurvivalService(store, llm_client=client)
    agent = IsekaiSceneGenerationAgent(service.model_gateway)

    result = agent.generate(
        adventure_id=47,
        scene=SceneState(location="旧矿道入口", environment="入口只有雾。", current_objective="确认环境。"),
        world_state={},
        model=model,
        generation_reason="repair_current",
        player_action="观察周围",
    )

    assert result.success is True
    assert result.payload["node"]["node_id"] == "old_mine_entrance"
    assert "异世界场景生成子 Agent" in client.calls[-1][0]["content"]


def test_prepare_turn_structures_generic_scene_before_action(store):
    activate_test_model(store)
    client = SceneGenerationLLMClient(valid_scene_payload())
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="Scene Structure", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="旧矿道入口",
            environment="入口只有雾。",
            important_objects=["周围环境"],
            npcs=[],
            current_objective="确认环境。",
            interactables=[],
            suggested_actions=[],
        ),
    )

    response = service.advance(adventure.id, MessageCreate(content="搜索碎石坡", locale="zh-CN"))

    scene = response.adventure.current_scene
    world_state = response.adventure.world_state
    assert scene.location_path["node_id"] == "old_mine_entrance"
    assert {entry["id"] for entry in scene.interactables} >= {"rusted_gate", "rubble_slope", "covered_side_crack"}
    assert response.dm_message.metadata["scene_structure"]["source"] == "scene_generation_agent"
    assert {edge["id"] for edge in response.dm_message.metadata["visible_edges"]} >= {"edge_gate_to_outer", "edge_slope_to_drainage"}
    assert any(edge["id"] == "edge_gate_to_outer" for edge in world_state["scene_graph"]["edges"])


def test_entering_revealed_hidden_edge_generates_stub_scene(store):
    activate_test_model(store)
    client = SequencedSceneGenerationLLMClient([valid_scene_payload(), hidden_drainage_payload()])
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="Hidden Stub", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="旧矿道入口",
            environment="入口只有雾。",
            important_objects=["周围环境"],
            npcs=[],
            current_objective="确认环境。",
            interactables=[],
            suggested_actions=[],
        ),
    )

    searched = service.advance(adventure.id, MessageCreate(content="搜索碎石坡", locale="zh-CN"))
    assert any(entry["id"] == "covered_side_crack" for entry in searched.adventure.current_scene.interactables)

    entered = service.advance(adventure.id, MessageCreate(content="进入侧缝", locale="zh-CN"))

    assert entered.adventure.current_scene.location_path["node_id"] == "hidden_drainage"
    assert {entry["id"] for entry in entered.adventure.current_scene.interactables} >= {"pale_moss", "narrow_exit"}
    assert entered.dm_message.metadata["scene_structure"]["source"] == "scene_generation_agent"


def test_concrete_observation_structures_scene_and_returns_specific_findings(store):
    activate_test_model(store)
    client = SceneGenerationIntentLLMClient(
        sulfur_outpost_payload(),
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "我检查焦黑墙面、硫磺粉末、骸骨徽记，并翻看旅行法术书。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [
                {
                    "step_id": "s1",
                    "action_type": "observe",
                    "target_text": "焦黑墙面、硫磺粉末、骸骨徽记、旅行法术书",
                }
            ],
        },
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="Sulfur Watchpost", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="艾尔文森林边缘的废弃岗哨",
            environment="破败岗哨里弥漫着硫磺味，墙面发黑，地上散着碎骨。",
            important_objects=["焦黑墙面", "硫磺粉末", "骸骨徽记", "旅行法术书"],
            npcs=[],
            current_objective="调查硫磺味和异常凋零的原因。",
            interactables=[],
            suggested_actions=[],
        ),
    )

    response = service.advance(
        adventure.id,
        MessageCreate(content="我检查焦黑墙面、硫磺粉末、骸骨徽记，并翻看旅行法术书。", locale="zh-CN"),
    )

    assert response.dm_message.metadata["scene_structure"]["success"] is True
    assert "角色快速观察周围" not in response.dm_message.content
    assert "不像普通火灾" in response.dm_message.content
    assert "仪式边界残留" in response.dm_message.content
    assert "召唤污染" in response.dm_message.content
    assert {"scorched_wall", "sulfur_powder", "bone_emblem", "travel_spellbook"} <= {
        entry["id"] for entry in response.adventure.current_scene.interactables
    }
    assert {
        "焦黑墙面显示爆发点在岗哨内部",
        "硫磺粉末疑似召唤仪式边界",
        "骸骨徽记与召唤污染记录相符",
    } <= set(response.dm_message.metadata["clues"])


def test_llm_observation_intent_structures_unstructured_scene_before_resolution(store):
    activate_test_model(store)
    client = SceneGenerationIntentLLMClient(
        druid_grove_payload(),
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "我走到被雷劈裂的巨橡树前，仔细辨认德鲁伊符文的含义，摸一摸树皮裂缝，看看是否有自然之力节点或隐藏入口。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [
                {"step_id": "s1", "action_type": "observe", "target_text": "德鲁伊符文"},
                {"step_id": "s2", "action_type": "search", "target_text": "树皮裂缝"},
                {"step_id": "s3", "action_type": "observe", "target_text": "自然节点"},
            ],
        },
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="Druid Grove", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="幽暗森林深处",
            environment="你在一棵被雷劈裂的巨橡树旁醒来，不远处有废弃猎人营地。",
            important_objects=[
                "一棵被雷劈裂的巨橡树，树干上刻着模糊的德鲁伊符文",
                "一处被遗弃的猎人营地，篝火余烬尚温，周围散落着破损的捕兽夹和几根啃过的兽骨",
            ],
            npcs=[],
            current_objective="调查雷击橡树上的德鲁伊符文。",
            interactables=[],
            suggested_actions=[],
        ),
    )

    response = service.advance(
        adventure.id,
        MessageCreate(
            content="我走到被雷劈裂的巨橡树前，仔细辨认德鲁伊符文的含义，摸一摸树皮裂缝，看看是否有自然之力节点或隐藏入口。",
            locale="zh-CN",
        ),
    )

    assert response.dm_message.metadata["scene_structure"]["success"] is True
    assert "角色快速观察周围" not in response.dm_message.content
    assert "德鲁伊符文不是普通警告" in response.dm_message.content
    assert "树皮裂缝里有发绿的树脂" in response.dm_message.content
    assert "自然节点的气息被抽走一半" in response.dm_message.content
    assert {
        "德鲁伊符文指向被扭曲的自然节点",
        "树皮裂缝残留微热绿树脂",
        "自然节点残留方向指向猎人营地",
    } <= set(response.dm_message.metadata["clues"])


def test_structured_object_description_still_returns_natural_finding_without_discovery_table(store):
    activate_test_model(store)
    payload = druid_grove_payload()
    payload["discovery_tables"] = []
    client = SceneGenerationIntentLLMClient(
        payload,
        {
            "schema_version": "isekai_intent_v1",
            "raw_text": "我解读德鲁伊符文。",
            "requires_clarification": False,
            "confidence": "high",
            "steps": [{"step_id": "s1", "action_type": "observe", "target_text": "德鲁伊符文"}],
        },
    )
    service = IsekaiSurvivalService(store, llm_client=client)
    adventure = service.create_adventure(AdventureCreate(title="Druid Object Description", mode="isekai_survival", locale="zh-CN"))
    service.adventures.update_scene(
        adventure.id,
        SceneState(
            location="幽暗森林深处",
            environment="雷击巨橡上有模糊的德鲁伊符文。",
            important_objects=["德鲁伊符文"],
            npcs=[],
            current_objective="解读符文。",
            interactables=[],
            suggested_actions=[],
        ),
    )

    response = service.advance(adventure.id, MessageCreate(content="我解读德鲁伊符文。", locale="zh-CN"))

    assert response.dm_message.metadata["scene_structure"]["success"] is True
    assert "行动结果：" not in response.dm_message.content
    assert "角色快速观察周围" not in response.dm_message.content
    assert "符文不是警告" in response.dm_message.content
