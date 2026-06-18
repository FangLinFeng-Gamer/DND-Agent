import pytest

from backend.src.agent.character_creation.rules.abilities import (
    ability_modifier,
    calculate_abilities,
    point_buy_cost,
    validate_point_buy,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


def test_point_buy_uses_phb_cost_table():
    assert [point_buy_cost(score) for score in range(8, 16)] == [
        0,
        1,
        2,
        3,
        4,
        5,
        7,
        9,
    ]


def test_point_buy_rejects_out_of_range_and_excess_cost():
    with pytest.raises(ValueError, match="between 8 and 15"):
        point_buy_cost(16)

    with pytest.raises(ValueError, match="exceeds 27"):
        validate_point_buy(
            {
                "strength": 15,
                "dexterity": 15,
                "constitution": 15,
                "intelligence": 15,
                "wisdom": 8,
                "charisma": 8,
            }
        )


def test_ability_modifier_uses_floor_division():
    assert ability_modifier(8) == -1
    assert ability_modifier(9) == -1
    assert ability_modifier(10) == 0
    assert ability_modifier(17) == 3


def test_mountain_dwarf_bonuses_are_separate_from_point_buy():
    repository = PHBRuleRepository.load_builtin()
    result = calculate_abilities(
        {
            "strength": 15,
            "dexterity": 12,
            "constitution": 14,
            "intelligence": 8,
            "wisdom": 10,
            "charisma": 10,
        },
        race_id="race.dwarf",
        subrace_id="race.mountain-dwarf",
        repository=repository,
    )

    assert result.point_buy_spent == 24
    assert result.racial_bonuses["strength"] == 2
    assert result.racial_bonuses["constitution"] == 2
    assert result.final["strength"] == 17
    assert result.final["constitution"] == 16
    assert result.modifiers["strength"] == 3
    assert result.sources["strength"][0]["source"] == "point_buy"


def test_half_elf_requires_two_distinct_non_charisma_choices():
    repository = PHBRuleRepository.load_builtin()
    base = {ability: 10 for ability in (
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    )}

    result = calculate_abilities(
        base,
        race_id="race.half-elf",
        choice_values={
            "half-elf-abilities": ["ability.dexterity", "ability.constitution"]
        },
        repository=repository,
    )

    assert result.racial_bonuses["charisma"] == 2
    assert result.racial_bonuses["dexterity"] == 1
    assert result.racial_bonuses["constitution"] == 1

    with pytest.raises(ValueError, match="distinct"):
        calculate_abilities(
            base,
            race_id="race.half-elf",
            choice_values={
                "half-elf-abilities": ["ability.dexterity", "ability.dexterity"]
            },
            repository=repository,
        )


def test_variant_human_applies_two_distinct_choices_not_all_scores():
    repository = PHBRuleRepository.load_builtin()
    base = {ability: 10 for ability in (
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    )}

    result = calculate_abilities(
        base,
        race_id="race.human",
        subrace_id="race.variant-human",
        choice_values={
            "variant-human-abilities": ["ability.strength", "ability.wisdom"]
        },
        repository=repository,
    )

    assert result.racial_bonuses["strength"] == 1
    assert result.racial_bonuses["wisdom"] == 1
    assert result.racial_bonuses["dexterity"] == 0
