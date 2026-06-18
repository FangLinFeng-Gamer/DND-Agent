import json

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict, Field, ValidationError

from backend.src.agent.character_creation.models import (
    CharacterCreationTurnResult,
    StateGraphResult,
)
from backend.src.agent.character_creation.deterministic import (
    basic_draft_issues,
    changed_core_fields,
    invalidate_changed_dependencies,
)
from backend.src.agent.character_creation.workflow import CharacterCreationStateGraph
from backend.src.agent.character_creation.tools import (
    CharacterCreationToolRegistry,
    CharacterToolContext,
)
from backend.src.agent.character_creation.supervisor import (
    CharacterCreationReActAgent,
)
from backend.src.agent.llm.langchain_model import OpenAICompatibleChatModel
from backend.src.services.characters import CharacterService
from backend.src.schemas.character import CharacterOut
from backend.src.schemas.character_creation import CharacterDraft
from backend.src.schemas.llm import LLMModelRecord


def _state_graph_result(**overrides) -> StateGraphResult:
    values = {
        "success": True,
        "draft_revision": 8,
        "changed_fields": ["background"],
        "current_step": "background",
        "next_step": "review",
        "validation_errors": [],
        "validation_warnings": ["Review the selected language."],
        "created_character_id": None,
        "committed": False,
        "facts": ["Background changed to Noble."],
        "allowed_actions": ["confirm", "update", "ask_rules"],
        "draft": CharacterDraft(
            revision=8,
            current_step="background",
            background="Noble",
        ),
    }
    values.update(overrides)
    return StateGraphResult(**values)


def _character() -> CharacterOut:
    return CharacterOut(
        id=42,
        name="Dale",
        race="Human",
        class_name="Fighter",
        level=1,
        background="Noble",
        alignment="Neutral",
        hp_current=12,
        hp_max=12,
        armor_class=16,
        strength=15,
        dexterity=14,
        constitution=15,
        intelligence=10,
        wisdom=12,
        charisma=8,
        skills={"athletics": 4},
        inventory=["longsword"],
        spells=[],
        notes="",
    )


class ScriptedToolModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    responses: list[AIMessage]
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted_character_tool_model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(list(messages))
        if not self.responses:
            raise RuntimeError("No scripted response remains.")
        return ChatResult(
            generations=[ChatGeneration(message=self.responses.pop(0))]
        )


def test_deterministic_helpers_share_core_changes_validation_and_invalidation():
    before = CharacterDraft(
        name="Dale",
        race="Human",
        class_name="Fighter",
        background="Soldier",
        completed_steps=["abilities", "background", "review"],
    )
    after = before.model_copy(deep=True)
    after.race = "Elf"

    changed = changed_core_fields(before, after)
    invalidate_changed_dependencies(before, after, changed)
    issues = basic_draft_issues(
        CharacterDraft(name="Dale", race="Unknown", class_name="Fighter"),
        valid_races={"Human", "Elf"},
        valid_classes={"Fighter"},
        valid_backgrounds={"Soldier"},
    )

    assert changed == ["race"]
    assert {"abilities", "background", "review"} <= set(after.invalid_steps)
    assert "review" not in after.completed_steps
    assert [(issue.code, issue.value) for issue in issues] == [
        ("unsupported_race", "Unknown"),
    ]


def test_state_graph_result_serializes_exact_tool_fields_without_draft():
    result = _state_graph_result()

    content = json.loads(result.to_tool_content())

    assert content == {
        "success": True,
        "draft_revision": 8,
        "changed_fields": ["background"],
        "current_step": "background",
        "next_step": "review",
        "validation_errors": [],
        "validation_warnings": ["Review the selected language."],
        "created_character_id": None,
        "committed": False,
        "facts": ["Background changed to Noble."],
        "allowed_actions": ["confirm", "update", "ask_rules"],
    }
    assert "draft" not in content


def test_state_graph_result_rejects_committed_result_without_character_id():
    with pytest.raises(
        ValidationError,
        match="A committed result requires created_character_id",
    ):
        _state_graph_result(committed=True, created_character_id=None)


def test_state_graph_result_rejects_revision_different_from_draft():
    with pytest.raises(
        ValidationError,
        match="draft_revision must match draft.revision",
    ):
        _state_graph_result(draft_revision=9)


def test_state_graph_result_rejects_current_step_different_from_draft():
    with pytest.raises(
        ValidationError,
        match="current_step must match draft.current_step",
    ):
        _state_graph_result(current_step="review")


def test_state_graph_result_rejects_character_id_when_not_committed():
    with pytest.raises(
        ValidationError,
        match="created_character_id requires committed=true",
    ):
        _state_graph_result(created_character_id=42, committed=False)


def test_state_graph_result_rejects_unsuccessful_committed_result():
    with pytest.raises(
        ValidationError,
        match="A committed result requires success=true",
    ):
        _state_graph_result(
            success=False,
            committed=True,
            created_character_id=42,
        )


def test_state_graph_result_default_lists_are_not_shared():
    required = {
        "success": True,
        "draft_revision": 1,
        "current_step": "identity",
        "next_step": "race",
        "draft": CharacterDraft(revision=1),
    }
    first = StateGraphResult(**required)
    second = StateGraphResult(**required)

    first.changed_fields.append("name")
    first.validation_errors.append("invalid")
    first.validation_warnings.append("warning")
    first.facts.append("fact")
    first.allowed_actions.append("update")

    assert second.changed_fields == []
    assert second.validation_errors == []
    assert second.validation_warnings == []
    assert second.facts == []
    assert second.allowed_actions == []


def test_character_creation_turn_result_validates_authoritative_values():
    draft = CharacterDraft(revision=9, name="Dale")
    character = _character()

    result = CharacterCreationTurnResult.model_validate(
        {
            "assistant_text": "Character created.",
            "draft": draft.model_dump(),
            "created_character": character.model_dump(),
            "validation_errors": [],
            "diagnostics": {
                "agent_kind": "react",
                "tool_call_count": 3,
            },
        }
    )

    assert result.assistant_text == "Character created."
    assert result.draft == draft
    assert result.created_character == character
    assert result.validation_errors == []
    assert result.diagnostics == {
        "agent_kind": "react",
        "tool_call_count": 3,
    }


def test_character_creation_turn_result_rejects_invalid_created_character():
    with pytest.raises(ValidationError):
        CharacterCreationTurnResult.model_validate(
            {
                "assistant_text": "Character created.",
                "draft": CharacterDraft().model_dump(),
                "created_character": {"id": "not-an-integer"},
                "validation_errors": [],
                "diagnostics": {},
            }
        )


LEGAL_ABILITIES = {
    "strength": 15,
    "dexterity": 15,
    "constitution": 15,
    "intelligence": 8,
    "wisdom": 8,
    "charisma": 8,
}


def _workflow(client) -> CharacterCreationStateGraph:
    return CharacterCreationStateGraph(client.app.state.store)


def _tool_registry(
    client,
    draft: CharacterDraft | None = None,
    *,
    explicit_confirmation: bool = False,
) -> tuple[CharacterCreationToolRegistry, CharacterToolContext]:
    context = CharacterToolContext(
        session_id=91,
        locale="en",
        workflow=_workflow(client),
        draft=draft or CharacterDraft(),
        explicit_confirmation=explicit_confirmation,
    )
    return CharacterCreationToolRegistry(context), context


def test_character_tool_registry_exposes_only_controlled_tools(client):
    registry, _ = _tool_registry(client)

    assert {tool.name for tool in registry.tools()} == {
        "get_character_draft",
        "search_character_rules",
        "explain_character_option",
        "apply_character_changes",
        "validate_character_draft",
        "confirm_character_creation",
    }


def test_character_tool_schemas_do_not_expose_session_or_store(client):
    registry, _ = _tool_registry(client)
    schemas = {
        tool.name: tool.get_input_schema().model_json_schema()
        for tool in registry.tools()
    }

    serialized = json.dumps(schemas)
    assert "session_id" not in serialized
    assert "store" not in serialized
    assert set(schemas["apply_character_changes"]["required"]) == {
        "changes",
        "expected_revision",
    }
    assert schemas["validate_character_draft"]["required"] == [
        "expected_revision"
    ]
    assert schemas["confirm_character_creation"]["required"] == [
        "expected_revision"
    ]


def test_character_state_tools_return_state_graph_json_and_update_context(client):
    registry, context = _tool_registry(client)
    tools = {tool.name: tool for tool in registry.tools()}

    content = tools["apply_character_changes"].invoke(
        {
            "changes": {
                "name": "Dale",
                "race": "Human",
                "class_name": "Fighter",
            },
            "expected_revision": 0,
        }
    )
    payload = json.loads(content)

    assert payload["success"] is True
    assert payload["draft_revision"] == 1
    assert payload["next_step"] == "background"
    assert context.draft.name == "Dale"
    assert context.draft.revision == 1
    assert context.latest_result is not None
    assert context.tool_results[-1].draft == context.draft
    assert context.called_tools == ["apply_character_changes"]


def test_character_confirmation_tool_uses_context_permission_not_model_input(client):
    draft = _review_ready_draft()
    registry, context = _tool_registry(
        client,
        draft,
        explicit_confirmation=False,
    )
    tool = {
        item.name: item for item in registry.tools()
    }["confirm_character_creation"]

    payload = json.loads(
        tool.invoke({"expected_revision": draft.revision})
    )

    assert payload["committed"] is False
    assert "Explicit confirmation is required." in payload["validation_errors"]
    assert context.draft.current_step == "review"
    assert CharacterService(client.app.state.store).list() == []


def test_character_confirmation_tool_builds_stable_session_revision_key(client):
    draft = _review_ready_draft()
    registry, context = _tool_registry(
        client,
        draft,
        explicit_confirmation=True,
    )
    tool = {
        item.name: item for item in registry.tools()
    }["confirm_character_creation"]

    first = json.loads(tool.invoke({"expected_revision": draft.revision}))

    assert first["committed"] is True
    assert context.draft.current_step == "completed"
    assert len(CharacterService(client.app.state.store).list()) == 1


def test_character_tools_stop_after_six_calls_without_running_workflow(client):
    registry, context = _tool_registry(client)
    get_draft = {
        item.name: item for item in registry.tools()
    }["get_character_draft"]

    for _ in range(6):
        assert json.loads(get_draft.invoke({}))["success"] is True
    limited = json.loads(get_draft.invoke({}))

    assert limited["success"] is False
    assert "tool call limit" in limited["validation_errors"][0].lower()
    assert context.tool_call_count == 7
    assert len(context.tool_results) == 7


def test_character_rule_tools_are_read_only_and_include_source(client):
    registry, context = _tool_registry(
        client,
        CharacterDraft(
            name="Dale",
            race="Human",
            class_name="Fighter",
        ),
    )
    tools = {tool.name: tool for tool in registry.tools()}

    search = json.loads(
        tools["search_character_rules"].invoke(
            {"query": "Fighter", "category": "class"}
        )
    )
    explanation = json.loads(
        tools["explain_character_option"].invoke(
            {"topic": "spellcasting"}
        )
    )

    assert search["results"]
    assert search["source"] == "PHB"
    assert explanation["facts"]
    assert explanation["source"] == "PHB"
    assert context.draft.revision == 0


def test_react_supervisor_observes_state_graph_tool_message(client):
    model = ScriptedToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_character_draft",
                        "args": {},
                        "id": "read-draft",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "apply_character_changes",
                        "args": {
                            "changes": {
                                "name": "Dale",
                                "race": "Human",
                                "class_name": "Fighter",
                            },
                            "expected_revision": 0,
                        },
                        "id": "apply-draft",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content=(
                    "The character concept is recorded. Enter the six ability "
                    "scores using the 27-point budget."
                )
            ),
        ]
    )
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=51,
        draft=CharacterDraft(),
        content="Dale Human Fighter",
        locale="en",
        recent_messages=[],
    )

    second_call_tools = [
        message for message in model.calls[1]
        if isinstance(message, ToolMessage)
    ]
    final_call_tools = [
        message for message in model.calls[2]
        if isinstance(message, ToolMessage)
    ]
    assert json.loads(second_call_tools[-1].content)["current_step"] == "identity"
    assert json.loads(final_call_tools[-1].content)["next_step"] == "background"
    assert result.draft.name == "Dale"
    assert result.draft.revision == 1
    assert result.diagnostics["agent_kind"] == "react"
    assert result.diagnostics["tool_call_count"] == 2


def test_react_supervisor_replaces_false_created_claim(client):
    model = ScriptedToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_character_draft",
                        "args": {},
                        "id": "read-draft",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Character created successfully."),
        ]
    )
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=52,
        draft=CharacterDraft(
            name="Dale",
            race="Human",
            class_name="Fighter",
            current_step="abilities",
        ),
        content="What is next?",
        locale="en",
    )

    assert result.created_character is None
    assert "created" not in result.assistant_text.lower()
    assert result.diagnostics["response_guard"] == "replaced"


@pytest.mark.parametrize(
    "false_claim",
    [
        "角色已保存。",
        "角色已定型。",
        "角色创建完成。",
        "The character has been finalized.",
    ],
)
def test_react_supervisor_rejects_other_uncommitted_claims(
    client,
    false_claim,
):
    model = ScriptedToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_character_draft",
                        "args": {},
                        "id": "read-draft",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content=false_claim),
        ]
    )
    locale = "zh-CN" if "角色" in false_claim else "en"
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=57,
        draft=CharacterDraft(
            name="Dale",
            race="Human",
            class_name="Fighter",
            current_step="abilities",
        ),
        content="下一步" if locale == "zh-CN" else "What is next?",
        locale=locale,
    )

    assert false_claim not in result.assistant_text
    assert result.diagnostics["response_guard"] == "replaced"


def test_react_supervisor_revision_conflict_can_be_observed_then_reread(client):
    model = ScriptedToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "apply_character_changes",
                        "args": {
                            "changes": {"name": "Mira"},
                            "expected_revision": 2,
                        },
                        "id": "stale-update",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_character_draft",
                        "args": {},
                        "id": "reread",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="The draft was refreshed. What would you like to change?"),
        ]
    )
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=53,
        draft=CharacterDraft(revision=3, name="Dale"),
        content="Rename the character to Mira.",
        locale="en",
    )

    conflict = json.loads(
        next(
            message.content
            for message in model.calls[1]
            if isinstance(message, ToolMessage)
        )
    )
    refreshed = json.loads(
        [
            message.content
            for message in model.calls[2]
            if isinstance(message, ToolMessage)
        ][-1]
    )
    assert conflict["success"] is False
    assert conflict["allowed_actions"] == ["get_draft"]
    assert refreshed["draft_revision"] == 3
    assert result.draft.name == "Dale"


def test_react_supervisor_preserves_blocking_validation_error(client):
    model = ScriptedToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "apply_character_changes",
                        "args": {
                            "changes": {"name": "Mira"},
                            "expected_revision": 2,
                        },
                        "id": "stale-update",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Try again."),
        ]
    )
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=56,
        draft=CharacterDraft(revision=3, name="Dale"),
        content="Rename the character to Mira.",
        locale="en",
    )

    assert "Expected revision 2" in result.assistant_text
    assert result.diagnostics["response_guard"] == "replaced"


def test_react_supervisor_without_model_uses_deterministic_fallback(client):
    agent = CharacterCreationReActAgent(client.app.state.store, model=None)

    result = agent.process(
        session_id=54,
        draft=CharacterDraft(),
        content="Dale Human Fighter",
        locale="en",
    )

    assert result.draft.name == "Dale"
    assert result.draft.race == "Human"
    assert result.draft.class_name == "Fighter"
    assert result.draft.current_step == "background"
    assert result.created_character is None
    assert result.diagnostics["agent_kind"] == "deterministic_fallback"
    assert "background" in result.assistant_text.lower()


def test_react_supervisor_falls_back_when_model_does_not_call_tool(client):
    model = ScriptedToolModel(
        responses=[
            AIMessage(content="请告诉我角色名称。"),
        ]
    )
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=58,
        draft=CharacterDraft(),
        content="戴尔",
        locale="zh-CN",
    )

    assert result.draft.name == "戴尔"
    assert result.draft.revision == 1
    assert result.diagnostics["next_step"] == "class"
    assert result.diagnostics["slot_extraction"] == "deterministic_after_model"


def test_react_supervisor_falls_back_when_model_request_fails(client):
    model = ScriptedToolModel(responses=[])
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=59,
        draft=CharacterDraft(),
        content="戴尔",
        locale="zh-CN",
    )

    assert result.draft.name == "戴尔"
    assert result.diagnostics["agent_kind"] == "react_fallback"
    assert result.diagnostics["slot_extraction"] == "deterministic_after_model"
    assert result.diagnostics["failure"] == "RuntimeError"


def test_react_supervisor_falls_back_after_read_only_tool_call(client):
    model = ScriptedToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_character_draft",
                        "args": {},
                        "id": "read-draft",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="请告诉我角色名称。"),
        ]
    )
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=60,
        draft=CharacterDraft(),
        content="戴尔",
        locale="zh-CN",
    )

    assert result.draft.name == "戴尔"
    assert result.diagnostics["slot_extraction"] == "deterministic_after_model"
    assert result.diagnostics["called_tools"] == ["get_character_draft"]


def test_react_supervisor_reports_openai_compatible_model_name(client):
    record = LLMModelRecord(
        id=2,
        name="DeepSeek",
        provider="openai_compatible",
        base_url="https://example.invalid/chat/completions",
        api_key_masked="****",
        api_key="secret",
        model_name="deepseek-v4-flash",
        temperature=0.7,
        max_context_tokens=4096,
        is_active=True,
        created_at="2026-06-11 00:00:00",
        updated_at="2026-06-11 00:00:00",
    )
    model = OpenAICompatibleChatModel(
        model_record=record,
        client=object(),
    )
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    assert agent._model_name() == "deepseek-v4-flash"


def test_react_supervisor_uses_selected_chinese_locale_for_guarded_reply(client):
    model = ScriptedToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_character_draft",
                        "args": {},
                        "id": "read-draft",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Character created successfully."),
        ]
    )
    agent = CharacterCreationReActAgent(
        client.app.state.store,
        model=model,
    )

    result = agent.process(
        session_id=55,
        draft=CharacterDraft(
            name="戴尔",
            race="Human",
            class_name="Fighter",
            current_step="abilities",
        ),
        content="下一步",
        locale="zh-CN",
    )

    assert result.assistant_text
    assert "Character created" not in result.assistant_text


def _review_ready_draft(revision: int = 4) -> CharacterDraft:
    draft = CharacterDraft(
        revision=revision,
        name="Dale",
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
    draft.abilities.base = dict(LEGAL_ABILITIES)
    draft.abilities.final = dict(LEGAL_ABILITIES)
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
    return draft


def test_character_workflow_apply_updates_core_fields_and_revision(client):
    result = _workflow(client).apply_changes(
        draft=CharacterDraft(revision=3),
        expected_revision=3,
        changes={
            "name": "Dale",
            "race": "Human",
            "class_name": "Fighter",
            "background": "Soldier",
            "alignment": "Neutral Good",
            "notes": "Keeps a field journal.",
            "abilities": LEGAL_ABILITIES,
        },
        locale="en",
    )

    assert result.success is True
    assert result.changed_fields == [
        "name",
        "race",
        "class_name",
        "background",
        "alignment",
        "notes",
        "abilities",
    ]
    assert result.draft_revision == 4
    assert result.draft.name == "Dale"
    assert result.draft.race == "Human"
    assert result.draft.class_name == "Fighter"
    assert result.draft.background == "Soldier"
    assert result.draft.abilities.base == LEGAL_ABILITIES
    assert result.next_step == "proficiencies"
    assert result.committed is False


def test_character_workflow_revision_conflict_preserves_draft(client):
    draft = CharacterDraft(revision=5, name="Dale")

    result = _workflow(client).apply_changes(
        draft=draft,
        expected_revision=4,
        changes={"name": "Mira"},
        locale="en",
    )

    assert result.success is False
    assert result.allowed_actions == ["get_draft"]
    assert result.draft == draft
    assert result.draft_revision == 5


def test_character_workflow_partial_apply_succeeds_while_reporting_missing_fields(client):
    result = _workflow(client).apply_changes(
        draft=CharacterDraft(revision=0),
        expected_revision=0,
        changes={"name": "Dale"},
        locale="en",
    )

    assert result.success is True
    assert result.draft.name == "Dale"
    assert result.draft_revision == 1
    assert result.next_step == "class"
    assert "Race is required." in result.validation_errors
    assert "Class is required." in result.validation_errors


def test_character_workflow_invalid_point_buy_preserves_valid_draft(client):
    draft = CharacterDraft(
        revision=2,
        name="Dale",
        race="Human",
        class_name="Fighter",
        background="Soldier",
        current_step="abilities",
    )
    before = draft.model_copy(deep=True)

    result = _workflow(client).apply_changes(
        draft=draft,
        expected_revision=2,
        changes={"abilities": {ability: 15 for ability in LEGAL_ABILITIES}},
        locale="en",
    )

    assert result.success is False
    assert result.validation_errors == ["Point-buy cost 54 exceeds 27."]
    assert result.draft == before
    assert result.draft_revision == 2
    assert result.next_step == "abilities"


def test_character_workflow_abilities_resolve_legacy_race_name(client):
    draft = CharacterDraft(
        revision=2,
        name="Dale",
        race="Human",
        class_name="Fighter",
        current_step="abilities",
    )

    result = _workflow(client).apply_changes(
        draft=draft,
        expected_revision=2,
        changes={"abilities": LEGAL_ABILITIES},
        locale="en",
    )

    assert result.success is True
    assert result.draft.selections.race_id == "race.human"
    assert result.draft.abilities.racial_bonuses == {
        ability: 1 for ability in LEGAL_ABILITIES
    }
    assert result.draft.abilities.final["strength"] == 16


@pytest.mark.parametrize(
    ("field", "value", "expected_invalid"),
    [
        ("race", "Elf", {"abilities", "background", "review"}),
        ("class_name", "Wizard", {"abilities", "spells", "review"}),
        ("background", "Noble", {"proficiencies", "equipment", "review"}),
    ],
)
def test_character_workflow_dependency_changes_invalidate_later_steps(
    client,
    field,
    value,
    expected_invalid,
):
    draft = _review_ready_draft()
    draft.completed_steps.extend(
        [
            "proficiencies",
            "class_features",
            "optional_rules",
            "spells",
            "equipment",
            "adventure_connection",
            "review",
        ]
    )

    result = _workflow(client).apply_changes(
        draft=draft,
        expected_revision=draft.revision,
        changes={field: value},
        locale="en",
    )

    assert result.success is True
    assert expected_invalid <= set(result.draft.invalid_steps)
    assert "review" not in result.draft.completed_steps


def test_character_workflow_validate_is_read_only_and_never_commits(client):
    draft = _review_ready_draft()
    service = CharacterService(client.app.state.store)

    result = _workflow(client).validate(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
    )

    assert result.success is True
    assert result.next_step == "review"
    assert result.draft == draft
    assert result.draft_revision == draft.revision
    assert result.committed is False
    assert service.list() == []


def test_character_workflow_confirm_requires_explicit_permission(client):
    draft = _review_ready_draft()
    service = CharacterService(client.app.state.store)

    result = _workflow(client).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=False,
        commit_key="session-39:revision-4",
    )

    assert result.success is False
    assert result.validation_errors == ["Explicit confirmation is required."]
    assert result.committed is False
    assert service.list() == []


def test_character_workflow_confirm_requires_review_ready_draft(client):
    draft = CharacterDraft(
        revision=1,
        name="Dale",
        race="Human",
        class_name="Fighter",
        current_step="abilities",
    )
    service = CharacterService(client.app.state.store)

    result = _workflow(client).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
    )

    assert result.success is False
    assert result.committed is False
    assert result.created_character_id is None
    assert service.list() == []


def test_character_workflow_confirm_success_creates_only_once(client):
    workflow = _workflow(client)
    service = CharacterService(client.app.state.store)
    draft = _review_ready_draft()

    created = workflow.confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-40:revision-4",
    )
    repeated = workflow.confirm(
        draft=created.draft,
        expected_revision=created.draft_revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-40:revision-5",
    )

    assert created.success is True
    assert created.committed is True
    assert created.created_character_id is not None
    assert created.current_step == "completed"
    assert repeated.success is False
    assert repeated.committed is False
    assert len(service.list()) == 1


@pytest.mark.parametrize("commit_key", [None, "   "])
def test_character_workflow_confirm_requires_stable_commit_key(
    client,
    commit_key,
):
    service = CharacterService(client.app.state.store)
    draft = _review_ready_draft()

    result = _workflow(client).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key=commit_key,
    )

    assert result.success is False
    assert result.committed is False
    assert result.created_character_id is None
    assert result.validation_errors == [
        "A non-empty commit_key is required for character confirmation."
    ]
    assert result.allowed_actions == ["confirm", "get_draft"]
    assert service.list() == []


def test_character_workflow_confirm_same_request_key_is_idempotent(client):
    workflow = _workflow(client)
    service = CharacterService(client.app.state.store)
    draft = _review_ready_draft()

    first = workflow.confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-41:revision-4",
    )
    retried = workflow.confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-41:revision-4",
    )

    assert first.success is True
    assert retried.success is True
    assert first.committed is True
    assert retried.committed is True
    assert retried.created_character_id == first.created_character_id
    assert len(service.list()) == 1


def test_character_workflow_confirm_persists_authoritative_draft_sheet(client):
    draft = _review_ready_draft(revision=12)
    draft.notes = "Carries the oath of the Ash Guard."
    draft.derived.hp_max = 17
    draft.derived.armor_class = 18
    draft.derived.skills = {
        "skill.athletics": 5,
        "skill.perception": 2,
    }
    draft.proficiencies["skills"] = [
        "skill.athletics",
        "skill.perception",
    ]
    draft.inventory = [
        {"item_id": "equipment.chain-mail", "quantity": 1},
        {"item_id": "equipment.longsword", "quantity": 2},
    ]
    draft.selections.spell_ids = ["spell.fire-bolt", "spell.mage-hand"]
    service = CharacterService(client.app.state.store)

    result = _workflow(client).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-45:revision-12",
    )

    persisted = service.get(result.created_character_id)
    assert persisted.strength == 16
    assert persisted.dexterity == 16
    assert persisted.constitution == 16
    assert persisted.intelligence == 9
    assert persisted.wisdom == 9
    assert persisted.charisma == 9
    assert persisted.hp_current == 17
    assert persisted.hp_max == 17
    assert persisted.armor_class == 18
    assert persisted.skills == draft.derived.skills
    assert persisted.proficiencies == draft.proficiencies
    assert persisted.inventory == draft.inventory
    assert persisted.spells == draft.selections.spell_ids
    assert persisted.notes == draft.notes


def test_character_workflow_rejects_commit_key_reused_for_different_payload(client):
    workflow = _workflow(client)
    service = CharacterService(client.app.state.store)
    original = _review_ready_draft(revision=20)
    changed = original.model_copy(deep=True)
    changed.revision = 21
    changed.name = "Mira"

    first = workflow.confirm(
        draft=original,
        expected_revision=original.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-46:confirm",
    )
    conflicting = workflow.confirm(
        draft=changed,
        expected_revision=changed.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-46:confirm",
    )

    assert first.success is True
    assert conflicting.success is False
    assert conflicting.committed is False
    assert conflicting.created_character_id is None
    assert conflicting.current_step == "review"
    assert conflicting.draft_revision == 21
    assert conflicting.validation_errors == [
        "commit_key already refers to a different character payload."
    ]
    assert conflicting.allowed_actions == ["get_draft", "confirm"]
    assert [character.name for character in service.list()] == ["Dale"]


def test_character_workflow_deleted_character_releases_commit_key(client):
    workflow = _workflow(client)
    service = CharacterService(client.app.state.store)
    draft = _review_ready_draft(revision=30)

    first = workflow.confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-47:confirm",
    )
    service.delete(first.created_character_id)
    recreated = CharacterCreationStateGraph(client.app.state.store).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-47:confirm",
    )

    assert recreated.success is True
    assert recreated.committed is True
    assert recreated.created_character_id != first.created_character_id
    assert len(service.list()) == 1


def test_character_workflow_confirm_key_is_idempotent_across_instances(client):
    store = client.app.state.store
    service = CharacterService(store)
    draft = _review_ready_draft()

    first = CharacterCreationStateGraph(store).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-42:revision-4",
    )
    retried = CharacterCreationStateGraph(store).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-42:revision-4",
    )

    assert retried.created_character_id == first.created_character_id
    assert len(service.list()) == 1


def test_character_workflow_confirm_revalidates_forged_point_buy(client):
    draft = _review_ready_draft()
    illegal = {ability: 15 for ability in LEGAL_ABILITIES}
    draft.abilities.base = illegal
    draft.abilities.final = illegal
    draft.abilities.point_buy_spent = 27
    draft.abilities.point_buy_remaining = 0
    service = CharacterService(client.app.state.store)

    result = _workflow(client).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-43:revision-4",
    )

    assert result.success is False
    assert result.committed is False
    assert result.created_character_id is None
    assert "Point-buy cost 54 exceeds 27." in result.validation_errors
    assert service.list() == []


def test_character_workflow_confirm_localizes_invalid_point_buy(client):
    draft = _review_ready_draft()
    illegal = {ability: 15 for ability in LEGAL_ABILITIES}
    draft.abilities.base = illegal
    draft.abilities.final = illegal

    result = _workflow(client).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="zh-CN",
        explicit_confirmation=True,
        commit_key="session-zh-invalid:revision-4",
    )

    assert result.success is False
    assert "54 点" in result.validation_errors[0]
    assert "27 点" in result.validation_errors[0]


def test_character_workflow_confirm_requires_current_review_step(client):
    draft = _review_ready_draft()
    draft.current_step = "abilities"
    service = CharacterService(client.app.state.store)

    result = _workflow(client).confirm(
        draft=draft,
        expected_revision=draft.revision,
        locale="en",
        explicit_confirmation=True,
        commit_key="session-44:revision-4",
    )

    assert result.success is False
    assert result.committed is False
    assert result.created_character_id is None
    assert "Character draft must be on the review step." in result.validation_errors
    assert service.list() == []
