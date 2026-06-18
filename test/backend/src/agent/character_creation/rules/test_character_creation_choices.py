from backend.src.agent.character_creation.rules.grants import resolve_grants
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


def test_builtin_pack_has_complete_skill_and_language_vocabularies():
    repository = PHBRuleRepository.load_builtin()

    assert len(repository.list("skill")) == 18
    assert {rule.id for rule in repository.list("language")} == {
        "language.abyssal",
        "language.celestial",
        "language.common",
        "language.deep-speech",
        "language.draconic",
        "language.dwarvish",
        "language.elvish",
        "language.giant",
        "language.gnomish",
        "language.goblin",
        "language.halfling",
        "language.infernal",
        "language.orc",
        "language.primordial",
        "language.sylvan",
        "language.undercommon",
    }


def test_builtin_pack_has_character_creation_tool_and_proficiency_groups():
    repository = PHBRuleRepository.load_builtin()

    tool_ids = {rule.id for rule in repository.list("tool")}
    assert {
        "tool.artisan.alchemist",
        "tool.artisan.blacksmith",
        "tool.artisan.carpenter",
        "tool.artisan.tinker",
        "tool.disguise-kit",
        "tool.forgery-kit",
        "tool.gaming.dice",
        "tool.herbalism-kit",
        "tool.instrument.lute",
        "tool.navigator",
        "tool.poisoner-kit",
        "tool.thieves-tools",
        "tool.vehicles.land",
        "tool.vehicles.water",
    } <= tool_ids
    assert {rule.id for rule in repository.list("armor")} == {
        "armor.heavy",
        "armor.light",
        "armor.medium",
        "armor.shield",
    }
    assert {rule.id for rule in repository.list("weapon")} == {
        "weapon.martial",
        "weapon.simple",
    }


def test_grant_resolver_aggregates_selected_proficiencies_with_sources():
    repository = PHBRuleRepository.load_builtin()

    result = resolve_grants(
        ["race.dwarf"],
        {"dwarf-tool": ["tool.artisan.blacksmith"]},
        repository,
    )

    assert result.proficiencies["tools"] == ["tool.artisan.blacksmith"]
    assert "weapon.battleaxe" in result.proficiencies["weapons"]
    assert result.sources["tools:tool.artisan.blacksmith"] == ["race.dwarf"]
    assert result.conflicts == []


def test_grant_resolver_reports_duplicate_proficiency_for_replacement():
    repository = PHBRuleRepository.load_builtin()

    result = resolve_grants(
        ["race.elf", "race.half-elf"],
        {
            "half-elf-abilities": [
                "ability.strength",
                "ability.constitution",
            ],
            "half-elf-skills": ["skill.perception", "skill.persuasion"],
            "half-elf-language": ["language.dwarvish"],
        },
        repository,
    )

    assert result.proficiencies["skills"] == [
        "skill.perception",
        "skill.persuasion",
    ]
    assert result.conflicts[0].category == "skills"
    assert result.conflicts[0].target == "skill.perception"
    assert result.conflicts[0].sources == ["race.elf", "race.half-elf"]


def test_grant_resolver_reports_duplicate_language_choices():
    repository = PHBRuleRepository.load_builtin()

    result = resolve_grants(
        ["race.elf", "background.acolyte"],
        {
            "acolyte-languages": [
                "language.elvish",
                "language.celestial",
            ],
        },
        repository,
    )

    assert result.conflicts[0].category == "languages"
    assert result.conflicts[0].target == "language.elvish"
    assert result.conflicts[0].sources == ["race.elf", "background.acolyte"]


def test_fixed_and_selected_proficiencies_aggregate_without_choice_overcount():
    repository = PHBRuleRepository.load_builtin()

    result = resolve_grants(
        ["race.human", "class.fighter", "background.noble"],
        {
            "human-language": ["language.elvish"],
            "fighter-skills": ["skill.athletics", "skill.perception"],
            "noble-gaming-set": ["tool.gaming.dice"],
            "noble-language": ["language.dwarvish"],
        },
        repository,
    )

    assert result.conflicts == []
    assert result.proficiencies["skills"] == [
        "skill.athletics",
        "skill.history",
        "skill.perception",
        "skill.persuasion",
    ]


def test_variant_human_keeps_parent_human_languages():
    repository = PHBRuleRepository.load_builtin()

    result = resolve_grants(
        ["race.human", "race.variant-human", "background.noble"],
        {
            "variant-human-abilities": [
                "ability.strength",
                "ability.dexterity",
            ],
            "variant-human-skill": ["skill.athletics"],
            "human-language": ["language.elvish"],
            "noble-gaming-set": ["tool.gaming.dice"],
            "noble-language": ["language.dwarvish"],
        },
        repository,
    )

    assert result.conflicts == []
    assert result.proficiencies["languages"] == [
        "language.common",
        "language.dwarvish",
        "language.elvish",
    ]
