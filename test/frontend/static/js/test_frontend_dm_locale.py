from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def test_streaming_dm_request_sends_selected_locale():
    api_js = (FRONTEND_DIR / "js" / "api.js").read_text(encoding="utf-8")
    game_js = (FRONTEND_DIR / "js" / "game.js").read_text(encoding="utf-8")

    assert "readStreamingResponse(" in game_js
    assert "state.selectedAdventureId" in game_js
    assert "state.locale" in game_js
    assert "{ characterId: getSelectedCharacter()?.id }" in game_js
    assert "content," in api_js
    assert "locale," in api_js
    assert "character_id" in api_js


def test_adventure_creation_sends_selected_locale():
    game_js = (FRONTEND_DIR / "js" / "game.js").read_text(encoding="utf-8")

    assert "locale: state.locale" in game_js
