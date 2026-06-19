import re
from sqlite3 import Row

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.story import StoryCreate, StoryOut, StoryUpdate


DEFAULT_STORY_ID = "mistbell_tower"

DEFAULT_STORY = StoryOut(
    id=DEFAULT_STORY_ID,
    title="月井节的失窃银铃",
    description="一个适合新手开局的边境村调查冒险，包含交涉、线索追踪和一次小型遭遇战。",
    world_background=(
        "柳溪村依靠一口古老月井生存。每年月井节，村民会摇响银铃感谢井灵守护水源。"
        "可今年银铃在仪式前夜失踪，井水开始泛出冷冷的银光，牲畜拒绝饮水，"
        "孩子们说夜里听见井底有人唱歌。村民努力维持节庆热闹，"
        "但湿脚印从井边一路延伸向废弃旧磨坊。"
    ),
    main_quest=(
        "找回月井银铃，查清失窃原因，阻止井水诅咒扩散，并决定如何处置被封在井下的小精露米。"
    ),
    opening_location="柳溪村广场",
    opening_environment=(
        "黄昏的节庆灯笼已经点亮，糖苹果、烤栗子和木笛声挤满广场。"
        "村长玛拉把冒险者请到月井旁，压低声音说明银铃失窃。"
        "就在她说话时，井中传来一声空洞回响，像有人在水面下轻轻敲钟。"
    ),
    opening_objective="询问村长玛拉，检查月井边的湿脚印，并决定先调查旧磨坊、节庆摊位，还是守夜人的小屋。",
    important_objects=["月井银铃", "湿泥脚印", "裂开的蓝玻璃珠", "旧磨坊钥匙"],
    npcs=["村长玛拉", "守夜人布伦", "卖糖苹果的妮娅", "井下小精露米"],
    encounters=[
        {
            "id": "moonwell_sprite",
            "title": "井下银铃的守护者",
            "description": (
                "玩家逼近银铃、强行夺取银铃，或在旧磨坊/月井线索处让井下威胁升级时，"
                "井水中的小精露米或被诅咒的银光会迎战。"
            ),
            "trigger_keywords": [
                "旧磨坊",
                "磨坊",
                "井下",
                "月井",
                "银铃",
                "水下",
                "攻击",
                "开打",
                "夺取银铃",
                "拿走银铃",
                "冲向",
                "砍",
            ],
            "enemies": [
                {
                    "name": "井水小妖露米",
                    "side": "enemy",
                    "hp": 9,
                    "hp_max": 9,
                    "ac": 12,
                    "attack_bonus": 3,
                    "damage": "1d6+1",
                    "damage_type": "cold",
                    "initiative_bonus": 2,
                    "kind": "npc",
                }
            ],
        }
    ],
)


class StoryService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def seed_defaults(self) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO stories (
                    id, title, description, world_background, main_quest,
                    opening_location, opening_environment, opening_objective,
                    important_objects_json, npcs_json, encounters_json
                )
                VALUES (
                    :id, :title, :description, :world_background, :main_quest,
                    :opening_location, :opening_environment, :opening_objective,
                    :important_objects_json, :npcs_json, :encounters_json
                )
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    world_background = excluded.world_background,
                    main_quest = excluded.main_quest,
                    opening_location = excluded.opening_location,
                    opening_environment = excluded.opening_environment,
                    opening_objective = excluded.opening_objective,
                    important_objects_json = excluded.important_objects_json,
                    npcs_json = excluded.npcs_json,
                    encounters_json = excluded.encounters_json,
                    updated_at = CURRENT_TIMESTAMP
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
                    important_objects_json, npcs_json, encounters_json
                )
                VALUES (
                    :id, :title, :description, :world_background, :main_quest,
                    :opening_location, :opening_environment, :opening_objective,
                    :important_objects_json, :npcs_json, :encounters_json
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
                    npcs_json = :npcs_json,
                    encounters_json = :encounters_json
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
        values["encounters_json"] = encode_json(values.pop("encounters"))
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
            encounters=decode_json(row["encounters_json"], []),
        )
