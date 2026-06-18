def test_character_creation_api_accepts_spell_operation(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()
    for operation, payload in [
        ("identity", {"name": "Spell Skip"}),
        ("class", {"class_id": "class.fighter"}),
        (
            "race",
            {
                "race_id": "race.human",
                "choice_values": {"human-language": ["language.elvish"]},
            },
        ),
        ("background", {"background_id": "background.soldier"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 15,
                    "dexterity": 12,
                    "constitution": 14,
                    "intelligence": 8,
                    "wisdom": 10,
                    "charisma": 10,
                }
            },
        ),
        (
            "proficiencies",
            {
                "choice_values": {
                    "fighter-skills": ["skill.perception", "skill.survival"],
                    "soldier-gaming-set": ["tool.gaming.dice"],
                }
            },
        ),
        (
            "class_features",
            {
                "class_option_ids": ["class_option.fighter.defense"],
                "choice_values": {
                    "fighter-style": ["class_option.fighter.defense"],
                },
            },
        ),
        ("optional_rules", {}),
    ]:
        session = client.patch(
            f"/api/character-creation/sessions/{session['id']}/draft",
            json={
                "expected_revision": session["revision"],
                "operation": operation,
                "payload": payload,
            },
        ).json()

    response = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": session["revision"],
            "operation": "spells",
            "payload": {"spell_ids": []},
        },
    )

    assert response.status_code == 200
    assert response.json()["draft"]["current_step"] == "equipment"
