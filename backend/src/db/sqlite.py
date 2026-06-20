import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        race TEXT NOT NULL,
        class_name TEXT NOT NULL,
        level INTEGER NOT NULL,
        experience_points INTEGER NOT NULL DEFAULT 0,
        background TEXT NOT NULL,
        alignment TEXT NOT NULL,
        hp_current INTEGER NOT NULL,
        hp_max INTEGER NOT NULL,
        armor_class INTEGER NOT NULL,
        strength INTEGER NOT NULL,
        dexterity INTEGER NOT NULL,
        constitution INTEGER NOT NULL,
        intelligence INTEGER NOT NULL,
        wisdom INTEGER NOT NULL,
        charisma INTEGER NOT NULL,
        skills_json TEXT NOT NULL,
        proficiencies_json TEXT NOT NULL,
        inventory_json TEXT NOT NULL,
        spells_json TEXT NOT NULL,
        notes TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS world_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        content TEXT NOT NULL,
        tags_json TEXT NOT NULL,
        source TEXT,
        page INTEGER,
        metadata_json TEXT NOT NULL,
        UNIQUE(category, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stories (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        world_background TEXT NOT NULL,
        main_quest TEXT NOT NULL,
        opening_location TEXT NOT NULL,
        opening_environment TEXT NOT NULL,
        opening_objective TEXT NOT NULL,
        important_objects_json TEXT NOT NULL,
        npcs_json TEXT NOT NULL,
        encounters_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS adventures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'dnd',
        world_id TEXT NOT NULL,
        character_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        summary TEXT NOT NULL,
        current_scene_json TEXT NOT NULL,
        world_state_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS adventure_characters (
        adventure_id INTEGER NOT NULL,
        character_id INTEGER NOT NULL,
        party_order INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'player',
        state_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (adventure_id, character_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_adventure_characters_adventure ON adventure_characters(adventure_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_adventure_characters_character ON adventure_characters(character_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS combat_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_id INTEGER NOT NULL UNIQUE,
        is_active INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        turn_index INTEGER NOT NULL,
        participants_json TEXT NOT NULL,
        action_log_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS generated_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        subject_id TEXT,
        prompt TEXT NOT NULL,
        status TEXT NOT NULL,
        result_uri TEXT,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS map_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        storage_key TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        width INTEGER,
        height INTEGER,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_assets_type ON map_assets(asset_type)
    """,
    """
    CREATE TABLE IF NOT EXISTS map_scenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        adventure_id INTEGER,
        story_id TEXT,
        grid_type TEXT NOT NULL,
        grid_size INTEGER NOT NULL,
        scale REAL NOT NULL,
        scale_unit TEXT NOT NULL,
        background_color TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 0,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_scenes_adventure ON map_scenes(adventure_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_scenes_story ON map_scenes(story_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS map_scene_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id INTEGER NOT NULL,
        asset_id INTEGER NOT NULL,
        item_type TEXT NOT NULL,
        layer TEXT NOT NULL,
        name TEXT,
        x REAL NOT NULL,
        y REAL NOT NULL,
        width REAL NOT NULL,
        height REAL NOT NULL,
        rotation REAL NOT NULL,
        locked INTEGER NOT NULL,
        visible INTEGER NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_scene_items_scene ON map_scene_items(scene_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS map_combat_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id INTEGER NOT NULL,
        adventure_id INTEGER NOT NULL,
        participant_name TEXT NOT NULL,
        side TEXT NOT NULL,
        kind TEXT NOT NULL,
        x REAL NOT NULL,
        y REAL NOT NULL,
        size REAL NOT NULL,
        speed_ft REAL NOT NULL,
        reach_ft REAL NOT NULL,
        visible INTEGER NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(scene_id, participant_name)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_combat_tokens_scene ON map_combat_tokens(scene_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_combat_tokens_adventure ON map_combat_tokens(adventure_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS map_walls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id INTEGER NOT NULL,
        x1 REAL NOT NULL,
        y1 REAL NOT NULL,
        x2 REAL NOT NULL,
        y2 REAL NOT NULL,
        wall_type TEXT NOT NULL,
        blocks_movement INTEGER NOT NULL,
        blocks_sight INTEGER NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_walls_scene ON map_walls(scene_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS map_lights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id INTEGER NOT NULL,
        x REAL NOT NULL,
        y REAL NOT NULL,
        radius REAL NOT NULL,
        color TEXT NOT NULL,
        intensity REAL NOT NULL,
        visible INTEGER NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_lights_scene ON map_lights(scene_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS map_fog_shapes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id INTEGER NOT NULL,
        geometry_json TEXT NOT NULL,
        mode TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_map_fog_shapes_scene ON map_fog_shapes(scene_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS llm_models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        provider TEXT NOT NULL,
        base_url TEXT NOT NULL,
        api_key TEXT NOT NULL,
        model_name TEXT NOT NULL,
        temperature REAL NOT NULL,
        max_context_tokens INTEGER NOT NULL,
        is_active INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS world_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        importance INTEGER NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS character_creation_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        locale TEXT NOT NULL,
        status TEXT NOT NULL,
        draft_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS character_creation_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS character_creation_commits (
        commit_key TEXT PRIMARY KEY,
        character_id INTEGER NOT NULL UNIQUE,
        payload_fingerprint TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


def encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def decode_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


class SQLiteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            for statement in SCHEMA:
                conn.execute(statement)
            self._ensure_column(conn, "adventures", "mode", "TEXT NOT NULL DEFAULT 'dnd'")
            self._ensure_column(conn, "adventures", "story_id", "TEXT NOT NULL DEFAULT 'mistbell_tower'")
            self._ensure_column(conn, "adventures", "story_snapshot_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "adventures", "world_state_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "stories", "encounters_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "combat_states", "action_log_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "character_creation_sessions", "revision", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "characters", "experience_points", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "adventure_characters", "state_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(
                conn,
                "characters",
                "proficiencies_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                conn,
                "character_creation_commits",
                "payload_fingerprint",
                "TEXT NOT NULL DEFAULT ''",
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO adventure_characters (
                    adventure_id, character_id, party_order, role
                )
                SELECT id, character_id, 0, 'player'
                FROM adventures
                """
            )
            self._backfill_adventure_character_state(conn)

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _backfill_adventure_character_state(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT
                adventure_characters.adventure_id,
                characters.*
            FROM adventure_characters
            JOIN characters ON characters.id = adventure_characters.character_id
            WHERE adventure_characters.state_json = '{}'
                OR adventure_characters.state_json = ''
            """
        ).fetchall()
        for row in rows:
            state = {
                "id": row["id"],
                "name": row["name"],
                "race": row["race"],
                "class_name": row["class_name"],
                "level": row["level"],
                "experience_points": row["experience_points"],
                "background": row["background"],
                "alignment": row["alignment"],
                "hp_current": row["hp_current"],
                "hp_max": row["hp_max"],
                "armor_class": row["armor_class"],
                "strength": row["strength"],
                "dexterity": row["dexterity"],
                "constitution": row["constitution"],
                "intelligence": row["intelligence"],
                "wisdom": row["wisdom"],
                "charisma": row["charisma"],
                "skills": decode_json(row["skills_json"], {}),
                "proficiencies": decode_json(row["proficiencies_json"], {}),
                "inventory": decode_json(row["inventory_json"], []),
                "spells": decode_json(row["spells_json"], []),
                "notes": row["notes"],
            }
            conn.execute(
                """
                UPDATE adventure_characters
                SET state_json = ?
                WHERE adventure_id = ? AND character_id = ?
                """,
                (encode_json(state), row["adventure_id"], row["id"]),
            )
