from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.src.schemas.adventure import SceneState


@dataclass(frozen=True)
class IsekaiLocationNode:
    node_id: str
    region: str
    site: str
    sublocation: str
    parent_id: str
    environment: str
    important_objects: list[str] = field(default_factory=list)
    interactables: list[dict[str, Any]] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    neighbors: list[str] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)


class IsekaiLocationService:
    def __init__(self):
        self.nodes = self._nodes()

    def path_for(self, node_id: str) -> dict[str, str]:
        node = self.nodes[node_id]
        display = " / ".join(part for part in [node.region, node.site, node.sublocation] if part)
        return {
            "region": node.region,
            "site": node.site,
            "sublocation": node.sublocation,
            "node_id": node.node_id,
            "parent_id": node.parent_id,
            "display_name": display,
        }

    def node_id_for_text(self, text: str, current_node_id: str = "") -> str:
        lowered = str(text or "")
        if "灰石镇" in lowered and "旅店" not in lowered:
            return "graystone_town"
        if "旧炉旅店" in lowered or "旅店前厅" in lowered or "前厅" in lowered:
            return "inn_front_hall"
        if "后厨" in lowered or "厨房" in lowered:
            return "inn_kitchen"
        if "客房" in lowered or "三号房" in lowered or "二楼" in lowered:
            return "inn_room_3"
        if "马厩" in lowered:
            return "inn_stable"
        return current_node_id

    def can_move(self, scene: SceneState, target_node_id: str) -> bool:
        current = str((scene.location_path or {}).get("node_id") or "")
        if not current:
            return True
        if current not in self.nodes:
            return True
        return target_node_id in self.nodes.get(current, IsekaiLocationNode("", "", "", "", "", "")).neighbors

    def move(self, scene: SceneState, target_node_id: str) -> SceneState:
        if target_node_id not in self.nodes:
            return scene
        if not self.can_move(scene, target_node_id):
            return scene
        node = self.nodes[target_node_id]
        path = self.path_for(target_node_id)
        return scene.model_copy(
            update={
                "location": path["display_name"],
                "location_path": path,
                "environment": node.environment,
                "important_objects": list(node.important_objects),
                "npcs": list(node.npcs),
                "current_objective": self._objective(target_node_id),
                "interactables": [dict(item) for item in node.interactables],
                "suggested_actions": list(node.suggested_actions),
            }
        )

    def scene_for(self, node_id: str, current_objective: str = "拿到今晚的落脚身份。") -> SceneState:
        node = self.nodes[node_id]
        path = self.path_for(node_id)
        return SceneState(
            location=path["display_name"],
            location_path=path,
            environment=node.environment,
            important_objects=list(node.important_objects),
            npcs=list(node.npcs),
            current_objective=current_objective,
            interactables=[dict(item) for item in node.interactables],
            suggested_actions=list(node.suggested_actions),
        )

    def _objective(self, node_id: str) -> str:
        return {
            "graystone_town": "在日落前找到能承认你身份的落脚点。",
            "inn_front_hall": "和店主谈妥住宿、食物或可交换的帮助。",
            "inn_kitchen": "确认能否通过修好锅把换取住宿权益。",
            "inn_room_3": "确认床位、钥匙和夜间安全。",
            "inn_stable": "查看马厩是否适合暂避或听取夜间动静。",
        }.get(node_id, "确认当前位置的可互动对象。")

    def _nodes(self) -> dict[str, IsekaiLocationNode]:
        return {
            "graystone_town": IsekaiLocationNode(
                node_id="graystone_town",
                region="灰石镇",
                site="镇门街",
                sublocation="",
                parent_id="graystone_region",
                environment="雨后的灰石镇门街挤着商队和巡逻民兵，旧炉旅店的招牌在前方冒着煤烟。",
                important_objects=["旧炉旅店", "巡逻民兵", "泥水街道"],
                interactables=[
                    {"id": "old_furnace_inn", "type": "place", "name": "旧炉旅店", "affordances": ["进入", "观察"]},
                    {"id": "town_notice", "type": "object", "name": "宵禁告示", "affordances": ["观察"]},
                ],
                suggested_actions=["进入旧炉旅店前厅", "查看宵禁告示"],
                neighbors=["inn_front_hall"],
            ),
            "inn_front_hall": IsekaiLocationNode(
                node_id="inn_front_hall",
                region="灰石镇",
                site="旧炉旅店",
                sublocation="前厅",
                parent_id="old_furnace_inn",
                environment="旧炉旅店前厅低矮温热，火塘边有几名旅人，店主站在柜台后打量外来者。",
                important_objects=["店主", "火塘", "后厨门", "二楼木梯"],
                npcs=["店主"],
                interactables=[
                    {
                        "id": "innkeeper_01",
                        "type": "npc",
                        "name": "店主",
                        "state": "戒备",
                        "affordances": ["交涉", "询问价格", "支付"],
                        "risk": "外来者身份会让报价更硬",
                    },
                    {"id": "kitchen_door", "type": "place", "name": "后厨", "affordances": ["进入", "观察"]},
                    {"id": "room_stairs", "type": "place", "name": "二楼客房", "affordances": ["进入", "观察"]},
                ],
                suggested_actions=["和店主讨价还价", "去后厨看看能否帮忙", "支付铜币买床位"],
                neighbors=["graystone_town", "inn_kitchen", "inn_room_3", "inn_stable"],
            ),
            "inn_kitchen": IsekaiLocationNode(
                node_id="inn_kitchen",
                region="灰石镇",
                site="旧炉旅店",
                sublocation="后厨",
                parent_id="old_furnace_inn",
                environment="后厨蒸汽贴着低梁翻滚，一只炖锅的锅把松脱，厨娘焦急地护着炉火。",
                important_objects=["松动锅把", "炖锅", "炉火"],
                npcs=["厨娘"],
                interactables=[
                    {
                        "id": "broken_pot_handle",
                        "type": "object",
                        "name": "松动锅把",
                        "affordances": ["修理", "观察"],
                        "risk": "拖太久会耽误晚餐，店主会失去耐心",
                    },
                    {"id": "kitchen_exit", "type": "place", "name": "前厅", "affordances": ["进入", "离开"]},
                ],
                suggested_actions=["修好松动锅把", "回到前厅"],
                neighbors=["inn_front_hall"],
            ),
            "inn_room_3": IsekaiLocationNode(
                node_id="inn_room_3",
                region="灰石镇",
                site="旧炉旅店",
                sublocation="二楼三号房",
                parent_id="old_furnace_inn",
                environment="二楼三号房狭窄但干燥，床架上铺着粗毯，窗外能听见镇墙方向的犬吠。",
                important_objects=["床位", "粗毯", "小窗"],
                interactables=[
                    {"id": "inn_room_3_bed", "type": "entitlement", "name": "二楼三号房床位", "affordances": ["休息", "睡觉"]},
                    {"id": "small_window", "type": "place", "name": "小窗", "affordances": ["观察"]},
                ],
                suggested_actions=["检查床位", "从小窗听夜里动静"],
                neighbors=["inn_front_hall"],
            ),
            "inn_stable": IsekaiLocationNode(
                node_id="inn_stable",
                region="灰石镇",
                site="旧炉旅店",
                sublocation="马厩",
                parent_id="old_furnace_inn",
                environment="马厩里铺着潮草，牲口不安地刨地，外墙缝里传来远处低嚎。",
                important_objects=["潮草", "外墙缝", "不安的马"],
                interactables=[
                    {"id": "stable_wall_gap", "type": "place", "name": "外墙缝", "affordances": ["观察", "聆听"]},
                ],
                suggested_actions=["听听外墙外的动静", "回到前厅"],
                neighbors=["inn_front_hall"],
            ),
        }
