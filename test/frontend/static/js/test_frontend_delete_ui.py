from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def frontend_js_text():
    files = [FRONTEND_DIR / "app.js", *sorted((FRONTEND_DIR / "js").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_frontend_exposes_story_character_and_adventure_delete_controls():
    app_js = frontend_js_text()

    assert "function deleteStory" in app_js
    assert "function deleteCharacter" in app_js
    assert "function deleteAdventure" in app_js
    assert '`/api/stories/${id}`' in app_js
    assert '`/api/characters/${id}`' in app_js
    assert '`/api/adventures/${id}`' in app_js
    assert 'method: "DELETE"' in app_js


def test_frontend_delete_copy_is_available_in_both_languages():
    app_js = frontend_js_text()

    assert '"deleteStory": "Delete story"' in app_js
    assert '"deleteCharacter": "Delete character"' in app_js
    assert '"deleteAdventure": "Delete adventure"' in app_js
    assert '"defaultStoryCannotDelete": "The default story cannot be deleted."' in app_js
    assert '"deleteStory": "删除剧本"' in app_js
    assert '"deleteCharacter": "删除角色"' in app_js
    assert '"deleteAdventure": "删除冒险"' in app_js
    assert '"defaultStoryCannotDelete": "默认剧本不能删除。"' in app_js
