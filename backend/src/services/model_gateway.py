from __future__ import annotations

import json
from typing import Any

from backend.src.agent.dm.output import extract_narration_text
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.adventure import MessageOut
from backend.src.schemas.llm import LLMModelRecord
from backend.src.services.adventures import AdventureService
from backend.src.services.context import ContextService
from backend.src.services.llm_models import LLMModelService


class ModelGateway:
    def __init__(self, store: SQLiteStore, llm_client: Any | None = None):
        self.store = store
        self.llm_client = llm_client
        self.models = LLMModelService(store)
        self.adventures = AdventureService(store)
        self.context = ContextService(store)

    def active_model(self) -> LLMModelRecord | None:
        return self.models.get_active_record()

    def estimate_tokens(self, text: str) -> int:
        return self.context.estimate_tokens(text)

    def chat(self, model: LLMModelRecord, messages: list[dict[str, Any]]) -> str:
        if not self.llm_client or not hasattr(self.llm_client, "chat"):
            raise RuntimeError("LLM client does not support chat.")
        return self.llm_client.chat(model, messages)

    def stream_chat(self, model: LLMModelRecord, messages: list[dict[str, Any]]):
        if not self.llm_client or not hasattr(self.llm_client, "stream_chat"):
            raise RuntimeError("LLM client does not support stream_chat.")
        yield from self.llm_client.stream_chat(model, messages)

    def stream_json_payload(
        self,
        model: LLMModelRecord,
        messages: list[dict[str, Any]],
    ):
        chunks: list[str] = []
        emitted_narration_length = 0
        for chunk in self.stream_chat(model, messages):
            chunks.append(chunk)
            narration = extract_narration_text("".join(chunks))
            if len(narration) > emitted_narration_length:
                delta = narration[emitted_narration_length:]
                emitted_narration_length = len(narration)
                yield {"type": "delta", "content": delta}
        raw_response = "".join(chunks)
        return json.loads(raw_response), extract_narration_text(raw_response)

    def recent_message_payloads(
        self,
        adventure_id: int,
        max_context_tokens: int,
        reserved_payload: Any | None = None,
        max_messages: int = 80,
    ) -> list[dict[str, Any]]:
        reserved_tokens = self.estimate_tokens(self._stable_json(reserved_payload or {}))
        message_budget = max(1, int(max_context_tokens) - reserved_tokens)
        selected: list[dict[str, Any]] = []
        used_tokens = 0

        for message in reversed(self.adventures.list_messages(adventure_id)):
            payload = self.message_payload(message)
            cost = self.estimate_tokens(self._stable_json(payload))
            if selected and used_tokens + cost > message_budget:
                break
            selected.append(payload)
            used_tokens += cost
            if len(selected) >= max_messages:
                break

        return list(reversed(selected))

    def message_payload(self, message: MessageOut) -> dict[str, Any]:
        return {
            "role": message.role,
            "content": message.content,
            "metadata": message.metadata,
            "created_at": message.created_at,
        }

    def _stable_json(self, payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
