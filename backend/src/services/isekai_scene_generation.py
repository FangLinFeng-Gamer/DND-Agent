from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from backend.src.schemas.adventure import SceneState


@dataclass(frozen=True)
class SceneValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SceneGenerationResult:
    success: bool
    payload: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    raw_response: str = ""


class IsekaiSceneValidator:
    def validate(self, payload: dict[str, Any], source_node_id: str = "") -> SceneValidationResult:
        errors: list[str] = []
        if not isinstance(payload, dict):
            return SceneValidationResult(valid=False, errors=["payload must be object"])
        if payload.get("schema_version") != "isekai_scene_node_v1":
            errors.append("schema_version must be isekai_scene_node_v1")
        node = payload.get("node") if isinstance(payload.get("node"), dict) else {}
        node_id = str(node.get("node_id") or "").strip()
        if not node_id:
            errors.append("node.node_id is required")
        object_ids = self._ids([*self._list(payload.get("visible_objects")), *self._list(payload.get("hidden_objects"))])
        duplicate_objects = self._duplicates(object_ids)
        for object_id in duplicate_objects:
            errors.append(f"duplicate object.id: {object_id}")
        stub_ids = {
            str(item.get("node_id") or "").strip()
            for item in self._list(payload.get("node_stubs"))
            if str(item.get("node_id") or "").strip()
        }
        edge_ids = self._ids([*self._list(payload.get("visible_edges")), *self._list(payload.get("hidden_edges"))])
        for edge_id in self._duplicates(edge_ids):
            errors.append(f"duplicate edge.id: {edge_id}")
        valid_to_ids = {node_id, *stub_ids}
        for edge in [*self._list(payload.get("visible_edges")), *self._list(payload.get("hidden_edges"))]:
            edge_id = str(edge.get("id") or "").strip()
            from_node = str(edge.get("from_node_id") or edge.get("from") or "").strip()
            to_node = str(edge.get("to_node_id") or edge.get("to") or "").strip()
            if not edge_id:
                errors.append("edge.id is required")
            if not from_node:
                errors.append(f"edge.from_node_id is required: {edge_id or '<missing>'}")
            elif source_node_id and from_node not in {source_node_id, node_id}:
                errors.append(f"edge.from_node_id must match source/current node: {edge_id}")
            elif node_id and from_node != node_id and not source_node_id:
                errors.append(f"edge.from_node_id must match node.node_id: {edge_id}")
            if not to_node:
                errors.append(f"edge.to_node_id is required: {edge_id or '<missing>'}")
            elif to_node not in valid_to_ids:
                errors.append(f"edge.to_node_id missing node stub: {to_node}")
        for stub in self._list(payload.get("node_stubs")):
            stub_id = str(stub.get("node_id") or "").strip()
            if not stub_id:
                errors.append("node_stub.node_id is required")
            if not str(stub.get("parent_node_id") or node_id).strip():
                errors.append(f"node_stub.parent_node_id is required: {stub_id or '<missing>'}")
        return SceneValidationResult(valid=not errors, errors=errors)

    def _list(self, value: Any) -> list[dict[str, Any]]:
        return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    def _ids(self, items: list[dict[str, Any]]) -> list[str]:
        return [str(item.get("id") or "").strip() for item in items if str(item.get("id") or "").strip()]

    def _duplicates(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for value in values:
            if value in seen and value not in duplicates:
                duplicates.append(value)
            seen.add(value)
        return duplicates


class IsekaiSceneGenerationAgent:
    def __init__(self, model_gateway: Any, validator: IsekaiSceneValidator | None = None):
        self.model_gateway = model_gateway
        self.validator = validator or IsekaiSceneValidator()

    def generate(
        self,
        *,
        adventure_id: int,
        scene: SceneState,
        world_state: dict[str, Any],
        model: Any,
        generation_reason: str,
        player_action: str = "",
    ) -> SceneGenerationResult:
        if model is None:
            return SceneGenerationResult(success=False, errors=["no_active_model"])
        try:
            raw_response = self.model_gateway.chat(
                model,
                self._messages(adventure_id, scene, world_state, generation_reason, player_action),
            )
            payload = self._loads_json_object(raw_response)
        except Exception as exc:
            return SceneGenerationResult(success=False, errors=[str(exc)])
        source_node_id = str((scene.location_path or {}).get("node_id") or "")
        validation = self.validator.validate(payload, source_node_id=source_node_id)
        if not validation.valid:
            return SceneGenerationResult(success=False, payload=payload, errors=validation.errors, raw_response=raw_response)
        return SceneGenerationResult(success=True, payload=payload, raw_response=raw_response)

    def _messages(
        self,
        adventure_id: int,
        scene: SceneState,
        world_state: dict[str, Any],
        generation_reason: str,
        player_action: str,
    ) -> list[dict[str, str]]:
        prompt_payload = {
            "adventure_id": adventure_id,
            "generation_reason": generation_reason,
            "player_action": player_action,
            "current_scene": scene.model_dump(mode="json"),
            "known_locations": world_state.get("known_locations", []),
            "location_history": world_state.get("location_history", []),
            "style_constraints": {
                "genre": "异世界生存探险",
                "avoid": ["普通小镇日常", "现代街边商业感", "无来源地点跳转"],
            },
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是异世界场景生成子 Agent。"
                    "你只生成结构化场景 JSON，不写最终 DM 旁白，不结算资源。"
                    "必须输出 schema_version=isekai_scene_node_v1。"
                    "隐藏区域必须提前以 hidden_edges 和 node_stubs 存在。"
                    "所有 edge.to_node_id 必须能在 node 或 node_stubs 中找到。"
                    "只输出 JSON 对象。"
                ),
            },
            {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
        ]

    def _loads_json_object(self, raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("scene generation payload must be a JSON object")
        return payload


def apply_scene_generation_payload(
    scene: SceneState,
    world_state: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[SceneState, dict[str, Any], dict[str, Any]]:
    node = dict(payload.get("node") or {})
    node_id = str(node.get("node_id") or (scene.location_path or {}).get("node_id") or "").strip()
    path = _location_path(node, node_id, scene)
    visible_objects = _normalized_objects(payload.get("visible_objects"), visible=True)
    hidden_objects = _normalized_objects(payload.get("hidden_objects"), visible=False)
    visible_edges = _normalized_edges(payload.get("visible_edges"), visible=True)
    hidden_edges = _normalized_edges(payload.get("hidden_edges"), visible=False)
    stubs = [dict(item) for item in payload.get("node_stubs", []) if isinstance(item, dict)]
    suggestions = [str(item).strip() for item in payload.get("suggested_actions", []) if str(item).strip()] if isinstance(payload.get("suggested_actions"), list) else []
    next_scene = scene.model_copy(
        update={
            "location": str(path.get("display_name") or scene.location),
            "location_path": path,
            "environment": str(node.get("environment") or scene.environment),
            "important_objects": [str(item.get("name") or item.get("id") or "") for item in visible_objects if str(item.get("name") or item.get("id") or "").strip()],
            "current_objective": str(node.get("current_objective") or node.get("objective") or scene.current_objective),
            "interactables": visible_objects,
            "suggested_actions": list(dict.fromkeys(suggestions))[:8],
        }
    )
    next_world = dict(world_state or {})
    graph = dict(next_world.get("scene_graph") or {})
    graph["nodes"] = _merge_nodes(graph.get("nodes"), [_node_record(node, path, next_scene, visible_objects), *stubs])
    graph["edges"] = _merge_by_id(graph.get("edges"), [*visible_edges, *hidden_edges])
    next_world["scene_graph"] = graph
    next_world["scene_objects"] = _merge_by_id(next_world.get("scene_objects"), [*visible_objects, *hidden_objects])
    content = dict(next_world.get("isekai_content") or {})
    discovery_tables = dict(content.get("discovery_tables") or {})
    for table in payload.get("discovery_tables", []) if isinstance(payload.get("discovery_tables"), list) else []:
        if not isinstance(table, dict):
            continue
        target_id = str(table.get("target_object_id") or "").strip()
        entries = table.get("entries") if isinstance(table.get("entries"), list) else []
        if target_id and entries:
            discovery_tables.setdefault(target_id, []).extend([dict(entry) for entry in entries if isinstance(entry, dict)])
    content["discovery_tables"] = discovery_tables
    next_world["isekai_content"] = content
    metadata = {
        "source": "scene_generation_agent",
        "node_id": node_id,
        "visible_object_ids": [str(item.get("id") or "") for item in visible_objects],
        "hidden_object_ids": [str(item.get("id") or "") for item in hidden_objects],
        "visible_edge_ids": [str(item.get("id") or "") for item in visible_edges],
        "hidden_edge_ids": [str(item.get("id") or "") for item in hidden_edges],
    }
    return next_scene, next_world, metadata


def _location_path(node: dict[str, Any], node_id: str, scene: SceneState) -> dict[str, Any]:
    path = dict(node.get("location_path") or {})
    path.setdefault("node_id", node_id)
    if not path.get("display_name"):
        parts = [str(path.get("region") or node.get("region") or ""), str(path.get("site") or node.get("site") or ""), str(path.get("sublocation") or node.get("sublocation") or "")]
        path["display_name"] = " / ".join(part for part in parts if part) or scene.location
    return path


def _normalized_objects(value: Any, *, visible: bool) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item.setdefault("type", "object")
        item.setdefault("affordances", ["观察"])
        item["visibility"] = "visible" if visible else "hidden"
        item.setdefault("presence", "current")
        objects.append(item)
    return objects


def _normalized_edges(value: Any, *, visible: bool) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item.setdefault("access", "open" if visible else "hidden")
        item["known_to_player"] = bool(item.get("known_to_player", visible))
        edges.append(item)
    return edges


def _node_record(node: dict[str, Any], path: dict[str, Any], scene: SceneState, interactables: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **node,
        "node_id": str(path.get("node_id") or node.get("node_id") or ""),
        "location_path": path,
        "environment": str(node.get("environment") or scene.environment),
        "current_objective": str(node.get("current_objective") or node.get("objective") or scene.current_objective),
        "interactables": [dict(item) for item in interactables],
        "suggested_actions": list(scene.suggested_actions),
        "generation_status": "complete",
    }


def _merge_nodes(existing: Any, additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _merge_by_key(existing, additions, "node_id")


def _merge_by_id(existing: Any, additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _merge_by_key(existing, additions, "id")


def _merge_by_key(existing: Any, additions: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    source_items: list[Any]
    if isinstance(existing, dict):
        source_items = list(existing.values())
    elif isinstance(existing, list):
        source_items = existing
    else:
        source_items = []
    for item in source_items:
        if isinstance(item, dict) and str(item.get(key) or "").strip():
            result[str(item[key])] = dict(item)
    for item in additions:
        if isinstance(item, dict) and str(item.get(key) or "").strip():
            result[str(item[key])] = dict(item)
    return list(result.values())
