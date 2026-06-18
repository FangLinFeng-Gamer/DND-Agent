from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def test_character_creation_page_uses_agent_session():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
    module_path = FRONTEND_DIR / "js" / "character-creation.js"

    assert module_path.exists()
    module = module_path.read_text(encoding="utf-8")
    assert "/api/character-creation/sessions" in module
    assert "locale: state.locale" in module
    assert 'api("/api/characters"' not in module
    assert 'id="character-creation-messages"' in html
    assert 'class="panel character-draft-panel"' in html
    assert 'id="character-wizard"' in html
    assert 'id="character-confirm"' in html
    assert "./js/character-creation.js" in app_js


def test_character_creation_page_has_agent_controls():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="character-agent-form"' in html
    assert 'id="character-agent-input"' in html
    assert 'id="character-agent-send"' in html
    assert 'id="character-validation"' in html


def test_character_creation_agent_shows_pending_reply_and_locks_all_controls():
    module = (FRONTEND_DIR / "js" / "character-creation.js").read_text(encoding="utf-8")

    assert 'pending: true' in module
    assert 'typingIndicatorNode(t("characterAgentThinking"))' in module
    assert "setCharacterCreationBusy(true)" in module
    assert "els.characterAgentInput.disabled = isBusy" in module
    assert "els.characterAgentSend.disabled = isBusy" in module
    assert "els.characterConfirm.disabled = isBusy" in module


def test_character_creation_agent_rejects_duplicate_submission_in_both_languages():
    module = (FRONTEND_DIR / "js" / "character-creation.js").read_text(encoding="utf-8")
    i18n = (
        (FRONTEND_DIR / "js" / "locales" / "en.js").read_text(encoding="utf-8")
        + (FRONTEND_DIR / "js" / "locales" / "zh-CN.js").read_text(encoding="utf-8")
    )

    assert 'setStatus(t("characterAgentStillResponding"), "error")' in module
    assert '"characterAgentStillResponding": "Character guide is still responding."' in i18n
    assert '"characterAgentStillResponding": "角色创建向导仍在回复。"' in i18n
