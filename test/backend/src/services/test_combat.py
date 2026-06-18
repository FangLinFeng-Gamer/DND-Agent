import pytest
from pydantic import ValidationError

from backend.src.schemas.combat import CombatActionRequest, CombatParticipantInput
from backend.src.services.combat import CombatService


def test_d20_check_with_fixed_roll():
    service = CombatService(rng=lambda sides: 15)
    result = service.roll_check(modifier=2, dc=16)
    assert result["rolls"] == [15]
    assert result["total"] == 17
    assert result["success"] is True


def test_advantage_uses_higher_roll():
    rolls = iter([3, 18])
    service = CombatService(rng=lambda sides: next(rolls))
    result = service.roll_check(modifier=1, dc=15, mode="advantage")
    assert result["rolls"] == [3, 18]
    assert result["kept"] == 18
    assert result["success"] is True


def test_disadvantage_uses_lower_roll():
    rolls = iter([19, 4])
    service = CombatService(rng=lambda sides: next(rolls))

    result = service.roll_check(modifier=5, dc=10, mode="disadvantage")

    assert result["rolls"] == [19, 4]
    assert result["kept"] == 4
    assert result["total"] == 9
    assert result["success"] is False


def test_attack_damage_and_turn_order():
    rolls = iter([17, 4, 12, 8])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 12, "ac": 14, "attack_bonus": 5, "damage": "1d8+3"},
            {"name": "Goblin", "side": "enemy", "hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d6+2"},
        ]
    )
    assert state["is_active"] is True
    assert state["participants"][0]["name"] == "Hero"
    result = service.resolve_attack(state, attacker_name="Hero", target_name="Goblin")
    assert result["hit"] is True
    assert result["damage"] == 7
    assert result["target"]["hp"] == 0
    assert result["state"]["is_active"] is False


def test_lethal_attack_that_eliminates_one_side_returns_inactive_state():
    rolls = iter([16, 7])
    service = CombatService(rng=lambda sides: next(rolls))
    state = {
        "participants": [
            {"name": "Hero", "side": "player", "hp": 12, "ac": 14, "attack_bonus": 5, "damage": "1d8+3", "kind": "pc", "initiative": 10, "defeated": False},
            {"name": "Guard", "side": "enemy", "hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d6+2", "kind": "npc", "initiative": 9, "defeated": False},
        ],
        "is_active": True,
        "round_number": 1,
        "turn_index": 0,
    }

    result = service.resolve_attack(state, attacker_name="Hero", target_name="Guard")

    assert result["hit"] is True
    assert result["target"]["defeated"] is True
    assert result["state"]["is_active"] is False


def test_resolve_attack_rejects_inactive_state():
    service = CombatService(rng=lambda sides: 10)
    state = {
        "participants": [
            {"name": "Hero", "side": "player", "hp": 12, "ac": 14, "attack_bonus": 5, "damage": "1d8+3", "kind": "pc", "initiative": 10, "defeated": False},
            {"name": "Guard", "side": "enemy", "hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d6+2", "kind": "npc", "initiative": 9, "defeated": False},
        ],
        "is_active": False,
        "round_number": 1,
        "turn_index": 0,
    }

    with pytest.raises(ValueError, match="inactive combat"):
        service.resolve_attack(state, attacker_name="Hero", target_name="Guard")


def test_advance_turn_rejects_inactive_state():
    service = CombatService(rng=lambda sides: 10)
    state = {
        "participants": [
            {"name": "Hero", "side": "player", "hp": 12, "ac": 14, "attack_bonus": 5, "damage": "1d8+3", "kind": "pc", "initiative": 10, "defeated": False},
            {"name": "Guard", "side": "enemy", "hp": 7, "ac": 13, "attack_bonus": 4, "damage": "1d6+2", "kind": "npc", "initiative": 9, "defeated": False},
        ],
        "is_active": False,
        "round_number": 1,
        "turn_index": 0,
    }

    with pytest.raises(ValueError, match="inactive combat"):
        service.advance_turn(state)


def test_miss_deals_no_damage():
    rolls = iter([10, 9, 2])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 12, "ac": 14, "attack_bonus": 1, "damage": "1d8+3"},
            {"name": "Guard", "side": "enemy", "hp": 7, "ac": 18, "attack_bonus": 4, "damage": "1d6+2"},
        ]
    )

    result = service.resolve_attack(state, attacker_name="Hero", target_name="Guard")

    assert result["hit"] is False
    assert result["damage"] == 0
    assert result["damage_roll"] is None
    assert result["target"]["hp"] == 7


def test_invalid_dice_expression_raises_clear_error():
    service = CombatService(rng=lambda sides: 1)

    with pytest.raises(ValueError, match="Invalid dice expression"):
        service.roll_damage("d8+3")


def test_roll_damage_supports_plain_and_negative_modifier_expressions():
    rolls = iter([5, 3, 4])
    service = CombatService(rng=lambda sides: next(rolls))

    plain = service.roll_damage("1d6")
    negative = service.roll_damage("2d4-1")

    assert plain == {"expression": "1d6", "rolls": [5], "modifier": 0, "total": 5}
    assert negative == {"expression": "2d4-1", "rolls": [3, 4], "modifier": -1, "total": 6}


def test_combat_participant_input_validates_damage_expression():
    participant = CombatParticipantInput(name="Hero", side="player", hp=12, ac=14, damage="2d6+3")

    assert participant.damage == "2d6+3"

    with pytest.raises(ValidationError):
        CombatParticipantInput(name="Hero", side="player", hp=12, ac=14, damage="d6+3")


def test_combat_action_request_accepts_old_attack_payload():
    request = CombatActionRequest(attacker_name="Hero", target_name="Goblin")

    assert request.action_type == "attack"
    assert request.actor_name == "Hero"
    assert request.attacker_name == "Hero"
    assert request.target_name == "Goblin"


def test_combat_action_request_accepts_new_payload():
    request = CombatActionRequest(
        actor_name="Hero",
        action_type="dash",
        movement_ft=15,
        difficult_terrain=True,
    )

    assert request.actor_name == "Hero"
    assert request.action_type == "dash"
    assert request.movement_ft == 15
    assert request.difficult_terrain is True


def test_start_combat_adds_initiative_bonus_and_default_turn_resources():
    rolls = iter([10, 12])
    service = CombatService(rng=lambda sides: next(rolls))

    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 12, "hp_max": 12, "ac": 14, "initiative_bonus": 3, "speed_ft": 30},
            {"name": "Goblin", "side": "enemy", "hp": 7, "hp_max": 7, "ac": 13, "initiative_bonus": 0, "speed_ft": 30},
        ]
    )

    assert [participant["name"] for participant in state["participants"]] == ["Hero", "Goblin"]
    hero = state["participants"][0]
    assert hero["initiative"] == 13
    assert hero["movement_remaining_ft"] == 30
    assert hero["action_available"] is True
    assert hero["reaction_available"] is True
    assert hero["conditions"] == []


def test_old_participants_are_upgraded_when_action_resolves():
    service = CombatService(rng=lambda sides: 20)
    state = {
        "participants": [
            {"name": "Hero", "side": "player", "hp": 10, "ac": 12, "attack_bonus": 2, "damage": "1d4", "kind": "pc", "initiative": 10, "defeated": False},
            {"name": "Rat", "side": "enemy", "hp": 1, "ac": 10, "attack_bonus": 0, "damage": "1d4", "kind": "npc", "initiative": 5, "defeated": False},
        ],
        "is_active": True,
        "round_number": 1,
        "turn_index": 0,
    }

    result = service.resolve_action(state, {"actor_name": "Hero", "action_type": "dodge"})

    assert result["state"]["participants"][0]["speed_ft"] == 30
    assert "dodge" in result["state"]["participants"][0]["conditions"]


def test_dash_disengage_and_dodge_consume_action_and_set_state():
    service = CombatService(rng=lambda sides: 10)
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12},
            {"name": "Orc", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 12},
        ]
    )

    dashed = service.resolve_action(state, {"actor_name": "Hero", "action_type": "dash"})["state"]
    hero = dashed["participants"][0]
    assert hero["movement_remaining_ft"] == 60
    assert hero["action_available"] is False

    service.advance_turn(dashed)
    service.advance_turn(dashed)
    disengaged = service.resolve_action(dashed, {"actor_name": "Hero", "action_type": "disengage"})["state"]
    assert disengaged["participants"][0]["disengage_active"] is True


def test_move_spends_double_movement_in_difficult_terrain_and_flags_opportunity():
    service = CombatService(rng=lambda sides: 10)
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "engaged_with": ["Orc"]},
            {"name": "Orc", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 12, "engaged_with": ["Hero"]},
        ]
    )

    result = service.resolve_action(
        state,
        {
            "actor_name": "Hero",
            "action_type": "move",
            "movement_ft": 10,
            "difficult_terrain": True,
            "leaves_reach_of": "Orc",
        },
    )

    hero = result["state"]["participants"][0]
    assert hero["movement_remaining_ft"] == 10
    assert result["opportunity_attack"]["eligible"] is True
    assert result["opportunity_attack"]["attacker_name"] == "Orc"


def test_total_cover_blocks_direct_attack_and_half_cover_adds_ac():
    rolls = iter([10, 9, 14])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat(
        [
            {"name": "Archer", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "attack_bonus": 0, "damage": "1d4"},
            {"name": "Goblin", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 14, "cover": "half"},
        ]
    )

    result = service.resolve_attack(state, "Archer", "Goblin")

    assert result["attack_roll"]["dc"] == 16
    assert result["hit"] is False

    state["participants"][1]["cover"] = "total"
    with pytest.raises(ValueError, match="total cover"):
        service.resolve_attack(state, "Archer", "Goblin")


def test_natural_20_hits_and_doubles_damage_dice():
    rolls = iter([10, 9, 20, 3, 4])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "attack_bonus": 0, "damage": "1d8+2"},
            {"name": "Ogre", "side": "enemy", "hp": 30, "hp_max": 30, "ac": 30},
        ]
    )

    result = service.resolve_attack(state, "Hero", "Ogre")

    assert result["hit"] is True
    assert result["critical"] is True
    assert result["damage"] == 9


def test_damage_resistance_vulnerability_immunity_and_temp_hp():
    service = CombatService(rng=lambda sides: 6)
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "attack_bonus": 20, "damage": "1d6", "damage_type": "fire"},
            {"name": "Target", "side": "enemy", "hp": 20, "hp_max": 20, "temp_hp": 3, "ac": 10, "resistances": ["fire"]},
        ]
    )

    result = service.resolve_attack(state, "Hero", "Target")

    assert result["damage"] == 3
    assert result["target"]["temp_hp"] == 0
    assert result["target"]["hp"] == 20


def test_character_at_zero_hp_tracks_death_saves_and_can_be_stabilized():
    rolls = iter([10, 9, 20])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "kind": "character", "hp": 0, "hp_max": 10, "ac": 12},
            {"name": "Goblin", "side": "enemy", "hp": 7, "hp_max": 7, "ac": 13},
        ]
    )

    result = service.resolve_action(state, {"actor_name": "Hero", "action_type": "death_save"})

    assert result["roll"]["kept"] == 20
    assert result["actor"]["hp"] == 1
    assert result["actor"]["death_saves"] == {"successes": 0, "failures": 0}


def test_zero_hp_character_turn_has_no_ordinary_turn_resources():
    rolls = iter([10, 9])
    service = CombatService(rng=lambda sides: next(rolls))

    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "kind": "character", "hp": 0, "hp_max": 10, "ac": 12},
            {"name": "Goblin", "side": "enemy", "hp": 7, "hp_max": 7, "ac": 13},
        ]
    )

    hero = state["participants"][0]
    assert hero["name"] == "Hero"
    assert hero["action_available"] is False
    assert hero["bonus_action_available"] is False
    assert hero["reaction_available"] is False
    assert hero["movement_remaining_ft"] == 0
    assert {"unconscious", "incapacitated"}.issubset(set(hero["conditions"]))


def test_character_at_zero_hp_cannot_take_ordinary_actions():
    service = CombatService(rng=lambda sides: 10)
    state = {
        "participants": [
            {
                "name": "Hero",
                "side": "player",
                "kind": "character",
                "hp": 0,
                "hp_max": 10,
                "ac": 12,
                "attack_bonus": 5,
                "damage": "1d8+3",
                "initiative": 10,
                "defeated": False,
            },
            {
                "name": "Goblin",
                "side": "enemy",
                "kind": "npc",
                "hp": 7,
                "hp_max": 7,
                "ac": 13,
                "initiative": 9,
                "defeated": False,
            },
        ],
        "is_active": True,
        "round_number": 1,
        "turn_index": 0,
    }

    with pytest.raises(ValueError, match="cannot act at 0 hit points"):
        service.resolve_action(
            state,
            {"actor_name": "Hero", "action_type": "attack", "target_name": "Goblin"},
        )

    with pytest.raises(ValueError, match="cannot act at 0 hit points"):
        service.resolve_action(state, {"actor_name": "Hero", "action_type": "dash"})


def test_incapacitated_participant_cannot_make_opportunity_attack():
    service = CombatService(rng=lambda sides: 10)
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "engaged_with": ["Fallen"]},
            {
                "name": "Fallen",
                "side": "enemy",
                "kind": "character",
                "hp": 0,
                "hp_max": 10,
                "ac": 13,
                "engaged_with": ["Hero"],
                "reaction_available": True,
                "conditions": ["incapacitated"],
            },
        ]
    )

    result = service.resolve_action(
        state,
        {"actor_name": "Hero", "action_type": "move", "movement_ft": 10, "leaves_reach_of": "Fallen"},
    )

    assert result["opportunity_attack"]["eligible"] is False


def test_grapple_uses_opposed_athletics_and_applies_grappled():
    rolls = iter([10, 9, 15, 9])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "athletics_bonus": 5},
            {"name": "Bandit", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 12, "athletics_bonus": 1},
        ]
    )

    result = service.resolve_action(
        state,
        {"actor_name": "Hero", "action_type": "grapple", "target_name": "Bandit", "defender_choice": "athletics"},
    )

    assert result["success"] is True
    assert "grappled" in result["target"]["conditions"]
    assert result["target"]["grappled_by"] == "Hero"


def test_shove_can_knock_target_prone():
    rolls = iter([10, 9, 16, 8])
    service = CombatService(rng=lambda sides: next(rolls))
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12, "athletics_bonus": 4},
            {"name": "Bandit", "side": "enemy", "hp": 10, "hp_max": 10, "ac": 12, "acrobatics_bonus": 2},
        ]
    )

    result = service.resolve_action(
        state,
        {"actor_name": "Hero", "action_type": "shove", "target_name": "Bandit", "defender_choice": "acrobatics", "shove_effect": "prone"},
    )

    assert result["success"] is True
    assert "prone" in result["target"]["conditions"]


def test_invalid_roll_mode_raises_clear_error():
    service = CombatService(rng=lambda sides: 1)

    with pytest.raises(ValueError, match="Invalid roll mode"):
        service.roll_check(mode="blessed")


def test_start_combat_requires_participants():
    service = CombatService(rng=lambda sides: 1)

    with pytest.raises(ValueError, match="at least one participant"):
        service.start_combat([])


def test_resolve_attack_requires_living_attacker_and_target():
    service = CombatService(rng=lambda sides: 10)
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 12, "ac": 14},
            {"name": "Guard", "side": "enemy", "hp": 7, "ac": 13},
        ]
    )

    with pytest.raises(ValueError, match="Missing attacker"):
        service.resolve_attack(state, attacker_name="Rogue", target_name="Guard")
    with pytest.raises(ValueError, match="Missing target"):
        service.resolve_attack(state, attacker_name="Hero", target_name="Ogre")


def test_advance_turn_ends_combat_when_one_side_lives():
    service = CombatService(rng=lambda sides: 10)
    state = service.start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 12, "ac": 14},
            {"name": "Goblin", "side": "enemy", "hp": 0, "ac": 13},
        ]
    )

    advanced = service.advance_turn(state)

    assert advanced["is_active"] is False


def test_advance_turn_wraps_once_while_skipping_defeated_participants():
    service = CombatService(rng=lambda sides: 10)
    state = {
        "participants": [
            {"name": "Down", "side": "player", "hp": 0, "ac": 10, "attack_bonus": 0, "damage": "1d4", "kind": "npc", "initiative": 10, "defeated": True},
            {"name": "Hero", "side": "player", "hp": 8, "ac": 14, "attack_bonus": 0, "damage": "1d4", "kind": "npc", "initiative": 9, "defeated": False},
            {"name": "Enemy", "side": "enemy", "hp": 8, "ac": 12, "attack_bonus": 0, "damage": "1d4", "kind": "npc", "initiative": 8, "defeated": False},
        ],
        "is_active": True,
        "round_number": 1,
        "turn_index": 2,
    }

    advanced = service.advance_turn(state)

    assert advanced["turn_index"] == 1
    assert advanced["round_number"] == 2


def test_end_combat_sets_inactive():
    service = CombatService(rng=lambda sides: 1)
    state = {"participants": [], "is_active": True, "round_number": 1, "turn_index": 0}

    ended = service.end_combat(state)

    assert ended["is_active"] is False
