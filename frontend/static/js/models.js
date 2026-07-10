import { api } from "./api.js?v=20260709-suggested-action";
import { els, state } from "./state.js?v=20260709-suggested-action";
import { t } from "./i18n.js?v=20260709-suggested-action";
import { emptyNode, numberOrDefault, setStatus, showError } from "./ui.js?v=20260709-suggested-action";

export async function loadModels() {
  try {
    state.models = await api("/api/models");
    renderModelList();
    setStatus(t("modelsLoaded"), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function saveModel() {
  const name = els.modelDisplayName.value.trim();
  const apiKey = els.modelApiKey.value.trim();
  if (!name) {
    setStatus(t("modelNameRequired"), "error");
    return;
  }
  if (!state.editingModelId && !apiKey) {
    setStatus(t("modelApiKeyRequired"), "error");
    return;
  }

  const payload = modelFormPayload();
  if (apiKey) {
    payload.api_key = apiKey;
  }

  const path = state.editingModelId ? `/api/models/${state.editingModelId}` : "/api/models";
  const method = state.editingModelId ? "PATCH" : "POST";
  try {
    const savedModel = await api(path, { method, body: JSON.stringify(payload) });
    state.editingModelId = savedModel.id;
    await api(`/api/models/${savedModel.id}/activate`, { method: "POST" });
    resetModelForm();
    await loadModels();
    setStatus(t("modelSavedAndActivated"), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function testModelConnection() {
  const apiKey = els.modelApiKey.value.trim();
  if (!state.editingModelId && !apiKey) {
    setStatus(t("modelApiKeyRequired"), "error");
    renderModelConnectionResult(t("modelApiKeyRequired"), false);
    return;
  }

  const payload = modelFormPayload({ includeExistingModelId: true, fallbackName: "Connectivity Test" });
  payload.api_key = apiKey;

  els.testModelConnection.disabled = true;
  renderModelConnectionResult(t("testingModelConnection"), null);
  setStatus(t("testingModelConnection"));
  try {
    const result = await api("/api/models/test", { method: "POST", body: JSON.stringify(payload) });
    renderModelConnectionResult(result.message, result.ok);
    setStatus(
      result.ok ? t("modelConnectionTestPassed") : t("modelConnectionTestFailed"),
      result.ok ? "ok" : "error",
    );
  } catch (error) {
    renderModelConnectionResult(error.message, false);
    showError(error);
  } finally {
    els.testModelConnection.disabled = false;
  }
}

export function editModel(model) {
  state.editingModelId = model.id;
  els.modelDisplayName.value = model.name;
  els.modelProvider.value = model.provider;
  els.modelBaseUrl.value = model.base_url;
  els.modelApiKey.value = "";
  els.modelApiKey.required = false;
  els.modelName.value = model.model_name;
  els.modelTemperature.value = model.temperature;
  els.modelMaxContext.value = model.max_context_tokens;
  setStatus(t("modelEditing", { name: model.name }), "ok");
}

export async function activateModel(id) {
  try {
    await api(`/api/models/${id}/activate`, { method: "POST" });
    await loadModels();
    setStatus(t("modelActivated"), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function deleteModel(id) {
  try {
    await api(`/api/models/${id}`, { method: "DELETE" });
    if (state.editingModelId === id) {
      resetModelForm();
    }
    await loadModels();
    setStatus(t("modelDeleted"), "ok");
  } catch (error) {
    showError(error);
  }
}

export function resetModelForm() {
  state.editingModelId = null;
  els.modelForm.reset();
  els.modelProvider.value = "openai_compatible";
  els.modelTemperature.value = "0.7";
  els.modelMaxContext.value = "4096";
  els.modelApiKey.required = true;
  renderModelConnectionResult("", null);
}

export function renderModelList() {
  if (!els.modelList) {
    return;
  }
  els.modelList.replaceChildren();
  if (!state.models.length) {
    els.modelList.append(emptyNode(t("noModelsYet")));
    return;
  }
  state.models.forEach((model) => {
    const item = document.createElement("div");
    item.className = `list-item model-item ${model.is_active ? "active" : ""}`;

    const body = document.createElement("button");
    body.type = "button";
    body.className = "model-summary";
    body.innerHTML = `<span class="item-title"></span><span class="item-meta"></span>`;
    body.querySelector(".item-title").textContent = model.name;
    body.querySelector(".item-meta").textContent = `${model.model_name} | ${model.is_active ? t("activeModel") : t("inactiveModel")} | ${model.api_key_masked}`;
    body.addEventListener("click", () => editModel(model));

    const actions = document.createElement("div");
    actions.className = "model-actions";
    const activate = document.createElement("button");
    activate.type = "button";
    activate.className = "secondary";
    activate.textContent = t("activateModel");
    activate.disabled = model.is_active;
    activate.addEventListener("click", () => activateModel(model.id));
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "secondary";
    edit.textContent = t("editModel");
    edit.addEventListener("click", () => editModel(model));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.textContent = t("deleteModel");
    remove.addEventListener("click", () => deleteModel(model.id));
    actions.append(activate, edit, remove);
    item.append(body, actions);
    els.modelList.append(item);
  });
}

function modelFormPayload({ includeExistingModelId = false, fallbackName = "" } = {}) {
  const payload = {
    name: els.modelDisplayName.value.trim() || fallbackName,
    provider: els.modelProvider.value,
    base_url: els.modelBaseUrl.value.trim(),
    model_name: els.modelName.value.trim(),
    temperature: numberOrDefault(els.modelTemperature.value, 0.7),
    max_context_tokens: numberOrDefault(els.modelMaxContext.value, 4096),
  };
  if (includeExistingModelId && state.editingModelId) {
    payload.existing_model_id = state.editingModelId;
  }
  return payload;
}

function renderModelConnectionResult(message, ok) {
  if (!els.modelConnectionResult) {
    return;
  }
  els.modelConnectionResult.textContent = message;
  els.modelConnectionResult.className = ok === null
    ? "model-test-result"
    : `model-test-result ${ok ? "ok" : "error"}`;
}
