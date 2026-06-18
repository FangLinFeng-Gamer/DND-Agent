def test_default_story_is_seeded(client):
    response = client.get("/api/stories")

    assert response.status_code == 200
    stories = response.json()
    assert any(story["id"] == "mistbell_tower" for story in stories)
    default_story = next(story for story in stories if story["id"] == "mistbell_tower")
    assert default_story["title"] == "Mistbell Tower"
    assert "Ravenford" in default_story["world_background"]


def test_create_and_get_custom_story(client):
    payload = {
        "title": "Ashen Mine",
        "description": "A short delve under a ruined silver mine.",
        "world_background": "The old mine feeds the frontier town but smoke now rises from sealed shafts.",
        "main_quest": "Find the missing miners and stop the fire below.",
        "opening_location": "North Mine Gate",
        "opening_environment": "Cold ash drifts across abandoned ore carts.",
        "opening_objective": "Question the foreman and inspect the blocked tunnel.",
        "important_objects": ["sealed shaft", "foreman's ledger"],
        "npcs": ["Foreman Brant"],
    }

    created = client.post("/api/stories", json=payload)

    assert created.status_code == 200
    story = created.json()
    assert story["id"].startswith("ashen-mine")
    assert story["title"] == "Ashen Mine"
    assert story["important_objects"] == ["sealed shaft", "foreman's ledger"]

    fetched = client.get(f"/api/stories/{story['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["main_quest"] == payload["main_quest"]


def test_delete_custom_story(client):
    payload = {
        "title": "Lantern Crypt",
        "description": "A contained dungeon under a roadside chapel.",
        "world_background": "Blue lanterns mark graves that refuse to stay quiet.",
        "main_quest": "Recover the stolen funeral bell before midnight.",
        "opening_location": "Old Chapel Yard",
        "opening_environment": "Cold fog coils around cracked headstones.",
        "opening_objective": "Find the fresh tracks near the chapel door.",
        "important_objects": ["blue lantern", "funeral bell"],
        "npcs": ["Sister Vale"],
    }
    story = client.post("/api/stories", json=payload).json()

    deleted = client.delete(f"/api/stories/{story['id']}")

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "id": story["id"]}
    missing = client.get(f"/api/stories/{story['id']}")
    assert missing.status_code == 404


def test_update_custom_story(client):
    payload = {
        "title": "Clockwork Shrine",
        "description": "A quiet shrine full of broken mechanisms.",
        "world_background": "Pilgrims once crossed the brass bridge to hear the shrine bells.",
        "main_quest": "Restart the shrine engine before the valley floods.",
        "opening_location": "Brass Bridge",
        "opening_environment": "Rain ticks against stopped gears and bronze lanterns.",
        "opening_objective": "Find the missing winding key.",
        "important_objects": ["winding key"],
        "npcs": ["Archivist Pell"],
    }
    story = client.post("/api/stories", json=payload).json()

    updated = client.patch(
        f"/api/stories/{story['id']}",
        json={
            "title": "Clockwork Shrine Revised",
            "main_quest": "Restart the shrine engine and rescue Archivist Pell.",
            "important_objects": ["winding key", "floodgate lever"],
        },
    )

    assert updated.status_code == 200
    data = updated.json()
    assert data["id"] == story["id"]
    assert data["title"] == "Clockwork Shrine Revised"
    assert data["main_quest"] == "Restart the shrine engine and rescue Archivist Pell."
    assert data["important_objects"] == ["winding key", "floodgate lever"]
    assert data["opening_location"] == payload["opening_location"]


def test_update_default_story_is_rejected(client):
    response = client.patch("/api/stories/mistbell_tower", json={"title": "Changed Default"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "default_story_locked"
    default_story = client.get("/api/stories/mistbell_tower")
    assert default_story.json()["title"] == "Mistbell Tower"


def test_delete_default_story_is_rejected(client):
    response = client.delete("/api/stories/mistbell_tower")

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "default_story_locked"
    default_story = client.get("/api/stories/mistbell_tower")
    assert default_story.status_code == 200


def test_missing_story_returns_structured_error(client):
    response = client.get("/api/stories/missing-story")

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "story_not_found"
