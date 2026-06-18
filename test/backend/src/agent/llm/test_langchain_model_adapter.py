import json

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from backend.src.agent.llm.langchain_model import OpenAICompatibleChatModel
from backend.src.schemas.llm import LLMModelRecord


class FakeToolCallingClient:
    def chat_message(self, model, messages, tools=None, tool_choice=None):
        assert tools
        return {
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "inspect_scene",
                        "arguments": json.dumps({"instruction": "Inspect the gate"}),
                    },
                }
            ],
        }


def model_record():
    return LLMModelRecord(
        id=1,
        name="Test",
        provider="openai_compatible",
        base_url="http://model.test/v1",
        api_key="sk-test",
        model_name="test-model",
        temperature=0.2,
        max_context_tokens=4096,
        is_active=True,
        api_key_masked="sk-***test",
        created_at="2026-06-06 00:00:00",
        updated_at="2026-06-06 00:00:00",
    )


def test_langchain_adapter_converts_openai_tool_calls():
    @tool
    def inspect_scene(instruction: str) -> str:
        """Inspect the current scene."""
        return instruction

    model = OpenAICompatibleChatModel(
        model_record=model_record(),
        client=FakeToolCallingClient(),
    ).bind_tools([inspect_scene])

    response = model.invoke([HumanMessage(content="Look around")])

    assert response.tool_calls[0]["name"] == "inspect_scene"
    assert response.tool_calls[0]["args"]["instruction"] == "Inspect the gate"
