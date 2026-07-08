from __future__ import annotations

from sqlite3 import Row
from typing import Any, List

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.adventure import AdventureCreate, AdventureOut, MessageOut, SceneState
from backend.src.schemas.character import CharacterOut, CharacterUpdate
from backend.src.schemas.story import StoryOut
from backend.src.services.character_progression import character_progression, level_for_experience
from backend.src.services.characters import CharacterService
from backend.src.services.world_state import (
    initial_world_state_for_story,
    normalize_world_state,
    public_world_state_view,
)
from backend.src.services.world_events import WorldEventService


class AdventureService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def create(self, adventure: AdventureCreate, scene: SceneState, story: StoryOut | None = None) -> AdventureOut:
        party = self.validate_party(adventure.effective_party_character_ids())
        primary_character_id = party[0].id
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO adventures (
                    title, mode, world_id, story_id, character_id, status, summary,
                    current_scene_json, story_snapshot_json, world_state_json
                )
                VALUES (
                    :title, :mode, :world_id, :story_id, :character_id, :status, :summary,
                    :current_scene_json, :story_snapshot_json, :world_state_json
                )
                """,
                {
                    "title": adventure.title,
                    "mode": adventure.mode or "dnd",
                    "world_id": adventure.world_id,
                    "story_id": adventure.story_id,
                    "character_id": primary_character_id,
                    "status": "active",
                    "summary": "",
                    "current_scene_json": encode_json(scene.model_dump()),
                    "story_snapshot_json": encode_json(story.model_dump() if story else {}),
                    "world_state_json": encode_json(initial_world_state_for_story(story)),
                },
            )
            adventure_id = cursor.lastrowid
            conn.executemany(
                """
                INSERT INTO adventure_characters (
                    adventure_id, character_id, party_order, role, state_json
                )
                VALUES (?, ?, ?, 'player', ?)
                """,
                [
                    (
                        adventure_id,
                        character.id,
                        index,
                        encode_json(character.model_dump(mode="json")),
                    )
                    for index, character in enumerate(party)
                ],
            )
            row = conn.execute("SELECT * FROM adventures WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._map_adventure_row(row)

    def create_isekai_shell(self, adventure: AdventureCreate, scene: SceneState) -> AdventureOut:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO adventures (
                    title, mode, world_id, story_id, character_id, status, summary,
                    current_scene_json, story_snapshot_json, world_state_json
                )
                VALUES (
                    :title, 'isekai_survival', :world_id, 'isekai_survival', 0, 'active', '',
                    :current_scene_json, '{}', '{}'
                )
                """,
                {
                    "title": adventure.title,
                    "world_id": adventure.world_id,
                    "current_scene_json": encode_json(scene.model_dump()),
                },
            )
            row = conn.execute("SELECT * FROM adventures WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._map_adventure_row(row)

    def list(self) -> list[AdventureOut]:
        with self.store.connect() as conn:
            rows = conn.execute("SELECT * FROM adventures ORDER BY id").fetchall()
        return [self._map_adventure_row(row) for row in rows]

    def get(self, adventure_id: int, include_messages: bool = True) -> AdventureOut:
        adventure = self._map_adventure_row(self._get_adventure_row(adventure_id))
        if include_messages:
            adventure.messages = self.list_messages(adventure_id)
        return adventure

    def delete(self, adventure_id: int) -> None:
        self.get(adventure_id, include_messages=False)
        with self.store.connect() as conn:
            conn.execute("DELETE FROM messages WHERE adventure_id = ?", (adventure_id,))
            conn.execute("DELETE FROM combat_states WHERE adventure_id = ?", (adventure_id,))
            conn.execute("DELETE FROM adventure_characters WHERE adventure_id = ?", (adventure_id,))
            conn.execute("DELETE FROM map_combat_tokens WHERE adventure_id = ?", (adventure_id,))
            conn.execute("DELETE FROM isekai_characters WHERE adventure_id = ?", (adventure_id,))
            conn.execute("DELETE FROM isekai_survival_states WHERE adventure_id = ?", (adventure_id,))
            conn.execute("DELETE FROM world_events WHERE adventure_id = ?", (adventure_id,))
            conn.execute("UPDATE map_scenes SET adventure_id = NULL, active = 0 WHERE adventure_id = ?", (adventure_id,))
            conn.execute("DELETE FROM adventures WHERE id = ?", (adventure_id,))

    def append_message(self, adventure_id: int, role: str, content: str, metadata: dict[str, Any] | None = None) -> MessageOut:
        self.get(adventure_id, include_messages=False)
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (adventure_id, role, content, metadata_json)
                VALUES (:adventure_id, :role, :content, :metadata_json)
                """,
                {
                    "adventure_id": adventure_id,
                    "role": role,
                    "content": content,
                    "metadata_json": encode_json(metadata or {}),
                },
            )
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._map_message_row(row)

    def get_message(self, message_id: int) -> MessageOut:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            raise api_error(404, "message_not_found", "Message not found.")
        return self._map_message_row(row)

    def update_message_metadata(self, message_id: int, metadata: dict[str, Any]) -> MessageOut:
        with self.store.connect() as conn:
            result = conn.execute(
                """
                UPDATE messages
                SET metadata_json = :metadata_json
                WHERE id = :message_id
                """,
                {"message_id": message_id, "metadata_json": encode_json(metadata)},
            )
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if result.rowcount == 0 or row is None:
            raise api_error(404, "message_not_found", "Message not found.")
        return self._map_message_row(row)

    def list_messages(self, adventure_id: int) -> List[MessageOut]:
        self._get_adventure_row(adventure_id)
        with self.store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE adventure_id = ? ORDER BY id",
                (adventure_id,),
            ).fetchall()
        return [self._map_message_row(row) for row in rows]

    def get_scene(self, adventure_id: int) -> SceneState:
        return self.get(adventure_id, include_messages=False).current_scene

    def update_scene(self, adventure_id: int, scene: SceneState, summary: str | None = None) -> SceneState:
        values: dict[str, Any] = {
            "adventure_id": adventure_id,
            "current_scene_json": encode_json(scene.model_dump()),
        }
        summary_sql = ""
        if summary is not None:
            values["summary"] = summary
            summary_sql = ", summary = :summary"

        with self.store.connect() as conn:
            result = conn.execute(
                f"""
                UPDATE adventures
                SET current_scene_json = :current_scene_json{summary_sql}, updated_at = CURRENT_TIMESTAMP
                WHERE id = :adventure_id
                """,
                values,
            )
        if result.rowcount == 0:
            raise api_error(404, "adventure_not_found", "Adventure not found.")
        return scene

    def get_world_state(self, adventure_id: int) -> dict[str, Any]:
        row = self._get_adventure_row(adventure_id)
        story = self._story_from_row(row)
        return normalize_world_state(decode_json(row["world_state_json"], {}), story)

    def update_world_state(self, adventure_id: int, world_state: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_world_state(world_state)
        with self.store.connect() as conn:
            result = conn.execute(
                """
                UPDATE adventures
                SET world_state_json = :world_state_json, updated_at = CURRENT_TIMESTAMP
                WHERE id = :adventure_id
                """,
                {
                    "adventure_id": adventure_id,
                    "world_state_json": encode_json(normalized),
                },
            )
        if result.rowcount == 0:
            raise api_error(404, "adventure_not_found", "Adventure not found.")
        return normalized

    def get_combat_state(self, adventure_id: int) -> dict[str, Any] | None:
        self.get(adventure_id, include_messages=False)
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM combat_states WHERE adventure_id = ?", (adventure_id,)).fetchone()
        if row is None:
            return None
        return {
            "participants": decode_json(row["participants_json"], []),
            "is_active": bool(row["is_active"]),
            "round_number": row["round_number"],
            "turn_index": row["turn_index"],
            "action_log": decode_json(row["action_log_json"], []),
        }

    def save_combat_state(self, adventure_id: int, state: dict[str, Any]) -> dict[str, Any]:
        self.get(adventure_id, include_messages=False)
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO combat_states (
                    adventure_id, is_active, round_number, turn_index, participants_json, action_log_json
                )
                VALUES (
                    :adventure_id, :is_active, :round_number, :turn_index, :participants_json, :action_log_json
                )
                ON CONFLICT(adventure_id) DO UPDATE SET
                    is_active = excluded.is_active,
                    round_number = excluded.round_number,
                    turn_index = excluded.turn_index,
                    participants_json = excluded.participants_json,
                    action_log_json = excluded.action_log_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                {
                    "adventure_id": adventure_id,
                    "is_active": 1 if state.get("is_active") else 0,
                    "round_number": state.get("round_number", 1),
                    "turn_index": state.get("turn_index", 0),
                    "participants_json": encode_json(state.get("participants", [])),
                    "action_log_json": encode_json(state.get("action_log", [])),
                },
            )
        return state

    def validate_party(self, character_ids: list[int]) -> list:
        if not character_ids:
            raise api_error(400, "party_required", "Select at least one character.")
        if len(character_ids) > 6:
            raise api_error(400, "party_too_large", "A party can include at most 6 characters.")
        if len(set(character_ids)) != len(character_ids):
            raise api_error(400, "party_duplicate_character", "A party cannot include the same character twice.")
        characters = []
        character_service = CharacterService(self.store)
        for character_id in character_ids:
            characters.append(character_service.get(character_id))
        return characters

    def get_party(self, adventure_id: int) -> list:
        row = self._get_adventure_row(adventure_id)
        return self._party_for_adventure(row["id"], row["character_id"])[1]

    def update_party_character_state(
        self,
        adventure_id: int,
        character_id: int,
        update: CharacterUpdate,
    ) -> CharacterOut:
        party_ids, party = self._party_for_adventure(adventure_id, fallback_character_id=character_id)
        if character_id not in party_ids:
            raise api_error(404, "adventure_character_not_found", "Character is not in this adventure.")
        current = next((character for character in party if character.id == character_id), None)
        if current is None:
            raise api_error(404, "adventure_character_not_found", "Character is not in this adventure.")

        values = update.model_dump(exclude_unset=True)
        CharacterService(self.store)._validate_update(values, current)
        if "experience_points" in values and "level" not in values:
            values["level"] = max(current.level, level_for_experience(values["experience_points"]))

        data = current.model_dump(mode="json")
        data.update(values)
        data.update(character_progression(data["level"], data["experience_points"]))
        updated = CharacterOut.model_validate(data)
        with self.store.connect() as conn:
            result = conn.execute(
                """
                UPDATE adventure_characters
                SET state_json = :state_json
                WHERE adventure_id = :adventure_id AND character_id = :character_id
                """,
                {
                    "adventure_id": adventure_id,
                    "character_id": character_id,
                    "state_json": encode_json(updated.model_dump(mode="json")),
                },
            )
        if result.rowcount == 0:
            raise api_error(404, "adventure_character_not_found", "Character is not in this adventure.")
        return updated

    def _get_adventure_row(self, adventure_id: int) -> Row:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM adventures WHERE id = ?", (adventure_id,)).fetchone()
        if row is None:
            raise api_error(404, "adventure_not_found", "Adventure not found.")
        return row

    def _map_adventure_row(self, row: Row) -> AdventureOut:
        mode = row["mode"] if "mode" in row.keys() else "dnd"
        party_ids, party_characters = self._party_for_adventure(row["id"], row["character_id"])
        isekai_character = self._isekai_character_for_adventure(row["id"]) if mode == "isekai_survival" else None
        survival_state = self._isekai_survival_state_for_adventure(row["id"]) if mode == "isekai_survival" else None
        current_scene = SceneState.model_validate(decode_json(row["current_scene_json"], {}))
        if mode == "isekai_survival":
            current_scene = self._isekai_scene_for_output(current_scene)
        world_events = (
            WorldEventService(self.store).list_known_for_adventure(row["id"])
            if mode == "isekai_survival"
            else []
        )
        world_state = public_world_state_view(
            normalize_world_state(decode_json(row["world_state_json"], {}), self._story_from_row(row))
        )
        if mode == "isekai_survival":
            from backend.src.services.isekai_worldview import IsekaiWorldviewNormalizer

            world_state["isekai_pressure_goals"] = IsekaiWorldviewNormalizer().pressure_goals()
        return AdventureOut(
            id=row["id"],
            title=row["title"],
            mode=mode,
            world_id=row["world_id"],
            story_id=row["story_id"],
            character_id=row["character_id"],
            party_character_ids=party_ids,
            party_characters=party_characters,
            status=row["status"],
            summary=row["summary"],
            current_scene=current_scene,
            world_state=world_state,
            isekai_character=isekai_character,
            survival_state=survival_state,
            world_events=world_events,
        )

    def _isekai_scene_for_output(self, scene: SceneState) -> SceneState:
        from backend.src.services.isekai_worldview import IsekaiWorldviewNormalizer

        repaired = IsekaiWorldviewNormalizer().repair_scene_state_payload(scene.model_dump())
        return SceneState.model_validate(repaired)

    def _story_from_row(self, row: Row) -> StoryOut | None:
        snapshot = decode_json(row["story_snapshot_json"], {})
        if not snapshot:
            return None
        return StoryOut.model_validate(snapshot)

    def _party_for_adventure(self, adventure_id: int, fallback_character_id: int) -> tuple[list[int], list]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT character_id, state_json
                FROM adventure_characters
                WHERE adventure_id = ?
                ORDER BY party_order, character_id
                """,
                (adventure_id,),
            ).fetchall()
        if not rows and fallback_character_id <= 0:
            return [], []
        party_ids = [row["character_id"] for row in rows] or [fallback_character_id]
        characters = []
        character_service = CharacterService(self.store)
        state_by_id = {row["character_id"]: decode_json(row["state_json"], {}) for row in rows}
        for character_id in party_ids:
            try:
                base = character_service.get(character_id)
                characters.append(self._character_from_state(base, state_by_id.get(character_id, {})))
            except Exception:
                continue
        if not characters and fallback_character_id:
            characters = [character_service.get(fallback_character_id)]
            party_ids = [fallback_character_id]
        return party_ids, characters

    def _isekai_character_for_adventure(self, adventure_id: int) -> dict[str, Any] | None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM isekai_characters WHERE adventure_id = ?", (adventure_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "adventure_id": row["adventure_id"],
            "name": row["name"],
            "race": row["race"],
            "class_name": row["class_name"],
            "background": row["background"],
            "alignment": row["alignment"],
            "level": row["level"],
            "hp_current": row["hp_current"],
            "hp_max": row["hp_max"],
            "armor_class": row["armor_class"],
            "strength": row["strength"],
            "dexterity": row["dexterity"],
            "constitution": row["constitution"],
            "intelligence": row["intelligence"],
            "wisdom": row["wisdom"],
            "charisma": row["charisma"],
            "gold": row["gold"],
            "inventory": decode_json(row["inventory_json"], []),
            "traits": decode_json(row["traits_json"], []),
            "world_reaction_tags": decode_json(row["world_reaction_tags_json"], []),
            "status_effects": decode_json(row["status_effects_json"], []),
        }

    def _isekai_survival_state_for_adventure(self, adventure_id: int) -> dict[str, Any] | None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM isekai_survival_states WHERE adventure_id = ?", (adventure_id,)).fetchone()
        if row is None:
            return None
        return {
            "adventure_id": row["adventure_id"],
            "day": row["day"],
            "time_of_day": row["time_of_day"],
            "hunger": row["hunger"],
            "thirst": row["thirst"],
            "fatigue": row["fatigue"],
            "sleep_need": row["sleep_need"],
            "temperature_risk": row["temperature_risk"],
            "morale": row["morale"],
            "weather": row["weather"],
            "location": row["location"],
            "shelter": row["shelter"],
            "last_action_type": row["last_action_type"],
            "state": decode_json(row["state_json"], {}),
        }

    def _character_from_state(self, base: CharacterOut, state: dict[str, Any]) -> CharacterOut:
        if not state:
            return base
        data = base.model_dump(mode="json")
        data.update(state)
        data["id"] = base.id
        data.update(character_progression(data["level"], data["experience_points"]))
        return CharacterOut.model_validate(data)

    def _map_message_row(self, row: Row) -> MessageOut:
        return MessageOut(
            id=row["id"],
            adventure_id=row["adventure_id"],
            role=row["role"],
            content=row["content"],
            metadata=decode_json(row["metadata_json"], {}),
            created_at=row["created_at"],
        )
