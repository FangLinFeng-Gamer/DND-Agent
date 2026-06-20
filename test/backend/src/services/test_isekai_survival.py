from backend.src.services.isekai import IsekaiSurvivalService


def test_random_isekai_character_has_survival_inventory_and_world_reaction_tags(store):
    service = IsekaiSurvivalService(store)

    character = service.generate_character()

    assert character.name
    assert character.race in {"Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Tiefling"}
    assert character.class_name in {"Fighter", "Ranger", "Rogue", "Wizard", "Cleric", "Druid"}
    assert character.gold >= 5
    assert character.inventory
    assert character.world_reaction_tags
