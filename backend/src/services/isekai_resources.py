from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.src.services.isekai_inventory import consume_waterskin_charge, refill_waterskins
from backend.src.services.isekai_time import IsekaiActionResolution


@dataclass(frozen=True)
class IsekaiResourceResult:
    character: dict[str, Any]
    delta: dict[str, Any]


class IsekaiResourceService:
    def apply(
        self,
        character: dict[str, Any],
        survival: dict[str, Any],
        action: IsekaiActionResolution,
        player_input: str,
    ) -> IsekaiResourceResult:
        updated = dict(character)
        inventory = [str(item) for item in updated.get("inventory", [])]
        status_effects = [str(effect) for effect in updated.get("status_effects", [])]
        changes: list[str] = []

        if action.action_type == "drink_water":
            inventory, change = self._consume_water(inventory)
            changes.append(change)
        elif action.action_type == "eat_food":
            inventory, change = self._consume_ration(inventory)
            changes.append(change)
        elif action.action_type == "refill_water":
            inventory, change = self._refill_water(inventory)
            changes.append(change)
        elif action.action_type == "eat_drink":
            text = str(player_input or "")
            if self._wants_food(text):
                inventory, change = self._consume_ration(inventory)
                changes.append(change)
            if self._wants_water(text):
                inventory, change = self._consume_water(inventory)
                changes.append(change)

        hp_delta, status_effects, added, removed = self._pressure_consequences(
            survival,
            status_effects,
            applies_damage=action.advances_time,
        )
        hp_current = max(0, int(updated.get("hp_current", 0)) + hp_delta)
        updated["hp_current"] = hp_current
        updated["inventory"] = inventory
        updated["status_effects"] = status_effects

        return IsekaiResourceResult(
            character=updated,
            delta={
                "hp_delta": hp_delta,
                "inventory_changes": [change for change in changes if change],
                "status_effects_added": added,
                "status_effects_removed": removed,
            },
        )

    def _wants_food(self, text: str) -> bool:
        return any(word in text for word in ["吃", "干粮", "食物", "饭", "eat", "food"])

    def _wants_water(self, text: str) -> bool:
        return any(word in text for word in ["喝", "饮", "水", "drink", "water"])

    def _consume_ration(self, inventory: list[str]) -> tuple[list[str], str]:
        result = list(inventory)
        for index, item in enumerate(result):
            if not item.startswith("干粮"):
                continue
            count = self._item_count(item, default=1)
            if count <= 1:
                result.pop(index)
            else:
                result[index] = f"干粮 x{count - 1}"
            return result, "消耗干粮 x1"
        return result, "没有可用干粮"

    def _consume_water(self, inventory: list[str]) -> tuple[list[str], str]:
        return consume_waterskin_charge(inventory)

    def _refill_water(self, inventory: list[str]) -> tuple[list[str], str]:
        return refill_waterskins(inventory)

    def _item_count(self, item: str, default: int) -> int:
        match = re.search(r"x\s*(\d+)", item)
        if not match:
            return default
        return max(0, int(match.group(1)))

    def _pressure_consequences(
        self,
        survival: dict[str, Any],
        status_effects: list[str],
        applies_damage: bool,
    ) -> tuple[int, list[str], list[str], list[str]]:
        effects = list(dict.fromkeys(status_effects))
        added: list[str] = []
        removed: list[str] = []
        hp_delta = 0

        rules = [
            ("饥饿虚弱", int(survival.get("hunger", 0)), 90, 70, -1),
            ("脱水", int(survival.get("thirst", 0)), 90, 70, -2),
            ("极度疲劳", max(int(survival.get("fatigue", 0)), int(survival.get("sleep_need", 0))), 90, 70, -1),
        ]
        for effect, value, high, safe, damage in rules:
            if value >= high:
                if effect not in effects:
                    effects.append(effect)
                    added.append(effect)
                if applies_damage:
                    hp_delta += damage
            elif value < safe and effect in effects:
                effects.remove(effect)
                removed.append(effect)

        return hp_delta, effects, added, removed
