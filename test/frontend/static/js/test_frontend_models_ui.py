from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def frontend_js_text():
    files = [FRONTEND_DIR / "app.js", *sorted((FRONTEND_DIR / "js").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def i18n_resource_text():
    return (
        (FRONTEND_DIR / "js" / "locales" / "en.js").read_text(encoding="utf-8")
        + (FRONTEND_DIR / "js" / "locales" / "zh-CN.js").read_text(encoding="utf-8")
    )


def test_frontend_has_model_config_view_and_navigation():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="model-config-view"' in html
    assert 'data-view-target="model-config"' in html
    assert 'data-i18n="models"' in html
    assert 'id="model-form"' in html
    assert 'id="model-list"' in html


def test_frontend_model_form_fields_are_present():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="model-display-name"' in html
    assert 'id="model-provider"' in html
    assert 'id="model-base-url"' in html
    assert 'id="model-api-key"' in html
    assert 'id="model-name"' in html
    assert 'id="model-temperature"' in html
    assert 'id="model-max-context"' in html


def test_frontend_model_i18n_and_api_calls_are_present():
    app_js = frontend_js_text()

    assert '"/api/models"' in app_js
    assert "loadModels" in app_js
    assert "saveModel" in app_js
    assert '"models": "Models"' in app_js
    assert '"models": "模型"' in app_js
    assert '"modelSaved": "Model saved"' in app_js
    assert '"modelSaved": "模型已保存"' in app_js


def test_saving_a_model_activates_the_saved_configuration():
    models_js = (FRONTEND_DIR / "js" / "models.js").read_text(encoding="utf-8")

    assert "const savedModel = await api(path" in models_js
    assert "state.editingModelId = savedModel.id" in models_js
    assert "await api(`/api/models/${savedModel.id}/activate`, { method: \"POST\" })" in models_js
    assert 'setStatus(t("modelSavedAndActivated"), "ok")' in models_js


def test_model_form_explains_supported_base_url_formats_in_both_languages():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    i18n = i18n_resource_text()

    assert 'data-i18n="modelBaseUrlHint"' in html
    assert '"saveModel": "Save & Activate"' in i18n
    assert '"modelSavedAndActivated": "Model saved and activated"' in i18n
    assert '"modelBaseUrlHint": "Use an API root URL or a full /chat/completions endpoint."' in i18n
    assert '"saveModel": "\u4fdd\u5b58\u5e76\u542f\u7528"' in i18n
    assert '"modelSavedAndActivated": "\u6a21\u578b\u5df2\u4fdd\u5b58\u5e76\u542f\u7528"' in i18n
    assert (
        '"modelBaseUrlHint": "\u53ef\u586b\u5199 API \u6839 URL \u6216\u5b8c\u6574\u7684 '
        '/chat/completions \u5730\u5740\u3002"'
    ) in i18n
