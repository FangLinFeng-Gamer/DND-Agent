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


def test_identity_mutation_increments_revision(client):
    session = start_session(client)

    response = patch_draft(
        client,
        session["id"],
        session["revision"],
        "identity",
        {
            "name": "Bruenor",
            "alignment": "Lawful Good",
            "appearance": "A broad-shouldered dwarf.",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["revision"] == 1
    assert updated["draft"]["name"] == "Bruenor"
    assert updated["draft"]["appearance"] == "A broad-shouldered dwarf."
    assert updated["draft"]["current_step"] == "class"
    assert "identity" in updated["draft"]["completed_steps"]


def test_race_and_point_buy_mutations_recalculate_abilities(client):
    session = start_session(client)
    race = patch_draft(
        client,
        session["id"],
        session["revision"],
        "race",
        {
            "race_id": "race.dwarf",
            "subrace_id": "race.mountain-dwarf",
            "choice_values": {},
        },
    ).json()

    abilities = patch_draft(
        client,
        session["id"],
        race["revision"],
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
    ).json()

    assert abilities["draft"]["abilities"]["point_buy_spent"] == 24
    assert abilities["draft"]["abilities"]["racial_bonuses"]["strength"] == 2
    assert abilities["draft"]["abilities"]["racial_bonuses"]["constitution"] == 2
    assert abilities["draft"]["abilities"]["final"]["strength"] == 17


def test_stale_revision_returns_conflict(client):
    session = start_session(client)
    first = patch_draft(
        client,
        session["id"],
        0,
        "identity",
        {"name": "First"},
    )
    assert first.status_code == 200

    stale = patch_draft(
        client,
        session["id"],
        0,
        "identity",
        {"name": "Stale"},
    )

    assert stale.status_code == 409
    assert stale.json()["detail"]["error"]["code"] == "draft_revision_conflict"


def test_point_buy_validation_error_is_localized(client):
    session = start_session(client, locale="zh-CN")

    response = patch_draft(
        client,
        session["id"],
        0,
        "abilities",
        {
            "base": {
                "strength": 16,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            }
        },
        locale="zh-CN",
    )

    assert response.status_code == 200
    message = " ".join(response.json()["validation_errors"])
    assert "8" in message
    assert "15" in message
