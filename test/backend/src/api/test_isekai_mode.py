def test_existing_dnd_create_defaults_to_dnd_mode(client):
    character = client.post(
        "/api/characters",
        json={"name": "Mode Hero", "race": "Human", "class_name": "Fighter"},
    ).json()

    response = client.post("/api/adventures", json={"title": "Mode Road", "character_id": character["id"]})

    assert response.status_code == 200
    adventure = response.json()
    assert adventure["mode"] == "dnd"
    assert adventure["character_id"] == character["id"]
    assert adventure["party_characters"][0]["name"] == "Mode Hero"
    assert adventure["isekai_character"] is None
    assert adventure["survival_state"] is None


def test_list_adventures_exposes_mode_for_frontend_filtering(client):
    character = client.post(
        "/api/characters",
        json={"name": "List Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    created = client.post("/api/adventures", json={"title": "List Road", "character_id": character["id"]}).json()

    response = client.get("/api/adventures")

    assert response.status_code == 200
    listed = next(item for item in response.json() if item["id"] == created["id"])
    assert listed["mode"] == "dnd"
