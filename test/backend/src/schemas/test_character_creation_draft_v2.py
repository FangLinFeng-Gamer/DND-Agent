from backend.src.schemas.character_creation import (
    CHARACTER_CREATION_STEPS,
    CharacterDraft,
)
from backend.src.services.character_drafts import CharacterDraftService


def test_v2_draft_contains_twelve_step_wizard_state():
    draft = CharacterDraft()

    assert draft.schema_version == 2
    assert len(CHARACTER_CREATION_STEPS) == 12
    assert draft.current_step == "identity"
    assert draft.completed_steps == []
    assert draft.invalid_steps == []
    assert draft.revision == 0
    assert set(draft.abilities.base) == {
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    }


def test_v2_draft_preserves_simple_character_fields():
    draft = CharacterDraft(
        name="Aria",
        race="Elf",
        class_name="Ranger",
        background="Soldier",
        alignment="Neutral Good",
        notes="Scout",
    )

    assert draft.name == "Aria"
    assert draft.race == "Elf"
    assert draft.class_name == "Ranger"
    assert draft.background == "Soldier"
    assert draft.alignment == "Neutral Good"
    assert draft.notes == "Scout"


def test_legacy_session_draft_is_migrated_on_read(client):
    service = CharacterDraftService(client.app.state.store)
    with client.app.state.store.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO character_creation_sessions (locale, status, draft_json)
            VALUES ('en', 'draft', ?)
            """,
            ('{"name":"Legacy","race":"Elf","class_name":"Wizard"}',),
        )
        session_id = cursor.lastrowid

    session = service.get(session_id)

    assert session.draft.schema_version == 2
    assert session.draft.name == "Legacy"
    assert session.draft.race == "Elf"
    assert session.draft.current_step == "identity"


def test_session_revision_is_returned_and_increments_after_message(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()

    updated = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "content": "My name is Revision, an Elf Ranger with a Soldier background.",
            "locale": "en",
        },
    ).json()

    assert session["revision"] == 0
    assert updated["revision"] == 1
    assert updated["draft"]["revision"] == 1
