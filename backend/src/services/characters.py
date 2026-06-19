import hashlib
import json
from sqlite3 import Row
from typing import Any

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.character import (
    CharacterCreate,
    CharacterDraftCommit,
    CharacterOut,
    CharacterUpdate,
)
from backend.src.services.character_progression import (
    character_progression,
    level_for_experience,
)


ABILITY_FIELDS = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
UPDATE_COLUMNS = {
    "name",
    "race",
    "class_name",
    "level",
    "experience_points",
    "background",
    "alignment",
    "hp_current",
    "hp_max",
    "armor_class",
    *ABILITY_FIELDS,
    "skills",
    "inventory",
    "spells",
    "notes",
}


class CharacterCommitConflict(ValueError):
    pass


class CharacterService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def create(self, character: CharacterCreate) -> CharacterOut:
        with self.store.connect() as conn:
            row = self._insert(conn, character)

        return self._map_row(row)

    def create_idempotent(
        self,
        character: CharacterDraftCommit,
        commit_key: str,
    ) -> CharacterOut:
        normalized_key = commit_key.strip()
        if not normalized_key:
            raise ValueError("commit_key must not be empty.")
        fingerprint = self._commit_fingerprint(character)

        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT characters.*, character_creation_commits.payload_fingerprint
                FROM character_creation_commits
                JOIN characters ON characters.id = character_creation_commits.character_id
                WHERE character_creation_commits.commit_key = ?
                """,
                (normalized_key,),
            ).fetchone()
            if existing is not None:
                if existing["payload_fingerprint"] != fingerprint:
                    raise CharacterCommitConflict(
                        "commit_key already refers to a different character payload."
                    )
                return self._map_row(existing)

            row = self._insert(conn, character)
            conn.execute(
                """
                INSERT INTO character_creation_commits (
                    commit_key,
                    character_id,
                    payload_fingerprint
                )
                VALUES (?, ?, ?)
                """,
                (normalized_key, row["id"], fingerprint),
            )
        return self._map_row(row)

    def list(self) -> list[CharacterOut]:
        with self.store.connect() as conn:
            rows = conn.execute("SELECT * FROM characters ORDER BY id").fetchall()
        return [self._map_row(row) for row in rows]

    def get(self, character_id: int) -> CharacterOut:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM characters WHERE id = ?", (character_id,)).fetchone()
        if row is None:
            raise api_error(404, "character_not_found", "Character not found.")
        return self._map_row(row)

    def update(self, character_id: int, update: CharacterUpdate) -> CharacterOut:
        values = update.model_dump(exclude_unset=True)
        current = self.get(character_id)
        self._validate_update(values, current)
        if "experience_points" in values and "level" not in values:
            values["level"] = max(current.level, level_for_experience(values["experience_points"]))

        if values:
            db_values = self._to_db_values(values)
            assignments = ", ".join(f"{column} = :{column}" for column in db_values)
            db_values["id"] = character_id
            with self.store.connect() as conn:
                result = conn.execute(
                    f"UPDATE characters SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id",
                    db_values,
                )
                if result.rowcount == 0:
                    raise api_error(404, "character_not_found", "Character not found.")
                row = conn.execute("SELECT * FROM characters WHERE id = ?", (character_id,)).fetchone()
                if row is None:
                    raise api_error(404, "character_not_found", "Character not found.")
            return self._map_row(row)

        return self.get(character_id)

    def delete(self, character_id: int) -> None:
        with self.store.connect() as conn:
            conn.execute(
                "DELETE FROM character_creation_commits WHERE character_id = ?",
                (character_id,),
            )
            result = conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        if result.rowcount == 0:
            raise api_error(404, "character_not_found", "Character not found.")

    def _default_ability_scores(self, class_name: str) -> dict[str, int]:
        scores = {field: 10 for field in ABILITY_FIELDS}
        primary_by_class = {
            "fighter": "strength",
            "ranger": "dexterity",
            "wizard": "intelligence",
        }
        scores[primary_by_class.get(class_name.lower(), "strength")] = 14
        return scores

    def _insert(
        self,
        conn,
        character: CharacterCreate | CharacterDraftCommit,
    ) -> Row:
        if isinstance(character, CharacterDraftCommit):
            values = {
                **character.model_dump(
                    exclude={
                        "draft_revision",
                        "skills",
                        "proficiencies",
                        "inventory",
                        "spells",
                    }
                ),
                "level": 1,
                "experience_points": 0,
                "skills_json": encode_json(character.skills),
                "proficiencies_json": encode_json(character.proficiencies),
                "inventory_json": encode_json(character.inventory),
                "spells_json": encode_json(character.spells),
            }
        else:
            scores = self._default_ability_scores(character.class_name)
            values = {
                "name": character.name,
                "race": character.race,
                "class_name": character.class_name,
                "level": level_for_experience(character.experience_points),
                "experience_points": character.experience_points,
                "background": character.background,
                "alignment": character.alignment,
                "hp_current": 10,
                "hp_max": 10,
                "armor_class": 12,
                **scores,
                "skills_json": encode_json({}),
                "proficiencies_json": encode_json({}),
                "inventory_json": encode_json(["Backpack", "Rations", "Torch"]),
                "spells_json": encode_json([]),
                "notes": character.notes,
            }
        cursor = conn.execute(
            """
            INSERT INTO characters (
                name, race, class_name, level, experience_points, background, alignment,
                hp_current, hp_max, armor_class, strength, dexterity,
                constitution, intelligence, wisdom, charisma, skills_json,
                proficiencies_json, inventory_json, spells_json, notes
            )
            VALUES (
                :name, :race, :class_name, :level, :experience_points, :background, :alignment,
                :hp_current, :hp_max, :armor_class, :strength, :dexterity,
                :constitution, :intelligence, :wisdom, :charisma,
                :skills_json, :proficiencies_json, :inventory_json,
                :spells_json, :notes
            )
            """,
            values,
        )
        return conn.execute(
            "SELECT * FROM characters WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    def _commit_fingerprint(self, character: CharacterDraftCommit) -> str:
        canonical = json.dumps(
            character.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _validate_update(self, values: dict[str, Any], current: CharacterOut) -> None:
        for key in values:
            if key not in UPDATE_COLUMNS:
                raise api_error(400, "validation_error", f"Unsupported character field: {key}.")

        for key, value in values.items():
            if value is None:
                raise api_error(400, "validation_error", f"{key} cannot be null.")

        if "level" in values and not 1 <= values["level"] <= 20:
            raise api_error(400, "validation_error", "Level must be between 1 and 20.")
        if "experience_points" in values and values["experience_points"] < 0:
            raise api_error(400, "validation_error", "Experience points cannot be negative.")
        for key in ("hp_current", "hp_max"):
            if key in values and values[key] < 0:
                raise api_error(400, "validation_error", "HP cannot be negative.")
        if "armor_class" in values and not 1 <= values["armor_class"] <= 30:
            raise api_error(400, "validation_error", "Armor class must be between 1 and 30.")
        for key in ABILITY_FIELDS:
            if key in values and not 1 <= values[key] <= 30:
                raise api_error(400, "validation_error", "Ability scores must be between 1 and 30.")

        hp_current = values.get("hp_current", current.hp_current)
        hp_max = values.get("hp_max", current.hp_max)
        if hp_max <= 0:
            raise api_error(400, "validation_error", "Maximum HP must be greater than 0.")
        if hp_current > hp_max:
            raise api_error(400, "validation_error", "Current HP cannot exceed maximum HP.")

    def _to_db_values(self, values: dict[str, Any]) -> dict[str, Any]:
        db_values = dict(values)
        for field in ("skills", "inventory", "spells"):
            if field in db_values:
                db_values[f"{field}_json"] = encode_json(db_values.pop(field))
        return db_values

    def _map_row(self, row: Row) -> CharacterOut:
        progression = character_progression(row["level"], row["experience_points"])
        return CharacterOut(
            id=row["id"],
            name=row["name"],
            race=row["race"],
            class_name=row["class_name"],
            level=row["level"],
            experience_points=row["experience_points"],
            next_level_experience=progression["next_level_experience"],
            experience_to_next_level=progression["experience_to_next_level"],
            level_progress=progression["level_progress"],
            background=row["background"],
            alignment=row["alignment"],
            hp_current=row["hp_current"],
            hp_max=row["hp_max"],
            armor_class=row["armor_class"],
            strength=row["strength"],
            dexterity=row["dexterity"],
            constitution=row["constitution"],
            intelligence=row["intelligence"],
            wisdom=row["wisdom"],
            charisma=row["charisma"],
            skills=decode_json(row["skills_json"], {}),
            proficiencies=decode_json(row["proficiencies_json"], {}),
            inventory=decode_json(row["inventory_json"], []),
            spells=decode_json(row["spells_json"], []),
            notes=row["notes"],
        )
