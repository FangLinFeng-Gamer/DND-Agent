import { els, state } from "./state.js?v=20260618-game-room-layout10";
import { enTranslations } from "./locales/en.js?v=20260618-game-room-layout10";
import { zhCNTranslations } from "./locales/zh-CN.js?v=20260618-game-room-layout10";

export const translations = {
  en: enTranslations,
  "zh-CN": zhCNTranslations,
};

export function t(key, values = {}) {
  return translate(state.locale, key, values);
}

export function translate(locale, key, values = {}) {
  const template = translations[locale]?.[key] || translations.en[key] || key;
  return Object.entries(values).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    template,
  );
}

export function applyTranslations(previousLocale = null) {
  document.documentElement.lang = state.locale;
  if (els.languageSelect) {
    els.languageSelect.value = state.locale;
  }

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-value]").forEach((node) => {
    const key = node.dataset.i18nValue;
    if (!previousLocale || node.value === translate(previousLocale, key)) {
      node.value = t(key);
    }
  });
}

export function setLocale(locale) {
  const previousLocale = state.locale;
  state.locale = locale === "zh-CN" ? "zh-CN" : "en";
  window.localStorage?.setItem("dnd-agent.locale", state.locale);
  applyTranslations(previousLocale);
}

export function localizeFeature(feature) {
  return localizePrefixed("feature", feature);
}

export function localizeStatus(status) {
  return localizePrefixed("status", status);
}

export function localizeRole(role) {
  return localizePrefixed("role", role);
}

export function localizeSide(side) {
  return localizePrefixed("side", side);
}

export function localizeCombatAction(action) {
  const labels = {
    attack: "combatActionAttack",
    dodge: "combatActionDodge",
    dash: "combatActionDash",
    disengage: "combatActionDisengage",
    end_turn: "combatActionEndTurn",
  };
  return t(labels[action] || "combatActionUnknown");
}

export function localizeRaceName(name) {
  return localizePrefixed("raceName", name);
}

export function localizeClassName(name) {
  return localizePrefixed("className", name);
}

export function localizeBackgroundName(name) {
  return localizePrefixed("backgroundName", name);
}

export function localizeEquipmentName(itemId) {
  return localizePrefixed("equipmentName", itemId);
}

export function localizeRaceTag(tag) {
  return localizePrefixed("raceTag", tag);
}

export function localizeRaceMechanicLabel(key) {
  const labels = {
    ability_score: "raceMechanicAbilityScore",
    size: "raceMechanicSize",
    speed: "raceMechanicSpeed",
    languages: "raceMechanicLanguages",
    features: "raceMechanicFeatures",
  };
  return t(labels[key] || key);
}

export function localizePrefixed(prefix, value) {
  const key = `${prefix}.${value}`;
  return Object.hasOwn(translations[state.locale] || {}, key) ? t(key) : value;
}

export function localizeWorldMessage(message) {
  if (message === "Found world entries.") {
    return t("worldEntriesFound");
  }
  if (message === "No world entries matched the search.") {
    return t("worldEntriesNotFound");
  }
  return message;
}
