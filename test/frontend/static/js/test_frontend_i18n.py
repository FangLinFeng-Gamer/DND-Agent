from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def frontend_js_text():
    files = [FRONTEND_DIR / "app.js", *sorted((FRONTEND_DIR / "js").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_static_ui_exposes_language_selector():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="language-select"' in html
    assert 'value="en"' in html
    assert 'value="zh-CN"' in html


def test_frontend_i18n_assets_include_english_and_chinese_copy():
    app_js = frontend_js_text()

    assert "translations" in app_js
    assert '"characters": "Characters"' in app_js
    assert '"characters": "角色"' in app_js
    assert "瑙掕壊" not in app_js
    assert "localStorage" in app_js


def test_language_selector_uses_readable_chinese_label():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert '<option value="zh-CN">中文</option>' in html
