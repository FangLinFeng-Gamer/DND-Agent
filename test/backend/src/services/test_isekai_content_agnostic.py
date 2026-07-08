from pathlib import Path

from backend.src.schemas.adventure import AdventureCreate, MessageCreate, SceneState
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.isekai import IsekaiSurvivalService
from backend.src.services.isekai_action_grounder import IsekaiActionGrounder
from backend.src.services.isekai_intent_schema import IsekaiIntentSchema
from backend.src.services.isekai_locations import IsekaiLocationService
from backend.src.services.isekai_time import IsekaiTimeService
from backend.src.services.llm_models import LLMModelService


class PayloadLLMClient:
    supports_intent_interpretation = False

    def __init__(self, payload: dict):
        self.payload = payload

    def chat(self, model, messages):
        import json

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


def test_old_furnace_pack_exposes_locations_offers_and_discoveries():
    from backend.src.services.isekai_content import IsekaiContentService

    service = IsekaiContentService()
    state = service.ensure_world_state({})
    nodes = service.location_nodes(state)
    offers = service.merchant_offers(state)
    discoveries = service.discovery_tables(state)

    assert "inn_front_hall" in nodes
    assert "inn_bed" in {offer["offer_id"] for offer in offers["innkeeper_01"]}
    assert "broken_pot_handle" in discoveries


def test_location_service_loads_nodes_from_content_pack():
    locations = IsekaiLocationService()

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
    forbidden = ["锁链女神", "麋鹿骸骨", "铁头箭"]

    assert not any(term in text for term in forbidden)
