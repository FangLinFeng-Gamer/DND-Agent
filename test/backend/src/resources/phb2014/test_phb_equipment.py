from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


STANDARD_CLASS_IDS = {
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


def test_equipment_pack_contains_combat_metadata():
    repository = PHBRuleRepository.load_builtin()

    chain_mail = repository.get("equipment.chain-mail")
    shield = repository.get("equipment.shield")
    rapier = repository.get("equipment.rapier")
    longbow = repository.get("equipment.longbow")

    assert chain_mail.metadata == {
        "category": "armor",
        "armor_category": "heavy",
        "base_ac": 16,
        "dexterity": "none",
        "strength": 13,
        "stealth_disadvantage": True,
        "weight": 55,
    }
    assert shield.metadata["ac_bonus"] == 2
    assert rapier.metadata["damage"] == "1d8"
    assert rapier.metadata["damage_type"] == "piercing"
    assert "finesse" in rapier.metadata["properties"]
    assert longbow.metadata["range"] == [150, 600]
    assert "ammunition" in longbow.metadata["properties"]


def test_starting_equipment_has_all_class_and_background_packages():
    repository = PHBRuleRepository.load_builtin()
    packages = repository.list("equipment_option")

    class_packages = {
        record.metadata["owner_id"]
        for record in packages
        if record.metadata.get("owner_type") == "class"
    }
    background_packages = {
        record.metadata["owner_id"]
        for record in packages
        if record.metadata.get("owner_type") == "background"
    }

    assert class_packages == STANDARD_CLASS_IDS
    assert background_packages == STANDARD_BACKGROUND_IDS


def test_equipment_records_are_bilingual():
    repository = PHBRuleRepository.load_builtin()

    for record in repository.list("equipment"):
        assert record.name.en
        assert record.name.zh_cn
        assert record.description.en
        assert record.description.zh_cn


def test_every_class_package_contains_complete_choice_groups():
    repository = PHBRuleRepository.load_builtin()
    expected_groups = {
        "class.barbarian": 2,
        "class.bard": 3,
        "class.cleric": 4,
        "class.druid": 3,
        "class.fighter": 4,
        "class.monk": 2,
        "class.paladin": 3,
        "class.ranger": 3,
        "class.rogue": 3,
        "class.sorcerer": 3,
        "class.warlock": 3,
        "class.wizard": 3,
    }
    packages = {
        record.metadata["owner_id"]: record
        for record in repository.list("equipment_option")
        if record.metadata.get("owner_type") == "class"
    }

    assert {
        owner_id: len(packages[owner_id].metadata["choice_groups"])
        for owner_id in expected_groups
    } == expected_groups


def test_standard_background_packages_do_not_use_placeholder_items():
    repository = PHBRuleRepository.load_builtin()
    packages = [
        record
        for record in repository.list("equipment_option")
        if record.metadata.get("owner_type") == "background"
    ]

    assert all(
        grant[0] != "equipment.generic-background-kit"
        for package in packages
        for grant in package.metadata.get("fixed", [])
    )
