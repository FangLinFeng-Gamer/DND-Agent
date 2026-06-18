from fastapi.testclient import TestClient

from backend.src.main import create_app


class FakeModelProbeClient:
    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.calls = []

    def chat_message(self, model, messages, json_mode=True, timeout=60):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "json_mode": json_mode,
                "timeout": timeout,
            }
        )
        if self.error:
            raise self.error
        return {"role": "assistant", "content": "pong"}


def test_model_connectivity_uses_form_values(tmp_path):
    app = create_app(db_path=tmp_path / "dnd-agent.sqlite3", static_dir=None)
    fake_client = FakeModelProbeClient()
    app.state.llm_client = fake_client

    with TestClient(app) as client:
        response = client.post(
            "/api/models/test",
            json={
                "name": "Connectivity Probe",
                "provider": "openai_compatible",
                "base_url": "https://api.example.test",
                "api_key": "sk-form-key",
                "model_name": "probe-model",
                "temperature": 0.2,
                "max_context_tokens": 2048,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["model_name"] == "probe-model"
    assert payload["latency_ms"] >= 0
    assert fake_client.calls[0]["model"].base_url == "https://api.example.test"
    assert fake_client.calls[0]["model"].api_key == "sk-form-key"
    assert fake_client.calls[0]["model"].model_name == "probe-model"
    assert fake_client.calls[0]["json_mode"] is False
    assert fake_client.calls[0]["timeout"] == 15


def test_model_connectivity_reuses_saved_api_key_for_existing_model(tmp_path):
    app = create_app(db_path=tmp_path / "dnd-agent.sqlite3", static_dir=None)
    fake_client = FakeModelProbeClient()
    app.state.llm_client = fake_client

    with TestClient(app) as client:
        saved = client.post(
            "/api/models",
            json={
                "name": "Saved Model",
                "provider": "openai_compatible",
                "base_url": "https://api.saved.test",
                "api_key": "sk-saved-key",
                "model_name": "saved-model",
            },
        ).json()
        response = client.post(
            "/api/models/test",
            json={
                "existing_model_id": saved["id"],
                "name": "Saved Model",
                "provider": "openai_compatible",
                "base_url": "https://api.edited.test",
                "api_key": "",
                "model_name": "edited-model",
                "temperature": 0.7,
                "max_context_tokens": 4096,
            },
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert fake_client.calls[0]["model"].api_key == "sk-saved-key"
    assert fake_client.calls[0]["model"].base_url == "https://api.edited.test"
    assert fake_client.calls[0]["model"].model_name == "edited-model"


def test_model_connectivity_reports_provider_failure(tmp_path):
    app = create_app(db_path=tmp_path / "dnd-agent.sqlite3", static_dir=None)
    app.state.llm_client = FakeModelProbeClient(error=RuntimeError("bad auth"))

    with TestClient(app) as client:
        response = client.post(
            "/api/models/test",
            json={
                "name": "Connectivity Probe",
                "provider": "openai_compatible",
                "base_url": "https://api.example.test",
                "api_key": "sk-form-key",
                "model_name": "probe-model",
            },
        )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "bad auth" in response.json()["message"]
