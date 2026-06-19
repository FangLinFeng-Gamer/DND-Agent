import json
from typing import Any

from pydantic import ValidationError

from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character import CharacterOut, CharacterUpdate
from backend.src.schemas.character_state import CharacterStateChange
from backend.src.services.adventures import AdventureService


class CharacterStateService:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.adventures = AdventureService(store)

    def apply_changes(self, adventure_id: int, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not payloads:
            return []
        party = self.adventures.get_party(adventure_id)
        applied = []
        for payload in payloads:
            try:
                change = CharacterStateChange.model_validate(payload)
            except ValidationError:
                continue
            character = self._resolve_character(change, party)
            if character is None:
                continue
            update = self._build_update(character, change)
            if not update:
                continue
            updated = self.adventures.update_party_character_state(
                adventure_id,
                character.id,
                CharacterUpdate.model_validate(update),
            )
            applied.append(
                {
                    "character_id": updated.id,
                    "character_name": updated.name,
                    "changes": update,
                    "reason": change.reason,
                }
            )
            party = [updated if member.id == updated.id else member for member in party]
        return applied

    def sync_party_hp_from_combat_state(self, adventure_id: int, state: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not state:
            return []
        party = self.adventures.get_party(adventure_id)
        by_id = {character.id: character for character in party}
        by_name = {character.name: character for character in party}
        changes = []
        for participant in state.get("participants", []):
            if participant.get("side") != "player" or participant.get("kind") not in {"character", "pc"}:
                continue
            character = None
            character_id = participant.get("character_id")
            if character_id is not None:
                try:
                    character = by_id.get(int(character_id))
                except (TypeError, ValueError):
                    character = None
            character = character or by_name.get(str(participant.get("name") or ""))
            if character is None:
                continue
            hp_current = max(0, min(int(participant.get("hp", character.hp_current)), character.hp_max))
            if hp_current == character.hp_current:
                continue
            updated = self.adventures.update_party_character_state(
                adventure_id,
                character.id,
                CharacterUpdate(hp_current=hp_current),
            )
            changes.append(
                {
                    "character_id": updated.id,
                    "character_name": updated.name,
                    "changes": {"hp_current": updated.hp_current},
                    "reason": "combat_state_sync",
                }
            )
            by_id[updated.id] = updated
            by_name[updated.name] = updated
        return changes

    def _resolve_character(
        self,
        change: CharacterStateChange,
        party: list[CharacterOut],
    ) -> CharacterOut | None:
        if change.character_id is not None:
            for character in party:
                if character.id == change.character_id:
                    return character
            return None
        if change.character_name:
            normalized = change.character_name.strip().lower()
            for character in party:
                if character.name.strip().lower() == normalized:
                    return character
            return None
        return party[0] if len(party) == 1 else None

    def _build_update(self, character: CharacterOut, change: CharacterStateChange) -> dict[str, Any]:
        update: dict[str, Any] = {}
        hp_max = change.hp_max if change.hp_max is not None else character.hp_max
        if change.hp_max is not None:
            update["hp_max"] = hp_max
        hp_current = None
        if change.hp_current is not None:
            hp_current = change.hp_current
        elif change.hp_delta is not None:
            hp_current = character.hp_current + change.hp_delta
        if hp_current is not None:
            update["hp_current"] = max(0, min(hp_current, hp_max))
        elif change.hp_max is not None and character.hp_current > hp_max:
            update["hp_current"] = hp_max

        experience_points = None
        if change.experience_points is not None:
            experience_points = change.experience_points
        elif change.experience_delta is not None:
            experience_points = character.experience_points + change.experience_delta
        if experience_points is not None:
            update["experience_points"] = max(0, experience_points)
        if change.level is not None:
            update["level"] = change.level

        inventory = list(character.inventory)
        original_inventory = json.dumps(inventory, ensure_ascii=False, sort_keys=True)
        inventory = self._add_inventory(inventory, change.add_inventory)
        inventory = self._remove_inventory(inventory, change.remove_inventory)
        if json.dumps(inventory, ensure_ascii=False, sort_keys=True) != original_inventory:
            update["inventory"] = inventory

        spells = list(character.spells)
        original_spells = list(spells)
        for spell in change.add_spells:
            if spell and spell not in spells:
                spells.append(spell)
        remove_spells = {spell for spell in change.remove_spells if spell}
        if remove_spells:
            spells = [spell for spell in spells if spell not in remove_spells]
        if spells != original_spells:
            update["spells"] = spells

        if change.notes_append and change.notes_append.strip():
            separator = "\n" if character.notes else ""
            update["notes"] = f"{character.notes}{separator}{change.notes_append.strip()}"
        return update

    def _add_inventory(
        self,
        inventory: list[str | dict[str, Any]],
        additions: list[str | dict[str, Any]],
    ) -> list[str | dict[str, Any]]:
        result = list(inventory)
        for entry in additions:
            key = self._inventory_key(entry)
            if not key:
                continue
            existing_index = next(
                (index for index, item in enumerate(result) if self._inventory_key(item) == key),
                None,
            )
            if existing_index is None:
                result.append(entry)
                continue
            existing = result[existing_index]
            if isinstance(existing, dict) and isinstance(entry, dict):
                merged = dict(existing)
                merged["quantity"] = int(merged.get("quantity", 1)) + int(entry.get("quantity", 1))
                result[existing_index] = merged
        return result

    def _remove_inventory(
        self,
        inventory: list[str | dict[str, Any]],
        removals: list[str | dict[str, Any]],
    ) -> list[str | dict[str, Any]]:
        result = list(inventory)
        for entry in removals:
            key = self._inventory_key(entry)
            if not key:
                continue
            remove_quantity = int(entry.get("quantity", 0)) if isinstance(entry, dict) else 0
            next_result = []
            removed = False
            for item in result:
                if self._inventory_key(item) != key or removed:
                    next_result.append(item)
                    continue
                removed = True
                if remove_quantity > 0 and isinstance(item, dict):
                    remaining = int(item.get("quantity", 1)) - remove_quantity
                    if remaining > 0:
                        kept = dict(item)
                        kept["quantity"] = remaining
                        next_result.append(kept)
            result = next_result
        return result

    def _inventory_key(self, entry: str | dict[str, Any]) -> str:
        if isinstance(entry, dict):
            return str(entry.get("item_id") or entry.get("id") or entry.get("name") or "")
        return str(entry)
