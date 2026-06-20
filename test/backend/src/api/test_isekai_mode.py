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


def test_create_isekai_adventure_generates_independent_character_and_survival_state(client):
    response = client.post(
        "/api/adventures",
        json={"title": "Fog Border", "mode": "isekai_survival", "locale": "zh-CN"},
    )

    assert response.status_code == 200
    adventure = response.json()
    assert adventure["mode"] == "isekai_survival"
    assert adventure["story_id"] == "isekai_survival"
    assert adventure["party_characters"] == []
    assert adventure["party_character_ids"] == []
    assert adventure["isekai_character"]["name"]
    assert adventure["isekai_character"]["race"]
    assert adventure["isekai_character"]["class_name"]
    assert adventure["isekai_character"]["gold"] >= 0
    assert adventure["survival_state"]["hunger"] >= 0
    assert adventure["survival_state"]["thirst"] >= 0
    assert adventure["messages"][0]["metadata"]["mode"] == "isekai_survival"


def test_isekai_character_is_not_added_to_dnd_character_list(client):
    client.post("/api/adventures", json={"title": "No Character Leak", "mode": "isekai_survival"}).json()

    characters = client.get("/api/characters").json()

    assert all(character["name"] != "No Character Leak" for character in characters)


def test_isekai_message_updates_survival_state(client):
    adventure = client.post(
        "/api/adventures",
        json={"title": "Stream Survival", "mode": "isekai_survival", "locale": "zh-CN"},
    ).json()
    before = adventure["survival_state"]["fatigue"]

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages",
        json={"content": "我寻找水源。", "locale": "zh-CN"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["adventure"]["survival_state"]["fatigue"] > before
    assert data["dm_message"]["metadata"]["mode"] == "isekai_survival"


def test_dnd_combat_api_rejects_isekai_adventure(client):
    adventure = client.post("/api/adventures", json={"title": "No Combat", "mode": "isekai_survival"}).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/combat/start",
        json={"enemies": [{"name": "Wolf", "hp": 8, "ac": 12, "attack_bonus": 3, "damage": "1d6"}]},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "mode_not_supported"
