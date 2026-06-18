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
    updated = response.json()
    assert updated["validation_errors"] == []
    return updated


def test_character_creation_api_accepts_equipment_operation(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()
    for operation, payload in [
        ("identity", {"name": "Equipment Wizard"}),
        ("class", {"class_id": "class.wizard"}),
        (
            "race",
            {
                "race_id": "race.human",
                "choice_values": {"human-language": ["language.elvish"]},
            },
        ),
        ("background", {"background_id": "background.sage"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 8,
                    "dexterity": 14,
                    "constitution": 14,
                    "intelligence": 15,
                    "wisdom": 10,
                    "charisma": 10,
                }
            },
        ),
        (
            "proficiencies",
            {
                "choice_values": {
                    "wizard-skills": ["skill.investigation", "skill.medicine"],
                    "sage-languages": ["language.dwarvish", "language.gnomish"],
                }
            },
        ),
        (
            "spells",
            {
                "spell_ids": [
                    "spell.fire-bolt",
                    "spell.mage-hand",
                    "spell.prestidigitation",
                    "spell.alarm",
                    "spell.detect-magic",
                    "spell.find-familiar",
                    "spell.mage-armor",
                    "spell.magic-missile",
                    "spell.shield",
                ]
            },
        ),
    ]:
        session = patch_step(client, session, operation, payload)

    response = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": session["revision"],
            "operation": "equipment",
            "payload": {
                "option_ids": [
                    "wizard-weapon-quarterstaff",
                    "wizard-focus-arcane",
                    "wizard-pack-scholar",
                ],
                "item_choices": {},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_errors"] == []
    draft = payload["draft"]
    assert draft["current_step"] == "adventure_connection"
    assert {entry["item_id"] for entry in draft["inventory"]} == {
        "equipment.arcane-focus",
        "equipment.common-clothes",
        "equipment.dagger",
        "equipment.gp",
        "equipment.ink",
        "equipment.letter",
        "equipment.quarterstaff",
        "equipment.quill",
        "equipment.scholars-pack",
        "equipment.spellbook",
    }
