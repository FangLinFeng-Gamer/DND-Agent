from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def frontend_text():
    files = [FRONTEND_DIR / "index.html", FRONTEND_DIR / "styles.css", *sorted((FRONTEND_DIR / "js").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_setup_has_mode_switch_and_isekai_setup_without_removing_dnd_setup():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    text = frontend_text()

    assert 'id="game-mode-switch"' in html
    assert 'data-game-mode="dnd"' in html
    assert 'data-game-mode="isekai_survival"' in html
    assert 'id="dnd-setup-content"' in html
    assert 'id="isekai-setup-content"' in html
    assert 'id="game-story-choice-list"' in html
    assert 'id="character-list"' in html
    assert 'id="isekai-adventure-form"' in html
    assert "selectedGameMode" in text
    assert "renderGameModeSetup" in text
    assert "createIsekaiAdventure" in text
    assert '"isekaiMode": "Isekai Generator"' in text
    assert '"isekaiMode": "异世界生成模拟器"' in text


def test_frontend_filters_adventure_list_by_selected_mode():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")

    assert "adventure.mode || \"dnd\"" in game_js
    assert "state.selectedGameMode" in game_js
    assert ".filter((adventure) => adventureMode(adventure) === state.selectedGameMode)" in game_js


def test_isekai_room_is_independent_from_dnd_room():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'id="isekai-room"' in html
    assert 'id="isekai-info-tabs"' in html
    assert 'id="isekai-character-panel"' in html
    assert 'id="isekai-survival-panel"' in html
    assert 'id="isekai-events-panel"' in html
    assert 'id="isekai-inventory-panel"' not in html
    assert 'id="isekai-environment-panel"' not in html
    assert "renderIsekaiAdventureDetail" in game_js
    assert 'adventureMode(adventure) === "isekai_survival"' in game_js
    assert "renderCombat(null)" not in game_js.split("function renderIsekaiAdventureDetail", 1)[1].split("function", 1)[0]
    assert ".isekai-room-layout" in css
    assert ".isekai-info-tabs" in css
    assert ".isekai-info-page.active" in css


def test_isekai_creation_shows_step_by_step_progress():
    text = frontend_text()
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    assert "ISEKAI_CREATION_PROGRESS_KEYS" in game_js
    assert "startIsekaiCreationProgress" in game_js
    assert "stopIsekaiCreationProgress" in game_js
    assert "renderIsekaiCreationProgress" in game_js
    assert "currentStepKey" in game_js
    assert '"isekaiProgressCurrent": "{step}"' in text
    assert '"isekaiProgressCurrent": "当前步骤：{step}"' in text
    assert '"isekaiProgressRace": "Generating race..."' in text
    assert '"isekaiProgressClass": "Generating class..."' in text
    assert '"isekaiProgressSurvival": "Configuring survival values..."' in text
    assert '"isekaiProgressEnvironment": "Generating starting environment..."' in text
    assert '"isekaiProgressRace": "正在生成种族..."' in text
    assert '"isekaiProgressClass": "正在生成职业..."' in text
    assert '"isekaiProgressEnvironment": "正在生成初始环境..."' in text
    assert ".isekai-progress-list" in css


def test_isekai_world_events_use_event_cards_instead_of_stat_rows():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    events_block = game_js.split("function renderIsekaiEvents", 1)[1].split("export function", 1)[0]
    assert "renderIsekaiEnvironmentSummary" in events_block
    assert "isekai-event-list" in events_block
    assert "isekai-event-card" in events_block
    assert "renderIsekaiPanel" not in events_block
    assert ".isekai-environment-card" in css
    assert ".isekai-event-list" in css
    assert ".isekai-event-card" in css
    assert "white-space: normal" in css


def test_isekai_character_panel_includes_inventory():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")

    character_block = game_js.split("function renderIsekaiCharacter", 1)[1].split("function", 1)[0]
    assert "isekaiInventory" in character_block
    assert "inventory" in character_block
    assert "renderIsekaiInventory" not in game_js


def test_isekai_survival_panel_renders_time_fields():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    i18n = (FRONTEND_DIR / "js/locales/en.js").read_text(encoding="utf-8") + (
        FRONTEND_DIR / "js/locales/zh-CN.js"
    ).read_text(encoding="utf-8")

    survival_block = game_js.split("function renderIsekaiSurvival", 1)[1].split("function", 1)[0]
    assert "survival?.day" in game_js
    assert "survival?.time_of_day" in game_js
    assert "formatIsekaiCurrentTime(survival)" in survival_block
    assert "last_time_delta_minutes" in survival_block
    assert "survival.shelter" in survival_block
    assert '"currentTime"' in i18n
    assert '"lastTimeCost"' in i18n
    assert '"hoursMinutesShort"' in i18n
    assert '"shelter"' in i18n


def test_isekai_survival_panel_displays_exact_clock_time():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    i18n = (FRONTEND_DIR / "js/locales/en.js").read_text(encoding="utf-8") + (
        FRONTEND_DIR / "js/locales/zh-CN.js"
    ).read_text(encoding="utf-8")

    assert "function formatIsekaiClockTime" in game_js
    assert "function formatIsekaiCurrentTime" in game_js
    assert "elapsed_minutes" in game_js
    assert "padStart(2, \"0\")" in game_js
    assert "${day} ${label} ${clock}" in game_js
    assert '"currentTime": "Current Time"' in i18n
    assert '"currentTime": "当前时间"' in i18n


def test_isekai_survival_panel_displays_player_positive_meters():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    i18n = (FRONTEND_DIR / "js/locales/en.js").read_text(encoding="utf-8") + (
        FRONTEND_DIR / "js/locales/zh-CN.js"
    ).read_text(encoding="utf-8")

    survival_block = game_js.split("function renderIsekaiSurvival", 1)[1].split("function", 1)[0]
    assert "formatIsekaiPositiveMeter(survival.hunger, true)" in survival_block
    assert "formatIsekaiPositiveMeter(survival.thirst, true)" in survival_block
    assert "formatIsekaiPositiveMeter(survival.fatigue, true)" in survival_block
    assert "formatIsekaiPositiveMeter(survival.sleep_need, true)" in survival_block
    assert "formatIsekaiPositiveMeter(survival.morale, false)" in survival_block
    assert '"satiety": "Satiety"' in i18n
    assert '"hydration": "Hydration"' in i18n
    assert '"energy": "Energy"' in i18n
    assert '"sleepSufficiency": "Sleep Sufficiency"' in i18n
    assert '"survivalDisplayHint": "Higher values mean better condition."' in i18n
    assert '"satiety": "饱腹度"' in i18n
    assert '"hydration": "水分"' in i18n
    assert '"energy": "精力"' in i18n
    assert '"sleepSufficiency": "睡眠充足"' in i18n
    assert '"survivalDisplayHint": "数值越高代表状态越好。"' in i18n
