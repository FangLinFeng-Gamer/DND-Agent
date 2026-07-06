import { api } from "./api.js?v=20260706-isekai-vitals";
import { els, state } from "./state.js?v=20260706-isekai-vitals";
import { t } from "./i18n.js?v=20260706-isekai-vitals";
import { emptyNode, setStatus, showError, showView } from "./ui.js?v=20260706-isekai-vitals";

export async function loadStories() {
  try {
    state.stories = await api("/api/stories");
    if (!state.stories.some((story) => story.id === state.selectedStoryId)) {
      state.selectedStoryId = state.stories[0]?.id || "mistbell_tower";
    }
    renderStorySelect();
    renderStoryList();
    renderGameStoryChoices();
    renderHomeStorySummary();
    setStatus(t("storiesLoaded"), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function createStory() {
  const payload = storyPayloadFromForm();
  if (!payload) {
    return;
  }

  try {
    if (state.editingStoryId) {
      const story = await api(`/api/stories/${state.editingStoryId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      state.selectedStoryId = story.id;
      populateStoryForm(story);
      await loadStories();
      document.dispatchEvent(new Event("dnd-agent:story-map-context-changed"));
      setStatus(t("storyUpdated", { title: story.title }), "ok");
      return;
    }

    const story = await api("/api/stories", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.selectedStoryId = story.id;
    state.editingStoryId = story.id;
    populateStoryForm(story);
    await loadStories();
    setStatus(t("storyCreated", { title: story.title }), "ok");
    document.dispatchEvent(new Event("dnd-agent:story-map-context-changed"));
    showView("story-create");
  } catch (error) {
    showError(error);
  }
}

export function storyPayloadFromForm() {
  const title = els.storyTitle.value.trim();
  if (!title) {
    setStatus(t("storyTitleRequired"), "error");
    return null;
  }

  return {
    title,
    description: els.storyDescription.value.trim(),
    world_background: els.storyWorldBackground.value.trim(),
    main_quest: els.storyMainQuest.value.trim(),
    opening_location: els.storyOpeningLocation.value.trim(),
    opening_environment: els.storyOpeningEnvironment.value.trim(),
    opening_objective: els.storyOpeningObjective.value.trim(),
    important_objects: [],
    npcs: [],
  };
}

export function resetStoryForm() {
  state.editingStoryId = null;
  els.storyForm.reset();
  els.storyFormTitle.textContent = t("createStory");
  els.cancelStoryEdit.classList.add("hidden");
  document.dispatchEvent(new Event("dnd-agent:story-map-context-changed"));
}

export async function editStory(story) {
  if (story.id === "mistbell_tower") {
    setStatus(t("defaultStoryCannotModify"), "error");
    return;
  }
  state.editingStoryId = story.id;
  state.selectedStoryId = story.id;
  populateStoryForm(story);
  renderStorySelect();
  renderStoryList();
  renderGameStoryChoices();
  renderHomeStorySummary();
  document.dispatchEvent(new Event("dnd-agent:story-map-context-changed"));
  setStatus(t("storyEditing", { title: story.title }), "ok");
  showView("story-create");
}

export function renderStorySelect() {
  if (!els.storySelect) {
    return;
  }
  els.storySelect.replaceChildren();
  state.stories.forEach((story) => {
    const option = document.createElement("option");
    option.value = story.id;
    option.textContent = localizedStoryText(story, "title");
    option.selected = story.id === state.selectedStoryId;
    els.storySelect.append(option);
  });
}

export function renderStoryList() {
  if (!els.storyList) {
    return;
  }
  els.storyList.replaceChildren();
  if (!state.stories.length) {
    els.storyList.append(emptyNode(t("noStoriesYet")));
    return;
  }
  state.stories.forEach((story) => {
    const item = document.createElement("div");
    item.className = `list-item ${story.id === state.selectedStoryId ? "active" : ""}`;
    const summary = document.createElement("button");
    summary.type = "button";
    summary.className = "item-summary";
    summary.innerHTML = `<span class="item-title"></span><span class="item-meta"></span>`;
    summary.querySelector(".item-title").textContent = localizedStoryText(story, "title");
    summary.querySelector(".item-meta").textContent =
      localizedStoryText(story, "description") || localizedStoryText(story, "opening_location");
    summary.addEventListener("click", () => {
      state.selectedStoryId = story.id;
      renderStorySelect();
      renderStoryList();
      renderGameStoryChoices();
      renderHomeStorySummary();
      resetGameSetupMode();
      document.dispatchEvent(new Event("dnd-agent:story-selection-changed"));
      showView("game");
    });
    const actions = document.createElement("div");
    actions.className = "item-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "secondary";
    edit.textContent = t("editStory");
    edit.disabled = story.id === "mistbell_tower";
    if (edit.disabled) {
      edit.title = t("defaultStoryCannotModify");
    }
    edit.addEventListener("click", () => editStory(story));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.textContent = t("deleteStory");
    remove.disabled = story.id === "mistbell_tower";
    if (remove.disabled) {
      remove.title = t("defaultStoryCannotDelete");
    }
    remove.addEventListener("click", () => deleteStory(story.id));
    actions.append(edit, remove);
    item.append(summary, actions);
    els.storyList.append(item);
  });
}

export function renderGameStoryChoices() {
  if (!els.gameStoryChoiceList) {
    return;
  }
  els.gameStoryChoiceList.replaceChildren();
  if (!state.stories.length) {
    els.gameStoryChoiceList.append(emptyNode(t("noStoriesYet")));
    return;
  }
  state.stories.forEach((story) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `choice-card story-choice-card ${story.id === state.selectedStoryId ? "selected" : ""}`;
    card.setAttribute("role", "listitem");
    card.innerHTML = `
      <span class="choice-card-kicker"></span>
      <strong></strong>
      <span class="choice-card-body"></span>
      <span class="choice-card-footer"></span>
    `;
    card.querySelector(".choice-card-kicker").textContent = story.id === "mistbell_tower" ? t("defaultStory") : t("story");
    card.querySelector("strong").textContent = localizedStoryText(story, "title");
    card.querySelector(".choice-card-body").textContent =
      localizedStoryText(story, "description") || localizedStoryText(story, "world_background");
    card.querySelector(".choice-card-footer").textContent =
      localizedStoryText(story, "opening_location") || localizedStoryText(story, "main_quest");
    card.addEventListener("click", () => {
      state.selectedStoryId = story.id;
      renderStorySelect();
      renderStoryList();
      renderGameStoryChoices();
      renderHomeStorySummary();
      document.dispatchEvent(new Event("dnd-agent:story-selection-changed"));
    });
    els.gameStoryChoiceList.append(card);
  });
}

export async function deleteStory(id) {
  if (id === "mistbell_tower") {
    setStatus(t("defaultStoryCannotDelete"), "error");
    return;
  }
  try {
    await api(`/api/stories/${id}`, { method: "DELETE" });
    if (state.selectedStoryId === id) {
      state.selectedStoryId = "mistbell_tower";
    }
    if (state.editingStoryId === id) {
      resetStoryForm();
    }
    await loadStories();
    setStatus(t("storyDeleted"), "ok");
  } catch (error) {
    showError(error);
  }
}

export function renderHomeStorySummary() {
  if (!els.homeStorySummary) {
    return;
  }
  const story = state.stories.find((item) => item.id === state.selectedStoryId) || state.stories[0];
  els.homeStorySummary.replaceChildren();
  if (!story) {
    els.homeStorySummary.append(emptyNode(t("noStoriesYet")));
    return;
  }
  const title = document.createElement("strong");
  title.textContent = localizedStoryText(story, "title");
  const background = document.createElement("p");
  background.textContent = localizedStoryText(story, "world_background");
  const quest = document.createElement("p");
  quest.textContent = localizedStoryText(story, "main_quest");
  els.homeStorySummary.append(title, background, quest);
}

export function localizedStoryText(story, field) {
  if (!story) {
    return "";
  }
  if (story.id === "mistbell_tower") {
    const key = {
      title: `defaultStoryTitle.${story.id}`,
      description: `defaultStoryDescription.${story.id}`,
      world_background: `defaultStoryBackground.${story.id}`,
      main_quest: `defaultStoryQuest.${story.id}`,
      opening_location: `defaultStoryOpeningLocation.${story.id}`,
    }[field];
    if (key) {
      const localized = t(key);
      if (localized !== key) {
        return localized;
      }
    }
  }
  return story[field] || "";
}

function resetGameSetupMode() {
  state.gameMode = "setup";
  state.routeAdventureId = null;
  state.selectedAdventureId = null;
  state.selectedAdventure = null;
}

function populateStoryForm(story) {
  state.editingStoryId = story.id;
  els.storyTitle.value = story.title;
  els.storyDescription.value = story.description || "";
  els.storyWorldBackground.value = story.world_background;
  els.storyMainQuest.value = story.main_quest;
  els.storyOpeningLocation.value = story.opening_location;
  els.storyOpeningEnvironment.value = story.opening_environment;
  els.storyOpeningObjective.value = story.opening_objective;
  els.storyFormTitle.textContent = t("storyEditing", { title: story.title });
  els.cancelStoryEdit.classList.remove("hidden");
}
