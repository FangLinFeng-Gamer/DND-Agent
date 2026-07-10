from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.src.db.sqlite import SQLiteStore, encode_json
from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_inventory import normalize_waterskins


@dataclass(frozen=True)
class IsekaiStateChangeResult:
    character: dict[str, Any]
    scene: SceneState | None
    applied: dict[str, Any]


class IsekaiStateChangeService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def apply(
        self,
        adventure_id: int,
        character: dict[str, Any],
        scene: SceneState,
        payload: dict[str, Any] | None,
        parsed_action: dict[str, Any] | None = None,
    ) -> IsekaiStateChangeResult:
        state_changes = payload.get("state_changes") if isinstance(payload, dict) else {}
        if not isinstance(state_changes, dict):
            state_changes = {}

        inventory = [str(item) for item in character.get("inventory", [])]
        added = self._sanitize_item_list(state_changes.get("add_items"))
        removed = self._sanitize_item_list(state_changes.get("remove_items"))
        npc_updates = self._sanitize_npc_updates(state_changes.get("npc_updates"))
        protected_changes = self._protected_state_changes(state_changes)
        added, removed, npc_updates, blocked = self._filter_state_changes(added, removed, npc_updates, parsed_action)
        blocked.update(protected_changes)
        errors: list[str] = []

        for item in added:
            inventory = self._add_item(inventory, item)
        for item in removed:
            before = list(inventory)
            inventory = self._remove_item(inventory, item)
            if before == inventory:
                errors.append(f"未找到可移除物品：{item}")

        updated = {**character, "inventory": inventory}
        if added or removed:
            self._update_inventory(adventure_id, inventory)
        gated_state_changes = {**state_changes, "npc_updates": npc_updates}
        next_scene, scene_applied = self._apply_scene_fields(scene, payload, gated_state_changes)

        return IsekaiStateChangeResult(
            character=updated,
            scene=next_scene if scene_applied else None,
            applied={
                "inventory_added": added,
                "inventory_removed": [item for item in removed if f"未找到可移除物品：{item}" not in errors],
                **scene_applied,
                "blocked": blocked,
                "errors": errors,
            },
        )

    def _filter_state_changes(
        self,
        added: list[str],
        removed: list[str],
        npc_updates: list[dict[str, Any]],
        parsed_action: dict[str, Any] | None,
    ) -> tuple[list[str], list[str], list[dict[str, Any]], dict[str, Any]]:
        parsed_action = parsed_action or {}
        action_type = str(parsed_action.get("action_type") or "")
        target_name = str(parsed_action.get("target_name") or "").strip()
        blocked: dict[str, Any] = {}

        if action_type in {"table_talk", "status_check", "clarification"}:
            self._record_blocked(blocked, "add_items", added)
            self._record_blocked(blocked, "remove_items", removed)
            self._record_blocked(blocked, "npc_updates", npc_updates)
            return [], [], [], blocked

        if action_type not in {"gather", "forage", "cook", "eat_drink", "search", "force_open"}:
            self._record_blocked(blocked, "add_items", added)
            added = []
        elif target_name and action_type in {"gather", "forage"}:
            allowed_added: list[str] = []
            for item in added:
                if self._item_matches_target(item, target_name):
                    allowed_added.append(item)
                else:
                    self._record_blocked(blocked, "add_items", [item])
            added = allowed_added

        if action_type not in {"manage_inventory", "eat_drink", "eat_food", "drink_water", "cook"}:
            self._record_blocked(blocked, "remove_items", removed)
            removed = []

        if action_type != "short_dialogue":
            self._record_blocked(blocked, "npc_updates", npc_updates)
            npc_updates = []

        return added, removed, npc_updates, blocked

    def _protected_state_changes(self, state_changes: dict[str, Any]) -> dict[str, Any]:
        blocked: dict[str, Any] = {}
        for key in [
            "money_changes",
            "item_rewards",
            "entitlement_changes",
            "relationship_changes",
            "quest_stage_changes",
            "npc_relationship_changes",
        ]:
            value = state_changes.get(key)
            if isinstance(value, list) and value:
                blocked[key] = [dict(item) if isinstance(item, dict) else item for item in value[:8]]
            elif isinstance(value, dict) and value:
                blocked[key] = dict(value)
        return blocked

    def _record_blocked(self, blocked: dict[str, Any], key: str, values: list[Any]) -> None:
        if not values:
            return
        blocked.setdefault(key, [])
        blocked[key].extend(values)

    def _item_matches_target(self, item: str, target_name: str) -> bool:
        item_text = str(item or "").strip()
        target = str(target_name or "").strip()
        return bool(item_text and target and (item_text in target or target in item_text))

    def _update_inventory(self, adventure_id: int, inventory: list[str]) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE isekai_characters
                SET inventory_json = :inventory_json,
                    updated_at = CURRENT_TIMESTAMP
                WHERE adventure_id = :adventure_id
                """,
                {"adventure_id": adventure_id, "inventory_json": encode_json(inventory)},
            )

    def _sanitize_item_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for entry in value[:8]:
            item = str(entry or "").strip()
            if not item or len(item) > 40:
                continue
            if any(marker in item for marker in ["{", "}", "[", "]", "系统", "metadata"]):
                continue
            if item not in items:
                items.append(item)
        return items

    def _apply_scene_fields(
        self,
        scene: SceneState,
        payload: dict[str, Any] | None,
        state_changes: dict[str, Any],
    ) -> tuple[SceneState, dict[str, Any]]:
        payload = payload if isinstance(payload, dict) else {}
        interactables = self._sanitize_interactables(payload.get("interactables"))
        suggested_actions = self._sanitize_text_list(payload.get("suggested_actions"), limit=5, max_length=80)
        npc_updates = self._sanitize_npc_updates(state_changes.get("npc_updates"))
        npc_states = self._merge_npc_states(scene.npc_states, npc_updates)
        npcs = self._merge_current_npc_names(scene.npcs, interactables, npc_updates)

        if not interactables and not suggested_actions and not npc_updates:
            return scene, {}

        next_scene = scene.model_copy(
            update={
                "interactables": interactables or scene.interactables,
                "suggested_actions": suggested_actions or scene.suggested_actions,
                "npc_states": npc_states,
                "npcs": npcs,
            }
        )
        return next_scene, {
            "interactables": interactables,
            "suggested_actions": suggested_actions,
            "npc_updates": npc_updates,
        }

    def _sanitize_interactables(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        result: list[dict[str, Any]] = []
        for entry in value[:6]:
            if not isinstance(entry, dict):
                continue
            name = self._clean_text(entry.get("name"), max_length=40)
            if not name:
                continue
            item = {
                "id": self._clean_text(entry.get("id"), max_length=40) or self._stable_id("interactable", name),
                "type": self._clean_text(entry.get("type"), max_length=20) or "object",
                "name": name,
            }
            state = self._clean_text(entry.get("state"), max_length=60)
            risk = self._clean_text(entry.get("risk"), max_length=80)
            affordances = self._sanitize_text_list(entry.get("affordances"), limit=5, max_length=24)
            if state:
                item["state"] = state
            if affordances:
                item["affordances"] = affordances
            if risk:
                item["risk"] = risk
            result.append(item)
        return result

    def _sanitize_npc_updates(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        result: list[dict[str, Any]] = []
        for entry in value[:6]:
            if not isinstance(entry, dict):
                continue
            name = self._clean_text(entry.get("name"), max_length=40)
            if not name:
                continue
            update: dict[str, Any] = {
                "id": self._clean_text(entry.get("id"), max_length=40) or self._stable_id("npc", name),
                "name": name,
            }
            attitude = self._clean_text(entry.get("attitude"), max_length=24)
            if attitude:
                update["attitude"] = attitude
            if isinstance(entry.get("trust"), int):
                update["trust"] = max(0, min(100, int(entry["trust"])))
            if isinstance(entry.get("trust_delta"), int):
                update["trust_delta"] = max(-100, min(100, int(entry["trust_delta"])))
            known_facts = self._sanitize_text_list(entry.get("known_facts"), limit=8, max_length=80)
            if known_facts:
                update["known_facts"] = known_facts
            result.append(update)
        return result

    def _merge_npc_states(
        self,
        current: list[dict[str, Any]],
        updates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged = [dict(npc) for npc in current if isinstance(npc, dict)]
        for update in updates:
            npc_id = str(update.get("id") or "")
            index = next(
                (
                    position
                    for position, npc in enumerate(merged)
                    if str(npc.get("id") or "") == npc_id or str(npc.get("name") or "") == update["name"]
                ),
                None,
            )
            existing = merged[index] if index is not None else {"id": npc_id, "name": update["name"], "trust": 20}
            trust = int(existing.get("trust", 20))
            if "trust" in update:
                trust = int(update["trust"])
            trust += int(update.get("trust_delta", 0))
            facts = self._dedupe([*existing.get("known_facts", []), *update.get("known_facts", [])], limit=12)
            next_npc = {
                **existing,
                "id": npc_id or str(existing.get("id") or self._stable_id("npc", update["name"])),
                "name": update["name"],
                "attitude": update.get("attitude", existing.get("attitude", "suspicious")),
                "trust": max(0, min(100, trust)),
                "known_facts": facts,
            }
            if index is None:
                merged.append(next_npc)
            else:
                merged[index] = next_npc
        return merged[-12:]

    def _merge_current_npc_names(
        self,
        current: list[str],
        interactables: list[dict[str, Any]],
        npc_updates: list[dict[str, Any]],
    ) -> list[str]:
        names = [str(name).strip() for name in current if str(name).strip()]
        for entry in interactables:
            if str(entry.get("type") or "").strip().lower() != "npc":
                continue
            name = str(entry.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        for update in npc_updates:
            name = str(update.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        return names[-12:]

    def _sanitize_text_list(self, value: Any, limit: int, max_length: int) -> list[str]:
        if not isinstance(value, list):
            return []
        return self._dedupe([self._clean_text(item, max_length=max_length) for item in value], limit=limit)

    def _dedupe(self, values: list[Any], limit: int) -> list[str]:
        result: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in result:
                result.append(text)
        return result[:limit]

    def _clean_text(self, value: Any, max_length: int) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text[:max_length]

    def _stable_id(self, prefix: str, name: str) -> str:
        ascii_key = re.sub(r"[^0-9a-zA-Z_]+", "_", name).strip("_").lower()
        if ascii_key:
            return f"{prefix}_{ascii_key[:24]}"
        return f"{prefix}_{abs(sum(ord(char) for char in name))}"

    def _add_item(self, inventory: list[str], item: str) -> list[str]:
        if "水囊" in item:
            return normalize_waterskins([*inventory, item])
        result = list(inventory)
        item_name, item_count = self._split_count(item)
        for index, existing in enumerate(result):
            existing_name, existing_count = self._split_count(existing)
            if existing_name != item_name:
                continue
            result[index] = self._format_count(item_name, existing_count + item_count)
            return result
        result.append(self._format_count(item_name, item_count))
        return result

    def _remove_item(self, inventory: list[str], item: str) -> list[str]:
        result = list(inventory)
        item_name, item_count = self._split_count(item)
        for index, existing in enumerate(result):
            existing_name, existing_count = self._split_count(existing)
            if existing_name != item_name:
                continue
            remaining = existing_count - item_count
            if remaining <= 0:
                result.pop(index)
            else:
                result[index] = self._format_count(existing_name, remaining)
            return result
        return result

    def _split_count(self, item: str) -> tuple[str, int]:
        text = str(item or "").strip()
        match = re.search(r"\s*x\s*(\d+)\s*$", text, flags=re.IGNORECASE)
        if not match:
            return text, 1
        name = text[: match.start()].strip()
        return name or text, max(1, int(match.group(1)))

    def _format_count(self, name: str, count: int) -> str:
        if count <= 1:
            return name
        return f"{name} x{count}"
