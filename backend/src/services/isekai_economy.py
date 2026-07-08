from __future__ import annotations

import random
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any


@dataclass(frozen=True)
class IsekaiEconomyResult:
    success: bool
    state: dict[str, Any]
    rewards: list[str] = field(default_factory=list)
    entitlements: list[dict[str, Any]] = field(default_factory=list)
    relationship_changes: list[dict[str, Any]] = field(default_factory=list)
    transaction: dict[str, str] | None = None
    error_code: str = ""
    shortfall_copper: int = 0
    alternatives: list[str] = field(default_factory=list)


class IsekaiEconomyService:
    BED_PRICE_COPPER = 3
    MEAL_PRICE_COPPER = 2
    STARTING_COPPER_MIN = 20
    STARTING_COPPER_MAX = 80
    PRICE_CONFIGS: dict[str, dict[str, Any]] = {
        "inn_bed": {"item": "二楼三号房床位", "price": {"copper": BED_PRICE_COPPER}, "price_copper": BED_PRICE_COPPER},
        "stew_meal": {"item": "热炖菜一碗", "price": {"copper": MEAL_PRICE_COPPER}, "price_copper": MEAL_PRICE_COPPER},
    }

    def starting_copper(self) -> int:
        return random.randint(self.STARTING_COPPER_MIN, self.STARTING_COPPER_MAX)

    def initial_state(self, copper_total: int | None = None) -> dict[str, Any]:
        return self.ensure_state(
            {"currency": {"copper_total": self.starting_copper() if copper_total is None else copper_total}},
            None,
        )

    def ensure_state(self, world_state: dict[str, Any] | None, character: dict[str, Any] | None) -> dict[str, Any]:
        state = dict(world_state or {})
        economy = dict(state.get("isekai_economy") or state)
        currency = dict(economy.get("currency") or {})
        economy["currency"] = {"copper_total": self._non_negative_int(currency.get("copper_total", 0))}
        economy["entitlements"] = [dict(item) for item in economy.get("entitlements", []) if isinstance(item, dict)]
        economy["transaction_log"] = [dict(item) for item in economy.get("transaction_log", []) if isinstance(item, dict)]
        economy["relationship_changes"] = [
            dict(item) for item in economy.get("relationship_changes", []) if isinstance(item, dict)
        ]
        economy["quotes"] = dict(economy.get("quotes") or {})
        return economy

    def display_currency(self, copper_total: int) -> dict[str, int]:
        copper = self._non_negative_int(copper_total)
        gold, rem = divmod(copper, 100)
        silver, copper = divmod(rem, 10)
        return {"gold": gold, "silver": silver, "copper": copper, "copper_total": self._non_negative_int(copper_total)}

    def price_to_copper(self, price: dict[str, Any] | int | None) -> int:
        if isinstance(price, int):
            return self._non_negative_int(price)
        if not isinstance(price, dict):
            return 0
        return (
            self._non_negative_int(price.get("gold", 0)) * 100
            + self._non_negative_int(price.get("silver", 0)) * 10
            + self._non_negative_int(price.get("copper", 0))
        )

    def price_for(self, item_id: str) -> int:
        config = self.PRICE_CONFIGS.get(item_id)
        if not config:
            return 0
        if "price_copper" in config:
            return self._non_negative_int(config["price_copper"])
        return self.price_to_copper(config.get("price"))

    def quote_bed(self, state: dict[str, Any]) -> IsekaiEconomyResult:
        next_state = self.ensure_state(state, {"gold": 0})
        price = self.price_for("inn_bed")
        next_state["quotes"] = {**next_state.get("quotes", {}), "inn_bed": price}
        relationship = self._relationship("店主", "可以交易，但仍在观察", 1)
        next_state["relationship_changes"] = [*next_state.get("relationship_changes", []), relationship][-12:]
        return IsekaiEconomyResult(
            success=True,
            state=next_state,
            relationship_changes=[relationship],
            rewards=[f"住宿报价：{price} 铜"],
        )

    def purchase(
        self,
        state: dict[str, Any],
        *,
        item_id: str,
        buyer_note: str,
        valid_until: str,
    ) -> IsekaiEconomyResult:
        current = self.ensure_state(state, {"gold": 0})
        if item_id not in self.PRICE_CONFIGS:
            return IsekaiEconomyResult(
                success=False,
                state=current,
                error_code="unknown_item",
                alternatives=["明确要买床位", "明确要买热炖菜", "先询问店主当前价格"],
            )
        price = self._price(item_id)
        copper = int(current["currency"]["copper_total"])
        if copper < price:
            return IsekaiEconomyResult(
                success=False,
                state=current,
                error_code="insufficient_funds",
                shortfall_copper=price - copper,
                alternatives=["帮后厨修锅把换取床位", "询问是否能赊账", "去马厩换更便宜的落脚处"],
            )
        next_state = {**current, "currency": {"copper_total": copper - price}}
        if item_id == "inn_bed":
            entitlement = self._bed_entitlement(valid_until)
            rewards = ["二楼三号房钥匙", "二楼三号房床位"]
            transaction = {"lost": f"{price} 铜", "gained": "、".join(rewards), "reason": buyer_note}
            relationship = self._relationship("店主", "愿意交易", 5)
            next_state["entitlements"] = self._upsert_entitlement(next_state.get("entitlements", []), entitlement)
            next_state["transaction_log"] = [*next_state.get("transaction_log", []), transaction][-20:]
            next_state["relationship_changes"] = [*next_state.get("relationship_changes", []), relationship][-12:]
            return IsekaiEconomyResult(
                success=True,
                state=next_state,
                rewards=rewards,
                entitlements=[entitlement],
                relationship_changes=[relationship],
                transaction=transaction,
            )
        if item_id == "stew_meal":
            transaction = {"lost": f"{price} 铜", "gained": "一碗热炖菜", "reason": buyer_note}
            next_state["transaction_log"] = [*next_state.get("transaction_log", []), transaction][-20:]
            return IsekaiEconomyResult(success=True, state=next_state, rewards=["一碗热炖菜"], transaction=transaction)
        return IsekaiEconomyResult(success=False, state=current, error_code="unknown_item")

    def purchase_offer(
        self,
        state: dict[str, Any],
        *,
        offer: dict[str, Any],
        buyer_note: str,
        valid_until: str,
    ) -> IsekaiEconomyResult:
        current = self.ensure_state(state, {"gold": 0})
        if not isinstance(offer, dict) or not str(offer.get("offer_id") or "").strip():
            return IsekaiEconomyResult(
                success=False,
                state=current,
                error_code="unknown_item",
                alternatives=["重新确认要购买的商品或服务"],
            )
        price = self._offer_price(offer)
        copper = int(current["currency"]["copper_total"])
        if copper < price:
            return IsekaiEconomyResult(
                success=False,
                state=current,
                error_code="insufficient_funds",
                shortfall_copper=price - copper,
                alternatives=[str(item) for item in offer.get("alternatives", []) if str(item).strip()]
                or ["询问是否有更便宜的替代方案", "先寻找能换取报酬的工作"],
            )
        grants = offer.get("grants") if isinstance(offer.get("grants"), dict) else {}
        reward_items = [str(item).strip() for item in grants.get("items", []) if str(item).strip()] if isinstance(grants.get("items"), list) else []
        entitlements = self._offer_entitlements(grants, offer, valid_until)
        fallback_name = str(offer.get("name") or offer.get("item") or offer.get("offer_id") or "").strip()
        rewards = [*reward_items, *[str(item.get("name") or item.get("status") or item.get("id")) for item in entitlements]]
        rewards = [str(item).strip() for item in rewards if str(item).strip()] or ([fallback_name] if fallback_name else [])
        gained = "、".join(rewards) if rewards else "交易权益"
        reason = str(buyer_note or "").strip() or (f"购买{fallback_name}" if fallback_name else "购买")
        transaction = {"lost": f"{price} 铜", "gained": gained, "reason": reason}
        next_state = {**current, "currency": {"copper_total": copper - price}}
        for entitlement in entitlements:
            next_state["entitlements"] = self._upsert_entitlement(next_state.get("entitlements", []), entitlement)
        next_state["transaction_log"] = [*next_state.get("transaction_log", []), transaction][-20:]
        relationship_changes = [
            dict(item) for item in grants.get("relationship_changes", []) if isinstance(item, dict)
        ] if isinstance(grants.get("relationship_changes"), list) else []
        if relationship_changes:
            next_state["relationship_changes"] = [*next_state.get("relationship_changes", []), *relationship_changes][-12:]
        return IsekaiEconomyResult(
            success=True,
            state=next_state,
            rewards=rewards,
            entitlements=entitlements,
            relationship_changes=relationship_changes,
            transaction=transaction,
        )

    def grant_repair_reward(self, state: dict[str, Any], *, valid_until: str) -> IsekaiEconomyResult:
        current = self.ensure_state(state, {"gold": 0})
        entitlement = self._bed_entitlement(valid_until)
        rewards = ["二楼三号房钥匙", "二楼三号房床位", "店主透露夜里镇墙外有异常低嚎"]
        transaction = {"lost": "0 铜", "gained": "二楼三号房钥匙、二楼三号房床位", "reason": "修好后厨锅把"}
        relationship = self._relationship("店主", "愿意交易", 12)
        next_state = {
            **current,
            "entitlements": self._upsert_entitlement(current.get("entitlements", []), entitlement),
            "transaction_log": [*current.get("transaction_log", []), transaction][-20:],
            "relationship_changes": [*current.get("relationship_changes", []), relationship][-12:],
        }
        return IsekaiEconomyResult(
            success=True,
            state=next_state,
            rewards=rewards,
            entitlements=[entitlement],
            relationship_changes=[relationship],
            transaction=transaction,
        )

    def _price(self, item_id: str) -> int:
        return self.price_for(item_id)

    def _offer_price(self, offer: dict[str, Any]) -> int:
        if "price_copper" in offer:
            return self._non_negative_int(offer.get("price_copper"))
        return self.price_to_copper(offer.get("price"))

    def _offer_entitlements(self, grants: dict[str, Any], offer: dict[str, Any], valid_until: str) -> list[dict[str, Any]]:
        raw = grants.get("entitlements")
        if not isinstance(raw, list):
            return []
        entitlements: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            entitlement = deepcopy(item)
            entitlement.setdefault("id", str(offer.get("offer_id") or "entitlement"))
            entitlement.setdefault("name", str(offer.get("name") or entitlement["id"]))
            entitlement.setdefault("valid_until", valid_until)
            entitlements.append(entitlement)
        return entitlements

    def _non_negative_int(self, value: Any) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    def _bed_entitlement(self, valid_until: str) -> dict[str, str]:
        return {
            "id": "inn_room_3_bed",
            "name": "二楼三号房床位",
            "item": "二楼三号房钥匙",
            "valid_until": valid_until,
            "status": "今晚有床位",
            "identity": "旧炉旅店临时住客",
        }

    def _relationship(self, name: str, attitude: str, delta: int) -> dict[str, Any]:
        return {"npc_id": "innkeeper_01", "name": name, "attitude": attitude, "delta": delta}

    def _upsert_entitlement(self, current: list[dict[str, Any]], entitlement: dict[str, Any]) -> list[dict[str, Any]]:
        result = [dict(item) for item in current if isinstance(item, dict) and item.get("id") != entitlement["id"]]
        result.append(dict(entitlement))
        return result[-12:]
