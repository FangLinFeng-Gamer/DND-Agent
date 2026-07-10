from __future__ import annotations

from typing import Any

from backend.src.services.isekai_quests import IsekaiQuestService
from backend.src.services.isekai_rewards import IsekaiRewardService


class IsekaiConsequenceResolver:
    def __init__(
        self,
        rewards: IsekaiRewardService | None = None,
        quests: IsekaiQuestService | None = None,
    ):
        self.rewards = rewards or IsekaiRewardService()
        self.quests = quests or IsekaiQuestService()

    def resolve(
        self,
        character: dict[str, Any],
        world_state: dict[str, Any],
        proposals: dict[str, Any] | None,
        *,
        action_type: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        proposals = proposals if isinstance(proposals, dict) else {}
        next_character = dict(character or {})
        next_world = dict(world_state or {})
        applied: dict[str, Any] = {"blocked": {}, "applied": {}}
        blocked: dict[str, Any] = {}

        money_changes = self._list(proposals.get("money_changes"))
        item_rewards = self._list(proposals.get("item_rewards"))
        entitlement_changes = self._list(proposals.get("entitlement_changes"))
        quest_stage_changes = self._list(proposals.get("quest_stage_changes"))
        npc_relationship_changes = self._list(proposals.get("npc_relationship_changes"))

        if action_type in {"table_talk", "status_check", "clarification"}:
            self._block(blocked, "money_changes", money_changes)
            self._block(blocked, "item_rewards", item_rewards)
            self._block(blocked, "entitlement_changes", entitlement_changes)
            self._block(blocked, "quest_stage_changes", quest_stage_changes)
            self._block(blocked, "npc_relationship_changes", npc_relationship_changes)
            applied["blocked"] = blocked
            return next_character, next_world, applied

        if action_type == "negotiate":
            self._block(blocked, "entitlement_changes", entitlement_changes)
            self._block(blocked, "item_rewards", item_rewards)
            self._block(blocked, "money_changes", money_changes)
            self._block(blocked, "quest_stage_changes", quest_stage_changes)
            if npc_relationship_changes:
                next_character, next_world, reward_applied = self.rewards.apply(
                    next_character,
                    next_world,
                    {"relationship_delta": npc_relationship_changes},
                    reason="交涉态度变化",
                )
                applied["applied"]["npc_relationship_changes"] = reward_applied["relationship_delta"]
            applied["blocked"] = blocked
            return next_character, next_world, applied

        if action_type == "quest_resolution":
            next_world, quest_applied = self.quests.apply_quest_proposals(
                next_world,
                quest_stage_changes,
                action_type=action_type,
            )
            if quest_applied.get("blocked"):
                self._block(blocked, "quest_stage_changes", quest_applied["blocked"])
            reward_payload = self._reward_payload(money_changes, item_rewards, entitlement_changes, npc_relationship_changes)
            next_character, next_world, reward_applied = self.rewards.apply(
                next_character,
                next_world,
                reward_payload,
                reason="任务结算",
            )
            applied["applied"]["quest_stage_changes"] = quest_applied.get("applied", [])
            applied["applied"]["rewards"] = reward_applied
            applied["blocked"] = blocked
            return next_character, next_world, applied

        if action_type == "purchase":
            reward_payload = self._reward_payload(money_changes, item_rewards, entitlement_changes, [], allow_negative_money=True)
            next_character, next_world, reward_applied = self.rewards.apply(
                next_character,
                next_world,
                reward_payload,
                reason="购买结算",
            )
            self._block(blocked, "quest_stage_changes", quest_stage_changes)
            self._block(blocked, "npc_relationship_changes", npc_relationship_changes)
            applied["applied"]["rewards"] = reward_applied
            applied["blocked"] = blocked
            return next_character, next_world, applied

        if action_type == "repair":
            self._block(blocked, "money_changes", money_changes)
            self._block(blocked, "item_rewards", item_rewards)
            self._block(blocked, "entitlement_changes", entitlement_changes)
            self._block(blocked, "quest_stage_changes", quest_stage_changes)
            next_character, next_world, reward_applied = self.rewards.apply(
                next_character,
                next_world,
                {"relationship_delta": npc_relationship_changes},
                reason="修理态度变化",
            )
            applied["applied"]["npc_relationship_changes"] = reward_applied["relationship_delta"]
            applied["blocked"] = blocked
            return next_character, next_world, applied

        self._block(blocked, "money_changes", money_changes)
        self._block(blocked, "item_rewards", item_rewards)
        self._block(blocked, "entitlement_changes", entitlement_changes)
        self._block(blocked, "quest_stage_changes", quest_stage_changes)
        self._block(blocked, "npc_relationship_changes", npc_relationship_changes)
        applied["blocked"] = blocked
        return next_character, next_world, applied

    def _reward_payload(
        self,
        money_changes: list[Any],
        item_rewards: list[Any],
        entitlement_changes: list[Any],
        npc_relationship_changes: list[Any],
        *,
        allow_negative_money: bool = False,
    ) -> dict[str, Any]:
        currency_delta = 0
        for change in money_changes:
            if isinstance(change, dict):
                currency_delta += self._int_value(change.get("copper_delta"))
            else:
                currency_delta += self._int_value(change)
        if not allow_negative_money:
            currency_delta = max(0, currency_delta)
        return {
            "items_added": [str(item) for item in item_rewards if str(item).strip()],
            "currency_delta": currency_delta,
            "entitlements_added": [dict(item) for item in entitlement_changes if isinstance(item, dict)],
            "relationship_delta": [dict(item) for item in npc_relationship_changes if isinstance(item, dict)],
            "clues_added": [],
        }

    def _list(self, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value[:8]
        if isinstance(value, dict):
            return [dict(value)]
        if value not in (None, "", []):
            return [value]
        return []

    def _block(self, blocked: dict[str, Any], key: str, values: list[Any]) -> None:
        if values:
            blocked[key] = values

    def _int_value(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
