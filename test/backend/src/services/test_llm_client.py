import json
from unittest.mock import patch

from backend.src.schemas.llm import LLMModelRecord
from backend.src.services.llm_client import OpenAICompatibleClient


class FakeHTTPResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps({"choices": [{"message": {"content": "{\"narration\":\"ok\"}"}}]}).encode("utf-8")


class FakeSseHTTPResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __iter__(self):
        return iter(
            [
                b'data: {"choices":[{"delta":{"content":"{\\"narration\\":\\"The door"}}]}\n',
                b'data: {"choices":[{"delta":{"content":" opens\\"}"}}]}\n',
                b"data: [DONE]\n",
            ]
        )


def model_record(base_url: str) -> LLMModelRecord:
    return LLMModelRecord(
        id=1,
        name="DeepSeek",
        provider="openai_compatible",
        base_url=base_url,
        api_key="sk-test",
        api_key_masked="sk-t...test",
        model_name="deepseek-chat",
        temperature=0.2,
        max_context_tokens=2048,
        is_active=True,
        created_at="2026-05-23 00:00:00",
        updated_at="2026-05-23 00:00:00",
    )


def test_client_uses_full_chat_completions_url_without_appending_path():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeHTTPResponse()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        OpenAICompatibleClient().chat(model_record("https://api.deepseek.com/chat/completions"), [])

    assert captured["url"] == "https://api.deepseek.com/chat/completions"


def test_client_appends_chat_completions_for_base_url():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeHTTPResponse()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        OpenAICompatibleClient().chat(model_record("https://api.deepseek.com"), [])

    assert captured["url"] == "https://api.deepseek.com/chat/completions"


def test_stream_chat_yields_openai_compatible_sse_content_chunks():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeSseHTTPResponse()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        chunks = list(OpenAICompatibleClient().stream_chat(model_record("https://api.deepseek.com"), []))

    assert captured["payload"]["stream"] is True
    assert chunks == ['{"narration":"The door', ' opens"}']
