from backend.src.agent.character_creation.messages import (
    CharacterCreationMessageRepository,
)
from backend.src.agent.character_creation.models import (
    CharacterCreationTurnResult,
)
from backend.src.agent.character_creation.supervisor import (
    CharacterCreationReActAgent,
)
from backend.src.services.character_drafts import CharacterDraftService


def test_character_creation_messages_persist_by_session(client):
    repository = CharacterCreationMessageRepository(client.app.state.store)
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "zh-CN"},
    ).json()

    repository.append(session["id"], "user", "戴尔 人类战士")
    repository.append(
        session["id"],
        "assistant",
        "请分配属性值",
        {"extractor": "llm"},
    )

    messages = repository.list_recent(session["id"], limit=12)

    assert [(item.role, item.content) for item in messages] == [
        ("user", "戴尔 人类战士"),
        ("assistant", "请分配属性值"),
    ]
    assert messages[-1].metadata == {"extractor": "llm"}


def test_character_creation_messages_return_latest_limit_in_chronological_order(client):
    repository = CharacterCreationMessageRepository(client.app.state.store)
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()

    for index in range(15):
        repository.append(session["id"], "user", f"message-{index}")

    messages = repository.list_recent(session["id"], limit=12)

    assert [item.content for item in messages] == [
        f"message-{index}" for index in range(3, 15)
    ]


def test_character_creation_service_persists_user_and_assistant_turns(client):
    repository = CharacterCreationMessageRepository(client.app.state.store)
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "zh-CN"},
    ).json()

    client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"locale": "zh-CN", "content": "戴尔 人类战士"},
    )
    client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"locale": "zh-CN", "content": "15、15、15、8、8、8"},
    )

    messages = repository.list_recent(session["id"], limit=12)

    assert [item.role for item in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[0].content == "戴尔 人类战士"
    assert messages[2].content == "15、15、15、8、8、8"


def test_character_creation_service_uses_react_supervisor(client):
    service = CharacterDraftService(client.app.state.store)

    assert isinstance(service.agent, CharacterCreationReActAgent)


class HistoryRecordingAgent:
    def __init__(self):
        self.histories = []

    def process(
        self,
        *,
        session_id,
        draft,
        content,
        locale,
        recent_messages,
    ):
        self.histories.append(recent_messages)
        return CharacterCreationTurnResult(
            assistant_text=f"reply:{content}",
            draft=draft,
            diagnostics={
                "agent_kind": "react",
                "responder": "template",
                "next_step": "identity",
            },
        )


def test_character_creation_service_passes_prior_turns_to_agent(client):
    service = CharacterDraftService(client.app.state.store)
    service.agent = HistoryRecordingAgent()
    session = service.create("en")

    service.handle_message(session.id, "first", "en")
    service.handle_message(session.id, "second", "en")

    assert service.agent.histories[0] == []
    assert service.agent.histories[1] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply:first"},
    ]


def test_character_creation_read_only_turn_keeps_revision_and_metadata(client):
    service = CharacterDraftService(client.app.state.store)
    service.agent = HistoryRecordingAgent()
    session = service.create("en")

    response = service.handle_message(session.id, "Explain Fighters.", "en")

    assert response.revision == 0
    assert response.draft.revision == 0
    assert response.metadata["agent_kind"] == "react"
    persisted = service.messages.list_recent(session.id, limit=2)
    assert persisted[-1].metadata["agent_kind"] == "react"


class ConcurrentRevisionAgent:
    def __init__(self, store):
        self.store = store

    def process(
        self,
        *,
        session_id,
        draft,
        content,
        locale,
        recent_messages,
    ):
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE character_creation_sessions
                SET revision = revision + 1
                WHERE id = ?
                """,
                (session_id,),
            )
        changed = draft.model_copy(deep=True)
        changed.revision += 1
        changed.name = "Mira"
        return CharacterCreationTurnResult(
            assistant_text="Updated.",
            draft=changed,
            diagnostics={"agent_kind": "react"},
        )


def test_character_creation_service_rejects_concurrent_session_change(client):
    service = CharacterDraftService(client.app.state.store)
    service.agent = ConcurrentRevisionAgent(client.app.state.store)
    session = service.create("en")

    from backend.src.agent.character_creation.rules.draft_service import (
        DraftRevisionConflict,
    )

    try:
        service.handle_message(session.id, "Rename to Mira.", "en")
    except DraftRevisionConflict:
        pass
    else:
        raise AssertionError("Expected DraftRevisionConflict.")

    persisted = service.get(session.id)
    assert persisted.revision == 1
    assert persisted.draft.name == ""
