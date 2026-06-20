from backend.src.schemas.adventure import AdventureCreate, MessageCreate
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


def test_survival_rules_increase_pressure_for_exploration(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Rule Road", mode="isekai_survival"))
    before = adventure.survival_state

    response = service.advance(adventure.id, MessageCreate(content="我沿着旧猎径探索。", locale="zh-CN"))

    after = response.adventure.survival_state
    assert after["fatigue"] > before["fatigue"]
    assert after["thirst"] > before["thirst"]
    assert response.dm_message.metadata["mode"] == "isekai_survival"
    assert response.dm_message.metadata["survival_delta"]["fatigue"] > 0
