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
