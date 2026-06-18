from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


STANDARD_BACKGROUND_IDS = {
    "background.acolyte",
    "background.charlatan",
    "background.criminal",
    "background.entertainer",
    "background.folk-hero",
    "background.guild-artisan",
    "background.hermit",
    "background.noble",
    "background.outlander",
    "background.sage",
    "background.sailor",
    "background.soldier",
    "background.urchin",
}


def test_builtin_pack_contains_thirteen_standard_phb_backgrounds():
    repository = PHBRuleRepository.load_builtin()

    standard = {
        rule.id
        for rule in repository.list("background")
        if not rule.metadata.get("custom")
    }

    assert standard == STANDARD_BACKGROUND_IDS


def test_standard_backgrounds_have_bilingual_features_and_equipment_refs():
    repository = PHBRuleRepository.load_builtin()

    for background_id in STANDARD_BACKGROUND_IDS:
        rule = repository.get(background_id)
        assert rule.name.en
        assert rule.name.zh_cn
        assert rule.metadata["feature_id"]
        assert rule.metadata["equipment_option_id"]
        assert len(
            [grant for grant in rule.grants if grant.kind == "skill_proficiency"]
        ) == 2


def test_background_variants_are_recorded_without_duplicate_base_backgrounds():
    repository = PHBRuleRepository.load_builtin()

    assert repository.get("background.criminal").metadata["variants"] == ["spy"]
    assert repository.get("background.entertainer").metadata["variants"] == [
        "gladiator"
    ]
    assert repository.get("background.noble").metadata["variants"] == ["knight"]
    assert repository.get("background.sailor").metadata["variants"] == ["pirate"]


def test_custom_background_requires_two_skills_and_two_language_or_tool_choices():
    repository = PHBRuleRepository.load_builtin()
    custom = repository.get("background.custom")

    assert custom.metadata["custom"] is True
    choices = {choice.id: choice for choice in custom.choices}
    assert choices["custom-background-skills"].minimum == 2
    assert choices["custom-background-skills"].maximum == 2
    assert choices["custom-background-language-tools"].minimum == 2
    assert choices["custom-background-language-tools"].maximum == 2
    assert "skill.stealth" in choices["custom-background-skills"].option_ids
    assert "language.elvish" in choices[
        "custom-background-language-tools"
    ].option_ids
    assert "tool.thieves-tools" in choices[
        "custom-background-language-tools"
    ].option_ids
