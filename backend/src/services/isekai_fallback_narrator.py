from __future__ import annotations

from typing import Any

from backend.src.schemas.adventure import SceneState


class IsekaiFallbackNarrator:
    def narrate(
        self,
        player_input: str,
        scene: SceneState,
        character: dict[str, Any],
        survival: dict[str, Any],
        delta: dict[str, Any],
    ) -> str:
        action_result = self._action_result(player_input, scene)
        time_text = " ".join(delta.get("visible_events") or []) or "这次行动没有明显消耗时间。"
        survival_text = self._survival_text(delta)
        interactables = self._interactable_text(scene)
        return (
            f"行动结果：{action_result}"
            f" 时间消耗：{time_text}"
            f" 环境反馈：{scene.environment}"
            f" 生存变化：{survival_text}"
            f" 可互动对象：{interactables}"
        )

    def _action_result(self, player_input: str, scene: SceneState) -> str:
        text = str(player_input or "行动").strip()
        return f"你在{scene.location}尝试{text}，周围的异界气息让每个选择都显得更谨慎。"

    def _survival_text(self, delta: dict[str, Any]) -> str:
        parts: list[str] = []
        mapping = {
            "hunger": "饱腹压力",
            "thirst": "口渴压力",
            "fatigue": "疲劳",
            "sleep_need": "睡眠需求",
            "morale": "士气",
        }
        for key, label in mapping.items():
            value = int(delta.get(key, 0))
            if value > 0:
                parts.append(f"{label}+{value}")
            elif value < 0:
                parts.append(f"{label}{value}")
        inventory_changes = [str(item) for item in delta.get("inventory_changes", []) if str(item).strip()]
        parts.extend(inventory_changes)
        return "，".join(parts) if parts else "没有明显数值变化。"

    def _interactable_text(self, scene: SceneState) -> str:
        names = [str(entry.get("name") or "").strip() for entry in scene.interactables if isinstance(entry, dict)]
        names = [name for name in names if name]
        if names:
            return "、".join(names[:6])
        if scene.important_objects:
            return "、".join(scene.important_objects[:6])
        return "暂时没有明确对象，可以继续观察或搜索。"
