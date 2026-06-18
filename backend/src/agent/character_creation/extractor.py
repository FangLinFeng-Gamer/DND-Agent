import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from backend.src.agent.character_creation.models import CharacterExtraction
from backend.src.agent.locale import language_instruction
from backend.src.schemas.character_creation import ABILITY_NAMES, CharacterDraft


class CharacterStructuredExtractor:
    def __init__(self, model: BaseChatModel | None):
        self.model = model

    def extract_with_model(
        self,
        draft: CharacterDraft,
        content: str,
        locale: str,
        recent_messages: list[dict[str, Any]],
    ) -> CharacterExtraction:
        if self.model is None:
            raise RuntimeError("No character extraction model is configured.")
        prompt = (
            "Extract DND 5e character creation changes. Return JSON only, with no "
            "markdown or explanation. Allowed keys are intent, name, race, class_name, "
            "background, alignment, notes, and ability_scores. intent must be one of "
            "provide_info, update, confirm, or help. ability_scores, when present, must "
            "contain strength, dexterity, constitution, intelligence, wisdom, and "
            "charisma. Use canonical English DND names for race, class_name, and "
            "background. Omit missing values and never invent them. "
            f"{language_instruction(locale)}"
        )
        message = self.model.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=json.dumps(
                        {
                            "current_draft": draft.model_dump(),
                            "recent_messages": recent_messages[-12:],
                            "message": content,
                        },
                        ensure_ascii=False,
                    )
                ),
            ]
        )
        return CharacterExtraction.model_validate(
            self._parse_model_payload(message.content)
        )

    def extract_ordered_abilities(self, content: str) -> dict[str, int] | None:
        if re.search(r"[A-Za-z\u4e00-\u9fff]", content):
            return None
        values = [int(value) for value in re.findall(r"\d+", content)]
        if len(values) != len(ABILITY_NAMES):
            return None
        return dict(zip(ABILITY_NAMES, values))

    def model_name(self) -> str | None:
        record = getattr(self.model, "model_record", None)
        return getattr(record, "model_name", None)

    def _parse_model_payload(self, content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        fenced = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if fenced:
            return json.loads(fenced.group(1))
        embedded = re.search(r"(\{.*\})", content, re.DOTALL)
        if embedded:
            return json.loads(embedded.group(1))
        raise ValueError("Model response did not contain a JSON object.")
