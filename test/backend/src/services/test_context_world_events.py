from backend.src.schemas.world_event import WorldEventCreate
from backend.src.services.adventures import AdventureService
from backend.src.services.context import ContextService
from backend.src.services.world_events import WorldEventService


def create_adventure(client):
    character = client.post(
        "/api/characters",
        json={"name": "Lysa", "race": "Human", "class_name": "Fighter"},
    ).json()
    return client.post("/api/adventures", json={"title": "Bell Road", "character_id": character["id"]}).json()


def test_world_events_are_persisted_for_an_adventure(client):
    adventure = create_adventure(client)
    service = WorldEventService(client.app.state.store)

    event = service.create(
        adventure["id"],
        WorldEventCreate(
            event_type="npc",
            title="Guard sacrifice",
            description="The gate guard held the line and died buying time.",
            importance=5,
            metadata={"npc": "Gate Guard"},
        ),
    )
    listed = service.list_for_adventure(adventure["id"], min_importance=4)

    assert event.id > 0
    assert event.title == "Guard sacrifice"
    assert listed == [event]


def test_context_service_updates_summary_when_context_exceeds_limit(client):
    adventure = create_adventure(client)
    adventure_service = AdventureService(client.app.state.store)
    event_service = WorldEventService(client.app.state.store)
    event_service.create(
        adventure["id"],
        WorldEventCreate(
            event_type="world",
            title="Bell cracked",
            description="The tower bell cracked and can no longer warn nearby villages.",
            importance=4,
        ),
    )
    for index in range(12):
        adventure_service.append_message(
            adventure["id"],
            "player" if index % 2 == 0 else "dm",
            f"Long event message {index} about the changing tower situation and the party response.",
        )

    context = ContextService(client.app.state.store).summarize_if_needed(
        adventure["id"],
        max_context_tokens=20,
    )
    updated = adventure_service.get(adventure["id"], include_messages=False)

    assert context.summary_updated is True
    assert "Bell cracked" in context.summary
    assert "Long event message 11" in context.summary
    assert updated.summary == context.summary
