from sqlite3 import Row
from typing import Any

from backend.src.agent.character_creation.supervisor import (
    CharacterCreationReActAgent,
)
from backend.src.agent.character_creation.messages import (
    CharacterCreationMessageRepository,
)
from backend.src.agent.locale import normalize_locale
from backend.src.agent.character_creation.rules.draft_service import (
    CharacterDraftRulesService,
    DraftRevisionConflict,
)
from backend.src.agent.llm.client import OpenAICompatibleClient
from backend.src.agent.llm.langchain_model import OpenAICompatibleChatModel
from backend.src.db.sqlite import SQLiteStore, decode_json, encode_json
from backend.src.schemas.character_creation import CharacterCreationSessionOut, CharacterDraft
from backend.src.schemas.character_creation import CharacterDraftMutation
from backend.src.services.character_creation_guide import CharacterCreationGuideService
from backend.src.services.llm_models import LLMModelService


class CharacterDraftService:
    def __init__(self, store: SQLiteStore):
        self.store = store
        active_model = LLMModelService(store).get_active_record()
        react_model = (
            OpenAICompatibleChatModel(model_record=active_model, client=OpenAICompatibleClient())
            if active_model
            else None
        )
        self.agent = CharacterCreationReActAgent(store, model=react_model)
        self.draft_rules = CharacterDraftRulesService()
        self.guide_service = CharacterCreationGuideService()
        self.messages = CharacterCreationMessageRepository(store)

    def create(self, locale: str) -> CharacterCreationSessionOut:
        normalized_locale = normalize_locale(locale)
        draft = CharacterDraft()
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO character_creation_sessions (locale, status, draft_json)
                VALUES (?, 'draft', ?)
                """,
                (normalized_locale, encode_json(draft.model_dump())),
            )
            session_id = cursor.lastrowid
        return self.get(session_id, assistant_message=self._welcome(normalized_locale))

    def get(self, session_id: int, assistant_message: str = "") -> CharacterCreationSessionOut:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM character_creation_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise LookupError(f"Character creation session {session_id} was not found.")
        return self._map(row, assistant_message)

    def guide(
        self,
        session_id: int,
        locale: str = "en",
        validation_errors: list[str] | None = None,
        step: str | None = None,
    ):
        normalized_locale = normalize_locale(locale)
        return self.guide_service.build(
            self.get(session_id),
            normalized_locale,
            validation_errors,
            step,
        )

    def handle_message(self, session_id: int, content: str, locale: str = "en") -> CharacterCreationSessionOut:
        session = self.get(session_id)
        normalized_locale = normalize_locale(locale)
        recent_messages = [
            {"role": message.role, "content": message.content}
            for message in self.messages.list_recent(session_id, limit=12)
        ]
        self.messages.append(session_id, "user", content)
        result = self.agent.process(
            session_id=session_id,
            draft=session.draft,
            content=content,
            locale=normalized_locale,
            recent_messages=recent_messages,
        )
        draft = result.draft
        errors = result.validation_errors
        created = result.created_character
        metadata = result.diagnostics
        status = "completed" if created else "draft"
        revision = draft.revision
        draft.revision = revision
        with self.store.connect() as conn:
            updated = conn.execute(
                """
                UPDATE character_creation_sessions
                SET locale = ?, status = ?, draft_json = ?, revision = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND revision = ?
                """,
                (
                    normalized_locale,
                    status,
                    encode_json(draft.model_dump()),
                    revision,
                    session_id,
                    session.revision,
                ),
            )
            if updated.rowcount != 1:
                raise DraftRevisionConflict(
                    "The character draft changed before this turn was saved."
                )
        response = CharacterCreationSessionOut(
            id=session_id,
            locale=normalized_locale,
            status=status,
            revision=revision,
            draft=draft,
            assistant_message=result.assistant_text,
            validation_errors=errors,
            created_character=created,
            metadata=metadata,
        )
        self.messages.append(
            session_id,
            "assistant",
            response.assistant_message,
            metadata,
        )
        return response

    def mutate(
        self,
        session_id: int,
        request: CharacterDraftMutation,
    ) -> CharacterCreationSessionOut:
        normalized_locale = normalize_locale(request.locale)
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM character_creation_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise LookupError(
                    f"Character creation session {session_id} was not found."
                )
            current_revision = row["revision"]
            if current_revision != request.expected_revision:
                raise DraftRevisionConflict(
                    f"Expected revision {request.expected_revision}, "
                    f"but current revision is {current_revision}."
                )
            draft = CharacterDraft.model_validate(
                decode_json(row["draft_json"], {})
            )
            draft.revision = current_revision
            result = self.agent.workflow.apply_changes(
                draft=draft,
                expected_revision=current_revision,
                changes=self._structured_changes(request),
                locale=normalized_locale,
            )
            if not result.success:
                errors = result.validation_errors or [
                    "The submitted character choice did not pass validation."
                ]
                return self._structured_failure_session(
                    session_id=session_id,
                    locale=normalized_locale,
                    status=row["status"],
                    draft=draft,
                    revision=current_revision,
                    operation=request.operation,
                    payload=request.payload,
                    errors=errors,
                )
            updated = result.draft
            updated.current_step = self.guide_service.active_step(updated)
            revision = current_revision + 1
            updated.revision = revision
            result = conn.execute(
                """
                UPDATE character_creation_sessions
                SET locale = ?, draft_json = ?, revision = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND revision = ?
                """,
                (
                    normalized_locale,
                    encode_json(updated.model_dump()),
                    revision,
                    session_id,
                    current_revision,
                ),
            )
            if result.rowcount != 1:
                raise DraftRevisionConflict(
                    "The character draft changed before this update was saved."
                )
        assistant_message = self._structured_success_message(
            updated,
            request.operation,
            request.payload,
            normalized_locale,
        )
        self.messages.append(
            session_id,
            "user",
            self._structured_user_message(
                request.operation,
                request.payload,
                normalized_locale,
                failed=False,
            ),
            {"source": "structured_wizard", "operation": request.operation},
        )
        self.messages.append(
            session_id,
            "assistant",
            assistant_message,
            {"source": "structured_wizard", "operation": request.operation},
        )
        return self.get(session_id, assistant_message=assistant_message)

    def _structured_failure_session(
        self,
        *,
        session_id: int,
        locale: str,
        status: str,
        draft: CharacterDraft,
        revision: int,
        operation: str,
        payload: dict[str, Any],
        errors: list[str],
    ) -> CharacterCreationSessionOut:
        assistant_message = self._structured_failure_message(errors, locale)
        self.messages.append(
            session_id,
            "user",
            self._structured_user_message(
                operation,
                payload,
                locale,
                failed=True,
            ),
            {"source": "structured_wizard", "operation": operation, "failed": True},
        )
        self.messages.append(
            session_id,
            "assistant",
            assistant_message,
            {
                "source": "structured_wizard",
                "operation": operation,
                "failed": True,
                "validation_errors": errors,
            },
        )
        return CharacterCreationSessionOut(
            id=session_id,
            locale=locale,
            status=status,
            revision=revision,
            draft=draft,
            assistant_message=assistant_message,
            validation_errors=errors,
            metadata={
                "agent_kind": "structured_wizard",
                "operation": operation,
                "failed": True,
            },
        )

    def _structured_changes(
        self,
        request: CharacterDraftMutation,
    ) -> dict[str, Any]:
        return {request.operation: request.payload}

    def _unsupported_structured_operation(self, operation: str) -> dict[str, Any]:
        raise ValueError(f"Unsupported character draft operation: {operation}.")

    def _structured_user_message(
        self,
        operation: str,
        payload: dict[str, Any],
        locale: str,
        *,
        failed: bool,
    ) -> str:
        if locale == "zh-CN":
            prefix = "界面尝试" if failed else "界面选择"
        else:
            prefix = "UI attempted" if failed else "UI selected"
        return f"{prefix}：{self._operation_label(operation, locale)} = {self._payload_summary(operation, payload, locale)}"

    def _structured_success_message(
        self,
        draft: CharacterDraft,
        operation: str,
        payload: dict[str, Any],
        locale: str,
    ) -> str:
        label = self._operation_label(operation, locale)
        value = self._payload_summary(operation, payload, locale)
        next_step = self.guide_service.active_step(draft)
        next_label = self.guide_service._step_label(next_step, locale)
        if locale == "zh-CN":
            return f"已记录：{label} = {value}。下一步：{next_label}。"
        return f"Recorded: {label} = {value}. Next: {next_label}."

    def _structured_failure_message(
        self,
        errors: list[str],
        locale: str,
    ) -> str:
        joined = " ".join(errors)
        if locale == "zh-CN":
            return f"未通过规则校验：{joined}"
        return f"Rule validation failed: {joined}"

    def _operation_label(self, operation: str, locale: str) -> str:
        labels = {
            "zh-CN": {
                "identity": "姓名",
                "race": "种族",
                "class": "职业",
                "abilities": "属性",
                "background": "背景",
                "proficiencies": "熟练项",
                "class_features": "职业特性",
                "spells": "法术",
            },
            "en": {
                "identity": "Name",
                "race": "Race",
                "class": "Class",
                "abilities": "Abilities",
                "background": "Background",
                "proficiencies": "Proficiencies",
                "class_features": "Class Features",
                "optional_rules": "Optional Rules",
                "spells": "Spells",
                "equipment": "Equipment",
                "adventure_connection": "Adventure Hook",
            },
        }
        return labels[locale].get(operation, operation)

    def _payload_summary(
        self,
        operation: str,
        payload: dict[str, Any],
        locale: str,
    ) -> str:
        if operation == "identity":
            return str(payload.get("name") or "").strip()
        if operation == "class":
            return self._rule_name(str(payload.get("class_id") or ""), locale)
        if operation == "race":
            return self._rule_name(
                str(payload.get("subrace_id") or payload.get("race_id") or ""),
                locale,
            )
        if operation == "background":
            return self._rule_name(str(payload.get("background_id") or ""), locale)
        if operation == "abilities":
            values = payload.get("base", payload)
            if isinstance(values, dict):
                return ", ".join(
                    f"{ability} {values[ability]}"
                    for ability in values
                )
        if operation == "proficiencies":
            choice_values = payload.get("choice_values", {})
            if isinstance(choice_values, dict):
                parts = []
                for choice_id, selected in choice_values.items():
                    names = [
                        self._rule_name(str(rule_id), locale)
                        for rule_id in selected
                    ]
                    parts.append(f"{choice_id}: {', '.join(names)}")
                return "; ".join(parts)
        if operation == "class_features":
            names = [
                self._rule_name(str(rule_id), locale)
                for rule_id in payload.get("class_option_ids", [])
            ]
            if names:
                return ", ".join(names)
            choice_values = payload.get("choice_values", {})
            if isinstance(choice_values, dict):
                return str(choice_values)
        if operation == "spells":
            spell_ids = payload.get("spell_ids", [])
            names = [self._rule_name(str(spell_id), locale) for spell_id in spell_ids[:3]]
            suffix = f" +{len(spell_ids) - 3}" if len(spell_ids) > 3 else ""
            return ", ".join(names) + suffix
        if operation == "optional_rules":
            feat_ids = payload.get("feat_ids", [])
            if feat_ids:
                return ", ".join(
                    self._rule_name(str(feat_id), locale) for feat_id in feat_ids
                )
            return "None" if locale == "en" else "无"
        if operation == "equipment":
            option_ids = payload.get("option_ids", [])
            if option_ids:
                return ", ".join(str(option_id) for option_id in option_ids[:3])
            return "Default equipment" if locale == "en" else "默认装备"
        if operation == "adventure_connection":
            values = [
                str(value).strip()
                for value in payload.values()
                if str(value).strip()
            ]
            if values:
                return "; ".join(values[:2])
            return "No hook" if locale == "en" else "无关联"
        return str(payload)

    def _rule_name(self, rule_id: str, locale: str) -> str:
        try:
            return self.guide_service.repository.get(rule_id).name.for_locale(locale)
        except LookupError:
            return rule_id

    def _welcome(self, locale: str) -> str:
        if locale == "zh-CN":
            return "请告诉我角色名称、种族、职业和背景。完成后我会展示角色卡并等待你确认。"
        return "Tell me the character name, race, class, and background. I will validate the sheet before confirmation."

    def _response(
        self,
        locale: str,
        draft: CharacterDraft,
        errors: list[str],
        confirmed: bool,
    ) -> str:
        if errors:
            return " ".join(errors)
        if confirmed:
            return "角色已创建。" if locale == "zh-CN" else "Character created."
        if locale == "zh-CN":
            return f"角色草稿：{draft.name}，{draft.race} {draft.class_name}，背景 {draft.background}。请回复“确认创建”。"
        return (
            f"Draft: {draft.name}, {draft.race} {draft.class_name}, background {draft.background}. "
            "Reply 'confirm' to create the character."
        )

    def _map(self, row: Row, assistant_message: str) -> CharacterCreationSessionOut:
        revision = row["revision"] if "revision" in row.keys() else 0
        draft = CharacterDraft.model_validate(decode_json(row["draft_json"], {}))
        draft.revision = revision
        return CharacterCreationSessionOut(
            id=row["id"],
            locale=row["locale"],
            status=row["status"],
            revision=revision,
            draft=draft,
            assistant_message=assistant_message,
        )
