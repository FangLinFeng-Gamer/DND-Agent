import pytest

from backend.src.agent.character_creation.rules.choices import validate_rule_choices
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


PHB_RACE_IDS = {
    "race.dragonborn",
    "race.dwarf",
    "race.elf",
    "race.gnome",
    "race.half-elf",
    "race.half-orc",
    "race.halfling",
    "race.human",
    "race.tiefling",
}

PHB_SUBRACE_IDS = {
    "race.drow",
    "race.forest-gnome",
    "race.high-elf",
    "race.hill-dwarf",
    "race.lightfoot-halfling",
    "race.mountain-dwarf",
    "race.rock-gnome",
    "race.stout-halfling",
    "race.variant-human",
    "race.wood-elf",
}


def test_builtin_pack_contains_all_phb_races_and_subraces():
    repository = PHBRuleRepository.load_builtin()

    assert {rule.id for rule in repository.list("race")} == PHB_RACE_IDS
    assert {rule.id for rule in repository.list("subrace")} == PHB_SUBRACE_IDS


def test_every_race_record_has_bilingual_summary_and_core_metadata():
    repository = PHBRuleRepository.load_builtin()

    for rule_id in PHB_RACE_IDS | PHB_SUBRACE_IDS:
        rule = repository.get(rule_id)
        assert rule.name.en
        assert rule.name.zh_cn
        assert rule.description.en
        assert rule.description.zh_cn
        assert rule.source == "PHB 2014"

    for rule_id in PHB_RACE_IDS:
        metadata = repository.get(rule_id).metadata
        assert metadata["size"] in {"small", "medium"}
        assert metadata["speed"] in {25, 30, 35}


def test_representative_racial_traits_are_structured_grants():
    repository = PHBRuleRepository.load_builtin()

    dwarf = repository.get("race.dwarf")
    high_elf = repository.get("race.high-elf")
    dragonborn = repository.get("race.dragonborn")
    half_orc = repository.get("race.half-orc")

    assert ("resistance", "damage.poison") in {
        (grant.kind, grant.target) for grant in dwarf.grants
    }
    assert ("cantrip_choice", "spell.wizard.cantrip") in {
        (grant.kind, grant.target) for grant in high_elf.grants
    }
    assert any(choice.id == "dragonborn-ancestry" for choice in dragonborn.choices)
    assert ("skill_proficiency", "skill.intimidation") in {
        (grant.kind, grant.target) for grant in half_orc.grants
    }


def test_racial_choices_validate_cardinality_membership_and_uniqueness():
    repository = PHBRuleRepository.load_builtin()
    half_elf = repository.get("race.half-elf")

    validate_rule_choices(
        half_elf,
        {
            "half-elf-abilities": [
                "ability.dexterity",
                "ability.constitution",
            ],
            "half-elf-skills": ["skill.insight", "skill.persuasion"],
            "half-elf-language": ["language.dwarvish"],
        },
    )

    with pytest.raises(ValueError, match="distinct"):
        validate_rule_choices(
            half_elf,
            {
                "half-elf-abilities": [
                    "ability.dexterity",
                    "ability.dexterity",
                ],
                "half-elf-skills": ["skill.insight", "skill.persuasion"],
                "half-elf-language": ["language.dwarvish"],
            },
        )

    with pytest.raises(ValueError, match="invalid"):
        validate_rule_choices(
            half_elf,
            {
                "half-elf-abilities": [
                    "ability.dexterity",
                    "ability.constitution",
                ],
                "half-elf-skills": ["skill.insight", "skill.unknown"],
                "half-elf-language": ["language.dwarvish"],
            },
        )
