import re
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"
LOCALE_DIR = FRONTEND_DIR / "js" / "locales"


def locale_keys(path):
    assert path.exists(), f"Missing locale resource: {path}"
    text = path.read_text(encoding="utf-8")
    keys = set(re.findall(r'^\s+"([^"]+)":', text, flags=re.MULTILINE))
    assert keys, f"No translation keys found in {path}"
    return keys


def test_i18n_uses_dedicated_locale_resource_modules():
    i18n_js = (FRONTEND_DIR / "js" / "i18n.js").read_text(encoding="utf-8")

    assert (LOCALE_DIR / "en.js").exists()
    assert (LOCALE_DIR / "zh-CN.js").exists()
    assert 'from "./locales/en.js?v=' in i18n_js
    assert 'from "./locales/zh-CN.js?v=' in i18n_js
    assert "en: enTranslations" in i18n_js
    assert '"zh-CN": zhCNTranslations' in i18n_js
    assert '"loadingCapabilities":' not in i18n_js


def test_locale_resource_keys_stay_in_sync():
    en_keys = locale_keys(LOCALE_DIR / "en.js")
    zh_cn_keys = locale_keys(LOCALE_DIR / "zh-CN.js")

    assert sorted(en_keys - zh_cn_keys) == []
    assert sorted(zh_cn_keys - en_keys) == []


def test_static_i18n_attributes_have_locale_entries():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    html_keys = set(re.findall(r'data-i18n(?:-[a-z]+)?="([^"]+)"', html))
    en_keys = locale_keys(LOCALE_DIR / "en.js")
    zh_cn_keys = locale_keys(LOCALE_DIR / "zh-CN.js")

    assert sorted(html_keys - en_keys) == []
    assert sorted(html_keys - zh_cn_keys) == []


def test_direct_translation_calls_have_locale_entries():
    source_files = [
        FRONTEND_DIR / "app.js",
        *(
            path
            for path in (FRONTEND_DIR / "js").rglob("*.js")
            if "locales" not in path.parts
        ),
    ]
    direct_keys = set()
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        direct_keys.update(re.findall(r'\bt\(\s*"([^"]+)"', text))
        direct_keys.update(re.findall(r'\btranslate\(\s*[^,\n]+,\s*"([^"]+)"', text))

    en_keys = locale_keys(LOCALE_DIR / "en.js")
    zh_cn_keys = locale_keys(LOCALE_DIR / "zh-CN.js")

    assert sorted(direct_keys - en_keys) == []
    assert sorted(direct_keys - zh_cn_keys) == []
