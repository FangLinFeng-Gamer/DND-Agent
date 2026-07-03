import { api } from "./api.js?v=20260703-isekai-time";
import { els, state } from "./state.js?v=20260703-isekai-time";
import {
  localizeBackgroundName,
  localizeClassName,
  localizeEquipmentName,
  localizeRaceName,
  t,
} from "./i18n.js?v=20260703-isekai-time";
import { loadCharacters } from "./game.js?v=20260703-isekai-time";
import { setStatus, showError, showView, typingIndicatorNode } from "./ui.js?v=20260703-isekai-time";


const POINT_BUY_COSTS = {
  8: 0,
  9: 1,
  10: 2,
  11: 3,
  12: 4,
  13: 5,
  14: 7,
  15: 9,
};


export async function ensureCharacterCreationSession({ keepBusy = false } = {}) {
  if (state.characterCreationSession?.status === "draft") {
    if (!state.characterCreationGuide) {
      await loadCharacterCreationGuide({ render: false });
    }
    renderCharacterCreation();
    return state.characterCreationSession;
  }
  if (!keepBusy) {
    setCharacterCreationBusy(true);
  }
  try {
    const shouldResetConversation = Boolean(
      state.characterCreationSession
      && state.characterCreationSession.status !== "draft",
    );
    const session = await api("/api/character-creation/sessions", {
      method: "POST",
      body: JSON.stringify({ locale: state.locale }),
    });
    state.characterCreationSession = session;
    state.characterCreationGuide = null;
    state.characterCreationEditingStep = null;
    if (shouldResetConversation || !state.characterCreationMessages.length) {
      state.characterCreationMessages = [
        { role: "assistant", content: session.assistant_message },
      ];
    }
    await loadCharacterCreationGuide({ render: false });
    renderCharacterCreation();
    return session;
  } catch (error) {
    showError(error);
    return null;
  } finally {
    if (!keepBusy) {
      setCharacterCreationBusy(false);
    }
  }
}


export async function sendCharacterCreationMessage(content = els.characterAgentInput.value.trim()) {
  if (state.characterCreationBusy) {
    setStatus(t("characterAgentStillResponding"), "error");
    return;
  }
  if (!content) {
    setStatus(t("characterAgentMessageRequired"), "error");
    return;
  }
  setCharacterCreationBusy(true);
  const pendingAssistant = {
    role: "assistant",
    content: "",
    pending: true,
  };
  state.characterCreationMessages.push({ role: "user", content });
  state.characterCreationMessages.push(pendingAssistant);
  els.characterAgentInput.value = "";
  renderCharacterCreation();
  try {
    const session = await ensureCharacterCreationSession({ keepBusy: true });
    if (!session) {
      removePendingCharacterGuideMessage(pendingAssistant);
      renderCharacterCreation();
      return;
    }
    const updated = await api(`/api/character-creation/sessions/${session.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, locale: state.locale }),
    });
    state.characterCreationSession = updated;
    await loadCharacterCreationGuide({ render: false });
    removePendingCharacterGuideMessage(pendingAssistant);
    state.characterCreationMessages.push({
      role: "assistant",
      content: updated.assistant_message,
    });
    renderCharacterCreation();
  } catch (error) {
    removePendingCharacterGuideMessage(pendingAssistant);
    renderCharacterCreation();
    showError(error);
  } finally {
    setCharacterCreationBusy(false);
  }
}


export async function loadCharacterCreationGuide({ render = true, step = state.characterCreationEditingStep } = {}) {
  const session = state.characterCreationSession;
  if (!session?.id) {
    state.characterCreationGuide = null;
    return null;
  }
  const params = new URLSearchParams({ locale: state.locale });
  if (step) {
    params.set("step", step);
  }
  const guide = await api(`/api/character-creation/sessions/${session.id}/guide?${params.toString()}`);
  state.characterCreationGuide = guide;
  state.characterCreationEditingStep = guide.active_step !== guide.actual_step
    ? guide.active_step
    : null;
  if (render) {
    renderCharacterCreation();
  }
  return guide;
}


export async function applyCharacterWizardChoice(option) {
  const session = state.characterCreationSession;
  if (!session?.id || state.characterCreationBusy) {
    return;
  }
  const operation = option?.metadata?.operation;
  const payload = buildWizardPayload(option);
  if (!operation || !payload) {
    return;
  }
  setCharacterCreationBusy(true);
  try {
    const updated = await api(`/api/character-creation/sessions/${session.id}/draft`, {
      method: "PATCH",
      body: JSON.stringify({
        expected_revision: session.revision,
        operation,
        payload,
        locale: state.locale,
      }),
    });
    state.characterCreationSession = updated;
    state.characterCreationEditingStep = null;
    if (updated.assistant_message) {
      state.characterCreationMessages.push({
        role: "assistant",
        content: updated.assistant_message,
      });
    }
    await loadCharacterCreationGuide({ render: false });
    renderCharacterCreation();
  } catch (error) {
    showError(error);
  } finally {
    setCharacterCreationBusy(false);
  }
}


export async function confirmCharacterCreation() {
  const phrase = state.locale === "zh-CN" ? "确认创建" : "confirm";
  await sendCharacterCreationMessage(phrase);
  const character = state.characterCreationSession?.created_character;
  if (!character) {
    return;
  }
  state.selectedCharacterId = character.id;
  await loadCharacters();
  resetCharacterCreationState();
  showView("game");
  setStatus(t("createdCharacter", { name: character.name }), "ok");
}


export function renderCharacterCreation() {
  const session = state.characterCreationSession;
  renderConversation();
  const draft = session?.draft || {};
  els.characterName.value = draft.name || "";
  renderWizard();

  const errors = session?.validation_errors || [];
  els.characterValidation.replaceChildren();
  if (errors.length) {
    const heading = document.createElement("strong");
    heading.textContent = t("characterValidation");
    const list = document.createElement("ul");
    errors.forEach((error) => {
      const item = document.createElement("li");
      item.textContent = error;
      list.append(item);
    });
    els.characterValidation.append(heading, list);
  }
  const valid = Boolean(
    draft.name
    && draft.race
    && draft.class_name
    && state.characterCreationGuide?.active_step === "review"
    && !errors.length
  );
  els.characterConfirm.disabled = state.characterCreationBusy || !valid;
}


export function setCharacterCreationBusy(isBusy) {
  state.characterCreationBusy = isBusy;
  els.characterAgentInput.disabled = isBusy;
  els.characterAgentSend.disabled = isBusy;
  els.characterConfirm.disabled = isBusy;
  if (isBusy) {
    setStatus(t("characterAgentThinking"));
  } else {
    renderCharacterCreation();
  }
}


function renderConversation() {
  els.characterCreationMessages.replaceChildren();
  if (!state.characterCreationMessages.length) {
    const empty = document.createElement("p");
    empty.className = "detail-empty";
    empty.textContent = t("characterAgentEmpty");
    els.characterCreationMessages.append(empty);
    return;
  }
  state.characterCreationMessages.forEach((message) => {
    const node = document.createElement("div");
    node.className = `agent-message ${message.role}`;
    const role = document.createElement("strong");
    role.textContent = message.role === "user" ? t("you") : t("characterGuide");
    const content = document.createElement("p");
    if (message.pending && !message.content) {
      content.append(typingIndicatorNode(t("characterAgentThinking")));
    } else {
      content.textContent = message.content;
    }
    node.append(role, content);
    els.characterCreationMessages.append(node);
  });
  els.characterCreationMessages.scrollTop = els.characterCreationMessages.scrollHeight;
}


function renderWizard() {
  if (!els.characterWizard) {
    return;
  }
  els.characterWizard.replaceChildren();
  const guide = state.characterCreationGuide;
  if (!guide) {
    const empty = document.createElement("p");
    empty.className = "detail-empty";
    empty.textContent = t("characterDraftEmpty");
    els.characterWizard.append(empty);
    return;
  }
  els.characterWizard.append(stepRail(guide.steps, guide.editable_steps || []));
  const active = document.createElement("div");
  active.className = "wizard-active-step";
  const heading = document.createElement("h3");
  heading.textContent = currentStepTitle(guide);
  active.append(heading);
  const prompt = guide.requirements?.prompt;
  if (prompt) {
    const note = document.createElement("p");
    note.className = "wizard-prompt";
    note.textContent = prompt;
    active.append(note);
  }
  if (guide.active_step === "identity") {
    active.append(identityEditor());
  } else if (guide.active_step === "abilities") {
    active.append(abilityEditor(guide));
  } else if (guide.requirements?.mode === "choice_groups") {
    active.append(choiceGroupSelector(guide));
  } else if (guide.requirements?.mode === "equipment") {
    active.append(equipmentSelector(guide));
  } else if (guide.requirements?.mode === "adventure_connection") {
    active.append(adventureConnectionEditor(guide));
  } else if (guide.active_step === "spells") {
    active.append(spellSelector(guide));
  } else if (guide.active_step === "review") {
    active.append(reviewPanel(guide));
  } else {
    active.append(optionGrid(guide.options));
  }
  els.characterWizard.append(active);
}


function stepRail(steps = [], editableSteps = []) {
  const rail = document.createElement("ol");
  rail.className = "wizard-steps";
  const editable = new Set(editableSteps);
  steps.forEach((step) => {
    const item = document.createElement("li");
    item.className = `wizard-step ${step.status}`;
    if (editable.has(step.id)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "wizard-step-action";
      button.textContent = step.label;
      button.disabled = state.characterCreationBusy;
      button.addEventListener("click", () => openCharacterWizardStep(step.id));
      item.append(button);
    } else {
      item.textContent = step.label;
    }
    rail.append(item);
  });
  return rail;
}


function optionGrid(options = []) {
  const grid = document.createElement("div");
  grid.className = "wizard-options";
  if (!options.length) {
    const empty = document.createElement("p");
    empty.className = "detail-empty";
    empty.textContent = state.locale === "zh-CN" ? "当前步骤暂无可选项。" : "No options are available for this step.";
    grid.append(empty);
    return grid;
  }
  options.forEach((option) => {
    grid.append(optionCard(option));
  });
  return grid;
}


function optionCard(option) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `wizard-option${option.selected ? " selected" : ""}`;
  button.disabled = state.characterCreationBusy || option.disabled;
  button.addEventListener("click", () => applyCharacterWizardChoice(option));
  const title = document.createElement("strong");
  title.textContent = option.title;
  button.append(title);
  if (option.subtitle) {
    const subtitle = document.createElement("span");
    subtitle.className = "wizard-option-subtitle";
    subtitle.textContent = option.subtitle;
    button.append(subtitle);
  }
  if (option.badges?.length) {
    button.append(badgeRow(option.badges));
  }
  return button;
}


function badgeRow(badges) {
  const row = document.createElement("span");
  row.className = "wizard-badges";
  badges.forEach((badge) => {
    const node = document.createElement("span");
    node.className = "wizard-badge";
    node.textContent = badge;
    row.append(node);
  });
  return row;
}


function choiceGroupSelector(guide) {
  const wrapper = document.createElement("div");
  wrapper.className = "wizard-choice-groups";
  const groups = guide.requirements?.choice_groups || [];
  if (!groups.length) {
    wrapper.append(optionGrid([]));
    return wrapper;
  }

  const selectedByGroup = Object.fromEntries(
    groups.map((group) => [group.id, new Set(group.selected || [])]),
  );
  const counters = {};
  const optionButtons = {};

  groups.forEach((group) => {
    const section = document.createElement("section");
    section.className = "wizard-choice-group";

    const header = document.createElement("div");
    header.className = "wizard-choice-header";
    const title = document.createElement("h4");
    title.textContent = group.title || group.id;
    const counter = document.createElement("span");
    counters[group.id] = counter;
    header.append(title, counter);
    section.append(header);

    const grid = document.createElement("div");
    grid.className = "wizard-options";
    optionButtons[group.id] = {};
    (group.options || []).forEach((option) => {
      const button = choiceGroupOptionButton(option, group, selectedByGroup[group.id]);
      optionButtons[group.id][option.id] = button;
      button.addEventListener("click", () => {
        toggleGroupedChoice(
          selectedByGroup[group.id],
          option.id,
          Number(group.maximum || 1),
        );
        refreshChoiceGroupState(groups, selectedByGroup, counters, optionButtons, save);
      });
      grid.append(button);
    });
    section.append(grid);
    wrapper.append(section);
  });

  const save = document.createElement("button");
  save.type = "button";
  save.className = "wizard-choice-save";
  save.textContent = state.locale === "zh-CN" ? "保存选择" : "Save Selections";
  save.addEventListener("click", () => {
    return applyCharacterWizardChoice({
      metadata: {
        operation: guide.active_step,
        payload: buildChoiceGroupPayload(guide, selectedByGroup),
      },
    });
  });
  wrapper.append(save);

  refreshChoiceGroupState(groups, selectedByGroup, counters, optionButtons, save);
  return wrapper;
}


function choiceGroupOptionButton(option, group, selected) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `wizard-option${selected.has(option.id) ? " selected" : ""}`;
  button.disabled = state.characterCreationBusy || Boolean(option.disabled);
  const title = document.createElement("strong");
  title.textContent = option.title || option.id;
  button.append(title);
  if (option.description) {
    const subtitle = document.createElement("span");
    subtitle.className = "wizard-option-subtitle";
    subtitle.textContent = option.description;
    button.append(subtitle);
  }
  if (option.rule_type) {
    button.append(badgeRow([option.rule_type]));
  }
  if (option.disabled_reason) {
    const disabledReason = document.createElement("span");
    disabledReason.className = "wizard-option-subtitle";
    disabledReason.textContent = option.disabled_reason;
    button.append(disabledReason);
  }
  return button;
}


function toggleGroupedChoice(selected, optionId, maximum) {
  if (selected.has(optionId)) {
    selected.delete(optionId);
    return;
  }
  if (maximum <= 1) {
    selected.clear();
    selected.add(optionId);
    return;
  }
  if (selected.size < maximum) {
    selected.add(optionId);
  }
}


function refreshChoiceGroupState(groups, selectedByGroup, counters, optionButtons, save) {
  let canSave = true;
  const selectedCounts = duplicateSensitiveSelectionCounts(groups, selectedByGroup);
  groups.forEach((group) => {
    const selected = selectedByGroup[group.id] || new Set();
    const minimum = Number(group.minimum || 0);
    const maximum = Number(group.maximum || minimum || 1);
    if (selected.size < minimum || selected.size > maximum) {
      canSave = false;
    }
    (group.options || []).forEach((option) => {
      if (option.disabled && selected.has(option.id)) {
        canSave = false;
      }
      if (
        selected.has(option.id)
        && isDuplicateSensitiveChoice(option)
        && (selectedCounts[option.id] || 0) > 1
      ) {
        canSave = false;
      }
    });
    if (counters[group.id]) {
      counters[group.id].textContent = state.locale === "zh-CN"
        ? `已选择 ${selected.size}/${maximum}`
        : `Selected ${selected.size}/${maximum}`;
    }
    Object.entries(optionButtons[group.id] || {}).forEach(([optionId, button]) => {
      const option = (group.options || []).find((item) => item.id === optionId) || {};
      const isSelected = selected.has(optionId);
      const duplicateSelectedElsewhere = isDuplicateSensitiveChoice(option)
        && (selectedCounts[optionId] || 0) > (isSelected ? 1 : 0);
      button.classList.toggle("selected", isSelected);
      button.disabled = state.characterCreationBusy
        || Boolean(option.disabled)
        || (!isSelected && duplicateSelectedElsewhere)
        || (!isSelected && selected.size >= maximum);
    });
  });
  save.disabled = state.characterCreationBusy || !canSave;
}


function duplicateSensitiveSelectionCounts(groups, selectedByGroup) {
  const counts = {};
  groups.forEach((group) => {
    const selected = selectedByGroup[group.id] || new Set();
    (group.options || []).forEach((option) => {
      if (!selected.has(option.id) || !isDuplicateSensitiveChoice(option)) {
        return;
      }
      counts[option.id] = (counts[option.id] || 0) + 1;
    });
  });
  return counts;
}


function isDuplicateSensitiveChoice(option) {
  return option?.rule_type === "skill" || option?.rule_type === "tool" || option?.rule_type === "language";
}


function buildChoiceGroupPayload(guide, selectedByGroup) {
  const choiceValues = {};
  (guide.requirements?.choice_groups || []).forEach((group) => {
    choiceValues[group.id] = [...(selectedByGroup[group.id] || [])];
  });
  const payload = { choice_values: choiceValues };
  if (guide.active_step === "class_features") {
    payload.class_option_ids = Object.values(choiceValues)
      .flat()
      .filter((value) => String(value).startsWith("class_option."));
  }
  return payload;
}


function equipmentSelector(guide) {
  const wrapper = document.createElement("div");
  wrapper.className = "wizard-choice-groups wizard-equipment";
  const requirements = guide.requirements || {};
  if (requirements.fixed_items?.length) {
    const fixed = document.createElement("section");
    fixed.className = "wizard-choice-group";
    const heading = document.createElement("h4");
    heading.textContent = state.locale === "zh-CN" ? "固定装备" : "Fixed Equipment";
    fixed.append(heading, equipmentItemList(requirements.fixed_items));
    wrapper.append(fixed);
  }

  const selectedByGroup = Object.fromEntries(
    (requirements.choice_groups || []).map((group) => [
      group.id,
      new Set(group.selected || []),
    ]),
  );
  const selectedItemsByGroup = Object.fromEntries(
    (requirements.item_choice_groups || []).map((group) => [
      group.id,
      new Set(group.selected || []),
    ]),
  );
  const counters = {};
  const optionButtons = {};
  const itemGroupsNode = document.createElement("div");
  const save = document.createElement("button");
  save.type = "button";
  save.className = "wizard-choice-save";
  save.textContent = state.locale === "zh-CN" ? "保存装备" : "Save Equipment";

  const refresh = () => {
    refreshChoiceGroupState(
      requirements.choice_groups || [],
      selectedByGroup,
      counters,
      optionButtons,
      save,
    );
    renderEquipmentItemChoiceGroups(
      itemGroupsNode,
      requirements,
      selectedByGroup,
      selectedItemsByGroup,
      save,
    );
  };

  (requirements.choice_groups || []).forEach((group) => {
    const section = document.createElement("section");
    section.className = "wizard-choice-group";
    const header = document.createElement("div");
    header.className = "wizard-choice-header";
    const title = document.createElement("h4");
    title.textContent = group.title || group.id;
    const counter = document.createElement("span");
    counters[group.id] = counter;
    header.append(title, counter);
    section.append(header);

    const grid = document.createElement("div");
    grid.className = "wizard-options";
    optionButtons[group.id] = {};
    (group.options || []).forEach((option) => {
      const button = choiceGroupOptionButton(option, group, selectedByGroup[group.id]);
      optionButtons[group.id][option.id] = button;
      button.addEventListener("click", () => {
        toggleGroupedChoice(
          selectedByGroup[group.id],
          option.id,
          Number(group.maximum || 1),
        );
        refresh();
      });
      grid.append(button);
    });
    section.append(grid);
    wrapper.append(section);
  });

  save.addEventListener("click", () => {
    applyCharacterWizardChoice({
      metadata: {
        operation: "equipment",
        payload: buildEquipmentPayload(
          requirements,
          selectedByGroup,
          selectedItemsByGroup,
        ),
      },
    });
  });
  wrapper.append(itemGroupsNode, save);
  refresh();
  return wrapper;
}


function equipmentItemList(items = []) {
  const list = document.createElement("ul");
  list.className = "wizard-equipment-list";
  items.forEach((item) => {
    const row = document.createElement("li");
    row.textContent = `${item.title}${item.quantity > 1 ? ` x${item.quantity}` : ""}`;
    list.append(row);
  });
  return list;
}


function renderEquipmentItemChoiceGroups(
  container,
  requirements,
  selectedByGroup,
  selectedItemsByGroup,
  save,
) {
  container.replaceChildren();
  const dynamicGroups = [];
  (requirements.choice_groups || []).forEach((group) => {
    (group.options || []).forEach((option) => {
      if (selectedByGroup[group.id]?.has(option.id)) {
        dynamicGroups.push(...(option.selectors || []));
      }
    });
  });
  const groups = [...(requirements.item_choice_groups || []), ...dynamicGroups];
  const counters = {};
  const optionButtons = {};
  groups.forEach((group) => {
    if (!selectedItemsByGroup[group.id]) {
      selectedItemsByGroup[group.id] = new Set(group.selected || []);
    }
    const section = document.createElement("section");
    section.className = "wizard-choice-group";
    const header = document.createElement("div");
    header.className = "wizard-choice-header";
    const title = document.createElement("h4");
    title.textContent = group.title || group.id;
    const counter = document.createElement("span");
    counters[group.id] = counter;
    header.append(title, counter);
    section.append(header);
    const grid = document.createElement("div");
    grid.className = "wizard-options";
    optionButtons[group.id] = {};
    (group.options || []).forEach((option) => {
      const button = choiceGroupOptionButton(
        option,
        group,
        selectedItemsByGroup[group.id],
      );
      optionButtons[group.id][option.id] = button;
      button.addEventListener("click", () => {
        toggleGroupedChoice(
          selectedItemsByGroup[group.id],
          option.id,
          Number(group.maximum || 1),
        );
        renderEquipmentItemChoiceGroups(
          container,
          requirements,
          selectedByGroup,
          selectedItemsByGroup,
          save,
        );
      });
      grid.append(button);
    });
    section.append(grid);
    container.append(section);
  });
  refreshChoiceGroupState(groups, selectedItemsByGroup, counters, optionButtons, save);
}


function buildEquipmentPayload(requirements, selectedByGroup, selectedItemsByGroup) {
  const visibleItemGroupIds = new Set(
    (requirements.item_choice_groups || []).map((group) => group.id),
  );
  (requirements.choice_groups || []).forEach((group) => {
    (group.options || []).forEach((option) => {
      if (selectedByGroup[group.id]?.has(option.id)) {
        (option.selectors || []).forEach((selector) => {
          visibleItemGroupIds.add(selector.id);
        });
      }
    });
  });
  return {
    option_ids: Object.values(selectedByGroup).flatMap((selected) => [...selected]),
    item_choices: Object.fromEntries(
      Object.entries(selectedItemsByGroup)
        .filter(([groupId]) => visibleItemGroupIds.has(groupId))
        .map(([groupId, selected]) => [groupId, [...selected]]),
    ),
  };
}


function adventureConnectionEditor(guide) {
  const form = document.createElement("form");
  form.className = "wizard-inline-form wizard-adventure-connection";
  const inputs = {};
  (guide.requirements?.fields || []).forEach((field) => {
    const label = document.createElement("label");
    const span = document.createElement("span");
    span.textContent = field.label || field.id;
    const input = document.createElement("textarea");
    input.name = field.id;
    input.value = field.value || "";
    inputs[field.id] = input;
    label.append(span, input);
    form.append(label);
  });
  const button = document.createElement("button");
  button.type = "submit";
  button.textContent = state.locale === "zh-CN" ? "保存冒险关联" : "Save Hook";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(
      Object.entries(inputs).map(([fieldId, input]) => [
        fieldId,
        input.value.trim(),
      ]),
    );
    applyCharacterWizardChoice({
      metadata: {
        operation: "adventure_connection",
        payload,
      },
    });
  });
  form.append(button);
  return form;
}


function identityEditor() {
  const form = document.createElement("form");
  form.className = "wizard-inline-form";
  const input = document.createElement("input");
  input.value = state.characterCreationSession?.draft?.name || "";
  input.placeholder = state.locale === "zh-CN" ? "角色名称" : "Character name";
  const button = document.createElement("button");
  button.type = "submit";
  button.textContent = state.locale === "zh-CN" ? "保存名称" : "Save Name";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    applyCharacterWizardChoice({
      metadata: {
        operation: "identity",
        payload: { name: input.value.trim() },
      },
    });
  });
  form.append(input, button);
  return form;
}


function abilityEditor(guide) {
  const form = document.createElement("form");
  form.className = "wizard-ability-form";
  const draft = state.characterCreationSession?.draft || {};
  const base = draft.abilities?.base || {};
  const requirements = guide?.requirements || {};
  const budget = requirements.budget ?? 27;
  const spent = requirements.spent ?? draft.abilities?.point_buy_spent ?? 0;
  const remaining = requirements.remaining ?? draft.abilities?.point_buy_remaining ?? budget;
  const summary = document.createElement("div");
  summary.className = "wizard-ability-summary";
  const summaryValues = {};
  abilitySummaryLabels(state.locale).forEach(([key, label]) => {
    const item = document.createElement("span");
    summaryValues[key] = item;
    summary.append(item);
  });
  updateAbilitySummary(summaryValues, { budget, spent, remaining });
  form.append(summary);
  const abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"];
  const inputs = {};
  const acceptedValues = Object.fromEntries(
    abilities.map((ability) => [ability, Number(base[ability] || 8)]),
  );
  const refreshSummary = (changedAbility = null) => {
    const values = Object.fromEntries(
      abilities.map((ability) => [ability, Number(inputs[ability].value)]),
    );
    let nextSpent = calculatePointBuySpent(values);
    if (
      changedAbility
      && Number(values[changedAbility]) > Number(acceptedValues[changedAbility])
      && Number.isFinite(nextSpent)
      && nextSpent > budget
    ) {
      values[changedAbility] = acceptedValues[changedAbility];
      inputs[changedAbility].value = String(acceptedValues[changedAbility]);
      nextSpent = calculatePointBuySpent(values);
    }
    if (Number.isFinite(nextSpent)) {
      Object.assign(acceptedValues, values);
      updateAbilityInputLimits(inputs, acceptedValues, budget);
    }
    updateAbilitySummary(summaryValues, {
      budget,
      spent: nextSpent,
      remaining: Number.isFinite(nextSpent) ? budget - nextSpent : null,
    });
  };
  abilities.forEach((ability) => {
    const label = document.createElement("label");
    const span = document.createElement("span");
    span.textContent = abilityLabel(ability);
    const input = document.createElement("input");
    input.type = "number";
    input.min = "8";
    input.max = "15";
    input.value = String(base[ability] || 8);
    input.name = ability;
    inputs[ability] = input;
    input.addEventListener("input", () => refreshSummary(ability));
    label.append(span, input);
    form.append(label);
  });
  updateAbilityInputLimits(inputs, acceptedValues, budget);
  const button = document.createElement("button");
  button.type = "submit";
  button.textContent = state.locale === "zh-CN" ? "保存属性" : "Save Abilities";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const values = {};
    abilities.forEach((ability) => {
      values[ability] = Number(form.querySelector(`[name="${ability}"]`).value);
    });
    applyCharacterWizardChoice({
      metadata: {
        operation: "abilities",
        payload: { base: values },
      },
    });
  });
  form.append(button);
  return form;
}


function abilitySummaryLabels(locale) {
  return locale === "zh-CN"
    ? [["budget", "可用点数"], ["spent", "已用"], ["remaining", "剩余"]]
    : [["budget", "Available"], ["spent", "Spent"], ["remaining", "Remaining"]];
}


function updateAbilitySummary(nodes, values) {
  const labels = Object.fromEntries(abilitySummaryLabels(state.locale));
  Object.entries(values).forEach(([key, value]) => {
    if (!nodes[key]) {
      return;
    }
    nodes[key].textContent = `${labels[key]} ${value ?? "-"}`;
  });
}


function calculatePointBuySpent(values) {
  let total = 0;
  for (const value of Object.values(values)) {
    const cost = POINT_BUY_COSTS[Number(value)];
    if (cost === undefined) {
      return NaN;
    }
    total += cost;
  }
  return total;
}


function updateAbilityInputLimits(inputs, values, budget) {
  Object.entries(inputs).forEach(([ability, input]) => {
    const otherSpent = Object.entries(values).reduce((total, [key, value]) => {
      if (key === ability) {
        return total;
      }
      return total + (POINT_BUY_COSTS[Number(value)] ?? 0);
    }, 0);
    let maxScore = 8;
    Object.keys(POINT_BUY_COSTS).forEach((score) => {
      const numericScore = Number(score);
      if (otherSpent + POINT_BUY_COSTS[numericScore] <= budget) {
        maxScore = Math.max(maxScore, numericScore);
      }
    });
    input.max = String(maxScore);
  });
}


async function openCharacterWizardStep(step) {
  if (state.characterCreationBusy) {
    return;
  }
  state.characterCreationEditingStep = step;
  setCharacterCreationBusy(true);
  try {
    await loadCharacterCreationGuide({ render: false, step });
    renderCharacterCreation();
  } catch (error) {
    state.characterCreationEditingStep = null;
    showError(error);
  } finally {
    setCharacterCreationBusy(false);
  }
}


function spellSelector(guide) {
  const wrapper = document.createElement("div");
  wrapper.className = "wizard-spells";
  const selected = new Set(guide.current_value?.spell_ids || []);
  const requirements = guide.requirements || {};
  const counter = document.createElement("p");
  counter.className = "wizard-prompt";
  counter.textContent = state.locale === "zh-CN"
    ? `已选戏法 ${requirements.selected_cantrips || 0}/${requirements.cantrips || 0}；1 环 ${requirements.selected_level_one || 0}/${requirements.level_one || 0}`
    : `Selected cantrips ${requirements.selected_cantrips || 0}/${requirements.cantrips || 0}, level one ${requirements.selected_level_one || 0}/${requirements.level_one || 0}`;
  wrapper.append(counter);
  const grid = document.createElement("div");
  grid.className = "wizard-options";
  guide.options.forEach((option) => {
    const card = optionCard({
      ...option,
      selected: selected.has(option.id),
      metadata: { operation: "spells", payload: { spell_ids: toggleId([...selected], option.id) } },
    });
    grid.append(card);
  });
  wrapper.append(grid);
  return wrapper;
}


function reviewPanel(guide) {
  const node = document.createElement("div");
  node.className = "wizard-review";
  const summary = guide.requirements?.summary || {};
  const text = document.createElement("p");
  text.textContent = state.locale === "zh-CN"
    ? "角色草稿已满足当前向导要求，可以确认创建。"
    : "The draft satisfies the current wizard requirements and can be confirmed.";
  node.append(text);
  const facts = document.createElement("dl");
  facts.className = "wizard-review-facts";
  const derived = summary.derived || {};
  [
    [t("name"), summary.name],
    [t("race"), localizeRaceName(summary.race)],
    [t("className"), localizeClassName(summary.class_name)],
    [t("background"), localizeBackgroundName(summary.background)],
    [t("hp"), derived.hp_max],
    [t("ac"), derived.armor_class],
    [t("speed"), derived.speed],
    [t("initiative"), derived.initiative],
  ].forEach(([label, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = String(value);
    facts.append(term, detail);
  });
  node.append(facts);
  if (summary.inventory?.length) {
    const inventory = document.createElement("section");
    const heading = document.createElement("h4");
    heading.textContent = t("inventory");
    inventory.append(heading);
    const list = document.createElement("ul");
    summary.inventory.forEach((entry) => {
      const item = document.createElement("li");
      item.textContent = inventoryEntryText(entry);
      list.append(item);
    });
    inventory.append(list);
    node.append(inventory);
  }
  return node;
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


function currentStepTitle(guide) {
  const step = guide.steps?.find((item) => item.id === guide.active_step);
  return step?.label || guide.active_step;
}


function buildWizardPayload(option) {
  return option?.metadata?.payload || null;
}


function toggleId(values, id) {
  return values.includes(id)
    ? values.filter((value) => value !== id)
    : [...values, id];
}


function abilityLabel(ability) {
  if (state.locale !== "zh-CN") {
    return ability.replace(/^\w/, (letter) => letter.toUpperCase());
  }
  return {
    strength: "力量",
    dexterity: "敏捷",
    constitution: "体质",
    intelligence: "智力",
    wisdom: "感知",
    charisma: "魅力",
  }[ability] || ability;
}


function removePendingCharacterGuideMessage(pendingMessage) {
  state.characterCreationMessages = state.characterCreationMessages.filter(
    (message) => message !== pendingMessage,
  );
}


function resetCharacterCreationState() {
  state.characterCreationSession = null;
  state.characterCreationGuide = null;
  state.characterCreationEditingStep = null;
  state.characterCreationMessages = [];
}
