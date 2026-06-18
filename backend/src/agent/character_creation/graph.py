import re

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from backend.src.agent.character_creation.deterministic import (
    basic_draft_issues,
    changed_core_fields,
    format_basic_issue,
    invalidate_changed_dependencies,
)
from backend.src.agent.character_creation.extractor import CharacterStructuredExtractor
from backend.src.agent.character_creation.responder import CharacterResponseComposer
from backend.src.agent.character_creation.state import CharacterCreationState
from backend.src.agent.character_creation.slots import first_missing_step, mark_completed_steps
from backend.src.agent.character_creation.rules.abilities import calculate_abilities
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.dm.schemas import AgentKind
from backend.src.agent.locale import normalize_locale
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character import CharacterCreate
from backend.src.schemas.character_creation import ABILITY_NAMES, CharacterDraft
from backend.src.services.characters import CharacterService
from backend.src.services.world import WorldService


SUPPORTED_CLASSES = {
    "Barbarian",
    "Bard",
    "Cleric",
    "Druid",
    "Fighter",
    "Monk",
    "Paladin",
    "Ranger",
    "Rogue",
    "Sorcerer",
    "Warlock",
    "Wizard",
}


CHINESE_RACES = {
    "人类": "Human",
    "精灵": "Elf",
    "矮人": "Dwarf",
    "半身人": "Halfling",
    "龙裔": "Dragonborn",
    "侏儒": "Gnome",
    "半精灵": "Half-Elf",
    "半兽人": "Half-Orc",
    "提夫林": "Tiefling",
}


CHINESE_CLASSES = {
    "野蛮人": "Barbarian",
    "吟游诗人": "Bard",
    "牧师": "Cleric",
    "德鲁伊": "Druid",
    "战士": "Fighter",
    "武僧": "Monk",
    "圣武士": "Paladin",
    "游侠": "Ranger",
    "游荡者": "Rogue",
    "盗贼": "Rogue",
    "术士": "Warlock",
    "邪术师": "Warlock",
    "法师": "Wizard",
    "巫师": "Wizard",
    "术法师": "Sorcerer",
}


CHINESE_BACKGROUNDS = {
    "士兵": "Soldier",
    "侍祭": "Acolyte",
    "罪犯": "Criminal",
    "艺人": "Entertainer",
    "平民英雄": "Folk Hero",
    "行会工匠": "Guild Artisan",
    "隐士": "Hermit",
    "贵族": "Noble",
    "化外之民": "Outlander",
    "智者": "Sage",
    "水手": "Sailor",
    "流浪儿": "Urchin",
}


class CharacterCreationAgent:
    agent_kind = AgentKind.REACT

    def __init__(self, store: SQLiteStore, model: BaseChatModel | None = None):
        self.model = model
        self.characters = CharacterService(store)
        self.world = WorldService(store)
        self.rules = PHBRuleRepository.load_builtin()
        self.extractor = CharacterStructuredExtractor(model)
        self.responder = CharacterResponseComposer(model)
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(CharacterCreationState)
        graph.add_node("guide_and_update", self._guide_and_update)
        graph.add_node("validate", self._validate)
        graph.add_node("compose_response", self._compose_response)
        graph.add_node("commit", self._commit)
        graph.add_edge(START, "guide_and_update")
        graph.add_edge("guide_and_update", "validate")
        graph.add_conditional_edges(
            "validate",
            self._route_after_validation,
            {"commit": "commit", "respond": "compose_response"},
        )
        graph.add_edge("commit", "compose_response")
        graph.add_edge("compose_response", END)
        return graph.compile(name="character_creation_agent")

    def process(
        self,
        draft: CharacterDraft,
        content: str,
        locale: str = "en",
        recent_messages: list[dict] | None = None,
    ) -> CharacterCreationState:
        return self.graph.invoke(
            {
                "draft": draft,
                "content": content,
                "locale": normalize_locale(locale),
                "recent_messages": recent_messages or [],
                "extracted_changes": {},
                "confirmed": self._is_confirmation(content),
                "changed_fields": [],
                "next_step": "identity",
                "missing_slots": [],
                "assistant_message": "",
                "metadata": {},
                "validation_errors": [],
                "created_character": None,
            }
        )

    def _guide_and_update(self, state: CharacterCreationState):
        draft = state["draft"].model_copy(deep=True)
        before = draft.model_dump()
        extractor = "fallback"
        ability_scores = self.extractor.extract_ordered_abilities(state["content"])
        if draft.current_step == "abilities" and ability_scores is not None:
            try:
                race_id, subrace_id = self._resolve_race_ids(draft.race)
                draft.abilities = calculate_abilities(
                    ability_scores,
                    race_id=race_id,
                    subrace_id=subrace_id,
                    repository=self.rules,
                )
                if "abilities" not in draft.completed_steps:
                    draft.completed_steps.append("abilities")
                draft.invalid_steps = [
                    step for step in draft.invalid_steps if step != "abilities"
                ]
                return self._update_result(before, draft, "ordered_abilities")
            except ValueError as exc:
                return self._update_result(
                    before,
                    draft,
                    "ordered_abilities",
                    [self._localize_ability_error(str(exc), state["locale"])],
                )
        if self.model is not None:
            try:
                extraction = self.extractor.extract_with_model(
                    draft,
                    state["content"],
                    state["locale"],
                    state.get("recent_messages", []),
                )
                payload = extraction.draft_changes()
                model_abilities = extraction.complete_ability_scores()
                if model_abilities is not None:
                    race_id, subrace_id = self._resolve_race_ids(
                        payload.get("race", draft.race)
                    )
                    updated_abilities = calculate_abilities(
                        model_abilities,
                        race_id=race_id,
                        subrace_id=subrace_id,
                        repository=self.rules,
                    )
                    payload["abilities"] = updated_abilities.model_dump()
                draft = CharacterDraft.model_validate(
                    {**draft.model_dump(), **payload}
                )
                extractor = "llm"
                result = self._update_result(before, draft, extractor)
                result["extracted_changes"] = payload
                model_name = self.extractor.model_name()
                if model_name:
                    result["metadata"]["model_name"] = model_name
                return result
            except Exception:
                pass
        self._fallback_extract(state["content"], draft)
        return self._update_result(before, draft, extractor)

    def _validate(self, state: CharacterCreationState):
        draft = state["draft"]
        chinese = state["locale"] == "zh-CN"
        errors = list(state.get("validation_errors", []))
        races = {entry.name for entry in self.world.search(category="race").results}
        issues = basic_draft_issues(
            draft,
            valid_races=races,
            valid_classes=SUPPORTED_CLASSES,
        )
        for issue in issues:
            if not chinese:
                errors.append(format_basic_issue(issue))
            elif issue.code == "missing_name":
                errors.append("请输入角色名称。")
            elif issue.code == "missing_race":
                errors.append("请选择角色种族。")
            elif issue.code == "unsupported_race":
                errors.append(f"不支持的种族：{issue.value}。")
            elif issue.code == "missing_class":
                errors.append("请选择角色职业。")
            elif issue.code == "unsupported_class":
                errors.append(f"不支持的职业：{issue.value}。")
        next_step, missing_slots = first_missing_step(draft)
        mark_completed_steps(draft, next_step)
        missing_payload = [slot.model_dump() for slot in missing_slots]
        metadata = {
            **state.get("metadata", {}),
            "changed_fields": state.get("changed_fields", []),
            "next_step": next_step,
            "missing_slots": missing_payload,
        }
        return {
            "draft": draft,
            "next_step": next_step,
            "missing_slots": missing_payload,
            "validation_errors": errors,
            "metadata": metadata,
        }

    def _route_after_validation(self, state: CharacterCreationState):
        if state["confirmed"] and state["next_step"] == "review" and not state["validation_errors"]:
            return "commit"
        return "respond"

    def _commit(self, state: CharacterCreationState):
        character = self.characters.create(CharacterCreate(**state["draft"].model_dump()))
        return {"created_character": character}

    def _compose_response(self, state: CharacterCreationState):
        template_message = self._template_response(state)
        message, responder = self.responder.compose(
            locale=state["locale"],
            draft=state["draft"].model_dump(),
            recent_messages=state.get("recent_messages", []),
            changed_fields=state.get("changed_fields", []),
            validation_errors=state.get("validation_errors", []),
            next_step=state.get("next_step", "identity"),
            missing_slots=state.get("missing_slots", []),
            template_message=template_message,
        )
        metadata = {
            **state.get("metadata", {}),
            "responder": responder,
        }
        model_name = self.extractor.model_name()
        if model_name:
            metadata["model_name"] = model_name
        return {"assistant_message": message, "metadata": metadata}

    def _template_response(self, state: CharacterCreationState):
        locale = state["locale"]
        draft = state["draft"]
        if state["created_character"]:
            message = "角色已创建。" if locale == "zh-CN" else "Character created."
        elif state["validation_errors"]:
            message = " ".join(state["validation_errors"])
        else:
            summary = self._draft_summary(draft, locale)
            missing_slots = state.get("missing_slots", [])
            if missing_slots:
                question = self._localized_slot_question(missing_slots[0], locale)
            else:
                question = "请确认创建角色。" if locale == "zh-CN" else "Please confirm character creation."
            if locale == "zh-CN":
                message = f"当前草稿：{summary}\n\n下一步：{question}"
            else:
                message = f"Current draft: {summary}\n\nNext: {question}"
        return message

    def _draft_summary(self, draft: CharacterDraft, locale: str) -> str:
        not_set_value = "未设置" if locale == "zh-CN" else "not set"
        race = self._localized_canonical_value(draft.race, locale) if draft.race else not_set_value
        class_name = self._localized_canonical_value(draft.class_name, locale) if draft.class_name else not_set_value
        background = (
            self._localized_canonical_value(draft.background, locale)
            if draft.background and draft.background != "Adventurer"
            else not_set_value
        )
        if locale == "zh-CN":
            background_text = f"背景{background}" if background == not_set_value else f"背景 {background}"
            return f"{draft.name or not_set_value}, {race} {class_name}, {background_text}"
        background_label = "背景" if locale == "zh-CN" else "background"
        return (
            f"{draft.name or not_set_value}, {race} {class_name}, "
            f"{background_label} {background}"
        )
        not_set = "未设置" if locale == "zh-CN" else "not set"
        return (
            f"{draft.name or not_set}, {draft.race or not_set} "
            f"{draft.class_name or not_set}, background {draft.background or not_set}"
        )

    def _localized_canonical_value(self, value: str, locale: str) -> str:
        if locale != "zh-CN":
            return value
        translations = {
            "Human": "人类",
            "Elf": "精灵",
            "Dwarf": "矮人",
            "Halfling": "半身人",
            "Dragonborn": "龙裔",
            "Gnome": "侏儒",
            "Half-Elf": "半精灵",
            "Half-Orc": "半兽人",
            "Tiefling": "提夫林",
            "Barbarian": "野蛮人",
            "Bard": "吟游诗人",
            "Cleric": "牧师",
            "Druid": "德鲁伊",
            "Fighter": "战士",
            "Monk": "武僧",
            "Paladin": "圣武士",
            "Ranger": "游侠",
            "Rogue": "游荡者",
            "Sorcerer": "术法师",
            "Warlock": "邪术师",
            "Wizard": "法师",
            "Soldier": "士兵",
            "Acolyte": "侍祭",
            "Criminal": "罪犯",
            "Entertainer": "艺人",
            "Folk Hero": "平民英雄",
            "Guild Artisan": "行会工匠",
            "Hermit": "隐士",
            "Noble": "贵族",
            "Outlander": "化外之民",
            "Sage": "智者",
            "Sailor": "水手",
            "Urchin": "流浪儿",
        }
        return translations.get(value, value)

    def _localized_slot_question(self, slot: dict, locale: str) -> str:
        if locale != "zh-CN":
            return slot["question"]
        if slot["id"] == "abilities.base":
            return (
                "请手动输入六项属性值：力量、敏捷、体质、智力、感知、魅力。"
                "你最多可以使用 27 点，每项基础属性必须在 8 到 15 之间，种族加值另行计算。"
                "购点花费：8=0、9=1、10=2、11=3、12=4、13=5、14=7、15=9。"
                "力量影响近战攻击、负重和运动；敏捷影响护甲等级、先攻、远程攻击和潜行；"
                "体质影响生命值和耐力；智力影响知识和法师施法；"
                "感知影响察觉、洞悉和求生；魅力影响社交和部分职业施法。"
            )
        questions = {
            "identity.name": "你的角色叫什么名字？",
            "race.base": "你想选择哪个种族？",
            "class.base": "你想选择哪个职业？",
            "abilities.base": "你想如何分配属性值：使用标准数组、购点，还是手动输入六项属性？",
            "background.base": "你想选择哪个背景？",
            "spells.known": "请选择这个职业在 1 级需要的法术。",
        }
        return questions.get(slot["id"], slot["question"])

    def _changed_fields(self, before: dict, draft: CharacterDraft) -> list[str]:
        return changed_core_fields(before, draft)

    def _invalidate_dependents(self, draft: CharacterDraft, changed_fields: list[str]) -> None:
        invalidate_changed_dependencies(None, draft, changed_fields)

    def _fallback_extract(self, content: str, draft: CharacterDraft) -> None:
        self._fallback_extract_chinese(content, draft)
        name_update = re.search(
            r"\b(?:change|update|rename|set)\s+(?:my\s+)?name\s+(?:to|as)\s+([A-Z][A-Za-z'-]+)",
            content,
            re.IGNORECASE,
        )
        if name_update:
            draft.name = name_update.group(1)
        for race in [entry.name for entry in self.world.search(category="race").results]:
            if re.search(rf"\b{re.escape(race)}\b", content, re.IGNORECASE):
                draft.race = race
                break
        if not draft.race:
            race_match = re.search(
                r"\b(?:an?|as)\s+(?:a\s+)?([A-Z][A-Za-z-]+)\s+(?:Fighter|Ranger|Wizard|Rogue|Cleric)\b",
                content,
            )
            if race_match:
                draft.race = race_match.group(1)
        for class_name in SUPPORTED_CLASSES:
            if re.search(rf"\b{class_name}\b", content, re.IGNORECASE):
                draft.class_name = class_name
                break
        background = re.search(
            r"\b(?:with|from)\s+(?:a\s+)?([A-Z][A-Za-z-]+)\s+background\b",
            content,
            re.IGNORECASE,
        )
        if background:
            draft.background = background.group(1).title()
        name = re.search(r"\b(?:name is|named|create)\s+([A-Z][A-Za-z'-]+)", content)
        if name:
            draft.name = name.group(1)
        elif not draft.name:
            direct = re.search(r"^([A-Z][A-Za-z'-]+)\b", content)
            if direct:
                draft.name = direct.group(1)

    def _update_result(
        self,
        before: dict,
        draft: CharacterDraft,
        extractor: str,
        validation_errors: list[str] | None = None,
    ) -> dict:
        changed_fields = self._changed_fields(before, draft)
        self._invalidate_dependents(draft, changed_fields)
        return {
            "draft": draft,
            "changed_fields": changed_fields,
            "metadata": {"extractor": extractor},
            "extracted_changes": {},
            "validation_errors": validation_errors or [],
        }

    def _resolve_race_ids(self, race_name: str) -> tuple[str | None, str | None]:
        for record in self.rules.list("race"):
            if record.name.en == race_name:
                return record.id, None
        for record in self.rules.list("subrace"):
            if record.name.en == race_name:
                return record.parent_id, record.id
        return None, None

    def _localize_ability_error(self, error: str, locale: str) -> str:
        if locale != "zh-CN":
            return error
        match = re.search(r"Point-buy cost (\d+) exceeds 27", error)
        if match:
            return (
                f"六项属性共花费 {match.group(1)} 点，超过可用的 27 点。"
                "请按照购点花费表重新分配。"
            )
        if "between 8 and 15" in error:
            return "每项基础属性必须在 8 到 15 之间，请重新输入六项属性值。"
        return error

    def _fallback_extract_chinese(self, content: str, draft: CharacterDraft) -> None:
        if not draft.race:
            for zh_name, canonical in CHINESE_RACES.items():
                if zh_name in content:
                    draft.race = canonical
                    break
        if not draft.class_name:
            for zh_name, canonical in CHINESE_CLASSES.items():
                if zh_name in content:
                    draft.class_name = canonical
                    break
        if not draft.background:
            for zh_name, canonical in CHINESE_BACKGROUNDS.items():
                if zh_name in content:
                    draft.background = canonical
                    break
        elif draft.background == "Adventurer":
            for zh_name, canonical in CHINESE_BACKGROUNDS.items():
                if zh_name in content:
                    draft.background = canonical
                    break
        if not draft.name:
            name = re.search(r"(?:名字叫|名叫|叫做|叫|名称是|名字是)\s*([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9_-]{0,20})", content)
            if name:
                draft.name = name.group(1).rstrip("，。,. ")
        if not draft.name and draft.race and draft.class_name:
            direct_name = re.match(
                r"\s*([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9_-]{0,20})\s+",
                content,
            )
            if direct_name:
                draft.name = direct_name.group(1)

    def _is_confirmation(self, content: str) -> bool:
        normalized = content.strip().lower()
        return normalized in {"confirm", "confirm creation", "确认", "确认创建"} or " and confirm" in normalized
