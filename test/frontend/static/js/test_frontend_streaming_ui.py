from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def frontend_js_text():
    files = [FRONTEND_DIR / "app.js", *sorted((FRONTEND_DIR / "js").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_frontend_uses_streaming_dm_endpoint_and_busy_state():
    app_js = frontend_js_text()

    assert "/messages/stream" in app_js
    assert "dmBusy" in app_js
    assert "setDmBusy(true)" in app_js
    assert "setDmBusy(false)" in app_js
    assert "readStreamingResponse" in app_js


def test_frontend_disables_message_controls_while_dm_is_busy():
    app_js = frontend_js_text()

    assert "els.messageInput.disabled = isBusy" in app_js
    assert "els.messageSend.disabled = isBusy" in app_js
    assert "if (state.dmBusy)" in app_js
    assert "dmStillResponding" in app_js


def test_frontend_has_typing_indicator_and_localized_busy_strings():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    app_js = frontend_js_text()
    css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'id="message-send"' in html
    assert "typing-indicator" in app_js
    assert ".typing-indicator" in css
    assert '"dmThinking": "DM is thinking..."' in app_js
    assert '"dmThinking": "DM 正在思考..."' in app_js
    assert '"dmStillResponding": "DM is still responding."' in app_js
    assert '"dmStillResponding": "DM 仍在回复。"' in app_js
