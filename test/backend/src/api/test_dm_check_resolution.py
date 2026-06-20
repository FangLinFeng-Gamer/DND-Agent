from backend.src.services.adventures import AdventureService


def test_resolve_pending_check_calculates_result_and_updates_message(client):
    character = client.post(
        "/api/characters",
        json={"name": "Resolver", "race": "Human", "class_name": "Ranger"},
    ).json()
    assert character["dexterity"] == 14
    adventure = client.post(
        "/api/adventures",
        json={"title": "Resolve Check", "character_id": character["id"]},
    ).json()
    service = AdventureService(client.app.state.store)
    dm_message = service.append_message(
        adventure["id"],
        "dm",
        "Make a Dexterity check.",
        {
            "pending_check": {
                "id": "check_1_dexterity_12",
                "status": "pending",
                "ability": "dexterity",
                "dc": 12,
                "reason": "Climb the wall",
                "character_id": character["id"],
                "character_name": character["name"],
                "source_message_id": 0,
            }
        },
    )
    metadata = dict(dm_message.metadata)
    metadata["pending_check"]["source_message_id"] = dm_message.id
    service.update_message_metadata(dm_message.id, metadata)

    response = client.post(
        f"/api/adventures/{adventure['id']}/checks/check_1_dexterity_12/resolve",
        json={"message_id": dm_message.id, "roll": 10, "locale": "zh-CN"},
    )

    assert response.status_code == 200
    data = response.json()
    resolved = next(message for message in data["messages"] if message["id"] == dm_message.id)
    assert resolved["metadata"]["pending_check"]["status"] == "resolved"
    result = resolved["metadata"]["dice_result"]
    assert result["rolls"] == [10]
    assert result["modifier"] == 2
    assert result["total"] == 12
    assert result["success"] is True
    assert result["source"] == "player_dice_tray"
    assert data["dm_message"]["role"] == "dm"
    assert "检定结果" in data["dm_message"]["content"]


def test_resolve_pending_check_rejects_duplicate_submission(client):
    character = client.post(
        "/api/characters",
        json={"name": "Duplicate", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Duplicate Check", "character_id": character["id"]},
    ).json()
    service = AdventureService(client.app.state.store)
    dm_message = service.append_message(
        adventure["id"],
        "dm",
        "Make a Strength check.",
        {
            "pending_check": {
                "id": "check_dup_strength_10",
                "status": "resolved",
                "ability": "strength",
                "dc": 10,
                "reason": "Force the door",
                "character_id": character["id"],
                "character_name": character["name"],
                "source_message_id": 0,
            },
            "dice_result": {
                "rolls": [12],
                "kept": 12,
                "modifier": 0,
                "total": 12,
                "dc": 10,
                "success": True,
            },
        },
    )

    response = client.post(
        f"/api/adventures/{adventure['id']}/checks/check_dup_strength_10/resolve",
        json={"message_id": dm_message.id, "roll": 15},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "check_already_resolved"
