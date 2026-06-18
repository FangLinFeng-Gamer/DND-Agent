from backend.src.agent.character_creation.derived.combat import (
    apply_combat_derived_values,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.character_creation.rules.draft_service import (
    CharacterDraftRulesService,
)
from backend.src.schemas.character_creation import CharacterDraft, CharacterDerivedSheet


def sheet_for(draft):
    return apply_combat_derived_values(
        draft,
        CharacterDerivedSheet(),
        PHBRuleRepository.load_builtin(),
    )


def test_armored_fighter_ac_hp_and_weapon_attack():
    draft = CharacterDraft()
    draft.selections.class_id = "class.fighter"
    draft.selections.class_option_ids = ["class_option.fighter.defense"]
    draft.abilities.modifiers.update(
        {"strength": 3, "dexterity": 2, "constitution": 2}
    )
    draft.proficiencies["weapons"] = ["weapon.simple", "weapon.martial"]
    draft.inventory = [
        {"item_id": "equipment.chain-mail", "quantity": 1},
        {"item_id": "equipment.shield", "quantity": 1},
        {"item_id": "equipment.battleaxe", "quantity": 1},
    ]

    sheet = sheet_for(draft)

    assert sheet.hp_max == 12
    assert sheet.armor_class == 19
    assert sheet.attacks == [
        {
            "item_id": "equipment.battleaxe",
            "ability": "strength",
            "attack_bonus": 5,
            "damage": "1d8+3",
            "damage_type": "slashing",
        }
    ]
    assert sheet.sources["armor_class"] == [
        {"source": "equipment.chain-mail", "value": 16},
        {"source": "equipment.shield", "value": 2},
        {"source": "class_option.fighter.defense", "value": 1},
    ]


def test_monk_uses_unarmored_defense():
    draft = CharacterDraft()
    draft.selections.class_id = "class.monk"
    draft.abilities.modifiers.update(
        {"dexterity": 3, "wisdom": 2, "constitution": 1}
    )
    draft.inventory = [
        {"item_id": "equipment.shortsword", "quantity": 1},
    ]

    sheet = sheet_for(draft)

    assert sheet.hp_max == 9
    assert sheet.armor_class == 15
    assert sheet.sources["armor_class"][-1]["source"] == "class.monk"


def test_draconic_sorcerer_uses_resilience_ac_and_bonus_hp():
    draft = CharacterDraft()
    draft.selections.class_id = "class.sorcerer"
    draft.selections.class_option_ids = [
        "class_option.sorcerer.draconic-bloodline"
    ]
    draft.abilities.modifiers.update({"dexterity": 2, "constitution": 2})

    sheet = sheet_for(draft)

    assert sheet.hp_max == 9
    assert sheet.armor_class == 15
    assert sheet.sources["armor_class"][-1]["source"] == (
        "class_option.sorcerer.draconic-bloodline"
    )


def test_equipment_mutation_recalculates_combat_sheet():
    draft = CharacterDraft()
    draft.selections.class_id = "class.fighter"
    draft.selections.class_option_ids = ["class_option.fighter.defense"]
    draft.proficiencies["weapons"] = ["weapon.simple", "weapon.martial"]

    updated = CharacterDraftRulesService().mutate(
        draft,
        "equipment",
        {
            "option_ids": [
                "fighter-armor-chain-mail",
                "fighter-weapons-weapon-and-shield",
                "fighter-ranged-handaxes",
                "fighter-pack-explorer",
            ],
            "item_choices": {
                "fighter-primary-martial-weapon": ["equipment.battleaxe"],
            },
        },
    )

    assert updated.derived.armor_class == 19
    assert {
        attack["item_id"] for attack in updated.derived.attacks
    } == {"equipment.battleaxe", "equipment.handaxe"}
