from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import ParsedIsekaiAction


@dataclass(frozen=True)
class NavigationResult:
    status: str
    navigation_intent: str
    target_node_id: str = ""
    target_name: str = ""
    edge_ids: list[str] = field(default_factory=list)
    reason: str = ""
    alternatives: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "navigation_intent": self.navigation_intent,
            "target_node_id": self.target_node_id,
            "target_name": self.target_name,
            "edge_ids": list(self.edge_ids),
            "reason": self.reason,
            "alternatives": list(self.alternatives),
            "metadata": dict(self.metadata),
        }


class IsekaiSceneNavigationService:
    def resolve(
        self,
        action: ParsedIsekaiAction,
        scene: SceneState,
        world_state: dict[str, Any] | None = None,
    ) -> NavigationResult:
        state = world_state or {}
        current_node_id = self._current_node_id(scene)
        text = self._action_text(action)
        if action.action_type == "leave_location" or self._is_leave_text(text):
            return self._resolve_leave(current_node_id, state)
        if self._is_return_to_settlement(action, text):
            return self._resolve_return_to_known_location(current_node_id, text, state)
        if action.action_type in {"enter_location", "travel"}:
            return self._resolve_direct_movement(action, scene, current_node_id, text, state)
        return NavigationResult(status="not_navigation", navigation_intent="none")

    def _resolve_leave(self, current_node_id: str, world_state: dict[str, Any]) -> NavigationResult:
        edge = self._first_edge(
            world_state,
            current_node_id,
            kinds={"back", "exit", "parent", "leave"},
        )
        if not edge:
            parent_id = str(self._node(world_state, current_node_id).get("parent_node_id") or "")
            if parent_id:
                return NavigationResult(
                    status="resolved",
                    navigation_intent="leave_current_scene",
                    target_node_id=parent_id,
                    reason="parent_node_fallback",
                )
            return NavigationResult(
                status="known_target_unknown_route",
                navigation_intent="leave_current_scene",
                reason="当前场景没有已知出口。",
                alternatives=["观察出口", "搜索来路", "寻找通风或光源方向"],
            )
        if self._edge_blocked(edge):
            return self._blocked(edge, "blocked_navigation")
        return NavigationResult(
            status="resolved",
            navigation_intent="leave_current_scene",
            target_node_id=self._edge_to(edge),
            target_name=str(edge.get("to_name") or ""),
            edge_ids=[str(edge.get("id") or "")],
            reason="matched_back_edge",
            metadata={"edge": dict(edge)},
        )

    def _resolve_return_to_known_location(
        self,
        current_node_id: str,
        text: str,
        world_state: dict[str, Any],
    ) -> NavigationResult:
        candidates = self._known_location_candidates(text, world_state)
        if not candidates:
            return NavigationResult(
                status="unknown_target",
                navigation_intent="seek_destination",
                reason="本局还没有已知聚落或目标地点。",
                alternatives=["寻找道路", "爬到高处观察炊烟", "沿水流寻找人类活动痕迹"],
            )
        if len(candidates) > 1:
            recent = self._most_recent_known_candidate(candidates, world_state)
            if recent:
                candidates = [recent]
            else:
                return NavigationResult(
                    status="ambiguous_target",
                    navigation_intent="clarification",
                    reason="存在多个可能的返回目标。",
                    alternatives=[str(item.get("name") or item.get("node_id") or "") for item in candidates],
                    metadata={"candidates": candidates},
                )
        target = candidates[0]
        target_node_id = str(target.get("node_id") or "")
        route = self._route_between(current_node_id, target_node_id, world_state)
        if route is None:
            return NavigationResult(
                status="known_target_unknown_route",
                navigation_intent="return_to_known_location",
                target_node_id=target_node_id,
                target_name=str(target.get("name") or ""),
                reason="目标已知，但当前没有可回放的路径或路线。",
                alternatives=["寻找道路", "检查来路痕迹", "寻找路牌", "沿溪流辨认方向"],
            )
        blocked = self._blocked_edge_in_route(route, world_state)
        if blocked:
            return self._blocked(blocked, "blocked_navigation")
        return NavigationResult(
            status="resolved",
            navigation_intent="return_to_known_location",
            target_node_id=target_node_id,
            target_name=str(target.get("name") or ""),
            edge_ids=route,
            reason="matched_location_history",
            metadata={"target": dict(target)},
        )

    def _resolve_direct_movement(
        self,
        action: ParsedIsekaiAction,
        scene: SceneState,
        current_node_id: str,
        text: str,
        world_state: dict[str, Any],
    ) -> NavigationResult:
        local_entry = self._scene_entry_target(action, scene, world_state)
        if local_entry:
            return local_entry
        if action.action_type == "enter_location" and action.target_id:
            return NavigationResult(status="not_navigation", navigation_intent="none")
        if action.action_type == "travel" and not self._has_specific_travel_target(action, text):
            return NavigationResult(status="not_navigation", navigation_intent="none")
        target_node_id = str(action.arguments.get("target_node_id") or "")
        if not target_node_id:
            target_node_id = self._target_node_from_interactable(action, world_state)
        if not target_node_id:
            target_node_id = self._node_id_for_text(text or action.target_name, world_state)
        if not target_node_id:
            return NavigationResult(
                status="unknown_target",
                navigation_intent="seek_destination" if action.action_type == "travel" else "clarification",
                reason="无法把移动目标绑定到本局场景图。",
                alternatives=["观察可见出口", "查看当前可进入对象", "寻找道路"],
            )
        route = self._route_between(current_node_id, target_node_id, world_state)
        if route is None:
            return NavigationResult(
                status="known_target_unknown_route",
                navigation_intent="travel_to_known_location",
                target_node_id=target_node_id,
                reason="目标存在，但当前没有合法连接路径。",
                alternatives=["寻找道路", "回到上一个已知地点", "检查是否有隐藏入口"],
            )
        blocked = self._blocked_edge_in_route(route, world_state)
        if blocked:
            return self._blocked(blocked, "blocked_navigation")
        return NavigationResult(
            status="resolved",
            navigation_intent="enter_adjacent_location" if action.action_type == "enter_location" else "travel_to_known_location",
            target_node_id=target_node_id,
            edge_ids=route,
            reason="matched_scene_graph_route",
        )

    def _scene_entry_target(self, action: ParsedIsekaiAction, scene: SceneState, world_state: dict[str, Any]) -> NavigationResult | None:
        if action.action_type != "enter_location" or not action.target_id:
            return None
        target = None
        for entry in scene.interactables:
            if isinstance(entry, dict) and str(entry.get("id") or "") == action.target_id:
                target = entry
                break
        if not target:
            return None
        linked_edge = self._known_edge_for_object(world_state, action.target_id)
        if linked_edge:
            return NavigationResult(
                status="resolved",
                navigation_intent="enter_adjacent_location",
                target_node_id=self._edge_to(linked_edge),
                target_name=action.target_name or str(target.get("name") or ""),
                edge_ids=[str(linked_edge.get("id") or "")],
                reason="current_scene_edge_object",
                metadata={"target_id": action.target_id, "edge": dict(linked_edge)},
            )
        target_node_id = str(target.get("target_node_id") or target.get("to_node_id") or "").strip()
        if not target_node_id and any(key in target for key in ["destination_environment", "destination_objects", "destination_scene_objects"]):
            target_node_id = f"scene_object:{action.target_id}"
        affordances = "".join(str(item) for item in target.get("affordances", []))
        if not target_node_id and "进入" in affordances:
            target_node_id = f"scene_object:{action.target_id}"
        if not target_node_id:
            return None
        return NavigationResult(
            status="resolved",
            navigation_intent="enter_adjacent_location",
            target_node_id=target_node_id,
            target_name=action.target_name or str(target.get("name") or ""),
            edge_ids=[],
            reason="current_scene_entry_object",
            metadata={"target_id": action.target_id, "legacy_local_edge": True},
        )

    def _known_edge_for_object(self, world_state: dict[str, Any], object_id: str) -> dict[str, Any] | None:
        for edge in self._edges(world_state):
            if not self._edge_known(edge):
                continue
            if str(edge.get("via_object_id") or "") == object_id:
                return edge
        return None

    def _current_node_id(self, scene: SceneState) -> str:
        return str((scene.location_path or {}).get("node_id") or "").strip()

    def _action_text(self, action: ParsedIsekaiAction) -> str:
        raw = str(action.arguments.get("raw_text") or "").strip()
        if raw:
            return raw
        return " ".join(part for part in [action.target_name, action.reason] if part)

    def _is_leave_text(self, text: str) -> bool:
        return any(word in text for word in ["离开这里", "离开此处", "退出", "出去", "返回上一个地方"])

    def _is_return_to_settlement(self, action: ParsedIsekaiAction, text: str) -> bool:
        if action.action_type not in {"travel", "enter_location", "leave_location"}:
            return False
        return any(word in text for word in ["回城", "回到城镇", "回镇", "回灰", "回铁炉", "回到镇", "回旅店"])

    def _has_specific_travel_target(self, action: ParsedIsekaiAction, text: str) -> bool:
        if action.arguments.get("target_node_id") or action.target_name:
            return True
        return any(word in text for word in ["前往", "去往", "移动到", "走到", "到达", "去"])

    def _known_location_candidates(self, text: str, world_state: dict[str, Any]) -> list[dict[str, Any]]:
        locations = [dict(item) for item in world_state.get("known_locations", []) if isinstance(item, dict)]
        named = [
            item
            for item in locations
            if str(item.get("name") or "").strip() and str(item.get("name") or "").strip() in text
        ]
        if named:
            return named
        if any(word in text for word in ["城镇", "回城", "回镇", "镇"]):
            return [item for item in locations if str(item.get("type") or "") in {"settlement", "town", "village"}]
        return locations

    def _most_recent_known_candidate(
        self,
        candidates: list[dict[str, Any]],
        world_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        candidate_ids = {str(item.get("node_id") or "") for item in candidates}
        history = [entry for entry in world_state.get("location_history", []) if isinstance(entry, dict)]
        for entry in reversed(history):
            for key in ["to_node_id", "from_node_id", "to", "from"]:
                node_id = str(entry.get(key) or "")
                if node_id in candidate_ids:
                    return next(item for item in candidates if str(item.get("node_id") or "") == node_id)
        return None

    def _route_between(self, current_node_id: str, target_node_id: str, world_state: dict[str, Any]) -> list[str] | None:
        if not current_node_id or not target_node_id:
            return None
        if current_node_id == target_node_id:
            return []
        direct = self._direct_edge(current_node_id, target_node_id, world_state)
        if direct:
            return [str(direct.get("id") or "")]
        history = self._history_route(current_node_id, target_node_id, world_state)
        if history is not None:
            return history
        return self._graph_route(current_node_id, target_node_id, world_state)

    def _direct_edge(self, current_node_id: str, target_node_id: str, world_state: dict[str, Any]) -> dict[str, Any] | None:
        for edge in self._edges(world_state):
            if not self._edge_known(edge):
                continue
            if str(edge.get("from_node_id") or "") == current_node_id and self._edge_to(edge) == target_node_id:
                return edge
            if str(edge.get("bidirectional") or "").lower() == "true":
                if str(edge.get("to_node_id") or "") == current_node_id and str(edge.get("from_node_id") or "") == target_node_id:
                    return edge
        return None

    def _history_route(self, current_node_id: str, target_node_id: str, world_state: dict[str, Any]) -> list[str] | None:
        history = [entry for entry in world_state.get("location_history", []) if isinstance(entry, dict)]
        if not history:
            return None
        route: list[str] = []
        cursor = current_node_id
        for entry in reversed(history):
            from_node = str(entry.get("from_node_id") or entry.get("from") or "")
            to_node = str(entry.get("to_node_id") or entry.get("to") or "")
            edge_id = str(entry.get("edge_id") or entry.get("via_edge_id") or "")
            if to_node == cursor:
                route.append(edge_id)
                cursor = from_node
            elif from_node == cursor:
                route.append(edge_id)
                cursor = to_node
            if cursor == target_node_id:
                return route
        return None

    def _graph_route(self, current_node_id: str, target_node_id: str, world_state: dict[str, Any]) -> list[str] | None:
        edges = [edge for edge in self._edges(world_state) if self._edge_known(edge)]
        queue: list[tuple[str, list[str]]] = [(current_node_id, [])]
        seen = {current_node_id}
        while queue:
            node_id, route = queue.pop(0)
            for edge in edges:
                if str(edge.get("from_node_id") or "") != node_id:
                    continue
                next_id = self._edge_to(edge)
                if not next_id or next_id in seen:
                    continue
                next_route = [*route, str(edge.get("id") or "")]
                if next_id == target_node_id:
                    return next_route
                seen.add(next_id)
                queue.append((next_id, next_route))
        return None

    def _first_edge(self, world_state: dict[str, Any], current_node_id: str, kinds: set[str]) -> dict[str, Any] | None:
        for edge in self._edges(world_state):
            if not self._edge_known(edge):
                continue
            if str(edge.get("from_node_id") or "") != current_node_id:
                continue
            if str(edge.get("kind") or edge.get("relation") or "") in kinds:
                return edge
        return None

    def _blocked_edge_in_route(self, edge_ids: list[str], world_state: dict[str, Any]) -> dict[str, Any] | None:
        by_id = {str(edge.get("id") or ""): edge for edge in self._edges(world_state)}
        for edge_id in edge_ids:
            edge = by_id.get(edge_id)
            if edge and self._edge_blocked(edge):
                return edge
        return None

    def _blocked(self, edge: dict[str, Any], intent: str) -> NavigationResult:
        blocked_by = edge.get("blocked_by", [])
        blockers = "、".join(str(item) for item in blocked_by) if isinstance(blocked_by, list) else str(blocked_by or "阻碍")
        return NavigationResult(
            status="blocked_route",
            navigation_intent=intent,
            target_node_id=self._edge_to(edge),
            edge_ids=[str(edge.get("id") or "")],
            reason=f"路径被{blockers}阻断。",
            alternatives=["清理阻碍", "寻找绕路", "观察阻断处", "退回安全位置"],
            metadata={"edge": dict(edge)},
        )

    def _edge_blocked(self, edge: dict[str, Any]) -> bool:
        access = str(edge.get("access") or "open")
        return access in {"blocked", "locked", "closed"} or bool(edge.get("blocked_by"))

    def _edge_known(self, edge: dict[str, Any]) -> bool:
        if edge.get("known_to_player", True) is False:
            return False
        return str(edge.get("access") or "open") != "hidden"

    def _edge_to(self, edge: dict[str, Any]) -> str:
        return str(edge.get("to_node_id") or edge.get("to") or "").strip()

    def _target_node_from_interactable(self, action: ParsedIsekaiAction, world_state: dict[str, Any]) -> str:
        target_id = str(action.target_id or "")
        if not target_id:
            return ""
        for obj in self._objects(world_state):
            if str(obj.get("id") or "") == target_id:
                return str(obj.get("target_node_id") or obj.get("to_node_id") or "").strip()
        return ""

    def _node_id_for_text(self, text: str, world_state: dict[str, Any]) -> str:
        query = str(text or "")
        best = ""
        best_score = 0
        for node in self._nodes(world_state):
            aliases = [str(item) for item in node.get("aliases", []) if str(item).strip()] if isinstance(node.get("aliases"), list) else []
            markers = [
                str(node.get("name") or ""),
                str(node.get("display_name") or ""),
                str(node.get("node_id") or ""),
                *aliases,
            ]
            for marker in markers:
                if marker and marker in query and len(marker) > best_score:
                    best = str(node.get("node_id") or "")
                    best_score = len(marker)
        return best

    def _edges(self, world_state: dict[str, Any]) -> list[dict[str, Any]]:
        graph = world_state.get("scene_graph") if isinstance(world_state.get("scene_graph"), dict) else {}
        edge_sources = [graph.get("edges"), world_state.get("scene_edges")]
        result: list[dict[str, Any]] = []
        for source in edge_sources:
            if isinstance(source, list):
                result.extend(dict(item) for item in source if isinstance(item, dict))
        return result

    def _nodes(self, world_state: dict[str, Any]) -> list[dict[str, Any]]:
        graph = world_state.get("scene_graph") if isinstance(world_state.get("scene_graph"), dict) else {}
        sources = [graph.get("nodes"), world_state.get("scene_nodes")]
        result: list[dict[str, Any]] = []
        for source in sources:
            if isinstance(source, dict):
                result.extend(dict(item) for item in source.values() if isinstance(item, dict))
            elif isinstance(source, list):
                result.extend(dict(item) for item in source if isinstance(item, dict))
        for location in world_state.get("known_locations", []):
            if isinstance(location, dict):
                result.append(dict(location))
        return result

    def _node(self, world_state: dict[str, Any], node_id: str) -> dict[str, Any]:
        for node in self._nodes(world_state):
            if str(node.get("node_id") or "") == node_id:
                return node
        return {}

    def _objects(self, world_state: dict[str, Any]) -> list[dict[str, Any]]:
        objects = world_state.get("scene_objects")
        if isinstance(objects, dict):
            return [dict(item) for item in objects.values() if isinstance(item, dict)]
        if isinstance(objects, list):
            return [dict(item) for item in objects if isinstance(item, dict)]
        return []
