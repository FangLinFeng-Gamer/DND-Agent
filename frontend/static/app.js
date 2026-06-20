import { api } from "./js/api.js?v=20260620-isekai-events";
import { bindElements, els, state } from "./js/state.js?v=20260620-isekai-events";
import { applyTranslations, setLocale, t } from "./js/i18n.js?v=20260620-isekai-events";
import { renderCapabilities, setStatus, showError, showView, viewFromPath } from "./js/ui.js?v=20260620-isekai-events";
import {
  deleteAdventure,
  getSelectedCharacter,
  loadAdventures,
  createAdventure,
  createIsekaiAdventure,
  renderAdventureDetail,
  renderAdventureList,
  renderGameModeSetup,
  renderCharacter,
  renderCharacterList,
  renderMapAssets,
  renderMapPreview,
  renderMapScenes,
  renderMapTokens,
  renderRules,
  searchRules,
  selectAdventure,
  setSelectedGameMode,
  sendIsekaiMessage,
  sendMessage,
  performCombatAction,
  endCombat,
  loadCharacters,
  loadMapAssets,
  loadMapScenes,
  loadStoryMapScenes,
  uploadMapAsset,
  createMapScene,
  syncMapTokens,
} from "./js/game.js?v=20260620-isekai-events";
import {
  confirmCharacterCreation,
  ensureCharacterCreationSession,
  renderCharacterCreation,
  sendCharacterCreationMessage,
} from "./js/character-creation.js?v=20260620-isekai-events";
import {
  createStory,
  loadStories,
  renderGameStoryChoices,
  renderHomeStorySummary,
  renderStoryList,
  renderStorySelect,
  resetStoryForm,
} from "./js/stories.js?v=20260620-isekai-events";
import { loadModels, renderModelList, resetModelForm, saveModel, testModelConnection } from "./js/models.js?v=20260620-isekai-events";
import { loadRaces, renderRaceDetail, renderRaceList, renderRaceOptions } from "./js/races.js?v=20260620-isekai-events";
import { initDiceTray, renderDiceTray } from "./js/dice.js?v=20260620-isekai-events";

async function loadCapabilities() {
  try {
    state.capabilities = await api("/api/system/capabilities");
    renderCapabilities();
    setStatus(t("capabilitiesLoaded"), "ok");
  } catch (error) {
    setStatus(t("capabilitiesUnavailable"), "error");
  }
}

function renderLocalizedViews() {
  renderCapabilities();
  renderStorySelect();
  renderStoryList();
  renderGameStoryChoices();
  renderHomeStorySummary();
  renderModelList();
  renderRaceOptions();
  renderRaceList();
  renderRaceDetail();
  renderCharacterList();
  renderCharacter(getSelectedCharacter());
  renderAdventureList();
  renderGameModeSetup();
  renderAdventureDetail();
  renderMapAssets();
  renderMapScenes();
  renderMapPreview();
  renderMapTokens();
  renderCharacterCreation();
  renderDiceTray();
  if (state.lastRules) {
    renderRules(state.lastRules);
  }
}

async function openView(view, options = {}) {
  if (view === "game" && options.forceSetup) {
    state.gameMode = "setup";
    state.selectedAdventureId = null;
    state.selectedAdventure = null;
    state.routeAdventureId = null;
    state.combat = null;
    state.selectedGameMode = "dnd";
  }
  showView(view, options);
  if (view === "character-create") {
    await ensureCharacterCreationSession();
  }
  if (view === "story-create") {
    await loadStoryMapScenes();
  }
  if (view === "game") {
    renderAdventureDetail();
  }
}

function wireEvents() {
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      await openView(button.dataset.viewTarget, { forceSetup: button.dataset.viewTarget === "game" });
    });
  });
  window.addEventListener("popstate", async () => {
    await openView(viewFromPath(window.location.pathname), { updateUrl: false });
  });
  els.languageSelect.addEventListener("change", (event) => {
    setLocale(event.target.value);
    renderLocalizedViews();
    setStatus(t("languageChanged"), "ok");
  });
  els.storyForm.addEventListener("submit", (event) => {
    event.preventDefault();
    createStory();
  });
  els.cancelStoryEdit.addEventListener("click", resetStoryForm);
  els.storySelect.addEventListener("change", (event) => {
    state.selectedStoryId = event.target.value;
    renderStoryList();
    renderGameStoryChoices();
    renderHomeStorySummary();
    renderAdventureDetail();
    loadStoryMapScenes();
  });
  document.addEventListener("dnd-agent:story-selection-changed", async () => {
    renderAdventureDetail();
    await loadStoryMapScenes();
  });
  document.addEventListener("dnd-agent:story-map-context-changed", () => loadStoryMapScenes());
  els.modelForm.addEventListener("submit", (event) => {
    event.preventDefault();
    saveModel();
  });
  els.refreshModels.addEventListener("click", loadModels);
  els.resetModelForm.addEventListener("click", resetModelForm);
  els.testModelConnection.addEventListener("click", testModelConnection);
  els.characterForm.addEventListener("submit", (event) => {
    event.preventDefault();
  });
  els.characterAgentForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendCharacterCreationMessage();
  });
  els.characterAgentInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendCharacterCreationMessage();
    }
  });
  els.characterConfirm.addEventListener("click", confirmCharacterCreation);
  els.adventureForm.addEventListener("submit", (event) => {
    event.preventDefault();
    createAdventure();
  });
  els.gameModeSwitch.addEventListener("click", (event) => {
    const button = event.target.closest("[data-game-mode]");
    if (button) {
      setSelectedGameMode(button.dataset.gameMode);
    }
  });
  els.isekaiAdventureForm.addEventListener("submit", (event) => {
    event.preventDefault();
    createIsekaiAdventure();
  });
  els.messageForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage();
  });
  els.isekaiMessageForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendIsekaiMessage();
  });
  els.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (state.dmBusy) {
        setStatus(t("dmStillResponding"), "error");
        return;
      }
      sendMessage();
    }
  });
  els.isekaiMessageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (state.dmBusy) {
        setStatus(t("dmStillResponding"), "error");
        return;
      }
      sendIsekaiMessage();
    }
  });
  els.combatActionAttack.addEventListener("click", () => performCombatAction("attack"));
  els.combatActionDodge.addEventListener("click", () => performCombatAction("dodge"));
  els.combatActionDash.addEventListener("click", () => performCombatAction("dash"));
  els.combatActionDisengage.addEventListener("click", () => performCombatAction("disengage"));
  els.endCombat.addEventListener("click", endCombat);
  els.rulesForm.addEventListener("submit", (event) => {
    event.preventDefault();
    searchRules();
  });
  els.mapUploadForm.addEventListener("submit", (event) => {
    event.preventDefault();
    uploadMapAsset();
  });
  els.mapSceneForm.addEventListener("submit", (event) => {
    event.preventDefault();
    createMapScene();
  });
  els.refreshCharacters.addEventListener("click", loadCharacters);
  els.refreshCharactersCreate.addEventListener("click", loadCharacters);
  els.refreshAdventures.addEventListener("click", loadAdventures);
  els.refreshStories.addEventListener("click", loadStories);
  els.refreshRaces.addEventListener("click", loadRaces);
  els.refreshMaps.addEventListener("click", async () => {
    await loadMapAssets();
    await loadMapScenes();
  });
  els.refreshStoryMaps.addEventListener("click", async () => {
    await loadMapAssets();
    await loadStoryMapScenes();
  });
  els.syncMapTokens.addEventListener("click", () => syncMapTokens());
}

document.addEventListener("DOMContentLoaded", async () => {
  bindElements();
  applyTranslations();
  wireEvents();
  initDiceTray();
  setStatus(t("loadingAppData"));
  state.view = viewFromPath(window.location.pathname);
  await openView(state.view, { replace: true });
  await Promise.all([loadCapabilities(), loadRaces(), loadStories(), loadModels(), loadCharacters(), loadAdventures(), loadMapAssets()]);
  renderAdventureDetail();
});
