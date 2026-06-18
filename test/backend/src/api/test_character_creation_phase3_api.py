def patch_step(client, session, operation, payload):
    response = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": session["revision"],
            "operation": operation,
            "payload": payload,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_fighter_completes_phase_three_with_deterministic_combat_sheet(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()
    session = patch_step(client, session, "identity", {"name": "Aric"})
    session = patch_step(
        client,
        session,
        "class",
        {"class_id": "class.fighter"},
    )
    session = patch_step(
        client,
        session,
        "race",
        {
            "race_id": "race.human",
            "choice_values": {"human-language": ["language.elvish"]},
        },
    )
    session = patch_step(
        client,
        session,
        "background",
        {"background_id": "background.soldier"},
    )
    session = patch_step(
        client,
        session,
        "abilities",
        {
            "base": {
                "strength": 15,
                "dexterity": 12,
                "constitution": 13,
                "intelligence": 8,
                "wisdom": 10,
                "charisma": 10,
            }
        },
    )
    session = patch_step(
        client,
        session,
        "proficiencies",
        {
            "choice_values": {
                "fighter-skills": ["skill.perception", "skill.survival"],
                "soldier-gaming-set": ["tool.gaming.dice"],
            }
        },
    )
    session = patch_step(
        client,
        session,
        "class_features",
        {
            "class_option_ids": ["class_option.fighter.defense"],
            "choice_values": {
                "fighter-style": ["class_option.fighter.defense"],
            },
        },
    )
    session = patch_step(client, session, "optional_rules", {})
    session = patch_step(client, session, "spells", {"spell_ids": []})
    session = patch_step(
        client,
        session,
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
                "soldier-gaming-set": ["equipment.dice-set"],
            },
        },
    )

    draft = session["draft"]
    assert draft["current_step"] == "adventure_connection"
    assert draft["derived"]["hp_max"] == 12
    assert draft["derived"]["armor_class"] == 19
    battleaxe = next(
        attack
        for attack in draft["derived"]["attacks"]
        if attack["item_id"] == "equipment.battleaxe"
    )
    assert battleaxe["attack_bonus"] == 5
    assert battleaxe["damage"] == "1d8+3"
    assert {"spells", "equipment"} <= set(draft["completed_steps"])
