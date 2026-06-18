import hashlib
import math
from pathlib import Path
from sqlite3 import Row

from fastapi import HTTPException

from backend.src.core.errors import api_error
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.maps import (
    MapCombatTokenOut,
    MapCombatTokenUpdate,
    MapContextOut,
    MapAssetOut,
    MapFogShapeOut,
    MapLightOut,
    MapSceneCreate,
    MapSceneItemCreate,
    MapSceneItemOut,
    MapSceneOut,
    MapSceneUpdate,
    MapWallOut,
)
from backend.src.services.adventures import AdventureService


ALLOWED_ASSET_TYPES = {"map", "token", "prop", "portrait"}
ALLOWED_GRID_TYPES = {"square", "hex", "none"}
ALLOWED_ITEM_TYPES = {"background", "token", "prop"}
ALLOWED_LAYERS = {"background", "object", "token", "gm"}
IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class MapAttackRangeError(ValueError):
    pass


class MapService:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.asset_root = store.db_path.parent / "assets"

    def upload_asset(
        self,
        *,
        name: str,
        asset_type: str,
        filename: str | None,
        mime_type: str,
        content: bytes,
    ) -> MapAssetOut:
        normalized_name = name.strip()
        normalized_type = asset_type.strip().lower()
        normalized_mime = mime_type.split(";", 1)[0].strip().lower()
        if not normalized_name:
            raise api_error(400, "asset_name_required", "Asset name is required.")
        if normalized_type not in ALLOWED_ASSET_TYPES:
            raise api_error(400, "unsupported_asset_type", "Unsupported map asset type.")
        if normalized_mime not in IMAGE_EXTENSIONS:
            raise api_error(400, "unsupported_asset_mime_type", "Only image assets are supported.")
        if not content:
            raise api_error(400, "empty_asset_file", "Uploaded asset file is empty.")

        digest = hashlib.sha256(content).hexdigest()
        extension = self._extension_for(filename, normalized_mime)
        storage_key = f"{digest[:2]}/{digest}{extension}"
        file_path = self._asset_file_path(storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_bytes(content)

        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO map_assets (
                    name, asset_type, storage_key, mime_type, sha256, size_bytes,
                    width, height, metadata_json
                )
                VALUES (
                    :name, :asset_type, :storage_key, :mime_type, :sha256, :size_bytes,
                    :width, :height, :metadata_json
                )
                """,
                {
                    "name": normalized_name,
                    "asset_type": normalized_type,
                    "storage_key": storage_key,
                    "mime_type": normalized_mime,
                    "sha256": digest,
                    "size_bytes": len(content),
                    "width": None,
                    "height": None,
                    "metadata_json": encode_json({"filename": Path(filename or normalized_name).name}),
                },
            )
            row = conn.execute("SELECT * FROM map_assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._map_asset_row(row)

    def list_assets(self, asset_type: str | None = None) -> list[MapAssetOut]:
        with self.store.connect() as conn:
            if asset_type:
                rows = conn.execute(
                    "SELECT * FROM map_assets WHERE asset_type = ? ORDER BY id DESC",
                    (asset_type.strip().lower(),),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM map_assets ORDER BY id DESC").fetchall()
        return [self._map_asset_row(row) for row in rows]

    def get_asset(self, asset_id: int) -> MapAssetOut:
        return self._map_asset_row(self._get_asset_row(asset_id))

    def get_asset_file(self, asset_id: int) -> tuple[MapAssetOut, Path]:
        asset = self.get_asset(asset_id)
        path = self._asset_file_path(asset.storage_key)
        if not path.exists() or not path.is_file():
            raise api_error(404, "asset_file_not_found", "Map asset file not found.")
        return asset, path

    def delete_asset(self, asset_id: int) -> None:
        self._get_asset_row(asset_id)
        with self.store.connect() as conn:
            in_use = conn.execute(
                "SELECT COUNT(*) AS count FROM map_scene_items WHERE asset_id = ?",
                (asset_id,),
            ).fetchone()["count"]
            if in_use:
                raise api_error(400, "asset_in_use", "Map asset is used by one or more scenes.")
            conn.execute("DELETE FROM map_assets WHERE id = ?", (asset_id,))

    def create_scene(self, scene: MapSceneCreate) -> MapSceneOut:
        self._validate_grid_type(scene.grid_type)
        if scene.adventure_id is not None:
            AdventureService(self.store).get(scene.adventure_id, include_messages=False)

        background_asset = None
        if scene.background_asset_id is not None:
            background_asset = self.get_asset(scene.background_asset_id)

        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO map_scenes (
                    name, adventure_id, story_id, grid_type, grid_size, scale,
                    scale_unit, background_color, active, metadata_json
                )
                VALUES (
                    :name, :adventure_id, :story_id, :grid_type, :grid_size, :scale,
                    :scale_unit, :background_color, :active, :metadata_json
                )
                """,
                {
                    "name": scene.name.strip(),
                    "adventure_id": scene.adventure_id,
                    "story_id": scene.story_id,
                    "grid_type": scene.grid_type,
                    "grid_size": scene.grid_size,
                    "scale": scene.scale,
                    "scale_unit": scene.scale_unit,
                    "background_color": scene.background_color,
                    "active": 0,
                    "metadata_json": encode_json(scene.metadata),
                },
            )
            scene_id = cursor.lastrowid
            if background_asset is not None:
                self._insert_item(
                    conn,
                    scene_id=scene_id,
                    item=MapSceneItemCreate(
                        asset_id=background_asset.id,
                        item_type="background",
                        layer="background",
                        name=background_asset.name,
                        width=background_asset.width or 1000,
                        height=background_asset.height or 1000,
                        locked=True,
                    ),
                )
        return self.get_scene(scene_id)

    def list_scenes(self, adventure_id: int | None = None, story_id: str | None = None) -> list[MapSceneOut]:
        clauses = []
        params = []
        if adventure_id is not None:
            clauses.append("adventure_id = ?")
            params.append(adventure_id)
        if story_id is not None:
            clauses.append("story_id = ?")
            params.append(story_id)
            if adventure_id is None:
                clauses.append("adventure_id IS NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.store.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM map_scenes {where} ORDER BY active DESC, id DESC",
                params,
            ).fetchall()
        return [self._map_scene_row(row) for row in rows]

    def bind_story_scenes_to_adventure(self, *, story_id: str, adventure_id: int) -> list[MapSceneOut]:
        AdventureService(self.store).get(adventure_id, include_messages=False)
        with self.store.connect() as conn:
            existing = conn.execute(
                "SELECT * FROM map_scenes WHERE adventure_id = ? ORDER BY active DESC, id DESC",
                (adventure_id,),
            ).fetchall()
            if existing:
                return [self._map_scene_row(row) for row in existing]

            templates = conn.execute(
                """
                SELECT *
                FROM map_scenes
                WHERE story_id = ? AND adventure_id IS NULL
                ORDER BY active DESC, id
                """,
                (story_id,),
            ).fetchall()
            has_active_template = any(bool(template["active"]) for template in templates)
            for index, template in enumerate(templates):
                cursor = conn.execute(
                    """
                    INSERT INTO map_scenes (
                        name, adventure_id, story_id, grid_type, grid_size, scale,
                        scale_unit, background_color, active, metadata_json
                    )
                    VALUES (
                        :name, :adventure_id, :story_id, :grid_type, :grid_size, :scale,
                        :scale_unit, :background_color, :active, :metadata_json
                    )
                    """,
                    {
                        "name": template["name"],
                        "adventure_id": adventure_id,
                        "story_id": story_id,
                        "grid_type": template["grid_type"],
                        "grid_size": template["grid_size"],
                        "scale": template["scale"],
                        "scale_unit": template["scale_unit"],
                        "background_color": template["background_color"],
                        "active": 1 if (bool(template["active"]) if has_active_template else index == 0) else 0,
                        "metadata_json": template["metadata_json"],
                    },
                )
                scene_id = cursor.lastrowid
                item_rows = conn.execute(
                    "SELECT * FROM map_scene_items WHERE scene_id = ? ORDER BY id",
                    (template["id"],),
                ).fetchall()
                for item in item_rows:
                    conn.execute(
                        """
                        INSERT INTO map_scene_items (
                            scene_id, asset_id, item_type, layer, name, x, y, width, height,
                            rotation, locked, visible, metadata_json
                        )
                        VALUES (
                            :scene_id, :asset_id, :item_type, :layer, :name, :x, :y, :width, :height,
                            :rotation, :locked, :visible, :metadata_json
                        )
                        """,
                        {
                            "scene_id": scene_id,
                            "asset_id": item["asset_id"],
                            "item_type": item["item_type"],
                            "layer": item["layer"],
                            "name": item["name"],
                            "x": item["x"],
                            "y": item["y"],
                            "width": item["width"],
                            "height": item["height"],
                            "rotation": item["rotation"],
                            "locked": item["locked"],
                            "visible": item["visible"],
                            "metadata_json": item["metadata_json"],
                        },
                    )
        return self.list_scenes(adventure_id=adventure_id)

    def get_scene(self, scene_id: int) -> MapSceneOut:
        return self._map_scene_row(self._get_scene_row(scene_id))

    def update_scene(self, scene_id: int, patch: MapSceneUpdate) -> MapSceneOut:
        self._get_scene_row(scene_id)
        values = patch.model_dump(exclude_unset=True)
        if "grid_type" in values and values["grid_type"] is not None:
            self._validate_grid_type(values["grid_type"])
        if "adventure_id" in values and values["adventure_id"] is not None:
            AdventureService(self.store).get(values["adventure_id"], include_messages=False)
        if not values:
            return self.get_scene(scene_id)

        assignments = []
        params = {"scene_id": scene_id}
        for key, value in values.items():
            column = "metadata_json" if key == "metadata" else key
            assignments.append(f"{column} = :{column}")
            params[column] = encode_json(value) if key == "metadata" else value
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        with self.store.connect() as conn:
            conn.execute(
                f"UPDATE map_scenes SET {', '.join(assignments)} WHERE id = :scene_id",
                params,
            )
        return self.get_scene(scene_id)

    def add_item(self, scene_id: int, item: MapSceneItemCreate) -> MapSceneItemOut:
        self._get_scene_row(scene_id)
        self._get_asset_row(item.asset_id)
        self._validate_item(item)
        with self.store.connect() as conn:
            item_id = self._insert_item(conn, scene_id=scene_id, item=item)
            row = conn.execute("SELECT * FROM map_scene_items WHERE id = ?", (item_id,)).fetchone()
        return self._map_item_row(row)

    def update_item(self, scene_id: int, item_id: int, item: MapSceneItemCreate) -> MapSceneItemOut:
        self._get_scene_row(scene_id)
        self._get_asset_row(item.asset_id)
        self._validate_item(item)
        with self.store.connect() as conn:
            result = conn.execute(
                """
                UPDATE map_scene_items
                SET asset_id = :asset_id,
                    item_type = :item_type,
                    layer = :layer,
                    name = :name,
                    x = :x,
                    y = :y,
                    width = :width,
                    height = :height,
                    rotation = :rotation,
                    locked = :locked,
                    visible = :visible,
                    metadata_json = :metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :item_id AND scene_id = :scene_id
                """,
                self._item_params(scene_id=scene_id, item_id=item_id, item=item),
            )
            if result.rowcount == 0:
                raise api_error(404, "map_scene_item_not_found", "Map scene item not found.")
            row = conn.execute("SELECT * FROM map_scene_items WHERE id = ?", (item_id,)).fetchone()
        return self._map_item_row(row)

    def activate_scene(self, scene_id: int) -> MapSceneOut:
        scene = self.get_scene(scene_id)
        with self.store.connect() as conn:
            if scene.adventure_id is not None:
                conn.execute(
                    "UPDATE map_scenes SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE adventure_id = ?",
                    (scene.adventure_id,),
                )
            elif scene.story_id is not None:
                conn.execute(
                    """
                    UPDATE map_scenes
                    SET active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE story_id = ? AND adventure_id IS NULL
                    """,
                    (scene.story_id,),
                )
            conn.execute(
                "UPDATE map_scenes SET active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (scene_id,),
            )
        return self.get_scene(scene_id)

    def get_active_scene_for_adventure(self, adventure_id: int) -> MapSceneOut | None:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM map_scenes WHERE adventure_id = ? AND active = 1 ORDER BY id DESC LIMIT 1",
                (adventure_id,),
            ).fetchone()
        return self._map_scene_row(row) if row is not None else None

    def ensure_combat_tokens(
        self,
        adventure_id: int,
        participants: list[dict] | tuple[dict, ...],
    ) -> list[MapCombatTokenOut]:
        scene = self.get_active_scene_for_adventure(adventure_id)
        if scene is None:
            return []

        grid_size = float(scene.grid_size or 70)
        side_counts: dict[str, int] = {}
        with self.store.connect() as conn:
            existing_rows = conn.execute(
                "SELECT * FROM map_combat_tokens WHERE scene_id = ?",
                (scene.id,),
            ).fetchall()
            existing = {row["participant_name"]: row for row in existing_rows}
            for index, participant in enumerate(participants):
                name = str(participant.get("name") or "").strip()
                if not name:
                    continue
                side = str(participant.get("side") or "enemy")
                kind = str(participant.get("kind") or "npc")
                speed_ft = float(participant.get("speed_ft", 30))
                reach_ft = float(participant.get("reach_ft", 5))
                metadata = {
                    "initiative": participant.get("initiative"),
                    "initiative_bonus": participant.get("initiative_bonus"),
                    "participant_index": index,
                }
                if name in existing:
                    conn.execute(
                        """
                        UPDATE map_combat_tokens
                        SET side = :side,
                            kind = :kind,
                            speed_ft = :speed_ft,
                            reach_ft = :reach_ft,
                            metadata_json = :metadata_json,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :id
                        """,
                        {
                            "id": existing[name]["id"],
                            "side": side,
                            "kind": kind,
                            "speed_ft": speed_ft,
                            "reach_ft": reach_ft,
                            "metadata_json": encode_json(metadata),
                        },
                    )
                    continue

                side_index = side_counts.get(side, 0)
                side_counts[side] = side_index + 1
                x, y = self._default_token_position(side=side, side_index=side_index, grid_size=grid_size)
                conn.execute(
                    """
                    INSERT INTO map_combat_tokens (
                        scene_id, adventure_id, participant_name, side, kind, x, y,
                        size, speed_ft, reach_ft, visible, metadata_json
                    )
                    VALUES (
                        :scene_id, :adventure_id, :participant_name, :side, :kind, :x, :y,
                        :size, :speed_ft, :reach_ft, :visible, :metadata_json
                    )
                    """,
                    {
                        "scene_id": scene.id,
                        "adventure_id": adventure_id,
                        "participant_name": name,
                        "side": side,
                        "kind": kind,
                        "x": x,
                        "y": y,
                        "size": grid_size,
                        "speed_ft": speed_ft,
                        "reach_ft": reach_ft,
                        "visible": 1,
                        "metadata_json": encode_json(metadata),
                    },
                )
        return self.list_combat_tokens(scene.id)

    def sync_scene_combat_tokens(self, scene_id: int) -> list[MapCombatTokenOut]:
        scene = self.get_scene(scene_id)
        if scene.adventure_id is None:
            raise api_error(400, "map_scene_not_bound", "Map scene is not bound to an adventure.")
        state = AdventureService(self.store).get_combat_state(scene.adventure_id)
        if state is None or not state.get("is_active"):
            return self.list_combat_tokens(scene_id)
        return self.ensure_combat_tokens(scene.adventure_id, state.get("participants", []))

    def list_combat_tokens(self, scene_id: int) -> list[MapCombatTokenOut]:
        self._get_scene_row(scene_id)
        with self.store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM map_combat_tokens WHERE scene_id = ? ORDER BY id",
                (scene_id,),
            ).fetchall()
        return [self._map_combat_token_row(row) for row in rows]

    def update_combat_token(
        self,
        scene_id: int,
        token_id: int,
        patch: MapCombatTokenUpdate,
    ) -> MapCombatTokenOut:
        self._get_scene_row(scene_id)
        values = patch.model_dump(exclude_unset=True)
        if not values:
            return self._get_combat_token(scene_id, token_id)

        assignments = []
        params = {"scene_id": scene_id, "token_id": token_id}
        for key, value in values.items():
            column = "metadata_json" if key == "metadata" else key
            assignments.append(f"{column} = :{column}")
            if key == "metadata":
                params[column] = encode_json(value or {})
            elif key == "visible":
                params[column] = 1 if value else 0
            else:
                params[column] = value
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        with self.store.connect() as conn:
            result = conn.execute(
                f"""
                UPDATE map_combat_tokens
                SET {', '.join(assignments)}
                WHERE id = :token_id AND scene_id = :scene_id
                """,
                params,
            )
            if result.rowcount == 0:
                raise api_error(404, "map_combat_token_not_found", "Map combat token not found.")
        return self._get_combat_token(scene_id, token_id)

    def get_map_context(self, adventure_id: int) -> MapContextOut:
        scene = self.get_active_scene_for_adventure(adventure_id)
        if scene is None:
            return MapContextOut(active_scene=None, tokens=[], distances={})
        tokens = self.list_combat_tokens(scene.id)
        return MapContextOut(
            active_scene=scene,
            tokens=tokens,
            distances=self._distance_matrix(scene, tokens),
        )

    def distances_from(self, adventure_id: int, participant_name: str) -> dict[str, float]:
        context = self.get_map_context(adventure_id)
        return context.distances.get(participant_name, {})

    def nearest_hostile_token(
        self,
        adventure_id: int,
        actor: dict,
        targets: list[dict],
    ) -> tuple[dict, float] | None:
        if not targets:
            return None
        distances = self.distances_from(adventure_id, str(actor.get("name") or ""))
        ranked = []
        for target in targets:
            name = str(target.get("name") or "")
            if name in distances:
                ranked.append((target, distances[name]))
        if not ranked:
            return None
        ranked.sort(key=lambda entry: (entry[1], int(entry[0].get("hp", 0)), str(entry[0].get("name", ""))))
        return ranked[0]

    def validate_attack_range(
        self,
        adventure_id: int,
        state: dict,
        action: dict,
    ) -> dict | None:
        if str(action.get("action_type") or "attack").replace("-", "_") != "attack":
            return None

        scene = self.get_active_scene_for_adventure(adventure_id)
        if scene is None:
            return None
        actor_name = str(action.get("actor_name") or action.get("attacker_name") or "")
        target_name = str(action.get("target_name") or "")
        if not actor_name or not target_name:
            return None

        tokens = self.list_combat_tokens(scene.id)
        actor_token = next((token for token in tokens if token.participant_name == actor_name and token.visible), None)
        target_token = next((token for token in tokens if token.participant_name == target_name and token.visible), None)
        if actor_token is None or target_token is None:
            return None

        actor = self._participant_by_name(state, actor_name)
        if actor is None:
            return None
        distance_ft = self._distance_ft(scene, actor_token, target_token)
        profile = self._attack_range_profile(actor, action.get("attack_id"))
        if profile["attack_kind"] == "ranged":
            normal_range = profile.get("normal_range_ft")
            long_range = profile.get("long_range_ft") or normal_range
            if long_range is not None and distance_ft > float(long_range):
                raise MapAttackRangeError(
                    f"{target_name} is {distance_ft:g} ft away, beyond {actor_name}'s range of {float(long_range):g} ft."
                )
            mode = str(action.get("mode") or "normal")
            long_range_disadvantage = normal_range is not None and distance_ft > float(normal_range)
            if long_range_disadvantage and mode == "normal":
                action["mode"] = "disadvantage"
                mode = "disadvantage"
            return {
                "scene_id": scene.id,
                "distance_ft": distance_ft,
                "attack_kind": "ranged",
                "normal_range_ft": normal_range,
                "long_range_ft": long_range,
                "within_normal_range": not long_range_disadvantage,
                "mode": mode,
            }

        reach_ft = float(profile.get("reach_ft") or actor.get("reach_ft") or actor_token.reach_ft or 5)
        if distance_ft > reach_ft:
            raise MapAttackRangeError(
                f"{target_name} is {distance_ft:g} ft away, beyond {actor_name}'s reach of {reach_ft:g} ft."
            )
        return {
            "scene_id": scene.id,
            "distance_ft": distance_ft,
            "attack_kind": "melee",
            "reach_ft": reach_ft,
            "within_reach": True,
        }

    def move_combat_token_toward_target(
        self,
        adventure_id: int,
        participant_name: str,
        target_name: str,
        movement_ft: float,
    ) -> dict | None:
        scene = self.get_active_scene_for_adventure(adventure_id)
        if scene is None:
            return None
        tokens = self.list_combat_tokens(scene.id)
        actor = next((token for token in tokens if token.participant_name == participant_name), None)
        target = next((token for token in tokens if token.participant_name == target_name), None)
        if actor is None or target is None:
            return None

        dx = target.x - actor.x
        dy = target.y - actor.y
        distance_px = math.hypot(dx, dy)
        if distance_px <= 0:
            return None
        grid_size = float(scene.grid_size or 70)
        scale = float(scene.scale or 5)
        max_move_px = max(0.0, float(movement_ft)) / scale * grid_size
        reach_px = max(0.0, float(actor.reach_ft)) / scale * grid_size
        move_px = min(max_move_px, max(0.0, distance_px - reach_px))
        if move_px <= 0:
            return None

        ratio = move_px / distance_px
        next_x = actor.x + dx * ratio
        next_y = actor.y + dy * ratio
        before = {"x": actor.x, "y": actor.y}
        updated = self.update_combat_token(
            scene.id,
            actor.id,
            MapCombatTokenUpdate(x=round(next_x, 3), y=round(next_y, 3)),
        )
        tokens_after = [updated if token.id == actor.id else token for token in tokens]
        distances_after = self._distance_matrix(scene, tokens_after)
        return {
            "participant_name": participant_name,
            "target_name": target_name,
            "from": before,
            "to": {"x": updated.x, "y": updated.y},
            "movement_ft": round(move_px / grid_size * scale, 1),
            "distance_before_ft": self._distance_ft(scene, actor, target),
            "distance_after_ft": distances_after.get(participant_name, {}).get(target_name),
        }

    def _extension_for(self, filename: str | None, mime_type: str) -> str:
        suffix = Path(filename or "").suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return ".jpg" if suffix == ".jpeg" else suffix
        return IMAGE_EXTENSIONS[mime_type]

    def _asset_file_path(self, storage_key: str) -> Path:
        root = self.asset_root.resolve()
        path = (root / storage_key).resolve()
        if root != path and root not in path.parents:
            raise api_error(400, "invalid_asset_path", "Invalid map asset path.")
        return path

    def _get_asset_row(self, asset_id: int) -> Row:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM map_assets WHERE id = ?", (asset_id,)).fetchone()
        if row is None:
            raise api_error(404, "map_asset_not_found", "Map asset not found.")
        return row

    def _get_scene_row(self, scene_id: int) -> Row:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM map_scenes WHERE id = ?", (scene_id,)).fetchone()
        if row is None:
            raise api_error(404, "map_scene_not_found", "Map scene not found.")
        return row

    def _get_combat_token(self, scene_id: int, token_id: int) -> MapCombatTokenOut:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM map_combat_tokens WHERE id = ? AND scene_id = ?",
                (token_id, scene_id),
            ).fetchone()
        if row is None:
            raise api_error(404, "map_combat_token_not_found", "Map combat token not found.")
        return self._map_combat_token_row(row)

    def _default_token_position(self, *, side: str, side_index: int, grid_size: float) -> tuple[float, float]:
        lane = grid_size * (1.5 + side_index * 1.25)
        if side == "player":
            return grid_size, lane
        if side == "enemy":
            return grid_size * 8, lane
        return grid_size * 4, lane

    def _insert_item(self, conn, *, scene_id: int, item: MapSceneItemCreate) -> int:
        self._validate_item(item)
        cursor = conn.execute(
            """
            INSERT INTO map_scene_items (
                scene_id, asset_id, item_type, layer, name, x, y, width, height,
                rotation, locked, visible, metadata_json
            )
            VALUES (
                :scene_id, :asset_id, :item_type, :layer, :name, :x, :y, :width, :height,
                :rotation, :locked, :visible, :metadata_json
            )
            """,
            self._item_params(scene_id=scene_id, item_id=None, item=item),
        )
        return cursor.lastrowid

    def _item_params(self, *, scene_id: int, item_id: int | None, item: MapSceneItemCreate) -> dict:
        params = {
            "scene_id": scene_id,
            "asset_id": item.asset_id,
            "item_type": item.item_type,
            "layer": item.layer,
            "name": item.name,
            "x": item.x,
            "y": item.y,
            "width": item.width,
            "height": item.height,
            "rotation": item.rotation,
            "locked": 1 if item.locked else 0,
            "visible": 1 if item.visible else 0,
            "metadata_json": encode_json(item.metadata),
        }
        if item_id is not None:
            params["item_id"] = item_id
        return params

    def _validate_grid_type(self, grid_type: str) -> None:
        if grid_type not in ALLOWED_GRID_TYPES:
            raise api_error(400, "unsupported_grid_type", "Unsupported map grid type.")

    def _validate_item(self, item: MapSceneItemCreate) -> None:
        if item.item_type not in ALLOWED_ITEM_TYPES:
            raise api_error(400, "unsupported_map_item_type", "Unsupported map item type.")
        if item.layer not in ALLOWED_LAYERS:
            raise api_error(400, "unsupported_map_layer", "Unsupported map layer.")

    def _map_asset_row(self, row: Row) -> MapAssetOut:
        return MapAssetOut(
            id=row["id"],
            name=row["name"],
            asset_type=row["asset_type"],
            storage_key=row["storage_key"],
            mime_type=row["mime_type"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            width=row["width"],
            height=row["height"],
            metadata=decode_json(row["metadata_json"], {}),
            file_url=f"/api/map-assets/{row['id']}/file",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _map_scene_row(self, row: Row) -> MapSceneOut:
        scene_id = row["id"]
        with self.store.connect() as conn:
            item_rows = conn.execute(
                "SELECT * FROM map_scene_items WHERE scene_id = ? ORDER BY id",
                (scene_id,),
            ).fetchall()
            wall_rows = conn.execute("SELECT * FROM map_walls WHERE scene_id = ? ORDER BY id", (scene_id,)).fetchall()
            light_rows = conn.execute("SELECT * FROM map_lights WHERE scene_id = ? ORDER BY id", (scene_id,)).fetchall()
            fog_rows = conn.execute("SELECT * FROM map_fog_shapes WHERE scene_id = ? ORDER BY id", (scene_id,)).fetchall()
        return MapSceneOut(
            id=scene_id,
            name=row["name"],
            adventure_id=row["adventure_id"],
            story_id=row["story_id"],
            grid_type=row["grid_type"],
            grid_size=row["grid_size"],
            scale=row["scale"],
            scale_unit=row["scale_unit"],
            background_color=row["background_color"],
            active=bool(row["active"]),
            metadata=decode_json(row["metadata_json"], {}),
            items=[self._map_item_row(item_row) for item_row in item_rows],
            walls=[self._map_wall_row(wall_row) for wall_row in wall_rows],
            lights=[self._map_light_row(light_row) for light_row in light_rows],
            fog_shapes=[self._map_fog_row(fog_row) for fog_row in fog_rows],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _map_item_row(self, row: Row) -> MapSceneItemOut:
        try:
            asset = self.get_asset(row["asset_id"])
        except HTTPException:
            asset = None
        return MapSceneItemOut(
            id=row["id"],
            scene_id=row["scene_id"],
            asset_id=row["asset_id"],
            item_type=row["item_type"],
            layer=row["layer"],
            name=row["name"],
            x=row["x"],
            y=row["y"],
            width=row["width"],
            height=row["height"],
            rotation=row["rotation"],
            locked=bool(row["locked"]),
            visible=bool(row["visible"]),
            metadata=decode_json(row["metadata_json"], {}),
            asset=asset,
        )

    def _map_combat_token_row(self, row: Row) -> MapCombatTokenOut:
        return MapCombatTokenOut(
            id=row["id"],
            scene_id=row["scene_id"],
            adventure_id=row["adventure_id"],
            participant_name=row["participant_name"],
            side=row["side"],
            kind=row["kind"],
            x=row["x"],
            y=row["y"],
            size=row["size"],
            speed_ft=row["speed_ft"],
            reach_ft=row["reach_ft"],
            visible=bool(row["visible"]),
            metadata=decode_json(row["metadata_json"], {}),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _distance_matrix(
        self,
        scene: MapSceneOut,
        tokens: list[MapCombatTokenOut],
    ) -> dict[str, dict[str, float]]:
        distances: dict[str, dict[str, float]] = {}
        visible_tokens = [token for token in tokens if token.visible]
        for origin in visible_tokens:
            distances[origin.participant_name] = {}
            for target in visible_tokens:
                if origin.id == target.id:
                    continue
                distances[origin.participant_name][target.participant_name] = self._distance_ft(scene, origin, target)
        return distances

    def _distance_ft(self, scene: MapSceneOut, origin: MapCombatTokenOut, target: MapCombatTokenOut) -> float:
        grid_size = float(scene.grid_size or 70)
        scale = float(scene.scale or 5)
        pixel_distance = math.hypot(target.x - origin.x, target.y - origin.y)
        return round(pixel_distance / grid_size * scale, 1)

    def _participant_by_name(self, state: dict, name: str) -> dict | None:
        return next((participant for participant in state.get("participants", []) if participant.get("name") == name), None)

    def _attack_range_profile(self, actor: dict, attack_id: str | None) -> dict:
        attacks = actor.get("attacks") or []
        selected = None
        if attack_id:
            selected = next(
                (
                    attack
                    for attack in attacks
                    if attack.get("item_id") == attack_id or attack.get("id") == attack_id
                ),
                None,
            )
        if selected is None and attacks:
            selected = attacks[0]
        if selected is None:
            return {"attack_kind": "melee", "reach_ft": actor.get("reach_ft", 5)}

        range_values = selected.get("range")
        normal_range = selected.get("normal_range_ft")
        long_range = selected.get("long_range_ft")
        if isinstance(range_values, (list, tuple)) and range_values:
            normal_range = range_values[0]
            long_range = range_values[1] if len(range_values) > 1 else range_values[0]
        attack_kind = selected.get("attack_kind") or ("ranged" if normal_range or long_range else "melee")
        return {
            "attack_kind": attack_kind,
            "reach_ft": selected.get("reach_ft", actor.get("reach_ft", 5)),
            "normal_range_ft": float(normal_range) if normal_range is not None else None,
            "long_range_ft": float(long_range) if long_range is not None else None,
        }

    def _map_wall_row(self, row: Row) -> MapWallOut:
        return MapWallOut(
            id=row["id"],
            scene_id=row["scene_id"],
            x1=row["x1"],
            y1=row["y1"],
            x2=row["x2"],
            y2=row["y2"],
            wall_type=row["wall_type"],
            blocks_movement=bool(row["blocks_movement"]),
            blocks_sight=bool(row["blocks_sight"]),
            metadata=decode_json(row["metadata_json"], {}),
        )

    def _map_light_row(self, row: Row) -> MapLightOut:
        return MapLightOut(
            id=row["id"],
            scene_id=row["scene_id"],
            x=row["x"],
            y=row["y"],
            radius=row["radius"],
            color=row["color"],
            intensity=row["intensity"],
            visible=bool(row["visible"]),
            metadata=decode_json(row["metadata_json"], {}),
        )

    def _map_fog_row(self, row: Row) -> MapFogShapeOut:
        return MapFogShapeOut(
            id=row["id"],
            scene_id=row["scene_id"],
            geometry=decode_json(row["geometry_json"], {}),
            mode=row["mode"],
            metadata=decode_json(row["metadata_json"], {}),
        )
