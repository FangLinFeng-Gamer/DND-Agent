import re
from sqlite3 import Row

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.story import StoryCreate, StoryOut, StoryUpdate


DEFAULT_STORY_ID = "mistbell_tower"

DEFAULT_STORY = StoryOut(
    id=DEFAULT_STORY_ID,
    title="Mistbell Tower",
    description="An introductory mystery around a haunted border-town signal tower.",
    world_background=(
        "Ravenford is a rain-soaked border town that survives on caravan trade, peat fires, "
        "and the old signal tower on the hill. For three nights the tower bell has rung by "
        "itself at midnight, caravans have vanished in the fog, and pale lights now move "
        "beneath the abandoned shrine below the road."
    ),
    main_quest=(
        "Investigate Mistbell Tower, find the missing caravan, and decide whether to restore "
        "or break the failing ward under the hill."
    ),
    opening_location="Ravenford Wayhouse",
    opening_environment=(
        "Rain taps against the shutters while worried townsfolk crowd the common room. "
        "Mayor Elira Voss waits beside a wet map, and the old tower bell sounds once from the fog."
    ),
    opening_objective="Speak with Mayor Elira Voss, inspect the tower road, and find the first trace of the missing caravan.",
    important_objects=["wet road map", "tower bell", "muddy caravan token"],
    npcs=["Mayor Elira Voss", "Tovin Reed the wayhouse keeper"],
)


class StoryService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def seed_defaults(self) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO stories (
                    id, title, description, world_background, main_quest,
                    opening_location, opening_environment, opening_objective,
                    important_objects_json, npcs_json
                )
                VALUES (
                    :id, :title, :description, :world_background, :main_quest,
                    :opening_location, :opening_environment, :opening_objective,
                    :important_objects_json, :npcs_json
                )
                """,
                self._to_db_values(DEFAULT_STORY),
            )

    def list(self) -> list[StoryOut]:
        with self.store.connect() as conn:
            rows = conn.execute("SELECT * FROM stories ORDER BY created_at, title").fetchall()
        return [self._map_row(row) for row in rows]

    def get(self, story_id: str) -> StoryOut:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
        if row is None:
            raise api_error(404, "story_not_found", "Story not found.")
        return self._map_row(row)

    def create(self, story: StoryCreate) -> StoryOut:
        story_id = self._unique_id(story.title)
        output = StoryOut(id=story_id, **story.model_dump())
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO stories (
                    id, title, description, world_background, main_quest,
                    opening_location, opening_environment, opening_objective,
                    important_objects_json, npcs_json
                )
                VALUES (
                    :id, :title, :description, :world_background, :main_quest,
                    :opening_location, :opening_environment, :opening_objective,
                    :important_objects_json, :npcs_json
                )
                """,
                self._to_db_values(output),
            )
            row = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
        return self._map_row(row)

    def delete(self, story_id: str) -> None:
        if story_id == DEFAULT_STORY_ID:
            raise api_error(400, "default_story_locked", "The default story cannot be deleted.")

        with self.store.connect() as conn:
            result = conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))
        if result.rowcount == 0:
            raise api_error(404, "story_not_found", "Story not found.")

    def update(self, story_id: str, update: StoryUpdate) -> StoryOut:
        if story_id == DEFAULT_STORY_ID:
            raise api_error(400, "default_story_locked", "The default story cannot be modified.")

        current = self.get(story_id)
        values = current.model_dump()
        values.update(update.model_dump(exclude_unset=True))
        output = StoryOut(**values)

        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE stories
                SET title = :title,
                    description = :description,
                    world_background = :world_background,
                    main_quest = :main_quest,
                    opening_location = :opening_location,
                    opening_environment = :opening_environment,
                    opening_objective = :opening_objective,
                    important_objects_json = :important_objects_json,
                    npcs_json = :npcs_json
                WHERE id = :id
                """,
                self._to_db_values(output),
            )
            row = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
        return self._map_row(row)

    def _unique_id(self, title: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "story"
        candidate = base
        suffix = 2
        with self.store.connect() as conn:
            while conn.execute("SELECT 1 FROM stories WHERE id = ?", (candidate,)).fetchone():
                candidate = f"{base}-{suffix}"
                suffix += 1
        return candidate

    def _to_db_values(self, story: StoryOut) -> dict[str, str]:
        values = story.model_dump()
        values["important_objects_json"] = encode_json(values.pop("important_objects"))
        values["npcs_json"] = encode_json(values.pop("npcs"))
        return values

    def _map_row(self, row: Row) -> StoryOut:
        return StoryOut(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            world_background=row["world_background"],
            main_quest=row["main_quest"],
            opening_location=row["opening_location"],
            opening_environment=row["opening_environment"],
            opening_objective=row["opening_objective"],
            important_objects=decode_json(row["important_objects_json"], []),
            npcs=decode_json(row["npcs_json"], []),
        )
