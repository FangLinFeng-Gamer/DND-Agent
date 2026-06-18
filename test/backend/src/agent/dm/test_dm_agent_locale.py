from backend.src.agent.dm.prompts import build_dm_messages, build_narration_messages
from backend.src.schemas.adventure import MessageCreate
from backend.src.services.dm import DMService


def create_adventure(client):
    character = client.post(
        "/api/characters",
        json={"name": "Locale Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    return client.post(
        "/api/adventures",
        json={"title": "Locale Test", "character_id": character["id"]},
    ).json()


def test_dm_and_narration_prompts_require_selected_language(client):
    adventure = create_adventure(client)
    service = DMService(client.app.state.store)
    character = service.characters.get(adventure["character_id"])
    context = service.context.summarize_if_needed(adventure["id"], 4096)

    dm_messages = build_dm_messages(
        context,
        service.adventures.get(adventure["id"]).current_scene,
        character,
        "查看房间",
        None,
        locale="zh-CN",
    )
    narration_messages = build_narration_messages(
        {"resolved_narration": "The door opens."},
        locale="zh-CN",
    )

    assert "Simplified Chinese" in dm_messages[0]["content"]
    assert "Simplified Chinese" in narration_messages[0]["content"]


def test_template_dm_uses_chinese_for_chinese_request(client):
    adventure = create_adventure(client)

    response = client.post(
        f"/api/adventures/{adventure['id']}/messages",
        json={"content": "查看房间", "locale": "zh-CN"},
    )

    assert response.status_code == 200
    assert any("\u4e00" <= character <= "\u9fff" for character in response.json()["dm_message"]["content"])


def test_adventure_opening_uses_selected_locale(client):
    character = client.post(
        "/api/characters",
        json={"name": "Opening Hero", "race": "Human", "class_name": "Fighter"},
    ).json()

    adventure = client.post(
        "/api/adventures",
        json={
            "title": "Chinese Opening",
            "character_id": character["id"],
            "locale": "zh-CN",
        },
    ).json()

    assert any(
        "\u4e00" <= character <= "\u9fff"
        for character in adventure["messages"][0]["content"]
    )


def test_dm_message_schema_locale_reaches_service(client):
    adventure = create_adventure(client)
    result = DMService(client.app.state.store).advance(
        adventure["id"],
        MessageCreate(content="查看房间", locale="zh-CN"),
    )

    assert any("\u4e00" <= character <= "\u9fff" for character in result.dm_message.content)
