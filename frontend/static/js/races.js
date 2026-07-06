import { api } from "./api.js?v=20260706-isekai-clock";
import { els, state } from "./state.js?v=20260706-isekai-clock";
import { localizeRaceMechanicLabel, localizeRaceName, localizeRaceTag, t } from "./i18n.js?v=20260706-isekai-clock";
import { emptyNode, pillNode, setStatus, showError } from "./ui.js?v=20260706-isekai-clock";

export async function loadRaces() {
  try {
    const response = await api("/api/world/search?category=race");
    state.races = response.results || [];
    if (!state.selectedRaceName && state.races.length) {
      state.selectedRaceName = state.races[0].name;
    }
    renderRaceOptions();
    renderRaceList();
    renderRaceDetail();
    setStatus(t("racesLoaded"), "ok");
  } catch (error) {
    showError(error);
  }
}

export function renderRaceOptions() {
  if (!els.characterRace) {
    return;
  }
  const selected = els.characterRace.value || state.selectedRaceName || t("defaultRace");
  els.characterRace.replaceChildren();
  state.races.forEach((race) => {
    const option = document.createElement("option");
    option.value = race.name;
    option.textContent = localizeRaceName(race.name);
    option.selected = race.name === selected;
    els.characterRace.append(option);
  });
}

export function renderRaceList() {
  if (!els.raceList) {
    return;
  }
  els.raceList.replaceChildren();
  if (!state.races.length) {
    els.raceList.append(emptyNode(t("noRacesYet")));
    return;
  }
  state.races.forEach((race) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `list-item ${race.name === state.selectedRaceName ? "active" : ""}`;
    item.innerHTML = `<span class="item-title"></span><span class="item-meta"></span>`;
    item.querySelector(".item-title").textContent = localizeRaceName(race.name);
    item.querySelector(".item-meta").textContent = race.tags.map(localizeRaceTag).join(" | ");
    item.addEventListener("click", () => {
      state.selectedRaceName = race.name;
      renderRaceList();
      renderRaceDetail();
      if (els.characterRace) {
        els.characterRace.value = race.name;
      }
    });
    els.raceList.append(item);
  });
}

export function renderRaceDetail() {
  if (!els.raceDetail) {
    return;
  }
  const race = state.races.find((item) => item.name === state.selectedRaceName);
  els.raceDetail.replaceChildren();
  if (!race) {
    els.raceDetail.className = "detail-empty";
    els.raceDetail.textContent = t("selectRace");
    return;
  }
  els.raceDetail.className = "detail-card";
  const title = document.createElement("strong");
  title.textContent = localizeRaceName(race.name);
  const summary = raceSectionNode(t("raceSummary"), localizedRaceText(race.metadata?.summary, race.content));
  const traits = raceSectionNode(t("raceTraits"), localizedRaceText(race.metadata?.traits, ""));
  const mechanics = renderRaceMechanics(race.metadata?.mechanics);
  const subraces = renderRaceSubraces(race.metadata?.subraces || []);
  const tags = document.createElement("div");
  tags.className = "pill-row";
  race.tags.forEach((tag) => tags.append(pillNode(localizeRaceTag(tag))));
  els.raceDetail.append(title, summary, traits, mechanics, subraces, tags);
}

export function localizedRaceText(value, fallback = "") {
  if (!value) {
    return fallback;
  }
  if (typeof value === "string") {
    return value;
  }
  const language = state.locale === "zh-CN" ? "zh" : "en";
  return value[language] || value.en || value.zh || fallback;
}

export function raceSectionNode(title, text) {
  const section = document.createElement("section");
  section.className = "race-section";
  const heading = document.createElement("strong");
  heading.textContent = title;
  const body = document.createElement("p");
  body.textContent = text;
  section.append(heading, body);
  return section;
}

export function renderRaceMechanics(mechanics = {}) {
  const section = document.createElement("section");
  section.className = "race-section";
  const heading = document.createElement("strong");
  heading.textContent = t("raceMechanics");
  const rows = document.createElement("div");
  rows.className = "race-mechanics";
  [
    "ability_score",
    "size",
    "speed",
    "languages",
    "features",
  ].forEach((key) => {
    if (!mechanics[key]) {
      return;
    }
    const row = document.createElement("p");
    row.innerHTML = `<span></span><strong></strong>`;
    row.querySelector("span").textContent = localizeRaceMechanicLabel(key);
    row.querySelector("strong").textContent = localizedRaceText(mechanics[key]);
    rows.append(row);
  });
  section.append(heading, rows);
  return section;
}

export function renderRaceSubraces(subraces) {
  const section = document.createElement("section");
  section.className = "race-section";
  const heading = document.createElement("strong");
  heading.textContent = t("raceSubraces");
  const content = document.createElement("p");
  if (!subraces.length) {
    content.textContent = "-";
  } else {
    content.textContent = subraces
      .map((subrace) => state.locale === "zh-CN" ? `${subrace.name} / ${subrace.zh}` : subrace.name)
      .join(", ");
  }
  section.append(heading, content);
  return section;
}
