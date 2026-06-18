from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import AIMessage

from backend.src.agent.character_creation.graph import CharacterCreationAgent
from backend.src.agent.dm.schemas import AgentKind
from backend.src.db.sqlite import encode_json
from backend.src.schemas.character_creation import CharacterDraft
from backend.src.services.characters import CharacterService


class MarkdownJsonModel:
    def invoke(self, messages):
        return AIMessage(
            content=(
                "好的，以下是 JSON：\n\n"
                "```json\n"
                '{"name":"验证者","race":"Human","class_name":"Fighter","background":"Soldier"}\n'
                "```"
            )
        )


class RecordingStructuredModel:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.content)


class SequencedCharacterModel:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        content = self.contents.pop(0)
        if isinstance(content, Exception):
            raise content
        return AIMessage(content=content)


def test_character_creation_uses_react_guidance_and_fixed_validation_graph(client):
    agent = CharacterCreationAgent(client.app.state.store)

    assert agent.agent_kind is AgentKind.REACT
    assert isinstance(agent.graph, CompiledStateGraph)


def test_character_creation_requires_validation_and_explicit_confirmation(client):
    started = client.post("/api/character-creation/sessions", json={"locale": "en"})
    assert started.status_code == 200
    session = started.json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "My name is Aria, an Elf Ranger with a Soldier background."},
    )
    assert response.status_code == 200
    draft = response.json()
    assert draft["draft"]["name"] == "Aria"
    assert draft["draft"]["race"] == "Elf"
    assert draft["draft"]["class_name"] == "Ranger"
    assert draft["created_character"] is None
    assert draft["metadata"]["next_step"] == "abilities"
    assert "abilities.base" in [slot["id"] for slot in draft["metadata"]["missing_slots"]]
    assert "ability" in draft["assistant_message"].lower()

    confirmed = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "confirm"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["created_character"] is None
    assert confirmed.json()["metadata"]["next_step"] == "abilities"


def test_character_creation_rejects_unknown_race_without_creating_character(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "en"}).json()
    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "Create Zed as a Martian Fighter and confirm."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_character"] is None
    assert payload["validation_errors"]
    assert client.get("/api/characters").json() == []


def test_character_creation_accepts_chinese_confirmation(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "zh-CN"}).json()
    client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "My name is Aria, an Elf Ranger with a Soldier background."},
    )

    confirmed = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "确认创建"},
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["created_character"] is None
    assert confirmed.json()["metadata"]["next_step"] == "abilities"


def test_character_creation_returns_chinese_welcome(client):
    response = client.post(
        "/api/character-creation/sessions",
        json={"locale": "zh-CN"},
    )

    assert response.status_code == 200
    assert "角色" in response.json()["assistant_message"]


def test_character_creation_message_updates_session_locale(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "Help me create a character.", "locale": "zh-CN"},
    )

    assert response.status_code == 200
    assert response.json()["locale"] == "zh-CN"
    assert "角色" in response.json()["assistant_message"]


def test_character_creation_extracts_json_from_model_markdown_response(client):
    agent = CharacterCreationAgent(client.app.state.store, model=MarkdownJsonModel())

    result = agent.process(
        CharacterDraft(),
        "我想创建一名人类战士，名字叫验证者，背景是士兵。",
        "zh-CN",
    )

    assert result["draft"].name == "验证者"
    assert result["draft"].race == "Human"
    assert result["draft"].class_name == "Fighter"
    assert result["draft"].background == "Soldier"
    assert result["validation_errors"] == []


def test_character_structured_extraction_receives_recent_history(client):
    model = RecordingStructuredModel(
        '{"intent":"update","race":"Elf","unexpected":"ignored"}'
    )
    agent = CharacterCreationAgent(client.app.state.store, model=model)
    draft = CharacterDraft(
        name="Dale",
        race="Human",
        class_name="Fighter",
    )

    result = agent.process(
        draft,
        "改成精灵",
        "zh-CN",
        recent_messages=[
            {"role": "user", "content": "戴尔 人类战士"},
            {"role": "assistant", "content": "请分配属性值"},
        ],
    )

    request_payload = __import__("json").loads(model.calls[0][1].content)
    assert request_payload["current_draft"]["name"] == "Dale"
    assert request_payload["recent_messages"] == [
        {"role": "user", "content": "戴尔 人类战士"},
        {"role": "assistant", "content": "请分配属性值"},
    ]
    assert request_payload["message"] == "改成精灵"
    assert result["draft"].race == "Elf"
    assert result["metadata"]["extractor"] == "llm"
    assert "unexpected" not in result["draft"].model_dump()


def test_character_responder_uses_validated_state_for_natural_reply(client):
    model = SequencedCharacterModel(
        [
            '{"intent":"provide_info","name":"Mira","race":"Human","class_name":"Fighter"}',
            "角色概念已经记录。接下来请按照 27 点购点规则分配六项属性。",
        ]
    )
    agent = CharacterCreationAgent(client.app.state.store, model=model)

    result = agent.process(CharacterDraft(), "米拉 人类战士", "zh-CN")

    response_payload = __import__("json").loads(model.calls[1][1].content)
    assert response_payload["locale"] == "zh-CN"
    assert response_payload["next_step"] == "background"
    assert response_payload["changed_fields"] == ["name", "race", "class_name"]
    assert response_payload["validation_errors"] == []
    assert result["assistant_message"] == (
        "角色概念已经记录。接下来请按照 27 点购点规则分配六项属性。"
    )
    assert result["metadata"]["responder"] == "llm"


def test_character_responder_falls_back_to_template_when_model_fails(client):
    model = SequencedCharacterModel(
        [
            '{"intent":"provide_info","name":"Mira","race":"Human","class_name":"Fighter"}',
            RuntimeError("response failed"),
        ]
    )
    agent = CharacterCreationAgent(client.app.state.store, model=model)

    result = agent.process(CharacterDraft(), "Mira Human Fighter", "en")

    assert "Current draft:" in result["assistant_message"]
    assert result["metadata"]["responder"] == "template"


def test_character_creation_fallback_extracts_chinese_name_race_class_and_background(client):
    agent = CharacterCreationAgent(client.app.state.store)

    result = agent.process(
        CharacterDraft(),
        "我想创建一名人类战士，名字叫验证者，背景是士兵。",
        "zh-CN",
    )

    assert result["draft"].name == "验证者"
    assert result["draft"].race == "Human"
    assert result["draft"].class_name == "Fighter"
    assert result["draft"].background == "Soldier"
    assert result["validation_errors"] == []


def test_character_creation_reports_next_step_and_missing_slots(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "en"}).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "My name is Mira, a Human Fighter with a Soldier background."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["next_step"] == "abilities"
    assert payload["metadata"]["changed_fields"] == ["name", "race", "class_name", "background"]
    assert payload["metadata"]["missing_slots"][0]["id"] == "abilities.base"
    assert payload["draft"]["current_step"] == "abilities"
    assert "review" not in payload["assistant_message"].lower()


def test_character_creation_next_question_uses_selected_chinese_locale(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "zh-CN"}).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "zh-CN",
            "content": "我想创建一名人类战士，名字叫验证者，背景是士兵。",
        },
    )

    assert response.status_code == 200
    message = response.json()["assistant_message"]
    assert "下一步" in message
    assert "属性" in message
    assert "How do you want" not in message
    assert "ability scores" not in message


def test_character_creation_chinese_summary_localizes_canonical_values(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "zh-CN"}).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "zh-CN",
            "content": "我想创建一名人类战士，名字叫验证者，背景是士兵。",
        },
    )

    message = response.json()["assistant_message"]
    assert "人类" in message
    assert "战士" in message
    assert "士兵" in message
    assert "Human Fighter" not in message
    assert "background Soldier" not in message


def test_character_creation_chinese_summary_treats_adventurer_as_unset_background(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "zh-CN"}).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "zh-CN",
            "content": "我想创建一名人类战士，名字叫验证者。",
        },
    )

    message = response.json()["assistant_message"]
    assert "背景未设置" in message
    assert "Adventurer" not in message
    assert "background Adventurer" not in message


def test_character_creation_ability_prompt_requires_manual_scores_with_explanation(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "zh-CN"}).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "zh-CN",
            "content": "我想创建一名人类战士，名字叫验证者，背景是士兵。",
        },
    )

    message = response.json()["assistant_message"]
    assert "手动输入六项属性" in message
    for ability in ("力量", "敏捷", "体质", "智力", "感知", "魅力"):
        assert ability in message
    assert "27 点" in message
    assert "8 到 15" in message
    assert "种族加值另行计算" in message
    assert "8=0" in message
    assert "15=9" in message
    assert "标准数组" not in message


def test_character_creation_english_ability_prompt_explains_point_budget(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "en"}).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "en",
            "content": "My name is Mira, a Human Fighter with a Soldier background.",
        },
    )

    message = response.json()["assistant_message"]
    assert "27 points" in message
    assert "between 8 and 15" in message
    assert "racial bonuses are applied separately" in message
    assert "8=0" in message
    assert "15=9" in message


def test_character_creation_accepts_ordered_manual_ability_scores(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "zh-CN"}).json()
    core = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "zh-CN",
            "content": "戴尔 人类战士",
        },
    ).json()
    client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": core["revision"],
            "operation": "background",
            "payload": {"background_id": "background.soldier"},
            "locale": "zh-CN",
        },
    )

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "zh-CN",
            "content": "15、15、15、8、8、8",
        },
    )

    payload = response.json()
    assert payload["validation_errors"] == []
    assert payload["draft"]["abilities"]["base"] == {
        "strength": 15,
        "dexterity": 15,
        "constitution": 15,
        "intelligence": 8,
        "wisdom": 8,
        "charisma": 8,
    }
    assert payload["draft"]["abilities"]["point_buy_spent"] == 27
    assert payload["metadata"]["next_step"] == "proficiencies"


def test_character_creation_rejects_manual_ability_scores_over_budget(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "zh-CN"}).json()
    core = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "zh-CN",
            "content": "戴尔 人类战士",
        },
    ).json()
    client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": core["revision"],
            "operation": "background",
            "payload": {"background_id": "background.soldier"},
            "locale": "zh-CN",
        },
    )

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={
            "locale": "zh-CN",
            "content": "15、15、15、15、15、15",
        },
    )

    payload = response.json()
    assert payload["metadata"]["next_step"] == "abilities"
    assert payload["validation_errors"]
    assert "54 点" in payload["assistant_message"]
    assert "27 点" in payload["assistant_message"]


def test_character_creation_name_update_preserves_existing_draft(client):
    session = client.post("/api/character-creation/sessions", json={"locale": "en"}).json()
    first = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "My name is Aria, an Elf Ranger with a Soldier background."},
    ).json()

    renamed = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "Change my name to Mira."},
    ).json()

    assert first["draft"]["race"] == "Elf"
    assert renamed["draft"]["name"] == "Mira"
    assert renamed["draft"]["race"] == "Elf"
    assert renamed["draft"]["class_name"] == "Ranger"
    assert renamed["draft"]["background"] == "Soldier"
    assert renamed["metadata"]["changed_fields"] == ["name"]
    assert renamed["metadata"]["next_step"] == "abilities"


def test_character_creation_race_update_invalidates_later_steps(client):
    agent = CharacterCreationAgent(client.app.state.store)
    draft = CharacterDraft(
        name="Aria",
        race="Human",
        class_name="Fighter",
        background="Soldier",
        current_step="review",
        completed_steps=["identity", "race", "class", "abilities", "background", "review"],
    )

    result = agent.process(draft, "Change my race to Elf.", "en")

    assert result["draft"].race == "Elf"
    assert result["draft"].name == "Aria"
    assert "race" not in result["draft"].invalid_steps
    assert "abilities" in result["draft"].invalid_steps
    assert "background" in result["draft"].invalid_steps
    assert result["metadata"]["changed_fields"] == ["race"]


def test_character_creation_fighter_does_not_require_level_one_spells(client):
    agent = CharacterCreationAgent(client.app.state.store)
    draft = CharacterDraft(
        name="Aria",
        race="Human",
        class_name="Fighter",
        background="Soldier",
        completed_steps=["identity", "race", "class", "abilities", "background"],
    )

    result = agent.process(draft, "continue", "en")

    slot_ids = [slot["id"] for slot in result["metadata"]["missing_slots"]]
    assert not any(slot_id.startswith("spells.") for slot_id in slot_ids)


def test_character_creation_wizard_requires_level_one_spell_selection(client):
    agent = CharacterCreationAgent(client.app.state.store)
    draft = CharacterDraft(
        name="Aria",
        race="Human",
        class_name="Wizard",
        background="Sage",
        completed_steps=["identity", "race", "class", "abilities", "background"],
    )

    result = agent.process(draft, "continue", "en")

    assert result["metadata"]["next_step"] == "spells"
    assert result["metadata"]["missing_slots"][0]["id"] == "spells.known"


def test_character_creation_chinese_complete_commits_once_when_review_ready(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "zh-CN"},
    ).json()
    draft = CharacterDraft(
        revision=4,
        name="戴尔",
        race="Human",
        class_name="Fighter",
        background="Soldier",
        current_step="review",
        completed_steps=[
            "identity",
            "class",
            "race",
            "background",
            "abilities",
            "proficiencies",
            "class_features",
            "optional_rules",
            "spells",
            "equipment",
            "adventure_connection",
        ],
    )
    draft.selections.race_id = "race.human"
    draft.selections.class_id = "class.fighter"
    draft.selections.background_id = "background.soldier"
    draft.abilities.base = {
        "strength": 15,
        "dexterity": 15,
        "constitution": 15,
        "intelligence": 8,
        "wisdom": 8,
        "charisma": 8,
    }
    draft.abilities.final = dict(draft.abilities.base)
    draft.abilities.point_buy_spent = 27
    draft.abilities.point_buy_remaining = 0
    draft.proficiencies["skills"] = [
        "skill.athletics",
        "skill.perception",
    ]
    draft.inventory = [
        {"item_id": "equipment.chain-mail", "quantity": 1},
        {"item_id": "equipment.longsword", "quantity": 1},
    ]
    draft.adventure_connection = {
        "motivation": "Protect the road.",
        "quest_hook": "Investigate the opening scene.",
    }
    with client.app.state.store.connect() as conn:
        conn.execute(
            """
            UPDATE character_creation_sessions
            SET draft_json = ?, revision = 4
            WHERE id = ?
            """,
            (encode_json(draft.model_dump()), session["id"]),
        )

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"locale": "zh-CN", "content": "完成"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["created_character"]["name"] == "戴尔"
    assert payload["metadata"]["committed"] is True
    assert len(CharacterService(client.app.state.store).list()) == 1


def test_character_creation_spell_help_keeps_current_step_and_draft(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "zh-CN"},
    ).json()
    before = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"locale": "zh-CN", "content": "戴尔 人类战士"},
    ).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"locale": "zh-CN", "content": "我不能学法术吗"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "draft"
    assert payload["revision"] == before["revision"]
    assert payload["metadata"]["next_step"] == "background"
    assert payload["created_character"] is None
    assert "1级纯战士没有职业施法能力" in payload["assistant_message"]
    assert payload["assistant_message"]
    assert CharacterService(client.app.state.store).list() == []


def test_character_creation_accepts_standalone_chinese_name(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "zh-CN"},
    ).json()

    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"locale": "zh-CN", "content": "戴尔"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["name"] == "戴尔"
    assert payload["revision"] == 1
    assert payload["metadata"]["next_step"] == "class"
    assert payload["assistant_message"]
