from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import IsekaiActionParser
from backend.src.services.isekai_time import IsekaiTimeService


def parser():
    return IsekaiActionParser(IsekaiTimeService())


def berry_scene():
    return SceneState(
        location="溪边荆棘丛",
        environment="荆棘藤上结着几簇颜色不同的浆果。",
        important_objects=["红浆果", "紫浆果"],
        npcs=[],
        current_objective="确认哪些植物可以作为补给。",
        interactables=[
            {
                "id": "red_berries_01",
                "type": "item",
                "name": "红浆果",
                "affordances": ["观察", "采集"],
                "risk": "误食可能中毒",
            },
            {
                "id": "purple_berries_01",
                "type": "item",
                "name": "紫浆果",
                "affordances": ["观察", "采集"],
                "risk": "颜色像本地毒莓",
            },
        ],
    )


def shelter_scene():
    return SceneState(
        location="溪边空地",
        environment="雨后的空地边有一间低矮小屋，屋檐下摆着半满的雨水桶。",
        important_objects=["小屋", "雨水桶", "松动门板"],
        npcs=[],
        current_objective="找到能熬过夜晚的落脚点。",
        interactables=[
            {
                "id": "hut_01",
                "type": "place",
                "name": "小屋",
                "affordances": ["进入", "观察"],
                "risk": "屋内可能有未知痕迹",
            },
            {
                "id": "rain_barrel_01",
                "type": "water_source",
                "name": "雨水桶",
                "affordances": ["装水", "观察"],
            },
            {
                "id": "loose_door_01",
                "type": "object",
                "name": "松动门板",
                "affordances": ["堵门", "加固"],
            },
        ],
    )


def inn_scene():
    return SceneState(
        location="灰石镇 / 旧炉旅店 / 前厅",
        location_path={
            "region": "灰石镇",
            "site": "旧炉旅店",
            "sublocation": "前厅",
            "node_id": "inn_front_hall",
            "parent_id": "old_furnace_inn",
            "display_name": "灰石镇 / 旧炉旅店 / 前厅",
        },
        environment="旧炉旅店前厅里，店主站在柜台后，后厨门半开。",
        important_objects=["店主", "后厨门"],
        npcs=["店主"],
        current_objective="拿到今晚的落脚身份。",
        interactables=[
            {"id": "innkeeper_01", "type": "npc", "name": "店主", "affordances": ["交涉", "询问价格", "支付"]},
            {"id": "kitchen_door", "type": "place", "name": "后厨", "affordances": ["进入", "观察"]},
            {"id": "broken_pot_handle", "type": "object", "name": "松动锅把", "affordances": ["修理", "观察"]},
            {"id": "stew_bowl", "type": "item", "name": "热炖菜", "affordances": ["食用", "购买"]},
        ],
    )


def test_parser_recognizes_inn_negotiation_purchase_repair_and_meal_actions():
    p = parser()

    negotiate = p.parse("和店主讨价还价，打听住宿价格", inn_scene())
    purchase = p.parse("支付铜币买床位", inn_scene())
    repair = p.parse("去后厨修锅把", inn_scene())
    meal = p.parse("吃已购买的热炖菜", inn_scene())

    assert negotiate.action_type == "negotiate"
    assert negotiate.arguments["scope"] == "indoor"
    assert purchase.action_type == "purchase"
    assert purchase.arguments["item_id"] == "inn_bed"
    assert repair.action_type == "repair"
    assert repair.target_id == "broken_pot_handle"
    assert repair.arguments["scope"] == "indoor"
    assert meal.action_type == "eat_meal"
    assert meal.arguments["scope"] == "indoor"


def test_parser_marks_indoor_location_move_scope():
    action = parser().parse("进入后厨", inn_scene())

    assert action.action_type == "enter_location"
    assert action.target_id == "kitchen_door"
    assert action.arguments["scope"] == "indoor"


def test_parser_splits_drink_water_from_eat_food():
    drink = parser().parse("我喝一口水", shelter_scene())
    eat = parser().parse("我吃一份干粮", shelter_scene())

    assert drink.action_type == "drink_water"
    assert drink.arguments["consumes"] == ["water"]
    assert drink.time_cost_minutes == 5
    assert eat.action_type == "eat_food"
    assert eat.arguments["consumes"] == ["food"]
    assert eat.time_cost_minutes == 10


def test_parser_keeps_combined_eat_and_drink_with_explicit_consumes():
    action = parser().parse("我吃干粮并喝水", shelter_scene())

    assert action.action_type == "eat_drink"
    assert action.arguments["consumes"] == ["food", "water"]


def test_parser_refill_water_binds_water_source_target():
    action = parser().parse("用水囊在雨水桶装水", shelter_scene())

    assert action.action_type == "refill_water"
    assert action.target_id == "rain_barrel_01"
    assert action.target_name == "雨水桶"
    assert action.arguments["resource"] == "water"
    assert "affordance_match:refill_water" in action.confidence_reasons


def test_parser_refill_water_uses_single_available_water_source():
    action = parser().parse("装水", shelter_scene())

    assert action.action_type == "refill_water"
    assert action.target_id == "rain_barrel_01"
    assert action.target_name == "雨水桶"
    assert "single_affordance_target:refill_water" in action.confidence_reasons


def test_parser_enter_location_binds_place_target_without_trailing_clause():
    action = parser().parse("进入小屋后不急着翻东西", shelter_scene())

    assert action.action_type == "enter_location"
    assert action.target_id == "hut_01"
    assert action.target_name == "小屋"
    assert action.arguments["caution"] is True
    assert "翻东西" not in action.target_name


def test_parser_secure_shelter_binds_barricade_target():
    action = parser().parse("用松动门板堵门", shelter_scene())

    assert action.action_type == "secure_shelter"
    assert action.target_id == "loose_door_01"
    assert action.target_name == "松动门板"
    assert action.time_cost_minutes == 20


def test_parser_binds_gather_action_to_exact_interactable_target():
    action = parser().parse("摘点红浆果", berry_scene())

    assert action.action_type == "gather"
    assert action.target_id == "red_berries_01"
    assert action.target_name == "红浆果"
    assert action.advances_time is True
    assert action.time_cost_minutes == 30
    assert action.confidence == "high"
    assert "exact_target_name" in action.confidence_reasons
    assert "affordance_match:gather" in action.confidence_reasons
    assert "target:red_berries_01" in action.matched_rules
    assert action.requires_clarification is False


def test_parser_keeps_compound_observe_then_gather_as_pending_intent_only():
    action = parser().parse("先观察红浆果，如果没毒就采一点", berry_scene())

    assert action.action_type == "observe"
    assert action.target_id == "red_berries_01"
    assert action.pending_intent == "gather_if_safe"
    assert action.advances_time is True
    assert action.time_cost_minutes == 15
    assert "compound:observe_then_gather_if_safe" in action.matched_rules


def test_parser_requires_clarification_for_ambiguous_targets():
    action = parser().parse("摘点浆果", berry_scene())

    assert action.action_type == "clarification"
    assert action.requires_clarification is True
    assert action.advances_time is False
    assert action.time_cost_minutes == 0
    assert [candidate["id"] for candidate in action.candidates] == ["red_berries_01", "purple_berries_01"]


def test_parser_handles_negated_sleep_as_seek_shelter():
    action = parser().parse("我不是要睡觉，我只是找个能睡的地方", berry_scene())

    assert action.action_type == "seek_shelter"
    assert action.advances_time is True
    assert action.time_cost_minutes == 45
    assert "negated_sleep" in action.matched_rules
