from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


EXPECTED_CLASS_COUNTS = {
    "bard": {0: 11, 1: 21},
    "cleric": {0: 7, 1: 15},
    "druid": {0: 8, 1: 16},
    "sorcerer": {0: 16, 1: 20},
    "warlock": {0: 9, 1: 11},
    "wizard": {0: 16, 1: 30},
}


def test_spell_pack_contains_complete_cantrip_and_first_level_class_lists():
    repository = PHBRuleRepository.load_builtin()
    spells = repository.list("spell")

    for class_name, level_counts in EXPECTED_CLASS_COUNTS.items():
        for level, expected_count in level_counts.items():
            actual = [
                spell
                for spell in spells
                if level == spell.metadata["level"]
                and class_name in spell.metadata["classes"]
            ]
            assert len(actual) == expected_count, (class_name, level)


def test_spells_have_bilingual_search_and_casting_metadata():
    repository = PHBRuleRepository.load_builtin()

    for spell in repository.list("spell"):
        assert spell.name.en
        assert spell.name.zh_cn
        assert spell.description.en
        assert spell.description.zh_cn
        assert spell.metadata["level"] in {0, 1}
        assert spell.metadata["school"]
        assert spell.metadata["casting_time"]
        assert spell.metadata["range"]
        assert spell.metadata["duration"]
        assert spell.metadata["classes"]

    alarm = repository.get("spell.alarm")
    fire_bolt = repository.get("spell.fire-bolt")
    sacred_flame = repository.get("spell.sacred-flame")

    assert alarm.metadata["ritual"] is True
    assert fire_bolt.metadata["attack"] == "ranged"
    assert sacred_flame.metadata["save"] == "dexterity"


def test_level_one_spellcasting_profiles_are_defined_on_classes():
    repository = PHBRuleRepository.load_builtin()

    assert repository.get("class.bard").metadata["spell_selection"] == {
        "mode": "known",
        "cantrips": 2,
        "level_one": 4,
        "slots": 2,
    }
    assert repository.get("class.cleric").metadata["spell_selection"] == {
        "mode": "prepared",
        "cantrips": 3,
        "prepared_formula": "wisdom+level",
        "slots": 2,
    }
    assert repository.get("class.wizard").metadata["spell_selection"] == {
        "mode": "spellbook",
        "cantrips": 3,
        "spellbook_level_one": 6,
        "prepared_formula": "intelligence+level",
        "slots": 2,
    }
