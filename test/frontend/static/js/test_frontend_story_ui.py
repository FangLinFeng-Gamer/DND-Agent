from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def frontend_js_text():
    files = [FRONTEND_DIR / "app.js", *sorted((FRONTEND_DIR / "js").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_frontend_has_home_story_creation_and_game_views():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="home-view"' in html
    assert 'id="story-create-view"' in html
    assert 'id="game-view"' in html
    assert 'data-view-target="game"' in html
    assert 'data-view-target="story-create"' in html


def test_frontend_story_form_and_selector_are_present():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="story-form"' in html
    assert 'id="story-form-title"' in html
    assert 'id="cancel-story-edit"' in html
    assert 'id="story-world-background"' in html
    assert 'id="story-main-quest"' in html
    assert 'id="story-opening-environment"' in html
    assert 'id="story-select"' in html


def test_frontend_story_i18n_and_api_calls_are_present():
    app_js = frontend_js_text()

    assert '"/api/stories"' in app_js
    assert "story_id" in app_js
    assert 'method: "PATCH"' in app_js
    assert "function editStory" in app_js
    assert "function resetStoryForm" in app_js
    assert '"homeTitle"' in app_js
    assert '"createStory"' in app_js


def test_frontend_uses_script_and_adventure_terms_in_chinese():
    app_js = frontend_js_text()

    assert '"story": "剧本"' in app_js
    assert '"stories": "剧本"' in app_js
    assert '"storyLibrary": "剧本库"' in app_js
    assert '"defaultStory": "默认剧本"' in app_js
    assert '"adventures": "冒险"' in app_js
    assert '"createAdventure": "创建冒险"' in app_js
    assert '"selectAdventure": "选择冒险"' in app_js
