from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_locations import IsekaiLocationService


def test_location_service_builds_structured_town_and_inn_path():
    service = IsekaiLocationService()

    path = service.path_for("inn_front_hall")

    assert path == {
        "region": "灰石镇",
        "site": "旧炉旅店",
        "sublocation": "前厅",
        "node_id": "inn_front_hall",
        "parent_id": "old_furnace_inn",
        "display_name": "灰石镇 / 旧炉旅店 / 前厅",
    }


def test_location_service_validates_adjacency_and_refreshes_interactables():
    service = IsekaiLocationService()
    scene = SceneState(
        location="灰石镇 / 旧炉旅店 / 前厅",
        location_path=service.path_for("inn_front_hall"),
        environment="旧炉旅店前厅里有店主、火塘和通往后厨的窄门。",
        important_objects=["店主", "火塘", "后厨门"],
        npcs=["店主"],
        current_objective="拿到今晚的落脚身份。",
        interactables=[],
    )

    moved = service.move(scene, "inn_kitchen")

    assert moved.location == "灰石镇 / 旧炉旅店 / 后厨"
    assert moved.location_path["node_id"] == "inn_kitchen"
    assert {entry["id"] for entry in moved.interactables} == {"broken_pot_handle", "kitchen_exit"}
    assert moved.suggested_actions == ["修好松动锅把", "回到前厅"]


def test_location_service_blocks_non_adjacent_node():
    service = IsekaiLocationService()
    scene = SceneState(
        location="灰石镇 / 旧炉旅店 / 前厅",
        location_path=service.path_for("inn_front_hall"),
        environment="旧炉旅店前厅。",
        current_objective="拿到今晚的落脚身份。",
    )

    assert service.can_move(scene, "town_gate") is False
