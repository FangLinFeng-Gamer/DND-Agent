from sqlite3 import Row

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.world_event import WorldEventCreate, WorldEventOut


class WorldEventService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def create(self, adventure_id: int, event: WorldEventCreate) -> WorldEventOut:
        self._ensure_adventure_exists(adventure_id)
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO world_events (
                    adventure_id, event_type, title, description, importance, metadata_json
                )
                VALUES (
                    :adventure_id, :event_type, :title, :description, :importance, :metadata_json
                )
                """,
                {
                    "adventure_id": adventure_id,
                    "event_type": event.event_type,
                    "title": event.title,
                    "description": event.description,
                    "importance": event.importance,
                    "metadata_json": encode_json(event.metadata),
                },
            )
            row = conn.execute("SELECT * FROM world_events WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._map_row(row)

    def list_for_adventure(self, adventure_id: int, min_importance: int = 0) -> list[WorldEventOut]:
        self._ensure_adventure_exists(adventure_id)
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM world_events
                WHERE adventure_id = ? AND importance >= ?
                ORDER BY id
                """,
                (adventure_id, min_importance),
            ).fetchall()
        return [self._map_row(row) for row in rows]

    def list_known_for_adventure(self, adventure_id: int, limit: int = 10) -> list[WorldEventOut]:
        events = self.list_for_adventure(adventure_id)
        known = [
            event
            for event in events
            if event.metadata.get("mode") == "isekai_survival"
            and event.metadata.get("known_to_character") is True
        ]
        return known[-limit:]

    def _ensure_adventure_exists(self, adventure_id: int) -> None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT id FROM adventures WHERE id = ?", (adventure_id,)).fetchone()
        if row is None:
            raise api_error(404, "adventure_not_found", "Adventure not found.")

    def _map_row(self, row: Row) -> WorldEventOut:
        return WorldEventOut(
            id=row["id"],
            adventure_id=row["adventure_id"],
            event_type=row["event_type"],
            title=row["title"],
            description=row["description"],
            importance=row["importance"],
            metadata=decode_json(row["metadata_json"], {}),
            created_at=row["created_at"],
        )
