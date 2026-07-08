from __future__ import annotations

from dataclasses import replace
from typing import Any

from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import ParsedIsekaiAction


class IsekaiActionPreconditionService:
    def __init__(self, time_service: Any):
        self.time = time_service

    def check(self, action: ParsedIsekaiAction, scene: SceneState) -> ParsedIsekaiAction:
        if action.action_type == "refill_water" and not self._has_water_source(action, scene):
            return self._fail(action, "missing_water_source", "附近没有可用水源，不能装水。")
        if action.action_type == "enter_location":
            if not action.target_id and not action.arguments.get("target_node_id"):
                return self._fail(action, "missing_location_target", "需要先明确可进入的地点。")
            if action.target_id and not self._entry_is_possible(action, scene):
                return self._fail(
                    action,
                    "entry_blocked",
                    f"{action.target_name or '目标'}暂时无法直接进入。",
                    {
                        "blocked_target": action.target_name,
                        "alternatives": [
                            "从破损处探身查看",
                            "撬开木板或车门",
                            "绕到另一侧找入口",
                            "先听听里面有没有动静",
                        ],
                    },
                )
        if action.action_type == "force_open" and not self._has_obstacle_target(action, scene):
            return self._fail(action, "missing_obstacle_target", "需要先明确要强行打开的障碍物。")
        return action

    def _has_water_source(self, action: ParsedIsekaiAction, scene: SceneState) -> bool:
        if not action.target_id:
            return False
        for entry in scene.interactables:
            if not isinstance(entry, dict) or str(entry.get("id") or "") != action.target_id:
                continue
            kind = str(entry.get("type") or "")
            affordances = "".join(str(item) for item in entry.get("affordances", []))
            return kind == "water_source" or any(word in affordances for word in ["装水", "取水", "补水"])
        return False

    def _entry_is_possible(self, action: ParsedIsekaiAction, scene: SceneState) -> bool:
        entry = self._interactable(action.target_id, scene)
        if not entry:
            return False
        affordances = "".join(str(item) for item in entry.get("affordances", []))
        if any(word in affordances for word in ["进入", "钻进", "从破口进入"]):
            return True
        state = str(entry.get("state") or "")
        if any(marker in state for marker in ["压住", "太窄", "锁住", "堵住", "塌", "卡住"]):
            return False
        return False

    def _has_obstacle_target(self, action: ParsedIsekaiAction, scene: SceneState) -> bool:
        if not action.target_id:
            return False
        entry = self._interactable(action.target_id, scene)
        if not entry:
            return False
        kind = str(entry.get("type") or "")
        affordances = "".join(str(item) for item in entry.get("affordances", []))
        return kind in {"obstacle", "door", "container", "lock"} or any(
            word in affordances for word in ["撬开", "撬锁", "强行打开", "打开", "破坏"]
        )

    def _interactable(self, target_id: str, scene: SceneState) -> dict[str, Any] | None:
        for entry in scene.interactables:
            if isinstance(entry, dict) and str(entry.get("id") or "") == target_id:
                return entry
        return None

    def _fail(
        self,
        action: ParsedIsekaiAction,
        code: str,
        reason: str,
        extra_arguments: dict[str, Any] | None = None,
    ) -> ParsedIsekaiAction:
        resolution = self.time.resolve_action_type("condition_failed")
        return replace(
            action,
            action_type=resolution.action_type,
            time_cost_minutes=resolution.time_cost_minutes,
            advances_time=resolution.advances_time,
            survival_intent=resolution.survival_intent,
            reason=reason,
            arguments={**action.arguments, "failed_precondition": code, **(extra_arguments or {})},
            confidence="high",
            confidence_reasons=[*action.confidence_reasons, f"precondition:{code}"],
            matched_rules=[*action.matched_rules, f"precondition:{code}"],
            requires_clarification=False,
        )
