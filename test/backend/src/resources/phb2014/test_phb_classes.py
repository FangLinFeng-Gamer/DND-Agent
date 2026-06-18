from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


PHB_CLASS_IDS = {
    "class.barbarian",
    "class.bard",
    "class.cleric",
    "class.druid",
    "class.fighter",
    "class.monk",
    "class.paladin",
    "class.ranger",
    "class.rogue",
    "class.sorcerer",
    "class.warlock",
    "class.wizard",
}


def test_builtin_pack_contains_all_twelve_phb_classes():
    repository = PHBRuleRepository.load_builtin()

    assert {rule.id for rule in repository.list("class")} == PHB_CLASS_IDS


def test_every_class_has_level_one_creation_metadata():
    repository = PHBRuleRepository.load_builtin()

    for class_id in PHB_CLASS_IDS:
        rule = repository.get(class_id)
        assert rule.metadata["hit_die"] in {6, 8, 10, 12}
        assert len(rule.metadata["saving_throws"]) == 2
        assert rule.metadata["level_one_features"]
        assert rule.metadata["primary_abilities"]
        assert rule.name.en
        assert rule.name.zh_cn


def test_level_one_subclass_choices_are_complete():
    repository = PHBRuleRepository.load_builtin()

    assert {
        option.id
        for option in repository.list("class_option")
        if option.parent_id == "class.cleric"
    } == {
        "class_option.cleric.knowledge",
        "class_option.cleric.life",
        "class_option.cleric.light",
        "class_option.cleric.nature",
        "class_option.cleric.tempest",
        "class_option.cleric.trickery",
        "class_option.cleric.war",
    }
    assert {
        option.id
        for option in repository.list("class_option")
        if option.parent_id == "class.sorcerer"
    } == {
        "class_option.sorcerer.draconic-bloodline",
        "class_option.sorcerer.wild-magic",
    }
    assert {
        option.id
        for option in repository.list("class_option")
        if option.parent_id == "class.warlock"
    } == {
        "class_option.warlock.archfey",
        "class_option.warlock.fiend",
        "class_option.warlock.great-old-one",
    }


def test_representative_class_proficiencies_and_choices_are_structured():
    repository = PHBRuleRepository.load_builtin()
    fighter = repository.get("class.fighter")
    rogue = repository.get("class.rogue")
    barbarian = repository.get("class.barbarian")

    assert ("armor_proficiency", "armor.heavy") in {
        (grant.kind, grant.target) for grant in fighter.grants
    }
    assert next(choice for choice in fighter.choices if choice.id == "fighter-skills").maximum == 2
    assert next(choice for choice in rogue.choices if choice.id == "rogue-skills").maximum == 4
    assert barbarian.metadata["hit_die"] == 12


def test_level_one_subclass_options_include_their_mechanical_grants():
    repository = PHBRuleRepository.load_builtin()

    life = repository.get("class_option.cleric.life")
    knowledge = repository.get("class_option.cleric.knowledge")
    draconic = repository.get("class_option.sorcerer.draconic-bloodline")
    fiend = repository.get("class_option.warlock.fiend")

    assert ("armor_proficiency", "armor.heavy") in {
        (grant.kind, grant.target) for grant in life.grants
    }
    assert {choice.id for choice in knowledge.choices} == {
        "knowledge-domain-languages",
        "knowledge-domain-skills",
    }
    assert draconic.metadata["level_one_features"] == [
        "dragon-ancestor",
        "draconic-resilience",
    ]
    assert fiend.metadata["level_one_features"] == ["dark-ones-blessing"]
