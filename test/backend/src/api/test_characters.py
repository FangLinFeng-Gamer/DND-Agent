def test_create_character_defaults(client):
    response = client.post("/api/characters", json={"name": "Aria", "race": "Elf", "class_name": "Ranger"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Aria"
    assert data["level"] == 1
    assert data["experience_points"] == 0
    assert data["next_level_experience"] == 300
    assert data["hp_current"] == data["hp_max"]
    assert data["armor_class"] >= 10


def test_character_experience_points_auto_level_and_expose_progress(client):
    created = client.post("/api/characters", json={"name": "Aria", "race": "Elf", "class_name": "Ranger"}).json()

    updated = client.patch(f"/api/characters/{created['id']}", json={"experience_points": 300})

    assert updated.status_code == 200
    data = updated.json()
    assert data["experience_points"] == 300
    assert data["level"] == 2
    assert data["next_level_experience"] == 900
    assert data["experience_to_next_level"] == 600
    assert data["level_progress"] == 0


def test_list_update_delete_character(client):
    created = client.post("/api/characters", json={"name": "Borin", "race": "Dwarf", "class_name": "Fighter"}).json()
    listed = client.get("/api/characters").json()
    assert any(item["id"] == created["id"] for item in listed)

    updated = client.patch(f"/api/characters/{created['id']}", json={"notes": "Carries an old map."})
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Carries an old map."

    deleted = client.delete(f"/api/characters/{created['id']}")
    assert deleted.status_code == 200
    missing = client.get(f"/api/characters/{created['id']}")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"]["code"] == "character_not_found"


def test_update_character_rejects_current_hp_above_max(client):
    created = client.post("/api/characters", json={"name": "Mira", "race": "Human", "class_name": "Wizard"}).json()

    response = client.patch(f"/api/characters/{created['id']}", json={"hp_current": 99, "hp_max": 10})

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "validation_error"


def test_update_character_rejects_null_numeric_field(client):
    created = client.post("/api/characters", json={"name": "Toma", "race": "Halfling", "class_name": "Rogue"}).json()

    response = client.patch(f"/api/characters/{created['id']}", json={"level": None})

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "validation_error"


def test_update_character_rejects_unknown_field(client):
    created = client.post("/api/characters", json={"name": "Nia", "race": "Human", "class_name": "Fighter"}).json()

    response = client.patch(f"/api/characters/{created['id']}", json={"favorite_color": "blue"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "validation_error"


def test_update_character_rejects_null_name(client):
    created = client.post("/api/characters", json={"name": "Perrin", "race": "Human", "class_name": "Fighter"}).json()

    response = client.patch(f"/api/characters/{created['id']}", json={"name": None})

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "validation_error"


def test_update_missing_character_returns_not_found(client):
    response = client.patch("/api/characters/999", json={"notes": "No one is here."})

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "character_not_found"


def test_update_character_rejects_lowering_hp_max_below_current(client):
    created = client.post("/api/characters", json={"name": "Rook", "race": "Dwarf", "class_name": "Fighter"}).json()

    response = client.patch(f"/api/characters/{created['id']}", json={"hp_max": 5})

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "validation_error"


def test_update_character_rejects_empty_body(client):
    created = client.post("/api/characters", json={"name": "Selene", "race": "Elf", "class_name": "Ranger"}).json()

    response = client.patch(f"/api/characters/{created['id']}", content="")

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "validation_error"


def test_update_character_rejects_malformed_json(client):
    created = client.post("/api/characters", json={"name": "Vex", "race": "Human", "class_name": "Wizard"}).json()

    response = client.patch(
        f"/api/characters/{created['id']}",
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "validation_error"
