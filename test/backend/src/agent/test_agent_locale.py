from backend.src.agent.locale import language_instruction, normalize_locale
from backend.src.schemas.adventure import MessageCreate
from backend.src.schemas.character_creation import CharacterCreationMessage


def test_normalize_locale_supports_english_and_simplified_chinese():
    assert normalize_locale("zh-CN") == "zh-CN"
    assert normalize_locale("en") == "en"
    assert normalize_locale("invalid") == "en"
    assert normalize_locale(None) == "en"


def test_language_instruction_is_explicit():
    assert "Simplified Chinese" in language_instruction("zh-CN")
    assert "English" in language_instruction("en")


def test_message_schemas_default_locale_to_english():
    assert MessageCreate(content="look").locale == "en"
    assert CharacterCreationMessage(content="help").locale == "en"
