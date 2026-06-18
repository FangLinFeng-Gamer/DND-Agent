from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


def test_builtin_pack_contains_all_42_phb_feats():
    repository = PHBRuleRepository.load_builtin()

    assert len(repository.list("feat")) == 42
    assert {
        "feat.alert",
        "feat.athlete",
        "feat.elemental-adept",
        "feat.grappler",
        "feat.magic-initiate",
        "feat.resilient",
        "feat.ritual-caster",
        "feat.war-caster",
        "feat.weapon-master",
    } <= {rule.id for rule in repository.list("feat")}


def test_feats_have_bilingual_text_and_structured_mechanics():
    repository = PHBRuleRepository.load_builtin()

    for feat in repository.list("feat"):
        assert feat.name.en
        assert feat.name.zh_cn
        assert feat.description.en
        assert feat.description.zh_cn
        assert feat.metadata["effects"]

    assert repository.get("feat.grappler").prerequisites[0].minimum == 13
    assert repository.get("feat.defensive-duelist").prerequisites[0].kind == (
        "ability_minimum"
    )
    assert repository.get("feat.elemental-adept").prerequisites[0].kind == (
        "spellcasting"
    )
    assert repository.get("feat.heavily-armored").prerequisites[0].values == [
        "armor.medium"
    ]
    assert repository.get("feat.heavy-armor-master").prerequisites[0].values == [
        "armor.heavy"
    ]


def test_choice_feats_define_canonical_choice_pools():
    repository = PHBRuleRepository.load_builtin()

    assert {
        choice.id for choice in repository.get("feat.resilient").choices
    } == {"resilient-ability"}
    assert {
        choice.id for choice in repository.get("feat.skilled").choices
    } == {"skilled-proficiencies"}
    assert {
        choice.id for choice in repository.get("feat.magic-initiate").choices
    } == {"magic-initiate-class"}
