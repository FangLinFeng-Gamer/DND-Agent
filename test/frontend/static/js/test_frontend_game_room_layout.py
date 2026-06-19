from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def read_frontend_file(name):
    return (FRONTEND_DIR / name).read_text(encoding="utf-8")


def test_game_start_and_room_layout_exposes_required_regions():
    html = read_frontend_file("index.html")
    css = read_frontend_file("styles.css")
    game_js = read_frontend_file("js/game.js")
    state_js = read_frontend_file("js/state.js")
    stories_js = read_frontend_file("js/stories.js")
    ui_js = read_frontend_file("js/ui.js")
    i18n_js = read_frontend_file("js/locales/en.js") + read_frontend_file("js/locales/zh-CN.js")

    for element_id in [
        "game-setup",
        "game-room",
        "game-story-choice-list",
        "game-party-summary",
        "game-party-warning",
        "room-route-tag",
        "room-adventure-title",
        "room-scene-meta",
        "room-story-meta",
        "room-party-meta",
        "room-party-list",
    ]:
        assert f'id="{element_id}"' in html

    for css_class in [
        "game-frame",
        "screen-title game-screen-title",
        "setup-layout",
        "choice-grid story-choice-grid",
        "choice-grid party-character-list",
        "setup-side",
        "start-card",
        "lock-note",
        "room-layout",
        "room-status",
        "side-rail",
        "compact-panel room-current-actor",
        "compact-panel room-party-panel",
        "compact-panel room-actions-panel",
        "compact-panel room-combat-panel",
        "dice-section",
        "map-stage",
        "map-toolbar",
        "map-canvas",
        "bottom-dock",
        "compact-panel quest-dock",
    ]:
        assert css_class in html

    map_stage_markup = html.split('class="map-stage"', 1)[1].split('class="chat-panel', 1)[0]
    for management_id in [
        "map-upload-form",
        "map-asset-list",
        "map-scene-form",
        "map-scene-list",
        "rules-form",
    ]:
        assert management_id not in map_stage_markup

    room_markup = html.split('id="game-room"', 1)[1].split("</main>", 1)[0]
    assert 'class="map-management-drawer"' not in room_markup
    assert room_markup.index('class="compact-panel dice-section"') < room_markup.index('class="compact-panel quest-dock"')
    assert room_markup.index('class="compact-panel quest-dock"') < room_markup.index('class="map-stage"')

    for key in [
        "gameSetupTitle",
        "setupStepStory",
        "setupStepParty",
        "setupStartCardTitle",
        "setupStartCardBody",
        "selectPartyCharacters",
        "createAndEnterRoom",
        "lockedPartyRuleTitle",
        "gameRoomTitle",
        "gameRoomSubtitle",
        "boundStory",
        "boundParty",
        "quickTools",
        "quickToolsHint",
        "storyMapBinding",
        "rulesReference",
        "mapStage",
        "dmAgentPanel",
        "partyMemberMeta",
    ]:
        assert f'"{key}"' in i18n_js

    assert ".workspace.setup-mode" in css
    assert ".workspace.room-mode" in css
    setup_mode_block = css.split(".workspace.setup-mode {", 1)[1].split("}", 1)[0]
    room_mode_block = css.split(".workspace.room-mode {", 1)[1].split("}", 1)[0]
    room_frame_block = css.split(".workspace.room-mode .game-frame {", 1)[1].split("}", 1)[0]
    assert "padding: 24px" in setup_mode_block
    assert "padding: 0" in room_mode_block
    assert "max-width: none" in room_frame_block
    assert "border-radius: 0" in room_frame_block
    assert "border: 0" in room_frame_block
    assert ".game-frame" in css
    assert "max-width: 1500px" in css
    assert "margin: 0 auto" in css
    assert "border: 1px solid rgba(240, 208, 96, .16)" in css
    assert "padding: 18px 20px 20px" in css
    assert ".screen-title {\n  display: grid;" in css
    screen_title_block = css.split(".screen-title {", 1)[1].split("}", 1)[0]
    assert "border:" not in screen_title_block
    assert "background:" not in screen_title_block
    assert "padding: 18px 20px 0" in screen_title_block
    assert "font-family: Consolas, monospace" in css
    assert "color: #f0e2bb" in css
    assert "color: #bda878" in css
    assert ".setup-layout" in css
    assert ".choice-card" in css
    assert ".start-card" in css
    assert ".lock-note" in css
    assert ".room-layout" in css
    assert "grid-template-columns: 375px minmax(420px, 1fr) 340px" in css
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in css
    assert ".side-rail" in css
    assert ".map-stage" in css
    assert ".map-canvas" in css
    assert ".map-board" in css
    assert ".bottom-dock" in css
    assert "grid-area: map" not in css

    assert "party_character_ids" in game_js
    assert "selectedPartyCharacterIds" in game_js
    assert "renderGameStoryChoices" in stories_js
    assert "game-story-choice-list" in state_js
    assert 'route.match(/^\\/game\\/(\\d+)$/)' in ui_js


def test_game_room_matches_static_compact_play_surface():
    css = read_frontend_file("styles.css")

    room_layout_block = css.split(".room-layout {", 1)[1].split("}", 1)[0]
    bottom_dock_block = css.split(".bottom-dock {", 1)[1].split("}", 1)[0]
    map_stage_block = css.split(".map-stage {", 1)[1].split("}", 1)[0]
    room_chat_block = css.split(".room-chat-panel {", 1)[1].split("}", 1)[0]
    room_chat_messages_block = css.split(".room-chat-panel .messages {", 1)[1].split("}", 1)[0]
    responsive_room_block = css.split("@media (max-width: 980px)", 1)[1].split("@media (max-width: 520px)", 1)[0]
    room_mode_block = css.split(".workspace.room-mode {", 1)[1].split("}", 1)[0]
    side_rail_block = css.split(".side-rail {", 1)[1].split("}", 1)[0]

    assert "grid-template-columns: 375px minmax(420px, 1fr) 340px" in room_layout_block
    assert "grid-template-columns: 250px minmax(520px, 1fr) 340px" not in room_layout_block
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in room_layout_block
    assert "min-height: calc(100vh - 168px)" in room_layout_block
    assert "\n  height: calc(100vh - 168px)" not in room_layout_block
    assert "overflow: auto" in room_mode_block
    assert "overflow: visible" in side_rail_block

    assert "grid-template-columns: minmax(0, 1fr) minmax(360px, 520px)" in bottom_dock_block
    assert "align-items: center" in bottom_dock_block
    assert "min-height: 58px" in bottom_dock_block
    assert "max-height: 78px" in bottom_dock_block
    assert "min-height: 150px" not in bottom_dock_block

    assert "grid-template-rows: auto minmax(0, 1fr)" in map_stage_block
    assert "grid-template-rows: auto auto minmax(0, 1fr)" not in map_stage_block

    assert "border: 1px solid rgba(169, 140, 84, .34)" in room_chat_block
    assert "border-radius: 10px" in room_chat_block
    assert "background:" in room_chat_block
    assert "height: min(100%, calc(100vh - 168px))" in room_chat_block
    assert "max-height: calc(100vh - 168px)" in room_chat_block
    assert "overflow: hidden" in room_chat_block
    assert "max-height: 100%" in room_chat_messages_block
    assert "overflow-y: auto" in room_chat_messages_block
    assert "overscroll-behavior: contain" in room_chat_messages_block
    assert ".room-chat-panel {" in responsive_room_block
    assert "height: min(620px, calc(100vh - 120px))" in responsive_room_block
    assert "max-height: min(620px, calc(100vh - 120px))" in responsive_room_block
    assert ".room-chat-panel .messages {" in responsive_room_block
    assert "height: auto" in responsive_room_block
    assert ".room-chat-panel .chat-head" in css
    assert ".character-tab-panel {" in css
    character_tab_block = css.split(".character-tab-panel {", 1)[1].split("}", 1)[0]
    assert "max-height: 220px" in character_tab_block
    assert "overflow-y: auto" in character_tab_block
