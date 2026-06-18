from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def read_frontend_file(name):
    return (FRONTEND_DIR / name).read_text(encoding="utf-8")


def i18n_resource_text():
    return read_frontend_file("js/locales/en.js") + read_frontend_file("js/locales/zh-CN.js")


def test_story_page_exposes_map_storage_panel():
    html = read_frontend_file("index.html")
    story_markup = html.split('id="story-create-view"', 1)[1].split('id="model-config-view"', 1)[0]

    for element_id in [
        "map-upload-form",
        "map-upload-file",
        "map-asset-list",
        "map-scene-form",
        "map-scene-name",
        "map-scene-list",
        "map-action-message",
    ]:
        assert f'id="{element_id}"' in story_markup

    for key in [
        "storyMapBinding",
        "uploadMap",
        "mapAssetLibrary",
        "mapSceneName",
        "createMapScene",
        "mapScenes",
    ]:
        assert f'data-i18n="{key}"' in story_markup


def test_game_room_uses_story_bound_map_without_map_management_panel():
    html = read_frontend_file("index.html")
    room_markup = html.split('id="game-room"', 1)[1].split("</main>", 1)[0]

    assert 'class="map-stage"' in room_markup
    assert 'id="map-preview"' in room_markup
    assert 'id="refresh-maps"' in room_markup
    assert 'id="sync-map-tokens"' in room_markup
    assert 'class="map-management-drawer"' not in room_markup

    for management_id in [
        "map-upload-form",
        "map-upload-file",
        "map-asset-list",
        "map-scene-form",
        "map-scene-name",
        "map-scene-list",
    ]:
        assert f'id="{management_id}"' not in room_markup

    assert room_markup.index('class="compact-panel dice-section"') < room_markup.index('class="compact-panel quest-dock"')
    assert room_markup.index('class="compact-panel quest-dock"') < room_markup.index('class="map-stage"')


def test_frontend_wires_map_storage_api_calls():
    app_js = read_frontend_file("app.js")
    state_js = read_frontend_file("js/state.js")
    game_js = read_frontend_file("js/game.js")
    i18n_js = i18n_resource_text()

    assert "loadMapAssets" in app_js
    assert "uploadMapAsset" in app_js
    assert "createMapScene" in app_js
    assert "selectedMapAssetId" in state_js
    assert "selectedMapSceneId" in state_js
    assert "selectedMapTokenId" in state_js
    assert "mapAssets" in state_js
    assert "mapScenes" in state_js
    assert "mapTokens" in state_js

    for api_path in [
        "/api/map-assets",
        "/api/map-scenes",
        "story_id=",
        "/activate",
        "/combat-tokens",
    ]:
        assert api_path in game_js

    for function_name in [
        "loadMapAssets",
        "loadMapScenes",
        "uploadMapAsset",
        "createMapScene",
        "activateMapScene",
        "renderMapPreview",
        "loadMapTokens",
        "syncMapTokens",
        "moveMapToken",
        "renderMapTokens",
        "showMapNotice",
    ]:
        assert function_name in game_js

    for token_wiring in [
        "map-token-layer",
        "selectedMapTokenId",
        "getBoundingClientRect",
        "moveMapToken",
    ]:
        assert token_wiring in game_js

    for key in [
        "maps",
        "mapUploaded",
        "mapSceneCreated",
        "mapSceneActivated",
        "selectAdventureBeforeMap",
        "syncMapTokens",
        "mapTokens",
        "selectMapTokenFirst",
    ]:
        assert f'"{key}"' in i18n_js


def test_frontend_shows_visible_map_precondition_errors():
    html = read_frontend_file("index.html")
    state_js = read_frontend_file("js/state.js")
    game_js = read_frontend_file("js/game.js")
    story_markup = html.split('id="story-create-view"', 1)[1].split('id="model-config-view"', 1)[0]

    assert 'id="map-action-message"' in story_markup
    assert '"map-action-message"' in state_js
    assert "els.mapActionMessage" in game_js
    assert 'showMapNotice("selectStoryBeforeMap", "error")' in game_js
    assert 'showMapNotice("selectMapAssetFirst", "error")' in game_js
