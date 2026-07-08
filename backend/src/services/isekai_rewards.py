from __future__ import annotations

from typing import Any

from backend.src.services.isekai_inventory import normalize_waterskins


class IsekaiRewardService:
    def apply(
        self,
        character: dict[str, Any],
        world_state: dict[str, Any],
        reward: dict[str, Any] | None,
        *,
        reason: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        reward = reward if isinstance(reward, dict) else {}
        next_character = dict(character or {})
        next_world = dict(world_state or {})
        economy = self._ensure_economy(next_world.get("isekai_economy"))
        applied = {
            "items_added": [],
            "currency_delta": 0,
            "relationship_delta": [],
            "clues_added": [],
            "entitlements_added": [],
        }

        inventory = [str(item) for item in next_character.get("inventory", [])]
        for item in self._text_list(reward.get("items_added")):
            inventory = self._add_item(inventory, item)
            applied["items_added"].append(item)
        next_character["inventory"] = inventory

        currency_delta = self._int_value(reward.get("currency_delta"))
        if currency_delta:
            current = int(economy["currency"]["copper_total"])
            economy["currency"] = {"copper_total": max(0, current + currency_delta)}
            applied["currency_delta"] = currency_delta
            transaction = {
                "lost": f"{abs(currency_delta)} 铜" if currency_delta < 0 else "0 铜",
                "gained": f"{currency_delta} 铜" if currency_delta > 0 else "",
                "reason": reason,
            }
            economy["transaction_log"] = [*economy.get("transaction_log", []), transaction][-20:]

        entitlements = [dict(item) for item in economy.get("entitlements", []) if isinstance(item, dict)]
        for entitlement in self._dict_list(reward.get("entitlements_added")):
            entitlements = [item for item in entitlements if item.get("id") != entitlement.get("id")]
            entitlements.append(entitlement)
            applied["entitlements_added"].append(entitlement)
        economy["entitlements"] = entitlements[-12:]

        relationship_changes = [dict(item) for item in economy.get("relationship_changes", []) if isinstance(item, dict)]
        for relationship in self._dict_list(reward.get("relationship_delta")):
            relationship_changes.append(relationship)
            applied["relationship_delta"].append(relationship)
        economy["relationship_changes"] = relationship_changes[-12:]

        clues = [str(item) for item in next_world.get("isekai_clues", []) if str(item).strip()]
        for clue in self._text_list(reward.get("clues_added")):
            if clue not in clues:
                clues.append(clue)
                applied["clues_added"].append(clue)
        next_world["isekai_clues"] = clues[-20:]
        next_world["isekai_economy"] = economy
        return next_character, next_world, applied

    def _ensure_economy(self, value: Any) -> dict[str, Any]:
        economy = dict(value or {})
        currency = dict(economy.get("currency") or {})
        economy["currency"] = {"copper_total": max(0, self._int_value(currency.get("copper_total")))}
        economy["entitlements"] = [dict(item) for item in economy.get("entitlements", []) if isinstance(item, dict)]
        economy["transaction_log"] = [dict(item) for item in economy.get("transaction_log", []) if isinstance(item, dict)]
        economy["relationship_changes"] = [
            dict(item) for item in economy.get("relationship_changes", []) if isinstance(item, dict)
        ]
        return economy

    def _add_item(self, inventory: list[str], item: str) -> list[str]:
        if "水囊" in item:
            return normalize_waterskins([*inventory, item])
        if item in inventory:
            return inventory
        return [*inventory, item]

    def _text_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value[:8]:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text[:60])
        return result

    def _dict_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value[:8] if isinstance(item, dict)]

    def _int_value(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
