def start_session(client, locale="en"):
    return client.post(
        "/api/character-creation/sessions",
        json={"locale": locale},
    ).json()


def patch_draft(client, session_id, revision, operation, payload, locale="en"):
    return client.patch(
        f"/api/character-creation/sessions/{session_id}/draft",
        json={
            "expected_revision": revision,
            "operation": operation,
            "payload": payload,
            "locale": locale,
        },
    )


def apply_patch(client, session, operation, payload):
    response = patch_draft(
        client,
        session["id"],
        session["revision"],
        operation,
        payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_non_spellcaster_can_complete_character_creation_steps_one_through_eight(
    client,
):
    session = start_session(client)
    session = apply_patch(client, session, "identity", {"name": "Bruenor"})
    session = apply_patch(
        client,
        session,
        "class",
        {"class_id": "class.fighter"},
    )
    session = apply_patch(
        client,
        session,
        "race",
        {
            "race_id": "race.dwarf",
            "subrace_id": "race.mountain-dwarf",
            "choice_values": {
                "dwarf-tool": ["tool.artisan.blacksmith"],
            },
        },
    )
    session = apply_patch(
        client,
        session,
        "background",
        {"background_id": "background.soldier"},
    )
    session = apply_patch(
        client,
        session,
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
    )
    session = apply_patch(
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
    session = apply_patch(
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
    session = apply_patch(client, session, "optional_rules", {})

    draft = session["draft"]
    assert session["revision"] == 8
    assert draft["current_step"] == "equipment"
    assert draft["completed_steps"][:9] == [
        "identity",
        "class",
        "race",
        "background",
        "abilities",
        "proficiencies",
        "class_features",
        "optional_rules",
        "spells",
    ]
    assert draft["selections"]["class_id"] == "class.fighter"
    assert draft["selections"]["background_id"] == "background.soldier"
    assert draft["selections"]["class_option_ids"] == [
        "class_option.fighter.defense"
    ]
    assert draft["proficiencies"]["skills"] == [
        "skill.athletics",
        "skill.intimidation",
        "skill.perception",
        "skill.survival",
    ]
    assert "tool.artisan.blacksmith" in draft["proficiencies"]["tools"]
    assert draft["derived"]["hp_max"] == 13
    assert draft["derived"]["speed"] == 25


def test_class_background_and_race_changes_invalidate_dependent_steps(client):
    session = start_session(client)
    session = apply_patch(client, session, "identity", {"name": "Revision"})
    session = apply_patch(client, session, "class", {"class_id": "class.fighter"})
    session = apply_patch(
        client,
        session,
        "race",
        {"race_id": "race.human", "choice_values": {"human-language": ["language.elvish"]}},
    )
    session = apply_patch(
        client,
        session,
        "background",
        {"background_id": "background.soldier"},
    )
    session = apply_patch(
        client,
        session,
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
    )
    session = apply_patch(
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
    session = apply_patch(
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
    session = apply_patch(client, session, "optional_rules", {})

    changed_class = apply_patch(
        client,
        session,
        "class",
        {"class_id": "class.rogue"},
    )
    assert {
        "proficiencies",
        "equipment",
        "adventure_connection",
        "review",
    } <= set(changed_class["draft"]["invalid_steps"])

    changed_background = apply_patch(
        client,
        changed_class,
        "background",
        {"background_id": "background.urchin"},
    )
    assert {"proficiencies", "equipment", "review"} <= set(
        changed_background["draft"]["invalid_steps"]
    )

    changed_race = apply_patch(
        client,
        changed_background,
        "race",
        {
            "race_id": "race.elf",
            "subrace_id": "race.wood-elf",
            "choice_values": {},
        },
    )
    assert {
        "proficiencies",
        "equipment",
        "adventure_connection",
        "review",
    } <= set(changed_race["draft"]["invalid_steps"])
    assert "human-language" not in changed_race["draft"]["selections"]["choice_values"]


def test_proficiency_conflicts_return_validation_error(client):
    session = start_session(client)
    session = apply_patch(client, session, "identity", {"name": "Conflict"})
    session = apply_patch(client, session, "class", {"class_id": "class.fighter"})
    session = apply_patch(
        client,
        session,
        "race",
        {
            "race_id": "race.elf",
            "subrace_id": "race.wood-elf",
            "choice_values": {},
        },
    )
    session = apply_patch(
        client,
        session,
        "background",
        {"background_id": "background.sailor"},
    )
    session = apply_patch(
        client,
        session,
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
    )

    response = patch_draft(
        client,
        session["id"],
        session["revision"],
        "proficiencies",
        {
            "choice_values": {
                "fighter-skills": ["skill.perception", "skill.survival"],
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "skill.perception" in " ".join(payload["validation_errors"])
    assert payload["revision"] == session["revision"]


def test_selected_level_one_subclass_adds_its_proficiencies(client):
    session = start_session(client)
    session = apply_patch(client, session, "identity", {"name": "Domain"})
    session = apply_patch(client, session, "class", {"class_id": "class.cleric"})
    session = apply_patch(
        client,
        session,
        "race",
        {
            "race_id": "race.human",
            "choice_values": {"human-language": ["language.elvish"]},
        },
    )
    session = apply_patch(
        client,
        session,
        "background",
        {"background_id": "background.sage"},
    )
    session = apply_patch(
        client,
        session,
        "abilities",
        {
            "base": {
                "strength": 10,
                "dexterity": 12,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 15,
                "charisma": 8,
            }
        },
    )
    session = apply_patch(
        client,
        session,
        "proficiencies",
        {
            "choice_values": {
                "cleric-skills": ["skill.insight", "skill.medicine"],
                "sage-languages": ["language.dwarvish", "language.gnomish"],
            }
        },
    )
    session = apply_patch(
        client,
        session,
        "class_features",
        {
            "class_option_ids": ["class_option.cleric.life"],
            "choice_values": {
                "cleric-domain": ["class_option.cleric.life"],
            },
        },
    )

    assert "armor.heavy" in session["draft"]["proficiencies"]["armor"]


def test_draconic_resilience_increases_level_one_hit_points(client):
    session = start_session(client)
    session = apply_patch(client, session, "identity", {"name": "Ember"})
    session = apply_patch(client, session, "class", {"class_id": "class.sorcerer"})
    session = apply_patch(
        client,
        session,
        "race",
        {
            "race_id": "race.human",
            "choice_values": {"human-language": ["language.elvish"]},
        },
    )
    session = apply_patch(
        client,
        session,
        "background",
        {"background_id": "background.sage"},
    )
    session = apply_patch(
        client,
        session,
        "abilities",
        {
            "base": {
                "strength": 8,
                "dexterity": 14,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 15,
            }
        },
    )
    session = apply_patch(
        client,
        session,
        "proficiencies",
        {
            "choice_values": {
                "sorcerer-skills": ["skill.deception", "skill.insight"],
                "sage-languages": ["language.dwarvish", "language.gnomish"],
            }
        },
    )
    session = apply_patch(
        client,
        session,
        "class_features",
        {
            "class_option_ids": [
                "class_option.sorcerer.draconic-bloodline"
            ],
            "choice_values": {
                "sorcerous-origin": [
                    "class_option.sorcerer.draconic-bloodline"
                ],
                "sorcerer-dragon-ancestor": [
                    "race_option.dragonborn.red"
                ],
            },
        },
    )

    assert session["draft"]["derived"]["hp_max"] == 9
