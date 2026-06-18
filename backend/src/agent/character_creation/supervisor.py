from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from backend.src.agent.character_creation.graph import CharacterCreationAgent
from backend.src.agent.character_creation.models import (
    CharacterCreationTurnResult,
    StateGraphResult,
)
from backend.src.agent.character_creation.tools import (
    CharacterCreationToolRegistry,
    CharacterToolContext,
    explain_character_option_payload,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.character_creation.workflow import CharacterCreationStateGraph
from backend.src.agent.character_creation.slots import missing_required_slots
from backend.src.agent.dm.react import build_react_agent
from backend.src.agent.dm.schemas import AgentKind
from backend.src.agent.llm.langchain_model import OpenAICompatibleChatModel
from backend.src.agent.locale import language_instruction, normalize_locale
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character import CharacterOut
from backend.src.schemas.character_creation import CharacterDraft
from backend.src.services.characters import CharacterService


class CharacterCreationReActAgent:
    agent_kind = AgentKind.REACT

    def __init__(
        self,
        store: SQLiteStore,
        model: BaseChatModel | None = None,
    ):
        self.store = store
        self.workflow = CharacterCreationStateGraph(store)
        self.characters = CharacterService(store)
        self.rules = PHBRuleRepository.load_builtin()
        self.legacy = CharacterCreationAgent(store)
        if isinstance(model, OpenAICompatibleChatModel):
            self.model = model.model_copy(update={"json_mode": False})
        else:
            self.model = model

    def process(
        self,
        *,
        session_id: int,
        draft: CharacterDraft,
        content: str,
        locale: str = "en",
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> CharacterCreationTurnResult:
        normalized_locale = normalize_locale(locale)
        explicit_confirmation = self._is_explicit_confirmation(content)
        if explicit_confirmation:
            return self._fallback_process(
                session_id=session_id,
                draft=draft,
                content=content,
                locale=normalized_locale,
                recent_messages=recent_messages or [],
                explicit_confirmation=True,
                agent_kind="deterministic_confirmation",
                slot_extraction="explicit_confirmation",
                model_name=self._model_name(),
            )
        if self.model is None:
            return self._fallback_process(
                session_id=session_id,
                draft=draft,
                content=content,
                locale=normalized_locale,
                recent_messages=recent_messages or [],
                explicit_confirmation=explicit_confirmation,
            )

        context = CharacterToolContext(
            session_id=session_id,
            locale=normalized_locale,
            workflow=self.workflow,
            draft=draft,
            explicit_confirmation=explicit_confirmation,
        )
        registry = CharacterCreationToolRegistry(context)
        tools = registry.tools()
        raw_text = ""
        responder = "llm"
        failure: str | None = None
        try:
            agent = build_react_agent(
                self.model,
                tools,
                self._system_prompt(normalized_locale),
                name="character_creation_supervisor",
            )
            result = agent.invoke(
                {
                    "messages": [
                        *self._history_messages(recent_messages or []),
                        {
                            "role": "user",
                            "content": content,
                        },
                    ]
                },
                config={"recursion_limit": 16},
            )
            raw_text = str(result["messages"][-1].content).strip()
            state_changed = any(
                item.changed_fields or item.committed
                for item in context.tool_results
            )
            deterministic_changes = self._fallback_changes(draft, content)
            needs_deterministic_update = (
                bool(deterministic_changes) and not state_changed
            )
            needs_deterministic_confirmation = (
                explicit_confirmation
                and not any(item.committed for item in context.tool_results)
            )
            if (
                context.tool_call_count == 0
                or needs_deterministic_update
                or needs_deterministic_confirmation
            ):
                return self._fallback_process(
                    session_id=session_id,
                    draft=draft,
                    content=content,
                    locale=normalized_locale,
                    recent_messages=recent_messages or [],
                    explicit_confirmation=explicit_confirmation,
                    agent_kind="react_fallback",
                    slot_extraction="deterministic_after_model",
                    model_name=self._model_name(),
                    tool_call_count=context.tool_call_count,
                    called_tools=context.called_tools,
                )
        except Exception as exc:
            return self._fallback_process(
                session_id=session_id,
                draft=draft,
                content=content,
                locale=normalized_locale,
                recent_messages=recent_messages or [],
                explicit_confirmation=explicit_confirmation,
                agent_kind="react_fallback",
                slot_extraction="deterministic_after_model",
                model_name=self._model_name(),
                tool_call_count=context.tool_call_count,
                called_tools=context.called_tools,
                failure=type(exc).__name__,
            )

        authoritative = context.latest_result or self.workflow.read(
            draft=context.draft,
            expected_revision=context.draft.revision,
            locale=normalized_locale,
        )
        fallback_text = self._template_response(authoritative, normalized_locale)
        assistant_text, guard = self._guard_response(
            raw_text,
            fallback_text,
            authoritative,
            normalized_locale,
        )
        if assistant_text == fallback_text:
            responder = "template"
        created_character = self._created_character(authoritative)
        diagnostics = {
            "agent_kind": "react",
            "tool_names": [tool.name for tool in tools],
            "tool_call_count": context.tool_call_count,
            "called_tools": context.called_tools,
            "state_graph_results": [
                item.model_dump(mode="json", exclude={"draft"})
                for item in context.tool_results
            ],
            "responder": responder,
            "model_name": self._model_name(),
            "next_step": authoritative.next_step,
            "changed_fields": authoritative.changed_fields,
            "missing_slots": self._missing_slots(authoritative),
            "committed": authoritative.committed,
            "response_guard": guard,
            "slot_extraction": (
                "react_tool_call"
                if any(item.changed_fields for item in context.tool_results)
                else "none"
            ),
        }
        if failure:
            diagnostics["failure"] = failure
        return CharacterCreationTurnResult(
            assistant_text=assistant_text,
            draft=authoritative.draft,
            created_character=created_character,
            validation_errors=authoritative.validation_errors,
            diagnostics=diagnostics,
        )

    def _fallback_process(
        self,
        *,
        session_id: int,
        draft: CharacterDraft,
        content: str,
        locale: str,
        recent_messages: list[dict[str, Any]],
        explicit_confirmation: bool,
        agent_kind: str = "deterministic_fallback",
        slot_extraction: str = "deterministic_fallback",
        model_name: str | None = None,
        tool_call_count: int = 0,
        called_tools: list[str] | None = None,
        failure: str | None = None,
    ) -> CharacterCreationTurnResult:
        help_request = self._is_help_request(content)
        if explicit_confirmation:
            result = self.workflow.confirm(
                draft=draft,
                expected_revision=draft.revision,
                locale=locale,
                explicit_confirmation=True,
                commit_key=(
                    f"character-session:{session_id}:revision:{draft.revision}"
                ),
            )
        else:
            changes = self._fallback_changes(draft, content)
            if changes:
                result = self.workflow.apply_changes(
                    draft=draft,
                    expected_revision=draft.revision,
                    changes=changes,
                    locale=locale,
                )
            else:
                result = self.workflow.read(
                    draft=draft,
                    expected_revision=draft.revision,
                    locale=locale,
                )
        assistant_text = self._template_response(result, locale)
        if help_request and not explicit_confirmation:
            explanation = explain_character_option_payload(
                draft=result.draft,
                topic=content,
                locale=locale,
                repository=self.rules,
            )
            assistant_text = (
                " ".join(explanation["facts"])
                + "\n\n"
                + assistant_text
            )
        diagnostics = {
            "agent_kind": agent_kind,
            "tool_names": [],
            "tool_call_count": tool_call_count,
            "called_tools": called_tools or [],
            "state_graph_results": [
                result.model_dump(mode="json", exclude={"draft"})
            ],
            "responder": "template",
            "model_name": model_name,
            "next_step": result.next_step,
            "changed_fields": result.changed_fields,
            "missing_slots": self._missing_slots(result),
            "committed": result.committed,
            "response_guard": "template",
            "history_count": len(recent_messages[-12:]),
            "slot_extraction": slot_extraction,
        }
        if failure:
            diagnostics["failure"] = failure
        return CharacterCreationTurnResult(
            assistant_text=assistant_text,
            draft=result.draft,
            created_character=self._created_character(result),
            validation_errors=result.validation_errors,
            diagnostics=diagnostics,
        )

    def _fallback_changes(
        self,
        draft: CharacterDraft,
        content: str,
    ) -> dict[str, Any]:
        if self._is_help_request(content):
            return {}
        ordered = self.legacy.extractor.extract_ordered_abilities(content)
        if draft.current_step == "abilities" and ordered is not None:
            return {"abilities": ordered}
        candidate = draft.model_copy(deep=True)
        self.legacy._fallback_extract(content, candidate)
        changes: dict[str, Any] = {}
        for field in (
            "name",
            "race",
            "class_name",
            "background",
            "alignment",
            "notes",
        ):
            if getattr(candidate, field) != getattr(draft, field):
                changes[field] = getattr(candidate, field)
        if changes:
            return changes
        standalone_name = self._standalone_name(draft, content)
        if standalone_name:
            return {"name": standalone_name}
        return changes

    def _standalone_name(
        self,
        draft: CharacterDraft,
        content: str,
    ) -> str | None:
        value = content.strip()
        if draft.name or draft.current_step != "identity" or not value:
            return None
        if len(value) > 40 or not all(
            character.isalpha()
            or character.isspace()
            or character in {"-", "'", "’"}
            for character in value
        ):
            return None
        normalized = value.casefold()
        reserved_names = {
            name.casefold()
            for record in self.rules.list()
            if record.rule_type in {"race", "subrace", "class", "background"}
            for name in (
                record.id,
                record.name.en,
                record.name.zh_cn,
            )
        }
        if normalized in reserved_names:
            return None
        return value

    def _system_prompt(self, locale: str) -> str:
        return (
            "You are the outer ReAct supervisor for DND 5e character creation. "
            "Plan and aggregate through the supplied tools only. Never write the "
            "database or invent draft changes. Read the latest ToolMessage after every "
            "stateful tool call and treat its StateGraphResult as authoritative. Use "
            "expected_revision from the latest result for mutations. On a revision "
            "conflict, call get_character_draft before another mutation. Ask exactly "
            "one next-step question. A rules/help question must not confirm or change "
            "the draft unless the player explicitly supplied a change. Never say the "
            "character is created, saved, finalized, or complete unless committed=true "
            "and created_character_id is present in the latest ToolMessage. Preserve "
            "all validation facts and numeric rules. Stop after at most six tool calls. "
            f"{language_instruction(locale)}"
        )

    def _history_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        for message in messages[-12:]:
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
            if role in {"user", "assistant"} and content:
                history.append({"role": role, "content": content})
        return history

    def _guard_response(
        self,
        text: str,
        fallback: str,
        result: StateGraphResult,
        locale: str,
    ) -> tuple[str, str]:
        if result.committed:
            return fallback, "committed_template"
        if not text:
            return fallback, "replaced"
        normalized = text.casefold()
        false_commit_claims = (
            "character created",
            "created successfully",
            "character saved",
            "creation complete",
            "finalized",
            "角色已创建",
            "创建成功",
            "已保存角色",
            "角色已保存",
            "创建完成",
            "已经定型",
            "角色已定型",
        )
        if not result.committed and any(
            claim in normalized for claim in false_commit_claims
        ):
            return fallback, "replaced"
        if (
            not result.success
            and result.validation_errors
            and any(error not in text for error in result.validation_errors)
        ):
            return fallback, "replaced"
        if locale == "zh-CN" and not self._contains_chinese(text):
            return fallback, "replaced"
        if locale == "en" and self._contains_chinese(text):
            return fallback, "replaced"
        return text, "accepted"

    def _template_response(
        self,
        result: StateGraphResult,
        locale: str,
    ) -> str:
        if result.committed:
            summary = self.legacy._draft_summary(result.draft, locale)
            return (
                f"角色已创建：{summary}。"
                if locale == "zh-CN"
                else f"Character created: {summary}."
            )
        if not result.success and result.validation_errors:
            return " ".join(result.validation_errors)
        draft = result.draft
        if locale == "zh-CN":
            summary = self.legacy._draft_summary(draft, locale)
            return (
                f"当前草稿：{summary}\n\n"
                f"下一步：{self._next_question(result.next_step, locale)}"
            )
        summary = self.legacy._draft_summary(draft, locale)
        return (
            f"Current draft: {summary}\n\n"
            f"Next: {self._next_question(result.next_step, locale)}"
        )

    def _next_question(self, next_step: str, locale: str) -> str:
        if next_step == "abilities":
            if locale == "zh-CN":
                return (
                    "请手动输入六项属性值：力量、敏捷、体质、智力、感知、魅力。"
                    "你最多可以使用 27 点，每项基础属性必须在 8 到 15 之间，"
                    "种族加值另行计算。购点花费：8=0、9=1、10=2、11=3、"
                    "12=4、13=5、14=7、15=9。"
                )
            return (
                "Enter six ability scores manually: Strength, Dexterity, "
                "Constitution, Intelligence, Wisdom, and Charisma. You may spend "
                "up to 27 points; each base score must be between 8 and 15, and "
                "racial bonuses are applied separately. Costs: 8=0, 9=1, 10=2, "
                "11=3, 12=4, 13=5, 14=7, 15=9."
            )
        questions = {
            "zh-CN": {
                "identity": "你的角色叫什么名字？",
                "race": "你想选择哪个种族？",
                "class": "你想选择哪个职业？",
                "background": "你想选择哪个背景？",
                "spells": "请选择这个职业在 1 级需要的法术。",
                "review": "请检查角色卡，然后回复“完成”进行确认。",
                "completed": "角色创建已经完成。",
            },
            "en": {
                "identity": "What is your character's name?",
                "race": "Which race do you want to play?",
                "class": "Which class do you want to play?",
                "background": "Which background do you want?",
                "spells": "Choose the level-one spells required by this class.",
                "review": "Review the character sheet, then reply 'complete' to confirm.",
                "completed": "Character creation is complete.",
            },
        }
        return questions[locale].get(
            next_step,
            (
                "请提供下一项角色信息。"
                if locale == "zh-CN"
                else "Provide the next character choice."
            ),
        )

    def _created_character(
        self,
        result: StateGraphResult,
    ) -> CharacterOut | None:
        if not result.committed or result.created_character_id is None:
            return None
        return self.characters.get(result.created_character_id)

    def _missing_slots(
        self,
        result: StateGraphResult,
    ) -> list[dict[str, Any]]:
        return [
            slot.model_dump(mode="json")
            for slot in missing_required_slots(result.draft)
            if slot.step == result.next_step
        ]

    def _model_name(self) -> str | None:
        record = getattr(self.model, "model_record", None)
        return getattr(record, "model_name", None) or getattr(
            self.model,
            "name",
            None,
        )

    def _is_explicit_confirmation(self, content: str) -> bool:
        normalized = content.strip().casefold()
        return normalized in {
            "confirm",
            "confirm creation",
            "complete",
            "done",
            "确认",
            "确认创建",
            "完成",
        }

    def _is_help_request(self, content: str) -> bool:
        normalized = content.strip().casefold()
        return (
            normalized.endswith(("?", "？", "吗"))
            or any(
                term in normalized
                for term in (
                    "help",
                    "explain",
                    "what can",
                    "how can",
                    "can i",
                    "can't",
                    "cannot",
                    "为什么",
                    "怎么",
                    "如何",
                    "能不能",
                    "不能",
                    "可以吗",
                )
            )
        )

    def _contains_chinese(self, value: str) -> bool:
        return any("\u4e00" <= character <= "\u9fff" for character in value)
