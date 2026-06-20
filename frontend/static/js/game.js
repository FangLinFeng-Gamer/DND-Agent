import { api, readErrorMessage, readStreamingResponse } from "./api.js?v=20260619-world-state-progress";
import { apiBase, els, state } from "./state.js?v=20260619-world-state-progress";
import { localizeCombatAction, localizeEquipmentName, localizeRole, localizeSide, localizeStatus, localizeWorldMessage, t } from "./i18n.js?v=20260619-world-state-progress";
import { localizedStoryText } from "./stories.js?v=20260619-world-state-progress";
import { emptyNode, pillNode, setStatus, showError, showView, statNode, typingIndicatorNode } from "./ui.js?v=20260619-world-state-progress";

export async function loadCharacters() {
  try {
    state.characters = await api("/api/characters");
    if (!state.selectedCharacterId && state.characters.length) {
      state.selectedCharacterId = state.characters[0].id;
    }
    if (!state.selectedPartyCharacterIds.length && state.selectedCharacterId) {
      state.selectedPartyCharacterIds = [state.selectedCharacterId];
    }
    state.selectedPartyCharacterIds = state.selectedPartyCharacterIds.filter((id) =>
      state.characters.some((character) => character.id === id),
    );
    if (state.selectedCharacterId && !state.characters.some((character) => character.id === state.selectedCharacterId)) {
      state.selectedCharacterId = state.characters[0]?.id || null;
    }
    renderCharacterList();
    renderCharacter(getSelectedCharacter());
    setStatus(t("charactersLoaded"), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function loadAdventures() {
  try {
    state.adventures = await api("/api/adventures");
    renderAdventureList();
    if (state.selectedAdventureId) {
      const exists = state.adventures.some((adventure) => adventure.id === state.selectedAdventureId);
      if (exists) {
        await selectAdventure(state.selectedAdventureId);
      } else {
        state.selectedAdventureId = null;
        state.selectedAdventure = null;
        state.gameMode = "setup";
        renderAdventureDetail();
      }
    }
    setStatus(t("adventuresLoaded"), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function createAdventure() {
  const partyIds = selectedPartyCharacterIds();
  const title = els.adventureTitle.value.trim();
  if (!partyIds.length) {
    setStatus(t("selectOrCreateCharacterFirst"), "error");
    return;
  }
  if (partyIds.length > 6) {
    setStatus(t("partySizeLimitError"), "error");
    return;
  }
  if (!title) {
    setStatus(t("adventureTitleRequired"), "error");
    return;
  }

  try {
    const adventure = await api("/api/adventures", {
      method: "POST",
      body: JSON.stringify({
        title,
        character_id: partyIds[0],
        party_character_ids: partyIds,
        story_id: state.selectedStoryId,
        locale: state.locale,
      }),
    });
    state.selectedAdventureId = adventure.id;
    state.gameMode = "room";
    await loadAdventures();
    await selectAdventure(adventure.id);
    setStatus(t("createdAdventure", { title: adventure.title }), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function selectAdventure(id, options = {}) {
  try {
    state.selectedAdventureId = Number(id);
    state.gameMode = "room";
    state.selectedAdventure = await api(`/api/adventures/${state.selectedAdventureId}`);
    state.selectedPartyCharacterIds = [...(state.selectedAdventure.party_character_ids || [state.selectedAdventure.character_id])];
    state.combat = await loadCombatState(state.selectedAdventureId);
    selectCurrentCombatantForRoom();
    state.combatResult = null;
    await loadMapScenes(state.selectedAdventureId);
    renderAdventureList();
    renderCharacter(getSelectedCharacter());
    renderAdventureDetail();
    showView("game", { updateUrl: options.updateUrl !== false, replace: Boolean(options.replace) });
    setStatus(t("selected", { title: state.selectedAdventure.title }), "ok");
    await resolveNpcTurns();
  } catch (error) {
    showError(error);
  }
}

export async function sendMessage() {
  if (state.dmBusy) {
    setStatus(t("dmStillResponding"), "error");
    return;
  }
  const content = els.messageInput.value.trim();
  if (!state.selectedAdventureId) {
    setStatus(t("selectAdventureBeforeSending"), "error");
    return;
  }
  if (!content) {
    setStatus(t("messageContentRequired"), "error");
    return;
  }

  const currentMessages = state.selectedAdventure?.messages || [];
  const pendingDm = {
    id: `pending-dm-${Date.now()}`,
    adventure_id: state.selectedAdventureId,
    role: "dm",
    content: "",
    metadata: { pending: true },
    created_at: "",
  };
  const optimisticMessages = [
    ...currentMessages,
    {
      id: `pending-player-${Date.now()}`,
      adventure_id: state.selectedAdventureId,
      role: "player",
      content,
      metadata: {},
      created_at: "",
    },
    pendingDm,
  ];
  renderMessages(optimisticMessages);
  setDmBusy(true);
  setStatus(t("dmThinking"));

  try {
    const response = await readStreamingResponse(
      state.selectedAdventureId,
      content,
      state.locale,
      (delta) => {
        pendingDm.content += delta;
        pendingDm.metadata.pending = !pendingDm.content;
        renderMessages(optimisticMessages);
      },
      { characterId: getSelectedCharacter()?.id },
    );
    els.messageInput.value = "";
    state.selectedAdventure = response.adventure;
    state.combat = response.combat_state;
    renderAdventureDetail(response.messages, response.scene, response.combat_state);
    setStatus(t("messageSent"), "ok");
    await resolveNpcTurns();
  } catch (error) {
    showError(error);
    if (!readErrorMessage(error.payload)) {
      setStatus(t("dmResponseFailed"), "error");
    }
  } finally {
    setDmBusy(false);
  }
}

export function setDmBusy(isBusy) {
  state.dmBusy = isBusy;
  els.messageInput.disabled = isBusy;
  els.messageSend.disabled = isBusy;
  els.messageForm.classList.toggle("busy", isBusy);
}

export async function loadCombatState(adventureId = state.selectedAdventureId) {
  if (!adventureId) {
    return null;
  }
  return await api(`/api/adventures/${adventureId}/combat`);
}

async function refreshSelectedAdventureState() {
  if (!state.selectedAdventureId) {
    return null;
  }
  state.selectedAdventure = await api(`/api/adventures/${state.selectedAdventureId}`);
  return state.selectedAdventure;
}

function readErrorCode(payload) {
  return payload?.detail?.error?.code || "";
}

export async function performCombatAction(actionType) {
  if (!state.selectedAdventureId || !state.combat?.is_active) {
    setStatus(t("selectAdventureBeforeCombat"), "error");
    return;
  }

  const actor = currentCombatant(state.combat);
  if (!actor) {
    setStatus(t("noCombatState"), "error");
    return;
  }
  if (!isPlayerCombatTurn(state.combat)) {
    setStatus(t("combatPlayerTurnOnly"), "error");
    await resolveNpcTurns();
    return;
  }
  if (!canCombatantAct(actor)) {
    setStatus(t("combatActorCannotAct"), "error");
    return;
  }

  const payload = {
    actor_name: actor.name,
    action_type: actionType,
  };
  if (actionType === "attack") {
    const target = firstHostileTarget(state.combat, actor);
    if (!target) {
      setStatus(t("combatActionNeedsTarget"), "error");
      return;
    }
    payload.target_name = target.name;
  }

  try {
    const result = await api(`/api/adventures/${state.selectedAdventureId}/combat/action`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.combat = result.state;
    state.combatResult = result;
    await refreshSelectedAdventureState();
    selectCurrentCombatantForRoom({ onlyIfMissing: true });
    renderCharacter(getSelectedCharacter());
    renderCombat(state.combat);
    await loadMapTokens();
    setStatus(t("combatActionResolved", { action: localizeCombatAction(actionType) }), "ok");
    await resolveNpcTurns();
  } catch (error) {
    showError(error);
  }
}

export async function resolveNpcTurns(maxTurns = 12) {
  if (!state.selectedAdventureId || state.combatNpcBusy || !isNpcCombatTurn(state.combat)) {
    return;
  }
  state.combatNpcBusy = true;
  let resolvedCount = 0;
  try {
    while (isNpcCombatTurn(state.combat) && resolvedCount < maxTurns) {
      const actor = currentCombatant(state.combat);
      setStatus(t("combatNpcThinking", { name: actor?.name || "-" }));
      setCombatControlsEnabled(false);
      const result = await api(`/api/adventures/${state.selectedAdventureId}/combat/npc-turn`, {
        method: "POST",
        body: JSON.stringify({ locale: state.locale }),
      });
      state.combat = result.state;
      state.combatResult = result;
      await refreshSelectedAdventureState();
      selectCurrentCombatantForRoom({ onlyIfMissing: true });
      renderCharacter(getSelectedCharacter());
      renderCombat(state.combat);
      await loadMapTokens();
      setStatus(t("combatNpcResolved", { name: actor?.name || "-" }), "ok");
      resolvedCount += 1;
    }
  } catch (error) {
    showError(error);
  } finally {
    state.combatNpcBusy = false;
    renderCombat(state.combat);
  }
}

export async function endCombat() {
  if (!state.selectedAdventureId || !state.combat?.is_active) {
    setStatus(t("noCombatState"), "error");
    return;
  }

  try {
    state.combat = await api(`/api/adventures/${state.selectedAdventureId}/combat/end`, { method: "POST" });
    state.combatResult = null;
    await refreshSelectedAdventureState();
    selectCurrentCombatantForRoom({ onlyIfMissing: true });
    renderCharacter(getSelectedCharacter());
    renderCombat(state.combat);
    await loadMapTokens();
    setStatus(t("combatEnded"), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function searchRules() {
  const query = els.rulesQuery.value.trim();
  const url = query ? `/api/world/search?query=${encodeURIComponent(query)}` : "/api/world/search";

  try {
    const result = await api(url);
    state.lastRules = result;
    renderRules(result);
    setStatus(localizeWorldMessage(result.message) || t("rulesSearchComplete"), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function loadMapAssets() {
  try {
    state.mapAssets = await api("/api/map-assets?asset_type=map");
    if (state.selectedMapAssetId && !state.mapAssets.some((asset) => asset.id === state.selectedMapAssetId)) {
      state.selectedMapAssetId = null;
    }
    if (!state.selectedMapAssetId && state.mapAssets.length) {
      state.selectedMapAssetId = state.mapAssets[0].id;
    }
    renderMapAssets();
  } catch (error) {
    showError(error);
  }
}

export async function loadMapScenes(adventureId = state.selectedAdventureId) {
  if (!adventureId) {
    state.mapScenes = [];
    state.selectedMapSceneId = null;
    state.mapTokens = [];
    state.selectedMapTokenId = null;
    renderMapScenes();
    renderMapTokens();
    renderMapPreview(null);
    return;
  }
  try {
    state.mapScenes = await api(`/api/map-scenes?adventure_id=${encodeURIComponent(adventureId)}`);
    const activeScene = state.mapScenes.find((scene) => scene.active);
    if (activeScene) {
      state.selectedMapSceneId = activeScene.id;
    } else if (state.selectedMapSceneId && !state.mapScenes.some((scene) => scene.id === state.selectedMapSceneId)) {
      state.selectedMapSceneId = null;
    }
    await loadMapTokens(state.selectedMapSceneId, { render: false });
    renderMapScenes();
    renderMapPreview(getSelectedMapScene());
  } catch (error) {
    showError(error);
  }
}

export async function uploadMapAsset() {
  const file = els.mapUploadFile?.files?.[0];
  if (!file) {
    setStatus(t("mapFileRequired"), "error");
    return;
  }
  try {
    const asset = await postMapAssetFile(file);
    state.selectedMapAssetId = asset.id;
    els.mapUploadFile.value = "";
    await loadMapAssets();
    setStatus(t("mapUploaded", { name: asset.name }), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function createMapScene() {
  const storyId = currentMapStoryId();
  if (!storyId) {
    showMapNotice("selectStoryBeforeMap", "error");
    setStatus(t("selectStoryBeforeMap"), "error");
    return;
  }
  const asset = getSelectedMapAsset();
  if (!asset) {
    showMapNotice("selectMapAssetFirst", "error");
    setStatus(t("selectMapAssetFirst"), "error");
    return;
  }
  const name = els.mapSceneName.value.trim() || asset.name;
  try {
    const scene = await api("/api/map-scenes", {
      method: "POST",
      body: JSON.stringify({
        name,
        story_id: storyId,
        background_asset_id: asset.id,
        grid_type: "square",
        grid_size: 70,
        scale: 5,
        scale_unit: "ft",
      }),
    });
    state.selectedMapSceneId = scene.id;
    els.mapSceneName.value = "";
    await loadStoryMapScenes(storyId);
    showMapNotice("mapSceneCreated", "ok", { name: scene.name });
    setStatus(t("mapSceneCreated", { name: scene.name }), "ok");
  } catch (error) {
    showError(error);
  }
}

export async function activateMapScene(sceneId) {
  try {
    const scene = await api(`/api/map-scenes/${sceneId}/activate`, { method: "POST" });
    state.selectedMapSceneId = scene.id;
    if (scene.adventure_id) {
      await loadMapScenes(scene.adventure_id || state.selectedAdventureId);
    } else {
      await loadStoryMapScenes(scene.story_id || currentMapStoryId());
    }
    if (state.combat?.is_active) {
      await syncMapTokens(scene.id, { quiet: true });
    }
    setStatus(t("mapSceneActivated", { name: scene.name }), "ok");
  } catch (error) {
    showError(error);
  }
}

export function showMapNotice(key, tone = "info", values = {}) {
  if (!els.mapActionMessage) {
    return;
  }
  els.mapActionMessage.textContent = t(key, values);
  els.mapActionMessage.className = `map-action-message ${tone}`;
}

export async function loadMapTokens(sceneId = state.selectedMapSceneId, options = {}) {
  if (!sceneId) {
    state.mapTokens = [];
    state.selectedMapTokenId = null;
    if (options.render !== false) {
      renderMapTokens();
      renderMapPreview(getSelectedMapScene());
    }
    return [];
  }
  try {
    state.mapTokens = await api(`/api/map-scenes/${sceneId}/combat-tokens`);
    if (state.selectedMapTokenId && !state.mapTokens.some((token) => token.id === state.selectedMapTokenId)) {
      state.selectedMapTokenId = null;
    }
    if (!state.selectedMapTokenId && state.mapTokens.length) {
      state.selectedMapTokenId = state.mapTokens[0].id;
    }
    if (options.render !== false) {
      renderMapTokens();
      renderMapPreview(getSelectedMapScene());
    }
    return state.mapTokens;
  } catch (error) {
    showError(error);
    return [];
  }
}

export async function syncMapTokens(sceneId = state.selectedMapSceneId, options = {}) {
  if (!sceneId) {
    setStatus(t("noMapSceneSelected"), "error");
    return [];
  }
  try {
    state.mapTokens = await api(`/api/map-scenes/${sceneId}/combat-tokens/sync`, { method: "POST" });
    if (state.selectedMapTokenId && !state.mapTokens.some((token) => token.id === state.selectedMapTokenId)) {
      state.selectedMapTokenId = null;
    }
    if (!state.selectedMapTokenId && state.mapTokens.length) {
      state.selectedMapTokenId = state.mapTokens[0].id;
    }
    renderMapTokens();
    renderMapPreview(getSelectedMapScene());
    if (!options.quiet) {
      setStatus(t("mapTokensSynced"), "ok");
    }
    return state.mapTokens;
  } catch (error) {
    showError(error);
    return [];
  }
}

export async function moveMapToken(tokenId, x, y) {
  const sceneId = state.selectedMapSceneId;
  if (!sceneId || !tokenId) {
    setStatus(t("selectMapTokenFirst"), "error");
    return null;
  }
  try {
    const token = await api(`/api/map-scenes/${sceneId}/combat-tokens/${tokenId}`, {
      method: "PATCH",
      body: JSON.stringify({ x, y }),
    });
    state.mapTokens = state.mapTokens.map((entry) => entry.id === token.id ? token : entry);
    state.selectedMapTokenId = token.id;
    renderMapTokens();
    renderMapPreview(getSelectedMapScene());
    setStatus(t("mapTokenMoved", { name: token.participant_name }), "ok");
    return token;
  } catch (error) {
    showError(error);
    return null;
  }
}

async function postMapAssetFile(file) {
  const params = new URLSearchParams({
    asset_type: "map",
    name: assetNameFromFile(file.name),
    filename: file.name,
  });
  const response = await fetch(`${apiBase}/api/map-assets?${params}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": file.type || "application/octet-stream",
    },
    body: await file.arrayBuffer(),
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(readErrorMessage(payload) || `Request failed with ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function assetNameFromFile(filename) {
  return filename.replace(/\.[^.]+$/, "").trim() || filename;
}

export function renderMessages(messages = []) {
  els.messages.replaceChildren();
  if (!messages.length) {
    els.messages.append(emptyNode(t("noMessagesYet")));
    return;
  }

  messages.forEach((message) => {
    const article = document.createElement("article");
    article.className = `message ${message.role === "player" ? "player" : "dm"}`;

    const role = document.createElement("span");
    role.className = "message-role";
    role.textContent = localizeRole(message.role);

    const content = document.createElement("p");
    if (message.metadata?.pending && !message.content) {
      content.append(typingIndicatorNode());
    } else {
      content.textContent = message.content;
    }

    article.append(role, content);
    els.messages.append(article);
  });
  els.messages.scrollTop = els.messages.scrollHeight;
}

export function renderCharacter(character) {
  els.characterDetail.replaceChildren();
  const party = roomPartyCharacters();
  if (party.length) {
    character = party.find((member) => member.id === state.selectedCharacterId) || character || party[0];
    state.selectedCharacterId = character.id;
  }
  if (!character) {
    els.characterDetail.className = "detail-empty";
    els.characterDetail.textContent = t("noCharacterSelected");
    return;
  }

  els.characterDetail.className = "character-card";
  const switcher = party.length > 1 ? characterSwitcher(party, character) : null;
  const title = document.createElement("strong");
  title.textContent = character.name;

  const meta = document.createElement("div");
  meta.className = "character-meta";
  meta.textContent = t("actorMetaLine", {
    level: character.level,
    race: character.race,
    className: character.class_name,
  });

  const bars = document.createElement("div");
  bars.className = "bars";
  const xpDisplay = character.next_level_experience
    ? `${character.experience_points || 0}/${character.next_level_experience}`
    : `${character.experience_points || 0}`;
  bars.append(
    barRow("HP", character.hp_current, character.hp_max, `${character.hp_current}/${character.hp_max}`),
    barRow(t("xp"), Number(character.level_progress || 0), 1, xpDisplay),
    barRow("AC", character.armor_class, 20, character.armor_class),
  );

  const tabs = characterStatusTabs(character);
  els.characterDetail.append(...[switcher, title, meta, bars, tabs].filter(Boolean));
}

function barRow(label, value, max, displayValue) {
  const row = document.createElement("div");
  row.className = "bar-row";
  const labelNode = document.createElement("span");
  labelNode.textContent = label;
  const track = document.createElement("div");
  track.className = "bar-track";
  const fill = document.createElement("span");
  fill.className = "bar-fill";
  fill.style.width = `${boundedPercent(value, max)}%`;
  track.append(fill);
  const valueNode = document.createElement("b");
  valueNode.textContent = displayValue;
  row.append(labelNode, track, valueNode);
  return row;
}

function characterSwitcher(party, selectedCharacter) {
  const switcher = document.createElement("div");
  switcher.className = "character-switcher";
  party.forEach((member) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `character-switch ${member.id === selectedCharacter.id ? "active" : ""}`.trim();
    button.textContent = member.name;
    button.setAttribute("aria-pressed", member.id === selectedCharacter.id ? "true" : "false");
    button.addEventListener("click", () => {
      state.selectedCharacterId = member.id;
      renderCharacter(member);
      renderRoomParty();
    });
    switcher.append(button);
  });
  return switcher;
}

function characterStatusTabs(character) {
  const tabs = [
    ["overview", t("characterTabOverview")],
    ["attributes", t("characterTabAttributes")],
    ["equipment", t("characterTabEquipment")],
    ["inventory", t("characterTabInventory")],
    ["spells", t("characterTabSpells")],
  ];
  if (!tabs.some(([id]) => id === state.characterDetailTab)) {
    state.characterDetailTab = "overview";
  }

  const wrapper = document.createElement("div");
  wrapper.className = "character-status-tabs";
  const nav = document.createElement("div");
  nav.className = "character-tab-list";
  tabs.forEach(([id, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `character-tab ${state.characterDetailTab === id ? "active" : ""}`.trim();
    button.textContent = label;
    button.setAttribute("aria-pressed", state.characterDetailTab === id ? "true" : "false");
    button.addEventListener("click", () => {
      state.characterDetailTab = id;
      renderCharacter(character);
    });
    nav.append(button);
  });
  const panel = document.createElement("div");
  panel.className = "character-tab-panel";
  renderCharacterTabPanel(panel, character, state.characterDetailTab);
  wrapper.append(nav, panel);
  return wrapper;
}

function renderCharacterTabPanel(panel, character, tab) {
  if (tab === "attributes") {
    panel.append(characterStatsGrid(character), characterSkillsList(character));
    return;
  }
  if (tab === "equipment") {
    const equipment = (character.inventory || []).filter(isLikelyEquipmentEntry);
    panel.append(characterPillSection(t("characterTabEquipment"), equipment, t("noEquipment")));
    panel.append(characterPillSection(t("proficiencies"), proficiencyEntries(character.proficiencies), t("noProficiencies")));
    return;
  }
  if (tab === "inventory") {
    panel.append(characterPillSection(t("characterTabInventory"), character.inventory || [], t("noInventory")));
    return;
  }
  if (tab === "spells") {
    panel.append(characterPillSection(t("characterTabSpells"), character.spells || [], t("noSpells")));
    return;
  }

  const actor = matchingCombatParticipant(character);
  const overview = document.createElement("div");
  overview.className = "character-overview";
  overview.append(
    statNode("HP", `${character.hp_current}/${character.hp_max}`),
    statNode("AC", character.armor_class),
    statNode(t("xp"), character.next_level_experience ? `${character.experience_points}/${character.next_level_experience}` : character.experience_points),
  );
  if (actor) {
    overview.append(
      statNode("ATK", signed(actor.attack_bonus)),
      statNode(t("damage"), actor.damage || "-"),
    );
  }
  panel.append(overview);
  const conditions = actor?.conditions || [];
  panel.append(characterPillSection(t("conditions"), conditions, t("noConditions")));
}

function characterStatsGrid(character) {
  const stats = document.createElement("div");
  stats.className = "stat-grid";
  [
    ["STR", character.strength],
    ["DEX", character.dexterity],
    ["CON", character.constitution],
    ["INT", character.intelligence],
    ["WIS", character.wisdom],
    ["CHA", character.charisma],
  ].forEach(([label, value]) => stats.append(statNode(label, value ?? "-")));
  return stats;
}

function characterSkillsList(character) {
  const skills = document.createElement("div");
  skills.className = "pill-row character-skills";
  Object.entries(character.skills || {}).forEach(([skill, value]) => {
    skills.append(pillNode(`${skill} ${signed(value)}`));
  });
  if (!skills.children.length) {
    skills.append(pillNode(t("noSkills")));
  }
  return skills;
}

function characterPillSection(label, values, emptyText) {
  const section = document.createElement("div");
  section.className = "character-section";
  const heading = document.createElement("span");
  heading.className = "character-section-title";
  heading.textContent = label;
  const pills = document.createElement("div");
  pills.className = "pill-row";
  const entries = values?.length ? values : [emptyText];
  entries.forEach((entry) => pills.append(pillNode(inventoryEntryText(entry))));
  section.append(heading, pills);
  return section;
}

function proficiencyEntries(proficiencies = {}) {
  return Object.entries(proficiencies).flatMap(([category, values]) =>
    (values || []).map((value) => `${category}: ${value}`),
  );
}

function matchingCombatParticipant(character) {
  return (state.combat?.participants || []).find((participant) => {
    const participantId = participant.character_id ?? participant.id ?? null;
    return participantId != null ? participantId === character.id : participant.name === character.name;
  }) || null;
}

function isLikelyEquipmentEntry(entry) {
  const key = inventoryEntryKey(entry).toLowerCase();
  return [
    "armor",
    "axe",
    "bow",
    "club",
    "crossbow",
    "dagger",
    "hammer",
    "leather",
    "lute",
    "mace",
    "mail",
    "plate",
    "rapier",
    "shield",
    "spear",
    "staff",
    "sword",
    "symbol",
  ].some((term) => key.includes(term));
}

function inventoryEntryKey(entry) {
  if (entry == null) {
    return "";
  }
  if (typeof entry !== "object") {
    return String(entry);
  }
  return String(entry.item_id || entry.id || entry.title || entry.name || "");
}

function boundedPercent(value, max) {
  const parsedValue = Number(value || 0);
  const parsedMax = Number(max || 0);
  if (!Number.isFinite(parsedValue) || !Number.isFinite(parsedMax) || parsedMax <= 0) {
    return 0;
  }
  return Math.max(4, Math.min(100, Math.round((parsedValue / parsedMax) * 100)));
}

function inventoryEntryText(entry) {
  if (entry == null) {
    return "";
  }
  if (typeof entry !== "object") {
    return String(entry);
  }
  const itemId = entry.item_id || entry.id || "";
  const label = entry.title || entry.name || (itemId ? localizeEquipmentName(itemId) : "");
  const quantity = Number(entry.quantity || 1);
  return `${label}${quantity > 1 ? ` x${quantity}` : ""}`;
}

export function renderScene(scene) {
  els.sceneDetail.replaceChildren();
  if (!scene) {
    els.sceneDetail.className = "detail-empty";
    els.sceneDetail.textContent = t("noActiveScene");
    return;
  }

  els.sceneDetail.className = "detail-card";
  const location = document.createElement("strong");
  location.textContent = scene.location;

  const environment = document.createElement("p");
  environment.textContent = scene.environment;

  const objective = document.createElement("p");
  objective.textContent = t("objective", { objective: scene.current_objective });

  const objects = document.createElement("div");
  objects.className = "pill-row";
  (scene.important_objects || []).forEach((item) => objects.append(pillNode(item)));
  if (!objects.children.length) {
    objects.append(pillNode(t("noNotableObjects")));
  }

  els.sceneDetail.append(location, environment, objective, objects);
}

export function renderWorldState(worldState) {
  if (!els.worldStatePhase || !els.worldStateClocks || !els.worldStateEvents) {
    return;
  }
  els.worldStateClocks.replaceChildren();
  els.worldStateEvents.replaceChildren();

  const phaseLabel = worldState?.phase_label || "";
  const clocks = [
    ...(worldState?.threat_clocks || []),
    ...(worldState?.pressure_clocks || []),
  ].filter((clock) => clock && clock.visible !== false);
  const events = worldState?.visible_events || [];

  if (!worldState || (!phaseLabel && !clocks.length && !events.length)) {
    els.worldStatePhase.className = "world-state-phase detail-empty";
    els.worldStatePhase.textContent = t("worldSituationEmpty");
    els.worldStateClocks.append(emptyNode(t("worldSituationEmpty")));
    return;
  }

  els.worldStatePhase.className = "world-state-phase";
  els.worldStatePhase.textContent = phaseLabel || t("worldSituation");

  if (!clocks.length) {
    els.worldStateClocks.append(emptyNode(t("worldSituationEmpty")));
  } else {
    clocks.forEach((clock) => {
      const item = document.createElement("div");
      item.className = `world-clock ${clock.severity ? `severity-${clock.severity}` : ""}`.trim();
      const label = document.createElement("span");
      label.textContent = `${clock.label || clock.id} ${Number(clock.value || 0)}/${Number(clock.max || 0)}`;
      item.append(label);
      els.worldStateClocks.append(item);
    });
  }

  if (!events.length) {
    els.worldStateEvents.append(emptyNode(t("worldSituationEmpty")));
  } else {
    events.slice(-3).forEach((event) => {
      const item = document.createElement("p");
      item.textContent = event;
      els.worldStateEvents.append(item);
    });
  }
}

function currentCombatant(combat) {
  const participants = combat?.participants || [];
  return participants[combat?.turn_index] || null;
}

function roomPartyCharacters() {
  return state.selectedAdventure?.party_characters || [];
}

function selectCurrentCombatantForRoom(options = {}) {
  const party = roomPartyCharacters();
  if (!party.length) {
    return;
  }
  if (
    options.onlyIfMissing
    && state.selectedCharacterId
    && party.some((character) => character.id === state.selectedCharacterId)
  ) {
    return;
  }
  const actor = currentCombatant(state.combat);
  const actorId = actor?.character_id ?? actor?.id ?? null;
  let selected = null;
  if (actorId != null) {
    selected = party.find((character) => character.id === actorId);
  }
  if (!selected && actor?.name) {
    selected = party.find((character) => character.name === actor.name);
  }
  state.selectedCharacterId = (selected || party[0]).id;
}

function firstHostileTarget(combat, actor) {
  return (combat?.participants || []).find(
    (participant) => participant.side !== actor.side && participant.hp > 0 && !participant.defeated,
  ) || null;
}

function isPlayerCombatant(actor) {
  return actor?.side === "player";
}

function canCombatantAct(actor) {
  const conditions = new Set(actor?.conditions || []);
  return Boolean(actor && !actor.defeated && Number(actor.hp || 0) > 0 && !conditions.has("incapacitated"));
}

function isNpcCombatTurn(combat) {
  const actor = currentCombatant(combat);
  return Boolean(combat?.is_active && actor && !isPlayerCombatant(actor));
}

function isPlayerCombatTurn(combat) {
  const actor = currentCombatant(combat);
  return Boolean(combat?.is_active && actor && isPlayerCombatant(actor));
}

export function renderCombat(combat) {
  if (els.combatTriggerNote) {
    els.combatTriggerNote.classList.toggle("hidden", Boolean(combat?.is_active));
  }
  els.combatDetail.replaceChildren();
  if (!combat) {
    els.combatDetail.className = "detail-empty";
    els.combatDetail.textContent = t("noCombatState");
    if (els.roomCombatMeta) {
      els.roomCombatMeta.textContent = t("noCombatState");
    }
    renderCombatResult(null);
    renderCombatLog([]);
    setCombatControlsEnabled(false);
    return;
  }

  els.combatDetail.className = "detail-card";
  const participants = combat.participants || [];
  const actor = currentCombatant(combat);
  const players = participants.filter((participant) => participant.side === "player");
  const enemies = participants.filter((participant) => participant.side === "enemy");

  const summary = document.createElement("strong");
  summary.textContent = combat.is_active
    ? t("roundTurn", { round: combat.round_number, turn: combat.turn_index + 1 })
    : t("combatEnded");
  if (els.roomCombatMeta) {
    els.roomCombatMeta.textContent = actor && combat.is_active
      ? t("currentCombatant", { name: actor.name })
      : summary.textContent;
  }

  const pairing = document.createElement("div");
  pairing.className = "combat-pairing";
  pairing.textContent = t("combatPairing", {
    players: namesOrDash(players),
    enemies: namesOrDash(enemies),
  });

  const current = document.createElement("div");
  current.className = "combat-current";
  current.textContent = actor && combat.is_active ? t("currentCombatant", { name: actor.name }) : t("combatEnded");

  const list = document.createElement("div");
  list.className = "combat-list";
  participants.forEach((participant, index) => {
    const row = document.createElement("div");
    row.className = `combatant ${index === combat.turn_index && combat.is_active ? "current" : ""}`;
    const line = document.createElement("span");
    line.className = "combatant-line";
    line.textContent = t("combatantLine", {
      name: participant.name,
      side: localizeSide(participant.side),
      hp: participant.hp,
      ac: participant.ac,
      initiative: participant.initiative,
    });
    const traits = document.createElement("div");
    traits.className = "pill-row combatant-traits";
    [
      `ATK ${signed(participant.attack_bonus)}`,
      participant.damage,
      ...(participant.conditions || []),
    ].filter(Boolean).forEach((trait) => traits.append(pillNode(trait)));
    row.append(line, traits);
    list.append(row);
  });

  els.combatDetail.append(summary, pairing, current, list);
  renderCombatResult(state.combatResult);
  renderCombatLog(combat.action_log || []);
  setCombatControlsEnabled(Boolean(combat.is_active));
}

function renderCombatResult(result) {
  if (!els.combatResult) {
    return;
  }
  els.combatResult.replaceChildren();
  if (!result) {
    els.combatResult.className = "combat-result detail-empty";
    els.combatResult.textContent = t("combatNoResult");
    return;
  }

  els.combatResult.className = "combat-result detail-card";
  els.combatResult.textContent = combatResultText(result);
}

function combatResultText(result) {
  const actor = result.actor?.name || result.actor_name || "-";
  if (result.action_type === "attack") {
    const outcome = result.critical
      ? t("combatOutcomeCritical")
      : result.hit
        ? t("combatOutcomeHit")
        : t("combatOutcomeMiss");
    return t("combatAttackResult", {
      actor,
      target: result.target?.name || result.target_name || "-",
      outcome,
      roll: rollTotal(result.attack_roll),
      damage: result.damage ?? 0,
    });
  }
  return t("combatSimpleActionResult", {
    actor,
    action: localizeCombatAction(result.action_type),
  });
}

function renderCombatLog(entries = []) {
  if (!els.combatLog) {
    return;
  }
  els.combatLog.replaceChildren();
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "combat-log-empty";
    empty.textContent = t("combatLogEmpty");
    els.combatLog.append(empty);
    return;
  }

  entries.forEach((entry) => {
    const item = document.createElement("article");
    item.className = `combat-log-entry ${entry.source || "system"}`;
    const meta = document.createElement("div");
    meta.className = "combat-log-meta";
    meta.textContent = t("combatLogMeta", {
      round: entry.round_number || "-",
      source: localizeCombatLogSource(entry.source),
    });
    const summary = document.createElement("strong");
    summary.textContent = combatLogSummary(entry);
    const effect = document.createElement("p");
    effect.textContent = combatLogEffect(entry);
    item.append(meta, summary, effect);
    els.combatLog.append(item);
  });
  els.combatLog.scrollTop = els.combatLog.scrollHeight;
}

function combatLogSummary(entry) {
  if (entry.action_type === "attack") {
    return t("combatLogAttackSummary", {
      actor: entry.actor_name || "-",
      target: entry.target_name || "-",
    });
  }
  return t("combatLogSimpleSummary", {
    actor: entry.actor_name || "-",
    action: localizeCombatAction(entry.action_type),
  });
}

function combatLogEffect(entry) {
  if (entry.action_type === "attack") {
    const targetHp = entry.target_hp ?? "-";
    const targetHpMax = entry.target_hp_max ?? "-";
    if (entry.hit === false) {
      return t("combatLogAttackMiss", {
        roll: entry.attack_roll_total ?? "-",
        target: entry.target_name || "-",
      });
    }
    const key = entry.target_defeated ? "combatLogAttackDefeated" : "combatLogAttackHit";
    return t(key, {
      roll: entry.attack_roll_total ?? "-",
      damage: entry.damage ?? 0,
      target: entry.target_name || "-",
      hp: targetHp,
      hpMax: targetHpMax,
    });
  }
  if (entry.action_type === "end_combat") {
    return t("combatLogEndCombat");
  }
  return t("combatLogSimpleEffect", { action: localizeCombatAction(entry.action_type) });
}

function localizeCombatLogSource(source) {
  if (source === "player") {
    return t("combatLogSourcePlayer");
  }
  if (source === "npc") {
    return t("combatLogSourceNpc");
  }
  return t("combatLogSourceSystem");
}

function rollTotal(roll) {
  return roll?.total ?? roll?.value ?? "-";
}

function namesOrDash(participants) {
  return participants.map((participant) => participant.name).join(", ") || "-";
}

function signed(value) {
  const number = Number(value || 0);
  return number >= 0 ? `+${number}` : String(number);
}

function setCombatControlsEnabled(isActive) {
  const actor = currentCombatant(state.combat);
  const canPlayerAct = Boolean(
    isActive && isPlayerCombatTurn(state.combat) && canCombatantAct(actor) && !state.combatNpcBusy,
  );
  [
    els.combatActionAttack,
    els.combatActionDodge,
    els.combatActionDash,
    els.combatActionDisengage,
  ].filter(Boolean).forEach((button) => {
    button.disabled = !canPlayerAct;
  });
  if (els.endCombat) {
    els.endCombat.disabled = !isActive || state.combatNpcBusy;
  }
}

export function renderCharacterList() {
  [els.characterList, els.characterCreateList].filter(Boolean).forEach((list) => list.replaceChildren());
  if (!state.characters.length) {
    [els.characterList, els.characterCreateList].filter(Boolean).forEach((list) => {
      list.append(emptyNode(t("noCharactersYet")));
    });
    renderPartySummary();
    return;
  }

  state.characters.forEach((character) => {
    const item = characterListItem(character, { mode: "party" });
    if (els.characterList) {
      els.characterList.append(item);
    }
    if (els.characterCreateList) {
      els.characterCreateList.append(characterListItem(character, { mode: "select" }));
    }
  });
  renderPartySummary();
}

export function characterListItem(character, options = {}) {
  const mode = options.mode || "select";
  const isPartySelected = state.selectedPartyCharacterIds.includes(character.id);
  const item = document.createElement("div");
  item.className = mode === "party"
    ? `choice-card character-choice-card ${isPartySelected ? "selected party-selected" : ""}`
    : `list-item ${character.id === state.selectedCharacterId ? "active" : ""}`;
  item.setAttribute("role", "listitem");
  const summary = document.createElement("button");
  summary.type = "button";
  summary.className = mode === "party" ? "choice-card-main" : "item-summary";
  summary.innerHTML = mode === "party"
    ? `<span class="choice-card-kicker"></span><strong></strong><span class="choice-card-body"></span><span class="select-state"></span>`
    : `<span class="item-title"></span><span class="item-meta"></span>`;
  const meta = t("characterMeta", {
      race: character.race,
      className: character.class_name,
      hpCurrent: character.hp_current,
      hpMax: character.hp_max,
  });
  if (mode === "party") {
    summary.querySelector(".choice-card-kicker").textContent = isPartySelected ? t("selectedPartyMember") : t("availableCharacter");
    summary.querySelector("strong").textContent = character.name;
    summary.querySelector(".choice-card-body").textContent = meta;
    summary.querySelector(".select-state").textContent = isPartySelected ? t("selectedForParty") : t("addToParty");
  } else {
    summary.querySelector(".item-title").textContent = character.name;
    summary.querySelector(".item-meta").textContent = meta;
  }
  summary.addEventListener("click", () => {
    if (mode === "party") {
      togglePartyCharacter(character.id);
    } else {
      state.selectedCharacterId = character.id;
    }
    renderCharacterList();
    renderCharacter(character);
    setStatus(t("selected", { title: character.name }), "ok");
  });
  const actions = document.createElement("div");
  actions.className = mode === "party" ? "choice-card-actions" : "item-actions";
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "secondary";
  remove.textContent = t("deleteCharacter");
  remove.addEventListener("click", () => deleteCharacter(character.id));
  actions.append(remove);
  item.append(summary, actions);
  return item;
}

export async function deleteCharacter(id) {
  try {
    await api(`/api/characters/${id}`, { method: "DELETE" });
    if (state.selectedCharacterId === id) {
      state.selectedCharacterId = null;
    }
    await loadCharacters();
    await loadAdventures();
    renderAdventureDetail();
    setStatus(t("characterDeleted"), "ok");
  } catch (error) {
    showError(error);
  }
}

export function renderAdventureList() {
  els.adventureList.replaceChildren();
  if (!state.adventures.length) {
    els.adventureList.append(emptyNode(t("noAdventuresYet")));
    return;
  }

  state.adventures.forEach((adventure) => {
    const item = document.createElement("div");
    item.className = `adventure-item ${adventure.id === state.selectedAdventureId ? "active" : ""}`;
    const summary = document.createElement("button");
    summary.type = "button";
    summary.className = "item-summary";
    summary.innerHTML = `<span class="item-title"></span><span class="item-meta"></span>`;
    summary.querySelector(".item-title").textContent = adventure.title;
    const partyNames = partyNamesForAdventure(adventure);
    summary.querySelector(".item-meta").textContent = t("adventureMeta", {
      status: localizeStatus(adventure.status),
      characterId: adventure.character_id,
      party: partyNames,
      count: adventure.party_character_ids?.length || 1,
    });
    summary.addEventListener("click", () => selectAdventure(adventure.id));
    const actions = document.createElement("div");
    actions.className = "item-actions";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.textContent = t("deleteAdventure");
    remove.addEventListener("click", () => deleteAdventure(adventure.id));
    actions.append(remove);
    item.append(summary, actions);
    els.adventureList.append(item);
  });
}

export async function deleteAdventure(id) {
  try {
    await api(`/api/adventures/${id}`, { method: "DELETE" });
    if (state.selectedAdventureId === id) {
      state.selectedAdventureId = null;
      state.selectedAdventure = null;
      state.gameMode = "setup";
      state.combat = null;
      state.mapScenes = [];
      state.selectedMapSceneId = null;
      state.mapTokens = [];
      state.selectedMapTokenId = null;
    }
    await loadAdventures();
    renderAdventureDetail();
    setStatus(t("adventureDeleted"), "ok");
  } catch (error) {
    showError(error);
  }
}

export function renderAdventureDetail(messages, scene, combat) {
  const adventure = state.selectedAdventure;
  renderGameMode();
  renderPartySummary();
  renderRoomParty();
  if (!adventure) {
    state.gameMode = "setup";
    renderGameMode();
    els.chatTitle.textContent = t("selectAdventure");
    els.chatSubtitle.textContent = t("chooseCharacterThenAdventure");
    renderMessages([]);
    renderScene(null);
    renderWorldState(null);
    renderCombat(null);
    renderMapScenes();
    renderMapTokens();
    renderMapPreview(null);
    return;
  }

  els.chatTitle.textContent = adventure.title;
  els.chatSubtitle.textContent = t("adventureSubtitle", {
    status: localizeStatus(adventure.status),
    worldId: adventure.world_id,
  });
  selectCurrentCombatantForRoom({ onlyIfMissing: true });
  renderCharacter(getSelectedCharacter());
  renderMessages(messages || adventure.messages || []);
  renderScene(scene || adventure.current_scene);
  renderWorldState(adventure.world_state);
  renderCombat(combat || state.combat);
  renderMapScenes();
  renderMapPreview(getSelectedMapScene());
  renderMapTokens();
  renderRoomHeader(adventure, scene || adventure.current_scene);
}

export function renderMapAssets() {
  if (!els.mapAssetList) {
    return;
  }
  els.mapAssetList.replaceChildren();
  if (!state.mapAssets.length) {
    els.mapAssetList.append(emptyNode(t("noMapAssetsYet")));
    return;
  }
  state.mapAssets.forEach((asset) => {
    const item = document.createElement("div");
    item.className = `list-item ${asset.id === state.selectedMapAssetId ? "active" : ""}`;
    const summary = document.createElement("button");
    summary.type = "button";
    summary.className = "item-summary";
    summary.innerHTML = `<span class="item-title"></span><span class="item-meta"></span>`;
    summary.querySelector(".item-title").textContent = asset.name;
    summary.querySelector(".item-meta").textContent = `${asset.asset_type} | ${Math.ceil(asset.size_bytes / 1024)} KB`;
    summary.addEventListener("click", () => {
      state.selectedMapAssetId = asset.id;
      renderMapAssets();
      setStatus(t("selectMapAsset", { name: asset.name }), "ok");
    });
    item.append(summary);
    els.mapAssetList.append(item);
  });
}

export function renderMapScenes() {
  if (!els.mapSceneList) {
    return;
  }
  els.mapSceneList.replaceChildren();
  if (!state.mapScenes.length) {
    els.mapSceneList.append(emptyNode(t("noMapScenesYet")));
    return;
  }
  state.mapScenes.forEach((scene) => {
    const item = document.createElement("div");
    item.className = `list-item ${scene.id === state.selectedMapSceneId ? "active" : ""}`;
    const summary = document.createElement("button");
    summary.type = "button";
    summary.className = "item-summary";
    summary.innerHTML = `<span class="item-title"></span><span class="item-meta"></span>`;
    summary.querySelector(".item-title").textContent = scene.name;
    summary.querySelector(".item-meta").textContent = scene.active
      ? t("activeMapScene")
      : t("mapPreviewMeta", { grid: scene.grid_type, scale: scene.scale, unit: scene.scale_unit });
    summary.addEventListener("click", () => activateMapScene(scene.id));
    item.append(summary);
    els.mapSceneList.append(item);
  });
}

export function renderMapPreview(scene = getSelectedMapScene()) {
  if (!els.mapPreview) {
    return;
  }
  els.mapPreview.replaceChildren();
  if (!scene) {
    els.mapPreview.className = "map-board detail-empty";
    els.mapPreview.textContent = t("noMapSceneSelected");
    return;
  }

  els.mapPreview.className = "map-board";
  const dimensions = mapSceneDimensions(scene);
  const title = document.createElement("strong");
  title.textContent = scene.name;

  const frame = document.createElement("div");
  frame.className = "map-preview-frame";
  frame.dataset.mapWidth = String(dimensions.width);
  frame.dataset.mapHeight = String(dimensions.height);
  frame.style.setProperty("--map-grid-size", `${Math.max(10, scene.grid_size || 70)}px`);
  frame.addEventListener("click", (event) => handleMapBoardClick(event, frame, scene));

  const background = firstBackgroundItem(scene);
  if (background?.asset?.file_url) {
    const image = document.createElement("img");
    image.src = `${apiBase}${background.asset.file_url}`;
    image.alt = scene.name;
    frame.append(image);
  } else {
    const empty = document.createElement("span");
    empty.className = "map-preview-empty";
    empty.textContent = t("noMapSceneSelected");
    frame.append(empty);
  }
  const grid = document.createElement("div");
  grid.className = "map-grid-overlay";
  const tokenLayer = document.createElement("div");
  tokenLayer.className = "map-token-layer";
  frame.append(grid, tokenLayer);

  const meta = document.createElement("p");
  meta.textContent = t("mapPreviewMeta", {
    grid: scene.grid_type,
    scale: scene.scale,
    unit: scene.scale_unit,
  });
  els.mapPreview.append(title, frame, meta);
  renderMapTokens(scene);
}

export function renderMapTokens(scene = getSelectedMapScene()) {
  if (els.mapTokenList) {
    els.mapTokenList.replaceChildren();
  }
  const sceneId = scene?.id || state.selectedMapSceneId;
  const tokens = state.mapTokens.filter((token) => !sceneId || token.scene_id === sceneId);
  if (!tokens.length) {
    if (els.mapTokenList) {
      els.mapTokenList.append(emptyNode(t("noMapTokensYet")));
    }
  } else if (els.mapTokenList) {
    tokens.forEach((token) => {
      const item = document.createElement("div");
      item.className = `list-item ${token.id === state.selectedMapTokenId ? "active" : ""}`;
      const summary = document.createElement("button");
      summary.type = "button";
      summary.className = "item-summary";
      summary.innerHTML = `<span class="item-title"></span><span class="item-meta"></span>`;
      summary.querySelector(".item-title").textContent = token.participant_name;
      summary.querySelector(".item-meta").textContent = t("mapTokenMeta", {
        side: localizeSide(token.side),
        x: Math.round(token.x),
        y: Math.round(token.y),
      });
      summary.addEventListener("click", () => {
        state.selectedMapTokenId = token.id;
        renderMapTokens(scene);
        renderMapPreview(scene);
        setStatus(t("mapTokenSelected", { name: token.participant_name }), "ok");
      });
      item.append(summary);
      els.mapTokenList.append(item);
    });
  }

  const layer = els.mapPreview?.querySelector(".map-token-layer");
  if (!layer || !scene) {
    return;
  }
  layer.replaceChildren();
  const dimensions = mapSceneDimensions(scene);
  tokens.forEach((token) => {
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = `map-token ${token.side === "player" ? "player" : "enemy"} ${token.id === state.selectedMapTokenId ? "selected" : ""}`;
    marker.textContent = tokenInitials(token.participant_name);
    marker.title = token.participant_name;
    marker.style.left = `${(token.x / dimensions.width) * 100}%`;
    marker.style.top = `${(token.y / dimensions.height) * 100}%`;
    marker.style.width = `${Math.max(7, (token.size / dimensions.width) * 100)}%`;
    marker.style.height = `${Math.max(7, (token.size / dimensions.height) * 100)}%`;
    marker.addEventListener("click", (event) => {
      event.stopPropagation();
      state.selectedMapTokenId = token.id;
      renderMapTokens(scene);
      setStatus(t("mapTokenSelected", { name: token.participant_name }), "ok");
    });
    layer.append(marker);
  });
}

async function handleMapBoardClick(event, frame, scene) {
  if (event.target.closest(".map-token")) {
    return;
  }
  const token = getSelectedMapToken();
  if (!token) {
    setStatus(t("selectMapTokenFirst"), "error");
    return;
  }
  const rect = frame.getBoundingClientRect();
  const dimensions = mapSceneDimensions(scene);
  const size = token.size || scene.grid_size || 70;
  const x = ((event.clientX - rect.left) / rect.width) * dimensions.width - size / 2;
  const y = ((event.clientY - rect.top) / rect.height) * dimensions.height - size / 2;
  await moveMapToken(token.id, Math.max(0, Math.round(x)), Math.max(0, Math.round(y)));
}

function getSelectedMapToken() {
  return state.mapTokens.find((token) => token.id === state.selectedMapTokenId) || null;
}

function mapSceneDimensions(scene) {
  const background = firstBackgroundItem(scene);
  return {
    width: Number(background?.width || scene?.metadata?.width || 1000),
    height: Number(background?.height || scene?.metadata?.height || 750),
  };
}

function tokenInitials(name) {
  const compact = String(name || "?").trim();
  if (!compact) {
    return "?";
  }
  const parts = compact.split(/\s+/).filter(Boolean);
  if (parts.length > 1) {
    return parts.map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  }
  return compact.slice(0, 2).toUpperCase();
}

function getSelectedMapAsset() {
  return state.mapAssets.find((asset) => asset.id === state.selectedMapAssetId) || null;
}

function currentMapStoryId() {
  return state.editingStoryId || null;
}

function getSelectedMapScene() {
  return state.mapScenes.find((scene) => scene.id === state.selectedMapSceneId) || state.mapScenes.find((scene) => scene.active) || null;
}

function firstBackgroundItem(scene) {
  return (scene?.items || []).find((item) => item.item_type === "background" && item.visible !== false) || null;
}

export function renderRules(result) {
  els.rulesResults.replaceChildren();
  if (!result.results || !result.results.length) {
    els.rulesResults.append(emptyNode(localizeWorldMessage(result.message) || t("noMatchingRules")));
    return;
  }

  result.results.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "rule-result";

    const name = document.createElement("strong");
    name.textContent = `${entry.name} (${entry.category})`;

    const content = document.createElement("p");
    content.textContent = entry.content;

    item.append(name, content);
    els.rulesResults.append(item);
  });
}

export function getSelectedCharacter() {
  const party = roomPartyCharacters();
  if (state.gameMode === "room" && party.length) {
    return party.find((character) => character.id === state.selectedCharacterId) || party[0];
  }
  return state.characters.find((character) => character.id === state.selectedCharacterId) || null;
}

function selectedPartyCharacterIds() {
  return state.selectedPartyCharacterIds.filter((id) => state.characters.some((character) => character.id === id));
}

function selectedPartyCharacters() {
  const ids = new Set(selectedPartyCharacterIds());
  return state.characters.filter((character) => ids.has(character.id));
}

function togglePartyCharacter(characterId) {
  const selected = new Set(state.selectedPartyCharacterIds);
  if (selected.has(characterId)) {
    selected.delete(characterId);
  } else if (selected.size >= 6) {
    setStatus(t("partySizeLimitError"), "error");
    return;
  } else {
    selected.add(characterId);
  }
  state.selectedPartyCharacterIds = [...selected];
}

function renderPartySummary() {
  if (!els.gamePartySummary) {
    return;
  }
  const party = selectedPartyCharacters();
  const story = state.stories.find((entry) => entry.id === state.selectedStoryId);
  els.gamePartySummary.replaceChildren();
  [
    [t("story"), localizedStoryText(story, "title") || state.selectedStoryId],
    [t("selectPartyCharacters"), party.map((character) => character.name).join(", ") || t("partyEmpty")],
    [t("partySummary", { count: party.length }), t("lockedPartyRule")],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "summary-row";
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    row.append(labelNode, valueNode);
    els.gamePartySummary.append(row);
  });
  if (!els.gamePartyWarning) {
    return;
  }
  els.gamePartyWarning.className = "map-action-message detail-empty";
  if (!party.length) {
    els.gamePartyWarning.textContent = t("partyRequired");
    els.gamePartyWarning.classList.add("error");
  } else if (party.length > 4) {
    els.gamePartyWarning.textContent = t("partySizeWarning");
    els.gamePartyWarning.classList.add("ok");
  } else {
    els.gamePartyWarning.textContent = t("lockedPartyRule");
  }
}

export async function loadStoryMapScenes(storyId = currentMapStoryId()) {
  if (!storyId) {
    state.mapScenes = [];
    state.selectedMapSceneId = null;
    state.mapTokens = [];
    state.selectedMapTokenId = null;
    renderMapScenes();
    renderMapTokens();
    return;
  }
  try {
    state.mapScenes = await api(`/api/map-scenes?story_id=${encodeURIComponent(storyId)}`);
    if (state.selectedMapSceneId && !state.mapScenes.some((scene) => scene.id === state.selectedMapSceneId)) {
      state.selectedMapSceneId = null;
    }
    if (!state.selectedMapSceneId && state.mapScenes.length) {
      state.selectedMapSceneId = state.mapScenes[0].id;
    }
    state.mapTokens = [];
    state.selectedMapTokenId = null;
    renderMapScenes();
    renderMapTokens();
  } catch (error) {
    showError(error);
  }
}

function renderGameMode() {
  const gameView = document.getElementById("game-view");
  if (!gameView) {
    return;
  }
  const roomMode = state.gameMode === "room" && Boolean(state.selectedAdventureId);
  gameView.classList.toggle("setup-mode", !roomMode);
  gameView.classList.toggle("room-mode", roomMode);
}

function renderRoomHeader(adventure, scene) {
  if (els.roomRouteTag) {
    els.roomRouteTag.textContent = `/game/${adventure.id}`;
  }
  if (els.roomAdventureTitle) {
    els.roomAdventureTitle.textContent = adventure.title;
  }
  if (els.roomSceneMeta) {
    const sceneText = [scene?.location, scene?.current_objective].filter(Boolean).join(" | ");
    els.roomSceneMeta.textContent = sceneText || t("noActiveScene");
  }
  if (els.roomStoryMeta) {
    els.roomStoryMeta.textContent = storyTitleForAdventure(adventure);
  }
  if (els.roomPartyMeta) {
    els.roomPartyMeta.textContent = partyNamesForAdventure(adventure);
  }
}

export function renderRoomParty() {
  if (!els.roomPartyList) {
    return;
  }
  els.roomPartyList.replaceChildren();
  els.roomPartyList.className = "party-list";
  const party = state.selectedAdventure?.party_characters || [];
  if (!party.length) {
    els.roomPartyList.append(emptyNode(t("partyEmpty")));
    return;
  }
  party.forEach((character) => {
    const row = document.createElement("button");
    row.type = "button";
    const current = isCurrentPartyMember(character);
    row.className = `party-member ${current ? "current" : ""}`.trim();
    const name = document.createElement("strong");
    name.textContent = character.name;
    const status = document.createElement("span");
    status.textContent = current ? t("currentPartyTurn") : t("waitingPartyTurn");
    row.append(name, status);
    row.addEventListener("click", () => {
      state.selectedCharacterId = character.id;
      renderCharacter(character);
      renderRoomParty();
    });
    els.roomPartyList.append(row);
  });
}

function isCurrentPartyMember(character) {
  const actor = currentCombatant(state.combat);
  const actorId = actor?.character_id ?? actor?.id ?? null;
  if (actorId != null) {
    return character.id === actorId;
  }
  if (actor?.name) {
    return character.name === actor.name;
  }
  return character.id === state.selectedCharacterId;
}

function partyNamesForAdventure(adventure) {
  const party = adventure.party_characters || [];
  if (party.length) {
    return party.map((character) => character.name).join(", ");
  }
  return `#${adventure.character_id}`;
}

function storyTitleForAdventure(adventure) {
  const story = state.stories.find((entry) => entry.id === adventure.story_id);
  return localizedStoryText(story, "title") || adventure.story_id;
}
