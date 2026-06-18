def test_story_template_can_start_multiple_adventures(client):
    character = client.post(
        "/api/characters",
        json={"name": "Ilyra", "race": "Elf", "class_name": "Ranger"},
    ).json()

    first = client.post(
        "/api/adventures",
        json={"title": "First Mistbell Run", "character_id": character["id"], "story_id": "mistbell_tower"},
    )
    second = client.post(
        "/api/adventures",
        json={"title": "Second Mistbell Run", "character_id": character["id"], "story_id": "mistbell_tower"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["story_id"] == "mistbell_tower"
    assert second.json()["story_id"] == "mistbell_tower"


def test_story_opening_message_introduces_world_quest_and_scene(client):
    character = client.post(
        "/api/characters",
        json={"name": "Mara", "race": "Human", "class_name": "Fighter"},
    ).json()
    story = client.get("/api/stories/mistbell_tower").json()

    response = client.post(
        "/api/adventures",
        json={"title": "Mistbell Opening", "character_id": character["id"], "story_id": story["id"]},
    )

    assert response.status_code == 200
    adventure = response.json()
    opening = adventure["messages"][0]["content"]
    assert story["world_background"] in opening
    assert story["main_quest"] in opening
    assert story["opening_environment"] in opening
    assert story["opening_objective"] in opening
    assert adventure["current_scene"]["location"] == story["opening_location"]
    assert adventure["current_scene"]["important_objects"] == story["important_objects"]


def test_create_adventure_rejects_missing_story(client):
    character = client.post(
        "/api/characters",
        json={"name": "Perrin", "race": "Human", "class_name": "Fighter"},
    ).json()

    response = client.post(
        "/api/adventures",
        json={"title": "Missing Story", "character_id": character["id"], "story_id": "missing-story"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "story_not_found"


def test_custom_story_action_reply_uses_current_scene(client):
    character = client.post(
        "/api/characters",
        json={"name": "Sella", "race": "Human", "class_name": "Fighter"},
    ).json()
    story = client.post(
        "/api/stories",
        json={
            "title": "Crystal Fen",
            "description": "A wetland mystery.",
            "world_background": "Crystal Fen is a marsh of blue reeds and old elven markers.",
            "main_quest": "Find the missing reed-cutters.",
            "opening_location": "Fen Lantern Dock",
            "opening_environment": "Mist curls around tied skiffs and silent blue crystals.",
            "opening_objective": "Question the dock warden.",
            "important_objects": ["silent blue crystal"],
            "npcs": ["Dock Warden Sella"],
        },
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Fen Run", "character_id": character["id"], "story_id": story["id"]},
    ).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages",
        json={"content": "I ask the dock warden what changed."},
    )

    assert response.status_code == 200
    reply = response.json()["dm_message"]["content"]
    assert "Fen Lantern Dock" in reply
    assert "watchtower" not in reply.lower()
