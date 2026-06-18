import json
import urllib.error
import urllib.request
from typing import Any

from backend.src.schemas.llm import LLMModelRecord


class OpenAICompatibleClient:
    def chat(self, model: LLMModelRecord, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": model.model_name,
            "messages": messages,
            "temperature": model.temperature,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self._chat_completions_url(model.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {model.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Model request failed: {exc}") from exc

        data: dict[str, Any] = json.loads(body)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Model response did not include choices.")
        content = choices[0].get("message", {}).get("content")
        if not content:
            raise RuntimeError("Model response did not include message content.")
        return content

    def stream_chat(self, model: LLMModelRecord, messages: list[dict[str, str]]):
        payload = {
            "model": model.model_name,
            "messages": messages,
            "temperature": model.temperature,
            "response_format": {"type": "json_object"},
            "stream": True,
        }
        request = urllib.request.Request(
            self._chat_completions_url(model.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {model.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    content = self._read_stream_content(chunk)
                    if content:
                        yield content
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Model request failed: {exc}") from exc

    def chat_message(
        self,
        model: LLMModelRecord,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        json_mode: bool = True,
        timeout: float = 60,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model.model_name,
            "messages": messages,
            "temperature": model.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        elif json_mode:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            self._chat_completions_url(model.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {model.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Model request failed: {exc}") from exc
        data: dict[str, Any] = json.loads(body)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Model response did not include choices.")
        return choices[0].get("message") or {}

    def _read_stream_content(self, chunk: dict[str, Any]) -> str:
        choices = chunk.get("choices") or []
        if not choices:
            return ""
        return choices[0].get("delta", {}).get("content") or ""

    def _chat_completions_url(self, base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"
