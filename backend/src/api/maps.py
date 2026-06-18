from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from backend.src.schemas.maps import (
    MapAssetOut,
    MapCombatTokenOut,
    MapCombatTokenUpdate,
    MapContextOut,
    MapSceneCreate,
    MapSceneItemCreate,
    MapSceneItemOut,
    MapSceneOut,
    MapSceneUpdate,
)
from backend.src.services.maps import MapService


router = APIRouter(tags=["maps"])


def map_service(request: Request) -> MapService:
    return MapService(request.app.state.store)


@router.post("/api/map-assets", response_model=MapAssetOut)
async def upload_map_asset(
    request: Request,
    asset_type: str = Query("map"),
    name: str = Query(..., min_length=1),
    filename: str | None = Query(None),
) -> MapAssetOut:
    return map_service(request).upload_asset(
        name=name,
        asset_type=asset_type,
        filename=filename,
        mime_type=request.headers.get("content-type", "application/octet-stream"),
        content=await request.body(),
    )


@router.get("/api/map-assets", response_model=list[MapAssetOut])
def list_map_assets(request: Request, asset_type: str | None = None) -> list[MapAssetOut]:
    return map_service(request).list_assets(asset_type=asset_type)


@router.get("/api/map-assets/{asset_id}/file")
def get_map_asset_file(asset_id: int, request: Request) -> FileResponse:
    asset, path = map_service(request).get_asset_file(asset_id)
    return FileResponse(path, media_type=asset.mime_type, filename=asset.name)


@router.get("/api/map-assets/{asset_id}", response_model=MapAssetOut)
def get_map_asset(asset_id: int, request: Request) -> MapAssetOut:
    return map_service(request).get_asset(asset_id)


@router.delete("/api/map-assets/{asset_id}")
def delete_map_asset(asset_id: int, request: Request) -> dict[str, bool | int]:
    map_service(request).delete_asset(asset_id)
    return {"deleted": True, "id": asset_id}


@router.post("/api/map-scenes", response_model=MapSceneOut)
def create_map_scene(scene: MapSceneCreate, request: Request) -> MapSceneOut:
    return map_service(request).create_scene(scene)


@router.get("/api/map-scenes", response_model=list[MapSceneOut])
def list_map_scenes(
    request: Request,
    adventure_id: int | None = None,
    story_id: str | None = None,
) -> list[MapSceneOut]:
    return map_service(request).list_scenes(adventure_id=adventure_id, story_id=story_id)


@router.get("/api/map-scenes/{scene_id}", response_model=MapSceneOut)
def get_map_scene(scene_id: int, request: Request) -> MapSceneOut:
    return map_service(request).get_scene(scene_id)


@router.patch("/api/map-scenes/{scene_id}", response_model=MapSceneOut)
def update_map_scene(scene_id: int, scene: MapSceneUpdate, request: Request) -> MapSceneOut:
    return map_service(request).update_scene(scene_id, scene)


@router.post("/api/map-scenes/{scene_id}/activate", response_model=MapSceneOut)
def activate_map_scene(scene_id: int, request: Request) -> MapSceneOut:
    return map_service(request).activate_scene(scene_id)


@router.post("/api/map-scenes/{scene_id}/items", response_model=MapSceneItemOut)
def add_map_scene_item(scene_id: int, item: MapSceneItemCreate, request: Request) -> MapSceneItemOut:
    return map_service(request).add_item(scene_id, item)


@router.patch("/api/map-scenes/{scene_id}/items/{item_id}", response_model=MapSceneItemOut)
def update_map_scene_item(scene_id: int, item_id: int, item: MapSceneItemCreate, request: Request) -> MapSceneItemOut:
    return map_service(request).update_item(scene_id, item_id, item)


@router.get("/api/map-scenes/{scene_id}/combat-tokens", response_model=list[MapCombatTokenOut])
def list_map_combat_tokens(scene_id: int, request: Request) -> list[MapCombatTokenOut]:
    return map_service(request).list_combat_tokens(scene_id)


@router.post("/api/map-scenes/{scene_id}/combat-tokens/sync", response_model=list[MapCombatTokenOut])
def sync_map_combat_tokens(scene_id: int, request: Request) -> list[MapCombatTokenOut]:
    return map_service(request).sync_scene_combat_tokens(scene_id)


@router.patch("/api/map-scenes/{scene_id}/combat-tokens/{token_id}", response_model=MapCombatTokenOut)
def update_map_combat_token(
    scene_id: int,
    token_id: int,
    patch: MapCombatTokenUpdate,
    request: Request,
) -> MapCombatTokenOut:
    return map_service(request).update_combat_token(scene_id, token_id, patch)


@router.get("/api/adventures/{adventure_id}/map-context", response_model=MapContextOut)
def get_adventure_map_context(adventure_id: int, request: Request) -> MapContextOut:
    return map_service(request).get_map_context(adventure_id)
