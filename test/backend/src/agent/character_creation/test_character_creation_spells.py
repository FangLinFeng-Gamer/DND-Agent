from pathlib import Path

from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.character_creation.workflow import CharacterCreationStateGraph
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character_creation import CharacterDraft


def test_react_workflow_accepts_spell_selection_changes(tmp_path: Path):
    repo = PHBRuleRepository.load_builtin()
    spell_ids = _wizard_spell_ids(repo)
    workflow = CharacterCreationStateGraph(_store(tmp_path))
    draft = _wizard_draft_ready_for_spells(workflow)

    result = workflow.apply_changes(
        draft=draft,
        expected_revision=draft.revision,
        changes={"spells": {"spell_ids": spell_ids}},
        locale="zh-CN",
    )

    assert result.success is True
    assert result.validation_errors == []
    assert "spells" in result.changed_fields
    assert result.draft.selections.spell_ids == spell_ids
    assert result.draft.derived.spellcasting["cantrips"] == spell_ids[:3]
    assert result.draft.derived.spellcasting["spellbook"] == spell_ids[3:]
    assert "spells" in result.draft.completed_steps
    assert "spells" not in result.draft.invalid_steps


def _store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "test.sqlite")
    store.init_schema()
    return store


def _wizard_draft_ready_for_spells(
    workflow: CharacterCreationStateGraph,
) -> CharacterDraft:
    result = workflow.apply_changes(
        draft=CharacterDraft(),
        expected_revision=0,
        locale="zh-CN",
        changes={
            "name": "Spell Test",
            "race": "Human",
            "class_name": "Wizard",
            "background": "Sage",
            "abilities": {
                "strength": 8,
                "dexterity": 14,
                "constitution": 14,
                "intelligence": 15,
                "wisdom": 10,
                "charisma": 10,
            },
            "proficiencies": {
                "choice_values": {
                    "human-language": ["language.dwarvish"],
                    "wizard-skills": ["skill.investigation", "skill.medicine"],
                    "sage-languages": ["language.draconic", "language.elvish"],
                }
            },
        },
    )
    assert result.success is True
    assert result.next_step == "spells"
    return result.draft


def _wizard_spell_ids(repo: PHBRuleRepository) -> list[str]:
    spells = repo.list("spell")
    cantrips = [
        spell.id
        for spell in spells
        if spell.metadata["level"] == 0
        and "wizard" in spell.metadata["classes"]
    ][:3]
    level_one = [
        spell.id
        for spell in spells
        if spell.metadata["level"] == 1
        and "wizard" in spell.metadata["classes"]
    ][:6]
    return cantrips + level_one
