import pytest

from backend.src.agent.character_creation.rules.equipment import (
    resolve_starting_equipment,
)
from backend.src.agent.character_creation.rules.draft_service import (
    CharacterDraftRulesService,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft


def quantities(inventory):
    return {entry["item_id"]: entry["quantity"] for entry in inventory}


def test_fighter_and_soldier_equipment_resolves_nested_choices():
    repository = PHBRuleRepository.load_builtin()

    inventory = resolve_starting_equipment(
        class_id="class.fighter",
        background_id="background.soldier",
        option_ids=[
            "fighter-armor-chain-mail",
            "fighter-weapons-weapon-and-shield",
            "fighter-ranged-light-crossbow",
            "fighter-pack-dungeoneer",
        ],
        item_choices={
            "fighter-primary-martial-weapon": ["equipment.battleaxe"],
            "soldier-gaming-set": ["equipment.dice-set"],
        },
        repository=repository,
    )
    result = quantities(inventory)

    assert result["equipment.chain-mail"] == 1
    assert result["equipment.shield"] == 1
    assert result["equipment.battleaxe"] == 1
    assert result["equipment.light-crossbow"] == 1
    assert result["equipment.crossbow-bolt"] == 20
    assert result["equipment.dungeoneers-pack"] == 1
    assert result["equipment.dice-set"] == 1
    assert result["equipment.common-clothes"] == 1
    assert result["equipment.gp"] == 10


def test_equipment_quantities_merge_across_grants():
    repository = PHBRuleRepository.load_builtin()

    inventory = resolve_starting_equipment(
        class_id="class.barbarian",
        background_id=None,
        option_ids=[
            "barbarian-primary-greataxe",
            "barbarian-secondary-handaxes",
        ],
        item_choices={},
        repository=repository,
    )

    assert quantities(inventory)["equipment.handaxe"] == 2
    assert quantities(inventory)["equipment.javelin"] == 4


def test_equipment_rejects_missing_or_foreign_choices():
    repository = PHBRuleRepository.load_builtin()

    with pytest.raises(ValueError, match="fighter-primary-martial-weapon"):
        resolve_starting_equipment(
            class_id="class.fighter",
            background_id=None,
            option_ids=[
                "fighter-armor-chain-mail",
                "fighter-weapons-weapon-and-shield",
                "fighter-ranged-light-crossbow",
                "fighter-pack-dungeoneer",
            ],
            item_choices={},
            repository=repository,
        )

    with pytest.raises(ValueError, match="does not belong"):
        resolve_starting_equipment(
            class_id="class.fighter",
            background_id=None,
            option_ids=["barbarian-primary-greataxe"],
            item_choices={},
            repository=repository,
        )


def test_equipment_mutation_saves_inventory_and_completes_step():
    service = CharacterDraftRulesService()
    draft = CharacterDraft()
    draft.selections.class_id = "class.fighter"
    draft.selections.background_id = "background.soldier"

    updated = service.mutate(
        draft,
        "equipment",
        {
            "option_ids": [
                "fighter-armor-chain-mail",
                "fighter-weapons-weapon-and-shield",
                "fighter-ranged-light-crossbow",
                "fighter-pack-dungeoneer",
            ],
            "item_choices": {
                "fighter-primary-martial-weapon": ["equipment.battleaxe"],
                "soldier-gaming-set": ["equipment.dice-set"],
            },
        },
    )

    assert updated.selections.equipment_option_ids == [
        "fighter-armor-chain-mail",
        "fighter-weapons-weapon-and-shield",
        "fighter-ranged-light-crossbow",
        "fighter-pack-dungeoneer",
    ]
    assert quantities(updated.inventory)["equipment.chain-mail"] == 1
    assert updated.current_step == "adventure_connection"
    assert "equipment" in updated.completed_steps


def test_class_or_background_change_clears_resolved_inventory():
    service = CharacterDraftRulesService()
    draft = CharacterDraft()
    draft.selections.class_id = "class.fighter"
    draft.selections.background_id = "background.soldier"
    draft.selections.equipment_option_ids = ["fighter-armor-chain-mail"]
    draft.inventory = [{"item_id": "equipment.chain-mail", "quantity": 1}]

    changed_class = service.mutate(
        draft,
        "class",
        {"class_id": "class.rogue"},
    )
    assert changed_class.selections.equipment_option_ids == []
    assert changed_class.inventory == []

    changed_background = service.mutate(
        draft,
        "background",
        {"background_id": "background.sage"},
    )
    assert changed_background.selections.equipment_option_ids == []
    assert changed_background.inventory == []
