from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"
APP_ASSET_VERSION = "20260620-isekai-events"


def test_frontend_app_entrypoint_is_split_into_focused_modules():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    assert f'<script type="module" src="/app.js?v={APP_ASSET_VERSION}"></script>' in html
    assert f'<link rel="stylesheet" href="/styles.css?v={APP_ASSET_VERSION}">' in html
    assert len(app_js.splitlines()) < 350
    assert "const translations" not in app_js
    assert "async function loadRaces" not in app_js
    assert f'./js/i18n.js?v={APP_ASSET_VERSION}' in app_js

    expected_modules = [
        "api.js",
        "game.js",
        "i18n.js",
        "models.js",
        "races.js",
        "state.js",
        "stories.js",
        "ui.js",
    ]
    for module_name in expected_modules:
        assert (FRONTEND_DIR / "js" / module_name).exists()
