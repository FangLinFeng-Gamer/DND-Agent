def model_payload(name="Local DM", api_key="sk-test-secret"):
    return {
        "name": name,
        "provider": "openai_compatible",
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key": api_key,
        "model_name": "local-dm",
        "temperature": 0.4,
        "max_context_tokens": 2048,
    }


def test_create_model_masks_api_key(client):
    response = client.post("/api/models", json=model_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "Local DM"
    assert data["provider"] == "openai_compatible"
    assert data["api_key_masked"] == "sk-t...cret"
    assert "api_key" not in data
    assert data["is_active"] is False


def test_update_and_activate_model(client):
    created = client.post("/api/models", json=model_payload()).json()

    updated = client.patch(
        f"/api/models/{created['id']}",
        json={"name": "Table DM", "temperature": 0.7, "api_key": "sk-updated-secret"},
    )
    activated = client.post(f"/api/models/{created['id']}/activate")
    listed = client.get("/api/models")

    assert updated.status_code == 200
    assert updated.json()["name"] == "Table DM"
    assert updated.json()["temperature"] == 0.7
    assert updated.json()["api_key_masked"] == "sk-u...cret"
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True
    assert listed.status_code == 200
    assert listed.json()[0]["is_active"] is True


def test_only_one_model_can_be_active(client):
    first = client.post("/api/models", json=model_payload(name="First", api_key="sk-first-secret")).json()
    second = client.post("/api/models", json=model_payload(name="Second", api_key="sk-second-secret")).json()

    client.post(f"/api/models/{first['id']}/activate")
    client.post(f"/api/models/{second['id']}/activate")
    listed = client.get("/api/models").json()

    active = [model for model in listed if model["is_active"]]
    assert [model["id"] for model in active] == [second["id"]]


def test_delete_model(client):
    created = client.post("/api/models", json=model_payload()).json()

    deleted = client.delete(f"/api/models/{created['id']}")
    listed = client.get("/api/models")

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "id": created["id"]}
    assert listed.json() == []
