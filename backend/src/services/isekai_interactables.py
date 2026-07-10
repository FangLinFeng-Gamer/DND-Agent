from __future__ import annotations

from typing import Any

from backend.src.schemas.adventure import SceneState


class IsekaiInteractableProjector:
    def project(self, scene: SceneState, action_type: str) -> tuple[list[dict[str, object]], list[str]]:
        interactables = [self._visible(entry) for entry in scene.interactables if self._is_current_visible(entry)]
        suggested = self._suggestions(interactables, action_type)
        return interactables[:6], suggested[:5]

    def _is_current_visible(self, entry: Any) -> bool:
        if not isinstance(entry, dict):
            return False
        visibility = str(entry.get("visibility") or "visible")
        presence = str(entry.get("presence") or "current")
        scope = str(entry.get("scope") or "current_node")
        return visibility != "hidden" and presence in {"", "current"} and scope in {"", "current_node", "scene"}

    def _visible(self, entry: dict[str, Any]) -> dict[str, object]:
        allowed = {
            "id",
            "type",
            "name",
            "aliases",
            "description",
            "state",
            "affordances",
            "risk",
            "tags",
            "source",
            "target_node_id",
            "destination_environment",
            "destination_objects",
            "destination_scene_objects",
        }
        return {key: entry[key] for key in allowed if key in entry}

    def _suggestions(self, interactables: list[dict[str, object]], action_type: str) -> list[str]:
        suggestions: list[str] = []
        for entry in interactables:
            name = str(entry.get("name") or "")
            affordances = [str(item) for item in entry.get("affordances", [])]
            if "观察" in affordances:
                suggestions.append(f"观察{name}")
            if "搜索" in affordances:
                suggestions.append(f"搜索{name}")
            if "解读" in affordances:
                suggestions.append(f"解读{name}")
            if "进入" in affordances:
                suggestions.append(f"进入{name}")
            if "装水" in affordances:
                suggestions.append(f"用水囊在{name}装水")
            if "打开" in affordances:
                suggestions.append(f"打开{name}")
            if "加固" in affordances:
                suggestions.append(f"加固{name}")
            if "堵门" in affordances:
                suggestions.append(f"用{name}堵门")
            if "撬开" in affordances:
                suggestions.append(f"强行撬开{name}")
            if "躲避" in affordances:
                suggestions.append(f"听到动静后躲到{name}")
            if "追踪" in affordances:
                suggestions.append(f"沿着{name}追踪")
            if "离开" in affordances:
                suggestions.append(f"从{name}离开")
        if action_type == "enter_location" and "先听一听屋内动静" not in suggestions:
            suggestions.append("先听一听屋内动静")
        return list(dict.fromkeys(suggestions))
