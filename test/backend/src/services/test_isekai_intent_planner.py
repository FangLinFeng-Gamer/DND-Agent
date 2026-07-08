from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import IsekaiActionParser
from backend.src.services.isekai_intent_planner import IsekaiIntentPlanner
from backend.src.services.isekai_time import IsekaiTimeService


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
                "risk": "靠得太快可能踩入泥坑或惊动附近东西",
            },
            {
                "id": "carriage_01",
                "type": "place",
                "name": "车厢",
                "state": "破口勉强可进入",
                "affordances": ["进入", "观察", "搜索"],
                "risk": "内部可能有陷阱或寄生虫",
            },
            {
                "id": "carriage_door_01",
                "type": "obstacle",
                "name": "车厢门",
                "state": "被泥土压住",
                "affordances": ["撬开", "观察"],
                "risk": "强行撬开会制造声响",
            },
        ],
    )


def test_planner_splits_compound_turn_into_limited_ordered_actions():
    planner = IsekaiIntentPlanner(IsekaiActionParser(IsekaiTimeService()))

    plan = planner.plan("喝水，然后小心靠近马车，进入车厢后不急着翻东西。", carriage_scene())

    assert [step.action.action_type for step in plan.steps] == ["drink_water", "approach", "enter_location"]
    assert [step.text for step in plan.steps] == ["喝水", "小心靠近马车", "进入车厢后不急着翻东西"]
    assert plan.steps[1].action.target_id == "wagon_01"
    assert plan.steps[1].action.arguments["style"] == "careful"
    assert plan.steps[2].action.target_id == "carriage_01"
    assert set(plan.steps[2].action.arguments["constraints"]) == {"no_loot", "no_search"}
    assert plan.truncated is False


def test_planner_limits_compound_turn_to_three_subactions():
    planner = IsekaiIntentPlanner(IsekaiActionParser(IsekaiTimeService()))

    plan = planner.plan("喝水，然后小心靠近马车，再进入车厢，接着搜索货袋，然后撬开暗格。", carriage_scene())

    assert [step.action.action_type for step in plan.steps] == ["drink_water", "approach", "enter_location"]
    assert plan.truncated is True


def test_parser_understands_approach_style_and_constraints():
    action = IsekaiActionParser(IsekaiTimeService()).parse("悄悄靠近马车，先不搜刮", carriage_scene())

    assert action.action_type == "approach"
    assert action.target_id == "wagon_01"
    assert action.arguments["style"] == "quiet"
    assert set(action.arguments["constraints"]) == {"no_loot", "no_search"}


def test_parser_understands_hide_or_avoid_and_force_open():
    parser = IsekaiActionParser(IsekaiTimeService())

    hide = parser.parse("听到动静后躲起来", carriage_scene())
    force_open = parser.parse("强行撬开车厢门", carriage_scene())

    assert hide.action_type == "hide"
    assert hide.arguments["style"] == "quiet"
    assert force_open.action_type == "force_open"
    assert force_open.target_id == "carriage_door_01"
    assert force_open.arguments["style"] == "forceful"


def test_parser_treats_lock_picking_as_force_open_without_new_action_type():
    scene = carriage_scene().model_copy(
        update={
            "interactables": [
                {
                    "id": "rusty_lock_01",
                    "type": "lock",
                    "name": "生锈门锁",
                    "affordances": ["撬锁", "观察"],
                    "risk": "撬锁会制造金属摩擦声",
                }
            ]
        }
    )

    action = IsekaiActionParser(IsekaiTimeService()).parse("强行撬锁", scene)

    assert action.action_type == "force_open"
    assert action.target_id == "rusty_lock_01"
    assert action.arguments["style"] == "forceful"
