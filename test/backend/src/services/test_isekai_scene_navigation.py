from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import ParsedIsekaiAction
from backend.src.services.isekai_scene_navigation import IsekaiSceneNavigationService


def make_action(action_type: str, text: str = "", **arguments) -> ParsedIsekaiAction:
    return ParsedIsekaiAction(
        action_type=action_type,
        time_cost_minutes=10,
        advances_time=True,
        survival_intent="move",
        reason="move",
        arguments={"raw_text": text, **arguments},
    )


def make_scene(node_id: str = "mine_entrance") -> SceneState:
    return SceneState(
        location="铁炉镇外 / 旧矿道入口",
        location_path={"node_id": node_id, "display_name": "铁炉镇外 / 旧矿道入口"},
        environment="旧矿道入口有一条回到林间小路的旧路。",
        current_objective="确认路线。",
        interactables=[],
    )


def test_leave_current_scene_uses_back_edge():
    world_state = {
        "scene_graph": {
            "edges": [
                {
                    "id": "edge_mine_to_path",
                    "from_node_id": "mine_entrance",
                    "to_node_id": "forest_path",
                    "kind": "back",
                    "access": "open",
                }
            ]
        }
    }

    result = IsekaiSceneNavigationService().resolve(
        make_action("leave_location", "离开这里"),
        make_scene(),
        world_state,
    )

    assert result.status == "resolved"
    assert result.navigation_intent == "leave_current_scene"
    assert result.target_node_id == "forest_path"
    assert result.edge_ids == ["edge_mine_to_path"]


def test_return_to_known_settlement_uses_location_history():
    world_state = {
        "known_locations": [{"node_id": "grey_oak_gate", "name": "灰橡镇", "type": "settlement"}],
        "location_history": [
            {"from_node_id": "grey_oak_gate", "to_node_id": "forest_path", "edge_id": "edge_town_to_path"},
            {"from_node_id": "forest_path", "to_node_id": "mine_entrance", "edge_id": "edge_path_to_mine"},
        ],
    }

    result = IsekaiSceneNavigationService().resolve(
        make_action("travel", "回到城镇"),
        make_scene(),
        world_state,
    )

    assert result.status == "resolved"
    assert result.navigation_intent == "return_to_known_location"
    assert result.target_node_id == "grey_oak_gate"
    assert result.edge_ids == ["edge_path_to_mine", "edge_town_to_path"]


def test_unknown_settlement_becomes_seek_destination():
    result = IsekaiSceneNavigationService().resolve(
        make_action("travel", "回到城镇"),
        make_scene(),
        {},
    )

    assert result.status == "unknown_target"
    assert result.navigation_intent == "seek_destination"
    assert "寻找道路" in result.alternatives


def test_blocked_edge_returns_blocked_route():
    world_state = {
        "scene_graph": {
            "edges": [
                {
                    "id": "edge_mine_to_path",
                    "from_node_id": "mine_entrance",
                    "to_node_id": "forest_path",
                    "kind": "back",
                    "access": "blocked",
                    "blocked_by": ["塌方"],
                }
            ]
        }
    }

    result = IsekaiSceneNavigationService().resolve(
        make_action("leave_location", "离开这里"),
        make_scene(),
        world_state,
    )

    assert result.status == "blocked_route"
    assert result.navigation_intent == "blocked_navigation"
    assert "清理阻碍" in result.alternatives


def test_hidden_edge_cannot_be_used_until_revealed():
    world_state = {
        "scene_graph": {
            "nodes": [
                {"node_id": "mine_entrance", "name": "旧矿道入口"},
                {"node_id": "hidden_drainage", "name": "隐藏排水道", "known_to_player": False},
            ],
            "edges": [
                {
                    "id": "edge_slope_to_drainage",
                    "from_node_id": "mine_entrance",
                    "to_node_id": "hidden_drainage",
                    "access": "hidden",
                    "known_to_player": False,
                }
            ],
        }
    }

    hidden = IsekaiSceneNavigationService().resolve(
        make_action("enter_location", "进入侧缝", target_node_id="hidden_drainage"),
        make_scene(),
        world_state,
    )

    assert hidden.status == "known_target_unknown_route"

    world_state["scene_graph"]["edges"][0]["access"] = "open"
    world_state["scene_graph"]["edges"][0]["known_to_player"] = True
    revealed = IsekaiSceneNavigationService().resolve(
        make_action("enter_location", "进入侧缝", target_node_id="hidden_drainage"),
        make_scene(),
        world_state,
    )

    assert revealed.status == "resolved"
    assert revealed.target_node_id == "hidden_drainage"
