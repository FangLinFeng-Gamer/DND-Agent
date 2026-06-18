import json
import inspect
from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, convert_to_openai_messages
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict, Field

from backend.src.schemas.llm import LLMModelRecord


class OpenAICompatibleChatModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_record: LLMModelRecord
    client: Any
    bound_tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: str | None = None
    json_mode: bool = True

    @property
    def _llm_type(self) -> str:
        return "dnd_openai_compatible"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool | Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ):
        return self.model_copy(
            update={
                "bound_tools": [convert_to_openai_tool(tool) for tool in tools],
                "tool_choice": tool_choice,
            }
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        call_kwargs = {
            "tools": self.bound_tools or None,
            "tool_choice": self.tool_choice,
        }
        if "json_mode" in inspect.signature(
            self.client.chat_message
        ).parameters:
            call_kwargs["json_mode"] = self.json_mode
        payload = self.client.chat_message(
            self.model_record,
            convert_to_openai_messages(messages),
            **call_kwargs,
        )
        tool_calls = []
        for call in payload.get("tool_calls") or []:
            function = call.get("function") or {}
            arguments = function.get("arguments") or "{}"
            try:
                args = json.loads(arguments)
            except json.JSONDecodeError:
                args = {"raw": arguments}
            tool_calls.append(
                {
                    "name": function.get("name") or "",
                    "args": args,
                    "id": call.get("id") or "",
                    "type": "tool_call",
                }
            )
        message = AIMessage(
            content=payload.get("content") or "",
            tool_calls=tool_calls,
        )
        return ChatResult(generations=[ChatGeneration(message=message)])
