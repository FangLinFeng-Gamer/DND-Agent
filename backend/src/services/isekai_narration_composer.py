from __future__ import annotations

from typing import Any

from backend.src.schemas.adventure import SceneState


class IsekaiNarrationComposer:
    def compose(self, result: Any, scene: SceneState) -> str:
        steps = list(getattr(result, "steps", []) or [])
        action_text = "；".join(str(step.result_text) for step in steps if str(step.result_text).strip())
        time_text = self._time_text(getattr(result, "delta", {}) or {})
        resource_text = self._resource_text(getattr(result, "delta", {}) or {})
        risk_text = self._risk_text(steps)
        interactable_text = self._interactable_text(scene)
        alternatives = self._alternatives_text(steps)
        reward_text = self._reward_text(getattr(result, "delta", {}) or {})
        natural = self._natural_exploration_text(
            action_text,
            time_text,
            resource_text,
            risk_text,
            interactable_text,
            getattr(result, "delta", {}) or {},
        )
        if natural:
            return natural
        if alternatives:
            action_text = f"{action_text} 可替代做法：{alternatives}"
        return (
            f"行动结果：{action_text or '你确认了当前意图，但还没有产生可执行动作。'}"
            f" 时间变化：{time_text}"
            f" 资源变化：{resource_text}"
            f" 风险变化：{risk_text}"
            f" 奖励与权益：{reward_text}"
            f" 新的可互动内容：{interactable_text}"
        )

    def _natural_exploration_text(
        self,
        action_text: str,
        time_text: str,
        resource_text: str,
        risk_text: str,
        interactable_text: str,
        delta: dict[str, Any],
    ) -> str:
        if delta.get("narration_style") != "exploration_discovery":
            return ""
        parts = [action_text]
        if time_text and time_text != "没有推进时间。":
            parts.append(f"时间变化：{time_text}")
        if resource_text and resource_text != "没有明显资源变化。":
            parts.append(f"资源变化：{resource_text}。")
        if risk_text and risk_text != "风险没有明显变化。":
            parts.append(f"风险变化：{risk_text}")
        if interactable_text:
            parts.append(f"现在你可以继续查看：{interactable_text}。")
        return " ".join(part.strip() for part in parts if part.strip())

    def _time_text(self, delta: dict[str, Any]) -> str:
        minutes = int(delta.get("time_cost_minutes", 0))
        if minutes <= 0:
            return "没有推进时间。"
        return " ".join(str(event) for event in delta.get("visible_events", []) if str(event).strip()) or f"时间推进了约 {minutes} 分钟。"

    def _resource_text(self, delta: dict[str, Any]) -> str:
        parts = [str(item) for item in delta.get("inventory_changes", []) if str(item).strip()]
        hp_delta = int(delta.get("hp_delta", 0))
        if hp_delta:
            parts.append(f"HP{hp_delta:+d}")
        survival_parts: list[str] = []
        for key, label in {
            "hunger": "饱腹压力",
            "thirst": "口渴压力",
            "fatigue": "疲劳",
            "sleep_need": "睡眠需求",
            "morale": "士气",
        }.items():
            value = int(delta.get(key, 0))
            if value:
                survival_parts.append(f"{label}{value:+d}")
        parts.extend(survival_parts)
        return "，".join(parts) if parts else "没有明显资源变化。"

    def _reward_text(self, delta: dict[str, Any]) -> str:
        parts: list[str] = []
        parts.extend(str(item) for item in delta.get("rewards", []) if str(item).strip())
        for entitlement in delta.get("entitlements", []):
            if isinstance(entitlement, dict):
                name = str(entitlement.get("name") or "").strip()
                valid_until = str(entitlement.get("valid_until") or "").strip()
                if name:
                    parts.append(f"{name}（有效期：{valid_until or '未注明'}）")
        for clue in delta.get("clues", []):
            if str(clue).strip():
                parts.append(f"线索：{clue}")
        shortfall = delta.get("shortfall_copper")
        if isinstance(shortfall, int) and shortfall > 0:
            parts.append(f"还差 {shortfall} 铜")
        return "，".join(parts) if parts else "没有新的权益或线索。"

    def _risk_text(self, steps: list[Any]) -> str:
        summaries = [
            str(getattr(getattr(step, "risk", None), "summary", "") or "").strip()
            for step in steps
            if str(getattr(getattr(step, "risk", None), "summary", "") or "").strip()
        ]
        return "；".join(summaries) if summaries else "风险没有明显变化。"

    def _interactable_text(self, scene: SceneState) -> str:
        names = [str(entry.get("name") or "").strip() for entry in scene.interactables if isinstance(entry, dict)]
        names = [name for name in names if name]
        if names:
            return "、".join(names[:6])
        if scene.important_objects:
            return "、".join(scene.important_objects[:6])
        return "暂时没有明确对象，可以继续观察。"

    def _alternatives_text(self, steps: list[Any]) -> str:
        alternatives: list[str] = []
        for step in steps:
            alternatives.extend(str(item) for item in getattr(step, "alternatives", []) if str(item).strip())
        return "、".join(dict.fromkeys(alternatives))
