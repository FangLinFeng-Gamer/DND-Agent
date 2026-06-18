import pytest

from backend.src.agent.character_creation.derived.spellcasting import (
    calculate_spellcasting,
    validate_spell_selection,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.character_creation.rules.draft_service import (
    CharacterDraftRulesService,
)
from backend.src.schemas.character_creation import CharacterDraft


def wizard_draft() -> CharacterDraft:
    draft = CharacterDraft()
    draft.selections.class_id = "class.wizard"
    draft.abilities.final["intelligence"] = 16
    draft.abilities.modifiers["intelligence"] = 3
    return draft


def test_wizard_spellbook_selection_and_spellcasting_values():
    repository = PHBRuleRepository.load_builtin()
    draft = wizard_draft()
    spell_ids = [
        "spell.fire-bolt",
        "spell.mage-hand",
        "spell.prestidigitation",
        "spell.alarm",
        "spell.detect-magic",
        "spell.find-familiar",
        "spell.mage-armor",
        "spell.magic-missile",
        "spell.shield",
    ]

    validate_spell_selection(draft, spell_ids, repository)
    result = calculate_spellcasting(draft, spell_ids, repository)

    assert result["ability"] == "intelligence"
    assert result["save_dc"] == 13
    assert result["attack_bonus"] == 5
    assert result["slots"] == {1: 2}
    assert result["cantrips"] == spell_ids[:3]
    assert result["spellbook"] == spell_ids[3:]
    assert result["prepared_limit"] == 4


def test_spell_selection_rejects_wrong_class_and_wrong_counts():
    repository = PHBRuleRepository.load_builtin()
    draft = wizard_draft()

    with pytest.raises(ValueError, match="spell-choice requirements"):
        validate_spell_selection(
            draft,
            [
                "spell.fire-bolt",
                "spell.mage-hand",
                "spell.prestidigitation",
                "spell.healing-word",
            ],
            repository,
        )

    with pytest.raises(ValueError, match="3 wizard cantrips"):
        validate_spell_selection(
            draft,
            [
                "spell.fire-bolt",
                "spell.mage-hand",
                "spell.alarm",
                "spell.detect-magic",
                "spell.find-familiar",
                "spell.mage-armor",
                "spell.magic-missile",
                "spell.shield",
            ],
            repository,
        )


def test_non_spellcaster_requires_empty_spell_selection():
    repository = PHBRuleRepository.load_builtin()
    draft = CharacterDraft()
    draft.selections.class_id = "class.fighter"

    validate_spell_selection(draft, [], repository)

    with pytest.raises(ValueError, match="spell-choice requirements"):
        validate_spell_selection(
            draft,
            ["spell.fire-bolt"],
            repository,
        )


def test_spellcasting_preview_allows_caster_before_spell_step():
    repository = PHBRuleRepository.load_builtin()

    assert calculate_spellcasting(wizard_draft(), [], repository) == {}


def test_spell_mutation_saves_selection_and_updates_derived_values():
    service = CharacterDraftRulesService()
    draft = wizard_draft()
    spell_ids = [
        "spell.fire-bolt",
        "spell.mage-hand",
        "spell.prestidigitation",
        "spell.alarm",
        "spell.detect-magic",
        "spell.find-familiar",
        "spell.mage-armor",
        "spell.magic-missile",
        "spell.shield",
    ]

    updated = service.mutate(draft, "spells", {"spell_ids": spell_ids})

    assert updated.selections.spell_ids == spell_ids
    assert updated.derived.spellcasting["save_dc"] == 13
    assert updated.current_step == "equipment"
    assert "spells" in updated.completed_steps


def test_class_change_clears_previous_spell_selection():
    service = CharacterDraftRulesService()
    draft = wizard_draft()
    draft.selections.spell_ids = ["spell.fire-bolt"]
    draft.derived.spellcasting = {"save_dc": 13}

    updated = service.mutate(draft, "class", {"class_id": "class.fighter"})

    assert updated.selections.spell_ids == []
    assert updated.derived.spellcasting == {}
