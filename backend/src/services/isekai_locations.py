from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_content import IsekaiContentService


@dataclass(frozen=True)
class IsekaiLocationNode:
    node_id: str
    region: str
    site: str
    sublocation: str
    parent_id: str
    environment: str
    aliases: list[str] = field(default_factory=list)
    objective: str = ""
    important_objects: list[str] = field(default_factory=list)
    interactables: list[dict[str, Any]] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    neighbors: list[str] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)


class IsekaiLocationService:
    def __init__(self, content: IsekaiContentService | None = None, world_state: dict[str, Any] | None = None):
        self.content = content or IsekaiContentService()
        self.nodes = self._nodes(world_state)

    def for_world_state(self, world_state: dict[str, Any] | None = None) -> "IsekaiLocationService":
        return IsekaiLocationService(self.content, world_state)

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
        query = str(text or "")
        best_node = ""
        best_score = 0
        for node in self.nodes.values():
            for marker in self._node_markers(node):
                if marker and marker in query and len(marker) > best_score:
                    best_node = node.node_id
                    best_score = len(marker)
        return best_node or current_node_id

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

    def scene_for(self, node_id: str, current_objective: str = "") -> SceneState:
        node = self.nodes[node_id]
        path = self.path_for(node_id)
        return SceneState(
            location=path["display_name"],
            location_path=path,
            environment=node.environment,
            important_objects=list(node.important_objects),
            npcs=list(node.npcs),
            current_objective=current_objective or self._objective(node_id),
            interactables=[dict(item) for item in node.interactables],
            suggested_actions=list(node.suggested_actions),
        )

    def _objective(self, node_id: str) -> str:
        node = self.nodes.get(node_id)
        return (node.objective if node else "") or "确认当前位置的可互动对象。"

    def _node_markers(self, node: IsekaiLocationNode) -> list[str]:
        markers = [
            node.region,
            node.site,
            node.sublocation,
            " / ".join(part for part in [node.region, node.site, node.sublocation] if part),
            *node.aliases,
        ]
        return sorted({str(marker).strip() for marker in markers if str(marker).strip()}, key=len, reverse=True)

    def _nodes(self, world_state: dict[str, Any] | None = None) -> dict[str, IsekaiLocationNode]:
        nodes: dict[str, IsekaiLocationNode] = {}
        for node_id, payload in self.content.location_nodes(world_state).items():
            nodes[node_id] = IsekaiLocationNode(
                node_id=str(payload.get("node_id") or node_id),
                region=str(payload.get("region") or ""),
                site=str(payload.get("site") or ""),
                sublocation=str(payload.get("sublocation") or ""),
                parent_id=str(payload.get("parent_id") or ""),
                environment=str(payload.get("environment") or ""),
                aliases=[str(item) for item in payload.get("aliases", [])],
                objective=str(payload.get("objective") or ""),
                important_objects=[str(item) for item in payload.get("important_objects", [])],
                interactables=[dict(item) for item in payload.get("interactables", []) if isinstance(item, dict)],
                suggested_actions=[str(item) for item in payload.get("suggested_actions", [])],
                neighbors=[str(item) for item in payload.get("neighbors", [])],
                npcs=[str(item) for item in payload.get("npcs", [])],
            )
        return nodes
