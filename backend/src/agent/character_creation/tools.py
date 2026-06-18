import json
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool

from backend.src.agent.character_creation.models import StateGraphResult
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.character_creation.workflow import CharacterCreationStateGraph
from backend.src.agent.locale import normalize_locale
from backend.src.schemas.character_creation import CharacterDraft


MAX_TOOL_CALLS = 6


def explain_character_option_payload(
    *,
    draft: CharacterDraft,
    topic: str,
    locale: str,
    repository: PHBRuleRepository,
) -> dict[str, Any]:
    normalized = topic.casefold().strip()
    facts: list[str] = []
    if (
        draft.class_name == "Fighter"
        and any(term in normalized for term in ("spell", "magic", "法术", "魔法"))
    ):
        if locale == "zh-CN":
            facts = [
                "1级纯战士没有职业施法能力。",
                "种族特性可能提供法术。",
                "满足条件的专长可以提供法术。",
                "后续可以通过兼职进入施法职业。",
            ]
        else:
            facts = [
                "A level-one single-class Fighter has no class spellcasting.",
                "A racial trait may grant spells.",
                "An eligible feat may grant spells.",
                "Later multiclassing can add a spellcasting class.",
            ]
    if not facts:
        matches = repository.search(topic, locale=locale)
        facts = [
            record.description.for_locale(locale)
            for record in matches[:5]
        ]
    if not facts:
        facts = [
            (
                "未找到直接匹配的玩家手册规则。"
                if locale == "zh-CN"
                else "No directly matching Player's Handbook rule was found."
            )
        ]
    return {
        "source": "PHB",
        "topic": topic,
        "draft_revision": draft.revision,
        "current_step": draft.current_step,
        "facts": facts,
        "draft_changed": False,
        "committed": False,
    }


@dataclass
class CharacterToolContext:
    session_id: int
    locale: str
    workflow: CharacterCreationStateGraph
    draft: CharacterDraft
    explicit_confirmation: bool = False
    latest_result: StateGraphResult | None = None
    tool_call_count: int = 0
    tool_results: list[StateGraphResult] = field(default_factory=list)
    called_tools: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.locale = normalize_locale(self.locale)
        self.draft = self.draft.model_copy(deep=True)


class CharacterCreationToolRegistry:
    def __init__(
        self,
        context: CharacterToolContext,
        repository: PHBRuleRepository | None = None,
    ):
        self.context = context
        self.rules = repository or PHBRuleRepository.load_builtin()

    def tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(
                func=self._get_character_draft,
                name="get_character_draft",
                description=(
                    "Read the authoritative character draft, revision, current step, "
                    "validation state, and allowed next actions."
                ),
            ),
            StructuredTool.from_function(
                func=self._search_character_rules,
                name="search_character_rules",
                description=(
                    "Read-only search of Player's Handbook character creation rules."
                ),
            ),
            StructuredTool.from_function(
                func=self._explain_character_option,
                name="explain_character_option",
                description=(
                    "Explain a character option using the current draft and PHB rules. "
                    "This tool never changes or confirms the draft."
                ),
            ),
            StructuredTool.from_function(
                func=self._apply_character_changes,
                name="apply_character_changes",
                description=(
                    "Apply structured player-provided changes through the deterministic "
                    "character creation StateGraph."
                ),
            ),
            StructuredTool.from_function(
                func=self._validate_character_draft,
                name="validate_character_draft",
                description=(
                    "Validate the current character draft without changing or committing it."
                ),
            ),
            StructuredTool.from_function(
                func=self._confirm_character_creation,
                name="confirm_character_creation",
                description=(
                    "Confirm and persist a review-ready character only when the current "
                    "player message explicitly grants confirmation permission."
                ),
            ),
        ]

    def _get_character_draft(self) -> str:
        """Read the current authoritative draft."""
        limited = self._begin_state_call("get_character_draft")
        if limited is not None:
            return limited.to_tool_content()
        return self._record(
            self.context.workflow.read(
                draft=self.context.draft,
                expected_revision=self.context.draft.revision,
                locale=self.context.locale,
            )
        )

    def _search_character_rules(
        self,
        query: str,
        category: str = "",
    ) -> str:
        """Search PHB rules by text and optional category."""
        if self._begin_read_only_call("search_character_rules"):
            return self._limit_payload()
        rule_type = category.strip() or None
        records = (
            self.rules.search(
                query,
                locale=self.context.locale,
                rule_type=rule_type,
            )
            if query.strip()
            else self.rules.list(rule_type)
        )
        return json.dumps(
            {
                "source": "PHB",
                "query": query,
                "category": category,
                "results": [
                    {
                        "id": record.id,
                        "type": record.rule_type,
                        "name": record.name.for_locale(self.context.locale),
                        "description": record.description.for_locale(
                            self.context.locale
                        ),
                        "source": record.source,
                        "prerequisites": [
                            item.model_dump(mode="json")
                            for item in record.prerequisites
                        ],
                    }
                    for record in records[:20]
                ],
            },
            ensure_ascii=False,
        )

    def _explain_character_option(self, topic: str) -> str:
        """Explain a PHB option in the context of the current draft."""
        if self._begin_read_only_call("explain_character_option"):
            return self._limit_payload()
        return json.dumps(
            explain_character_option_payload(
                draft=self.context.draft,
                topic=topic,
                locale=self.context.locale,
                repository=self.rules,
            ),
            ensure_ascii=False,
        )

    def _apply_character_changes(
        self,
        changes: dict[str, Any],
        expected_revision: int,
    ) -> str:
        """Apply structured changes to the current draft."""
        limited = self._begin_state_call("apply_character_changes")
        if limited is not None:
            return limited.to_tool_content()
        return self._record(
            self.context.workflow.apply_changes(
                draft=self.context.draft,
                expected_revision=expected_revision,
                changes=changes,
                locale=self.context.locale,
            )
        )

    def _validate_character_draft(self, expected_revision: int) -> str:
        """Validate the current draft without committing it."""
        limited = self._begin_state_call("validate_character_draft")
        if limited is not None:
            return limited.to_tool_content()
        return self._record(
            self.context.workflow.validate(
                draft=self.context.draft,
                expected_revision=expected_revision,
                locale=self.context.locale,
            )
        )

    def _confirm_character_creation(self, expected_revision: int) -> str:
        """Persist the current draft after explicit player confirmation."""
        limited = self._begin_state_call("confirm_character_creation")
        if limited is not None:
            return limited.to_tool_content()
        commit_key = (
            f"character-session:{self.context.session_id}:"
            f"revision:{expected_revision}"
        )
        return self._record(
            self.context.workflow.confirm(
                draft=self.context.draft,
                expected_revision=expected_revision,
                locale=self.context.locale,
                explicit_confirmation=self.context.explicit_confirmation,
                commit_key=commit_key,
            )
        )

    def _begin_state_call(self, tool_name: str) -> StateGraphResult | None:
        self.context.called_tools.append(tool_name)
        self.context.tool_call_count += 1
        if self.context.tool_call_count <= MAX_TOOL_CALLS:
            return None
        result = StateGraphResult(
            success=False,
            draft_revision=self.context.draft.revision,
            current_step=self.context.draft.current_step,
            next_step=self.context.draft.current_step,
            validation_errors=[
                f"Character tool call limit of {MAX_TOOL_CALLS} was exceeded."
            ],
            facts=["No operation was executed after the tool call limit."],
            allowed_actions=[],
            draft=self.context.draft.model_copy(deep=True),
        )
        self.context.latest_result = result
        self.context.tool_results.append(result)
        return result

    def _begin_read_only_call(self, tool_name: str) -> bool:
        self.context.called_tools.append(tool_name)
        self.context.tool_call_count += 1
        return self.context.tool_call_count > MAX_TOOL_CALLS

    def _limit_payload(self) -> str:
        return json.dumps(
            {
                "success": False,
                "validation_errors": [
                    f"Character tool call limit of {MAX_TOOL_CALLS} was exceeded."
                ],
                "source": "system",
            },
            ensure_ascii=False,
        )

    def _record(self, result: StateGraphResult) -> str:
        self.context.latest_result = result
        self.context.draft = result.draft.model_copy(deep=True)
        self.context.tool_results.append(result)
        return result.to_tool_content()
