from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import IsekaiActionParser
from backend.src.services.isekai_action_preconditions import IsekaiActionPreconditionService
from backend.src.services.isekai_time import IsekaiTimeService


def parser():
    return IsekaiActionParser(IsekaiTimeService())


def preconditions():
    return IsekaiActionPreconditionService(IsekaiTimeService())


def scene_without_water():
    return SceneState(
        location="干燥小屋",
        environment="屋内只有木箱和干草，没有任何水源。",
        important_objects=["木箱", "干草"],
        npcs=[],
        current_objective="找水并熬过夜晚。",
        interactables=[
            {"id": "crate_01", "type": "object", "name": "木箱", "affordances": ["搜索"]},
        ],
    )


def scene_with_water():
    return scene_without_water().model_copy(
        update={
            "interactables": [
                {"id": "rain_barrel_01", "type": "water_source", "name": "雨水桶", "affordances": ["装水", "观察"]},
            ]
        }
    )


def blocked_carriage_scene():
    return SceneState(
        location="泥泞旧路",
        environment="侧翻马车陷在泥里，车门被泥土压住，破口太窄。",
        important_objects=["侧翻马车", "车厢", "车厢门", "狭窄破口"],
        npcs=[],
        current_objective="确认车厢内部情况。",
        interactables=[
            {
                "id": "carriage_01",
                "type": "place",
                "name": "车厢",
                "state": "车门被泥土压住，破口太窄",
                "affordances": ["观察", "听动静"],
                "risk": "强行进入可能卡住或制造声响",
            },
            {
                "id": "carriage_door_01",
                "type": "obstacle",
                "name": "车厢门",
                "state": "被泥土压住",
                "affordances": ["撬开", "观察"],
                "risk": "撬开会制造声响",
            },
        ],
    )


def enterable_carriage_scene():
    return blocked_carriage_scene().model_copy(
        update={
            "interactables": [
                {
                    "id": "carriage_01",
                    "type": "place",
                    "name": "车厢",
                    "state": "破口勉强可进入",
                    "affordances": ["进入", "观察"],
                    "risk": "内部可能有陷阱或寄生虫",
                }
            ]
        }
    )


def test_refill_water_without_water_source_fails_without_time():
    action = parser().parse("装水", scene_without_water())

    checked = preconditions().check(action, scene_without_water())

    assert checked.action_type == "condition_failed"
    assert checked.advances_time is False
    assert checked.time_cost_minutes == 0
    assert checked.requires_clarification is False
    assert checked.arguments["failed_precondition"] == "missing_water_source"
    assert "precondition:missing_water_source" in checked.matched_rules


def test_refill_water_with_water_source_passes():
    action = parser().parse("在雨水桶装水", scene_with_water())

    checked = preconditions().check(action, scene_with_water())

    assert checked.action_type == "refill_water"
    assert checked.target_id == "rain_barrel_01"
    assert checked.advances_time is True


def test_enter_location_without_target_fails_without_time():
    action = parser().parse("进入小屋", scene_without_water())

    checked = preconditions().check(action, scene_without_water())

    assert checked.action_type == "condition_failed"
    assert checked.advances_time is False
    assert checked.arguments["failed_precondition"] == "missing_location_target"
    assert "precondition:missing_location_target" in checked.matched_rules


def test_enter_location_blocked_by_scene_physics_returns_alternatives():
    scene = blocked_carriage_scene()
    action = parser().parse("进入车厢", scene)

    checked = preconditions().check(action, scene)

    assert checked.action_type == "condition_failed"
    assert checked.advances_time is False
    assert checked.arguments["failed_precondition"] == "entry_blocked"
    assert checked.arguments["blocked_target"] == "车厢"
    assert checked.arguments["alternatives"] == [
        "从破损处探身查看",
        "撬开木板或车门",
        "绕到另一侧找入口",
        "先听听里面有没有动静",
    ]


def test_enter_location_with_entry_affordance_passes_physical_check():
    scene = enterable_carriage_scene()
    action = parser().parse("进入车厢", scene)

    checked = preconditions().check(action, scene)

    assert checked.action_type == "enter_location"
    assert checked.target_id == "carriage_01"


def test_force_open_requires_obstacle_target():
    action = parser().parse("强行撬开木板", scene_without_water())

    checked = preconditions().check(action, scene_without_water())

    assert checked.action_type == "condition_failed"
    assert checked.arguments["failed_precondition"] == "missing_obstacle_target"
