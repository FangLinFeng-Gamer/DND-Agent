from backend.src.agent.character_creation.models import (
    CharacterCreationHistoryMessage,
)
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json


class CharacterCreationMessageRepository:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def append(
        self,
        session_id: int,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> CharacterCreationHistoryMessage:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO character_creation_messages (
                    session_id, role, content, metadata_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, encode_json(metadata or {})),
            )
            row = conn.execute(
                "SELECT * FROM character_creation_messages WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._map(row)

    def list_recent(
        self,
        session_id: int,
        limit: int = 12,
    ) -> list[CharacterCreationHistoryMessage]:
        with self.store.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM character_creation_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._map(row) for row in reversed(rows)]

    def _map(self, row) -> CharacterCreationHistoryMessage:
        return CharacterCreationHistoryMessage(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            metadata=decode_json(row["metadata_json"], {}),
            created_at=row["created_at"],
        )
