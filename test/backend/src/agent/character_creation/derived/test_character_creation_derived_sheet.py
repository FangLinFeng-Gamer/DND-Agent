from backend.src.agent.character_creation.derived.sheet import calculate_derived_sheet
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft


def fighter_draft() -> CharacterDraft:
    draft = CharacterDraft()
    draft.selections.race_id = "race.dwarf"
    draft.selections.subrace_id = "race.mountain-dwarf"
    draft.selections.class_id = "class.fighter"
    draft.abilities.final = {
        "strength": 17,
        "dexterity": 12,
        "constitution": 16,
        "intelligence": 8,
        "wisdom": 10,
        "charisma": 10,
    }
    draft.abilities.modifiers = {
        "strength": 3,
        "dexterity": 1,
        "constitution": 3,
        "intelligence": -1,
        "wisdom": 0,
        "charisma": 0,
    }
    draft.proficiencies["skills"] = ["skill.perception", "skill.survival"]
    return draft


def test_calculates_initiative_saves_skills_and_passive_perception():
    result = calculate_derived_sheet(fighter_draft(), PHBRuleRepository.load_builtin())

    assert result.initiative == 1
    assert result.saving_throws["strength"] == 5
    assert result.saving_throws["constitution"] == 5
    assert result.saving_throws["dexterity"] == 1
    assert result.skills["skill.perception"] == 2
    assert result.skills["skill.arcana"] == -1
    assert result.passive_perception == 12


def test_derived_values_include_explainable_sources():
    result = calculate_derived_sheet(fighter_draft(), PHBRuleRepository.load_builtin())

    assert result.sources["initiative"] == [
        {"source": "ability.dexterity", "value": 1}
    ]
    assert result.sources["saving_throw.strength"] == [
        {"source": "ability.strength", "value": 3},
        {"source": "class.fighter", "value": 2},
    ]
    assert result.sources["skill.skill.perception"] == [
        {"source": "ability.wisdom", "value": 0},
        {"source": "proficiency.skill.perception", "value": 2},
    ]
    assert result.sources["passive_perception"] == [
        {"source": "base", "value": 10},
        {"source": "skill.perception", "value": 2},
    ]
