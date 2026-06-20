import { els, state } from "./state.js?v=20260620-isekai-events";
import { enTranslations } from "./locales/en.js?v=20260620-isekai-events";
import { zhCNTranslations } from "./locales/zh-CN.js?v=20260620-isekai-events";

export const translations = {
  en: enTranslations,
  "zh-CN": zhCNTranslations,
};

const zhEquipmentTerms = {
  arcane: "奥术",
  bell: "铃",
  bone: "骨制",
  bronze: "青铜",
  cloak: "斗篷",
  copper: "铜制",
  cracked: "裂纹",
  dagger: "匕首",
  dark: "暗色",
  dust: "粉尘",
  festival: "节庆",
  gold: "金制",
  golden: "金制",
  helm: "头盔",
  helmet: "头盔",
  holy: "神圣",
  iron: "铁制",
  key: "钥匙",
  lantern: "提灯",
  leather: "皮革",
  longsword: "长剑",
  moon: "月",
  moonwell: "月井",
  old: "旧",
  potion: "药水",
  prayer: "祷告",
  ring: "戒指",
  robe: "长袍",
  rusty: "生锈",
  scroll: "卷轴",
  shield: "盾牌",
  silver: "银制",
  small: "小型",
  steel: "钢制",
  sword: "剑",
  token: "信物",
  wooden: "木制",
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
  const localized = localizePrefixed("equipmentName", itemId);
  return localized === itemId ? humanizeEquipmentId(itemId) : localized;
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

function humanizeEquipmentId(itemId) {
  const raw = String(itemId || "").replace(/^equipment\./, "").trim();
  if (!raw) {
    return "";
  }
  const parts = raw.split(/[-_]+/).filter(Boolean);
  if (parts.length === 0) {
    return raw;
  }
  if (state.locale === "zh-CN") {
    return parts.map((part) => zhEquipmentTerms[part] || part).join("");
  }
  return parts.map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
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
