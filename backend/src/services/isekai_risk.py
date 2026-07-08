from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IsekaiRiskResult:
    deltas: dict[str, int] = field(default_factory=dict)
    summary: str = ""
    tags: list[str] = field(default_factory=list)


class IsekaiRiskService:
    def assess(self, action: Any, survival: dict[str, Any] | None = None) -> IsekaiRiskResult:
        action_type = str(getattr(action, "action_type", "") or "")
        arguments = getattr(action, "arguments", {}) or {}
        style = str(arguments.get("style") or "normal")
        time_of_day = str((survival or {}).get("time_of_day") or "")
        night = time_of_day in {"夜晚", "深夜"}
        deltas = {"noise": 0, "danger": 0, "exposure": 0, "opportunity": 0}
        tags: list[str] = []
        summary = "风险没有明显变化。"

        if action_type == "approach":
            if style == "careful":
                deltas.update({"danger": -1, "opportunity": -1})
                summary = "你放慢动作确认落脚点，风险降低，但夜色和机会窗口被消耗。"
                tags = ["risk_down", "opportunity_cost"]
            elif style == "quiet":
                deltas.update({"noise": -1, "danger": 0, "opportunity": -1})
                summary = "你压低声响靠近，暴露机会减少，但耗掉了观察窗口。"
                tags = ["quiet", "opportunity_cost"]
            elif style == "quick":
                deltas.update({"noise": 1, "danger": 1, "opportunity": 1})
                summary = "你快速靠近，抢到时间，但踩响泥水的风险上升。"
                tags = ["quick", "risk_up"]
            else:
                deltas.update({"danger": 1 if night else 0})
                summary = "你靠近目标，距离变化让后续互动更直接。"
                tags = ["position"]
        elif action_type in {"hide", "avoid"}:
            deltas.update({"noise": -1, "exposure": -2, "opportunity": -1})
            summary = "你降低声响并避开视线，暴露降低，但放弃了直接推进的机会。"
            tags = ["stealth", "exposure_down"]
        elif action_type == "force_open":
            deltas.update({"noise": 3, "danger": 2 + (1 if night else 0), "opportunity": 1})
            summary = "你强行处理障碍，速度更快，但制造声响并提高危险。"
            tags = ["noise", "risk_up"]
        elif action_type == "search":
            deltas.update({"noise": 1, "danger": 1 if night else 0})
            summary = "你翻找目标，可能发现补给，也可能制造细碎声响。"
            tags = ["search"]
        elif action_type == "travel" and night:
            deltas.update({"danger": 2, "exposure": 1})
            summary = "夜间赶路推进很快，但迷路、野兽和巡逻风险明显上升。"
            tags = ["night_travel", "risk_up"]

        return IsekaiRiskResult(deltas=deltas, summary=summary, tags=tags)
