import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_save_model_submits_model_config_and_refreshes_list(tmp_path):
    script_path = tmp_path / "save-model-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    models_url = json.dumps((PROJECT_ROOT / "frontend/static/js/models.js").as_uri())
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return null; } },
            };

            class FakeElement {
              constructor(value = "") {
                this.value = value;
                this.required = true;
                this.children = [];
                this.className = "";
                this.textContent = "";
              }

              reset() {
                this.resetCalled = true;
              }

              replaceChildren(...children) {
                this.children = children;
              }

              append(...children) {
                this.children.push(...children);
              }

              querySelector() {
                return new FakeElement();
              }

              addEventListener() {}
            }

            globalThis.document = {
              createElement() {
                return new FakeElement();
              },
              getElementById() {
                return new FakeElement();
              },
            };

            const savedModel = {
              id: 42,
              name: "Codex UI Probe",
              provider: "openai_compatible",
              base_url: "https://api.example.test",
              api_key_masked: "sk-t...7890",
              model_name: "ui-probe-model-latest",
              temperature: 0.4,
              max_context_tokens: 8192,
              is_active: true,
              created_at: "2026-06-12 00:00:00",
              updated_at: "2026-06-12 00:00:00",
            };

            function jsonResponse(payload) {
              return {
                ok: true,
                status: 200,
                headers: {
                  get(name) {
                    return name.toLowerCase() === "content-type" ? "application/json" : "";
                  },
                },
                async json() {
                  return payload;
                },
                async text() {
                  return JSON.stringify(payload);
                },
              };
            }

            const requests = [];
            globalThis.fetch = async (url, options = {}) => {
              requests.push({ url, options });
              if (url === "/api/models" && options.method === "POST") {
                return jsonResponse({ ...savedModel, is_active: false });
              }
              if (url === "/api/models/42/activate" && options.method === "POST") {
                return jsonResponse(savedModel);
              }
              if (url === "/api/models" && !options.method) {
                return jsonResponse([savedModel]);
              }
              throw new Error(`Unexpected request: ${options.method || "GET"} ${url}`);
            };

            const { els, state } = await import(__STATE_URL__);
            const { saveModel } = await import(__MODELS_URL__);

            Object.assign(els, {
              status: new FakeElement(),
              modelForm: new FakeElement(),
              modelDisplayName: new FakeElement("Codex UI Probe"),
              modelProvider: new FakeElement("openai_compatible"),
              modelBaseUrl: new FakeElement("https://api.example.test"),
              modelApiKey: new FakeElement("sk-test-1234567890"),
              modelName: new FakeElement("ui-probe-model-latest"),
              modelTemperature: new FakeElement("0.4"),
              modelMaxContext: new FakeElement("8192"),
              modelList: new FakeElement(),
            });

            await saveModel();

            assert.deepEqual(
              requests.map((request) => `${request.options.method || "GET"} ${request.url}`),
              ["POST /api/models", "POST /api/models/42/activate", "GET /api/models"],
            );
            assert.equal(state.models[0].model_name, "ui-probe-model-latest");
            assert.equal(state.models[0].is_active, true);
            """
        )
        .replace("__STATE_URL__", state_url)
        .replace("__MODELS_URL__", models_url),
        encoding="utf-8",
    )

    result = subprocess.run(["node", str(script_path)], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr


def test_model_connection_test_submits_form_values_and_shows_result(tmp_path):
    script_path = tmp_path / "test-model-connection.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    models_url = json.dumps((PROJECT_ROOT / "frontend/static/js/models.js").as_uri())
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return null; } },
            };

            class FakeElement {
              constructor(value = "") {
                this.value = value;
                this.required = true;
                this.children = [];
                this.className = "";
                this.textContent = "";
                this.disabled = false;
              }

              replaceChildren(...children) {
                this.children = children;
              }

              append(...children) {
                this.children.push(...children);
              }

              addEventListener() {}
            }

            globalThis.document = {
              createElement() {
                return new FakeElement();
              },
              getElementById() {
                return new FakeElement();
              },
            };

            function jsonResponse(payload) {
              return {
                ok: true,
                status: 200,
                headers: {
                  get(name) {
                    return name.toLowerCase() === "content-type" ? "application/json" : "";
                  },
                },
                async json() {
                  return payload;
                },
                async text() {
                  return JSON.stringify(payload);
                },
              };
            }

            const requests = [];
            globalThis.fetch = async (url, options = {}) => {
              requests.push({ url, options });
              if (url === "/api/models/test" && options.method === "POST") {
                return jsonResponse({
                  ok: true,
                  message: "Connected to probe-model in 12 ms.",
                  latency_ms: 12,
                  model_name: "probe-model",
                });
              }
              throw new Error(`Unexpected request: ${options.method || "GET"} ${url}`);
            };

            const { els, state } = await import(__STATE_URL__);
            const { testModelConnection } = await import(__MODELS_URL__);

            Object.assign(els, {
              status: new FakeElement(),
              modelDisplayName: new FakeElement("Probe"),
              modelProvider: new FakeElement("openai_compatible"),
              modelBaseUrl: new FakeElement("https://api.example.test"),
              modelApiKey: new FakeElement("sk-form-key"),
              modelName: new FakeElement("probe-model"),
              modelTemperature: new FakeElement("0.2"),
              modelMaxContext: new FakeElement("2048"),
              testModelConnection: new FakeElement(),
              modelConnectionResult: new FakeElement(),
            });
            state.editingModelId = 42;

            await testModelConnection();

            assert.deepEqual(
              requests.map((request) => `${request.options.method || "GET"} ${request.url}`),
              ["POST /api/models/test"],
            );
            assert.deepEqual(JSON.parse(requests[0].options.body), {
              existing_model_id: 42,
              name: "Probe",
              provider: "openai_compatible",
              base_url: "https://api.example.test",
              api_key: "sk-form-key",
              model_name: "probe-model",
              temperature: 0.2,
              max_context_tokens: 2048,
            });
            assert.match(els.modelConnectionResult.textContent, /Connected to probe-model/);
            assert.equal(els.modelConnectionResult.className, "model-test-result ok");
            assert.equal(els.status.textContent, "Model connectivity test passed");
            """
        )
        .replace("__STATE_URL__", state_url)
        .replace("__MODELS_URL__", models_url),
        encoding="utf-8",
    )

    result = subprocess.run(["node", str(script_path)], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
