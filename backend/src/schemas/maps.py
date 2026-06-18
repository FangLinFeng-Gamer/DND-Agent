from typing import Any

from pydantic import BaseModel, Field


class MapAssetOut(BaseModel):
    id: int
    name: str
    asset_type: str
    storage_key: str
    mime_type: str
    sha256: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    file_url: str
    created_at: str
    updated_at: str


class MapSceneItemCreate(BaseModel):
    asset_id: int
    item_type: str = "token"
    layer: str = "token"
    name: str | None = None
    x: float = 0
    y: float = 0
    width: float = 70
    height: float = 70
    rotation: float = 0
    locked: bool = False
    visible: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class MapSceneItemOut(BaseModel):
    id: int
    scene_id: int
    asset_id: int
    item_type: str
    layer: str
    name: str | None = None
    x: float
    y: float
    width: float
    height: float
    rotation: float
    locked: bool
    visible: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    asset: MapAssetOut | None = None


class MapWallOut(BaseModel):
    id: int
    scene_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    wall_type: str
    blocks_movement: bool
    blocks_sight: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class MapLightOut(BaseModel):
    id: int
    scene_id: int
    x: float
    y: float
    radius: float
    color: str
    intensity: float
    visible: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class MapFogShapeOut(BaseModel):
    id: int
    scene_id: int
    geometry: dict[str, Any]
    mode: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MapCombatTokenUpdate(BaseModel):
    x: float | None = None
    y: float | None = None
    size: float | None = Field(default=None, gt=0)
    speed_ft: float | None = Field(default=None, ge=0)
    reach_ft: float | None = Field(default=None, ge=0)
    visible: bool | None = None
    metadata: dict[str, Any] | None = None


class MapCombatTokenOut(BaseModel):
    id: int
    scene_id: int
    adventure_id: int
    participant_name: str
    side: str
    kind: str
    x: float
    y: float
    size: float
    speed_ft: float
    reach_ft: float
    visible: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class MapSceneCreate(BaseModel):
    name: str = Field(min_length=1)
    adventure_id: int | None = None
    story_id: str | None = None
    background_asset_id: int | None = None
    grid_type: str = "square"
    grid_size: int = Field(default=70, ge=1)
    scale: float = Field(default=5, gt=0)
    scale_unit: str = "ft"
    background_color: str = "#1a1208"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MapSceneUpdate(BaseModel):
    name: str | None = None
    adventure_id: int | None = None
    story_id: str | None = None
    grid_type: str | None = None
    grid_size: int | None = Field(default=None, ge=1)
    scale: float | None = Field(default=None, gt=0)
    scale_unit: str | None = None
    background_color: str | None = None
    metadata: dict[str, Any] | None = None


class MapSceneOut(BaseModel):
    id: int
    name: str
    adventure_id: int | None = None
    story_id: str | None = None
    grid_type: str
    grid_size: int
    scale: float
    scale_unit: str
    background_color: str
    active: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    items: list[MapSceneItemOut] = Field(default_factory=list)
    walls: list[MapWallOut] = Field(default_factory=list)
    lights: list[MapLightOut] = Field(default_factory=list)
    fog_shapes: list[MapFogShapeOut] = Field(default_factory=list)
    created_at: str
    updated_at: str


class MapContextOut(BaseModel):
    active_scene: MapSceneOut | None = None
    tokens: list[MapCombatTokenOut] = Field(default_factory=list)
    distances: dict[str, dict[str, float]] = Field(default_factory=dict)
