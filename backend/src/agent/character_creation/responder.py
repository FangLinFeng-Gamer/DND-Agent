import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from backend.src.agent.llm.langchain_model import OpenAICompatibleChatModel


class CharacterResponseComposer:
    def __init__(self, model: BaseChatModel | None):
        if isinstance(model, OpenAICompatibleChatModel):
            self.model = model.model_copy(update={"json_mode": False})
        else:
            self.model = model

    def compose(
        self,
        *,
        locale: str,
        draft: dict[str, Any],
        recent_messages: list[dict[str, Any]],
        changed_fields: list[str],
        validation_errors: list[str],
        next_step: str,
        missing_slots: list[dict[str, Any]],
        template_message: str,
    ) -> tuple[str, str]:
        if self.model is None:
            return template_message, "template"
        prompt = (
            "You are a DND 5e character creation guide. Write a natural player-facing "
            "reply in the requested locale. Preserve every supplied numeric rule and "
            "validation fact exactly. Do not claim a state change unless it appears in "
            "changed_fields. Ask exactly one next question when another choice is "
            "required. Do not output JSON or markdown code fences."
        )
        payload = {
            "locale": locale,
            "current_draft": draft,
            "recent_messages": recent_messages[-12:],
            "changed_fields": changed_fields,
            "validation_errors": validation_errors,
            "next_step": next_step,
            "missing_slots": missing_slots,
            "fallback_message": template_message,
        }
        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(
                        content=json.dumps(payload, ensure_ascii=False)
                    ),
                ]
            )
            message = str(response.content).strip()
            if message:
                return message, "llm"
        except Exception:
            pass
        return template_message, "template"
