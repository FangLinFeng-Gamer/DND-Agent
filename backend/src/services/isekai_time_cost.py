from __future__ import annotations

from typing import Any


class IsekaiTimeCostService:
    def minutes(
        self,
        action_type: str,
        arguments: dict[str, Any] | None = None,
        environment_modifiers: dict[str, Any] | None = None,
    ) -> int:
        args = arguments or {}
        modifiers = environment_modifiers or {}
        scope = str(args.get("scope") or "")
        intensity = str(args.get("intensity") or args.get("style") or "normal")
        base = self._base(action_type, scope)
        if intensity in {"careful", "谨慎"}:
            base += 5 if action_type in {"repair", "search", "eat_meal"} else 2
        elif intensity in {"quick", "快速"}:
            base = max(1, base - 3)
        if modifiers.get("dark"):
            base += 5
        if modifiers.get("crowded") and action_type in {"travel", "search", "enter_location", "leave_location"}:
            base += 3
        return self._clamp_for(action_type, scope, base)

    def _base(self, action_type: str, scope: str) -> int:
        if action_type == "observe":
            return 2
        if action_type in {"enter_location", "leave_location"} and scope == "indoor":
            return 3
        if action_type == "short_dialogue":
            return 8
        if action_type == "negotiate":
            return 12
        if action_type == "repair":
            return 10
        if action_type == "search":
            return 20
        if action_type == "eat_meal":
            return 20
        if action_type == "travel" and scope == "town":
            return 15
        if action_type == "travel" and scope == "wilderness":
            return 75
        return 10

    def _clamp_for(self, action_type: str, scope: str, value: int) -> int:
        ranges = {
            ("observe", ""): (1, 3),
            ("enter_location", "indoor"): (1, 5),
            ("leave_location", "indoor"): (1, 5),
            ("short_dialogue", ""): (5, 10),
            ("negotiate", ""): (10, 15),
            ("repair", "indoor"): (10, 20),
            ("search", "room"): (15, 35),
            ("eat_meal", ""): (15, 30),
            ("travel", "town"): (10, 20),
            ("travel", "wilderness"): (60, 90),
        }
        low, high = ranges.get((action_type, scope), ranges.get((action_type, ""), (1, 90)))
        return max(low, min(high, int(value)))
