import json

from backend.src.services.adventures import AdventureService


def parse_ndjson(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_adventure_creation_initializes_world_state(client):
    character = client.post(
        "/api/characters",
        json={"name": "Luma", "race": "Human", "class_name": "Fighter"},
    ).json()

    response = client.post(
        "/api/adventures",
        json={"title": "Mistbell Clock", "character_id": character["id"], "story_id": "mistbell_tower"},
    )

    assert response.status_code == 200
    adventure = response.json()
    assert adventure["world_state"]["phase"] == "festival_evening"
    assert adventure["world_state"]["phase_label"] == "节庆黄昏"
    moonwell = adventure["world_state"]["threat_clocks"][0]
    assert moonwell["id"] == "moonwell_curse"
    assert moonwell["value"] == 0
    assert moonwell["max"] == 6


def test_adventure_world_state_is_isolated_per_session(client):
    character = client.post(
        "/api/characters",
        json={"name": "Sera", "race": "Human", "class_name": "Fighter"},
    ).json()
    first = client.post(
        "/api/adventures",
        json={"title": "First Clock", "character_id": character["id"], "story_id": "mistbell_tower"},
    ).json()
    second = client.post(
        "/api/adventures",
        json={"title": "Second Clock", "character_id": character["id"], "story_id": "mistbell_tower"},
    ).json()

    first["world_state"]["threat_clocks"][0]["value"] = 3

    fresh_second = client.get(f"/api/adventures/{second['id']}").json()
    assert fresh_second["world_state"]["threat_clocks"][0]["value"] == 0
    assert first["id"] != second["id"]


def test_adventure_detail_exposes_only_public_world_state(client):
    character = client.post(
        "/api/characters",
        json={"name": "Hidden Clock", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Hidden State", "character_id": character["id"], "story_id": "mistbell_tower"},
    ).json()
    service = AdventureService(client.app.state.store)
    world_state = service.get_world_state(adventure["id"])
    world_state["hidden_events"].append("守夜人已经锁定了嫌疑人。")
    world_state["pressure_clocks"].append(
        {
            "id": "private_alarm",
            "label": "私密警戒",
            "value": 2,
            "max": 4,
            "visible": False,
            "severity": "danger",
        }
    )
    service.update_world_state(adventure["id"], world_state)

    response = client.get(f"/api/adventures/{adventure['id']}")

    assert response.status_code == 200
    public_state = response.json()["world_state"]
    assert "hidden_events" not in public_state
    assert all(clock["id"] != "private_alarm" for clock in public_state["pressure_clocks"])


def test_status_question_message_does_not_advance_world_state(client):
    character = client.post(
        "/api/characters",
        json={"name": "Kira", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Status Clock", "character_id": character["id"], "story_id": "mistbell_tower"},
    ).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages",
        json={"content": "equipment.steel-longsword是什么", "locale": "zh-CN"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["world_state"]["threat_clocks"][0]["value"] == 0
    assert data["world_state"]["last_advance"]["advanced"] is False
    assert data["dm_message"]["metadata"]["world_state"]["classification"]["message_type"] == "status_question"


def test_in_world_action_message_advances_world_state(client):
    character = client.post(
        "/api/characters",
        json={"name": "Toma", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Action Clock", "character_id": character["id"], "story_id": "mistbell_tower"},
    ).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages",
        json={"content": "我去铁匠铺搜查后院", "locale": "zh-CN"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["world_state"]["threat_clocks"][0]["value"] == 1
    assert data["world_state"]["last_advance"]["advanced"] is True
    assert data["world_state"]["last_advance"]["affected_clocks"] == ["moonwell_curse"]
    assert data["dm_message"]["metadata"]["world_state"]["pending_delta"]["pending_visible_events"]


def test_streaming_final_includes_updated_world_state(client):
    character = client.post(
        "/api/characters",
        json={"name": "Stream Clock", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Streaming Clock", "character_id": character["id"], "story_id": "mistbell_tower"},
    ).json()

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages/stream",
        json={"content": "我去铁匠铺搜查后院", "locale": "zh-CN"},
    )
    final = parse_ndjson(response)[-1]

    assert response.status_code == 200
    assert final["type"] == "final"
    assert final["world_state"]["threat_clocks"][0]["value"] == 1
    assert final["adventure"]["world_state"]["threat_clocks"][0]["value"] == 1
