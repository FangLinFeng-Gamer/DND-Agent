from __future__ import annotations

from sqlite3 import Row
from typing import Any, List

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.adventure import AdventureCreate, AdventureOut, MessageOut, SceneState
from backend.src.schemas.story import StoryOut
from backend.src.services.characters import CharacterService


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
                    title, world_id, story_id, character_id, status, summary,
                    current_scene_json, story_snapshot_json
                )
                VALUES (
                    :title, :world_id, :story_id, :character_id, :status, :summary,
                    :current_scene_json, :story_snapshot_json
                )
                """,
                {
                    "title": adventure.title,
                    "world_id": adventure.world_id,
                    "story_id": adventure.story_id,
                    "character_id": primary_character_id,
                    "status": "active",
                    "summary": "",
                    "current_scene_json": encode_json(scene.model_dump()),
                    "story_snapshot_json": encode_json(story.model_dump() if story else {}),
                },
            )
            adventure_id = cursor.lastrowid
            conn.executemany(
                """
                INSERT INTO adventure_characters (
                    adventure_id, character_id, party_order, role
                )
                VALUES (?, ?, ?, 'player')
                """,
                [(adventure_id, character.id, index) for index, character in enumerate(party)],
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
        }

    def save_combat_state(self, adventure_id: int, state: dict[str, Any]) -> dict[str, Any]:
        self.get(adventure_id, include_messages=False)
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO combat_states (
                    adventure_id, is_active, round_number, turn_index, participants_json
                )
                VALUES (
                    :adventure_id, :is_active, :round_number, :turn_index, :participants_json
                )
                ON CONFLICT(adventure_id) DO UPDATE SET
                    is_active = excluded.is_active,
                    round_number = excluded.round_number,
                    turn_index = excluded.turn_index,
                    participants_json = excluded.participants_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                {
                    "adventure_id": adventure_id,
                    "is_active": 1 if state.get("is_active") else 0,
                    "round_number": state.get("round_number", 1),
                    "turn_index": state.get("turn_index", 0),
                    "participants_json": encode_json(state.get("participants", [])),
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

    def _get_adventure_row(self, adventure_id: int) -> Row:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM adventures WHERE id = ?", (adventure_id,)).fetchone()
        if row is None:
            raise api_error(404, "adventure_not_found", "Adventure not found.")
        return row

    def _map_adventure_row(self, row: Row) -> AdventureOut:
        party_ids, party_characters = self._party_for_adventure(row["id"], row["character_id"])
        return AdventureOut(
            id=row["id"],
            title=row["title"],
            world_id=row["world_id"],
            story_id=row["story_id"],
            character_id=row["character_id"],
            party_character_ids=party_ids,
            party_characters=party_characters,
            status=row["status"],
            summary=row["summary"],
            current_scene=SceneState.model_validate(decode_json(row["current_scene_json"], {})),
        )

    def _party_for_adventure(self, adventure_id: int, fallback_character_id: int) -> tuple[list[int], list]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT character_id
                FROM adventure_characters
                WHERE adventure_id = ?
                ORDER BY party_order, character_id
                """,
                (adventure_id,),
            ).fetchall()
        party_ids = [row["character_id"] for row in rows] or [fallback_character_id]
        characters = []
        character_service = CharacterService(self.store)
        for character_id in party_ids:
            try:
                characters.append(character_service.get(character_id))
            except Exception:
                continue
        if not characters and fallback_character_id:
            characters = [character_service.get(fallback_character_id)]
            party_ids = [fallback_character_id]
        return party_ids, characters

    def _map_message_row(self, row: Row) -> MessageOut:
        return MessageOut(
            id=row["id"],
            adventure_id=row["adventure_id"],
            role=row["role"],
            content=row["content"],
            metadata=decode_json(row["metadata_json"], {}),
            created_at=row["created_at"],
        )
