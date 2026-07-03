import { apiBase, els, state } from "./state.js?v=20260703-isekai-time";
import { readErrorMessage } from "./api.js?v=20260703-isekai-time";
import { localizeFeature, t } from "./i18n.js?v=20260703-isekai-time";

export const VIEW_ROUTES = {
  home: "/home",
  races: "/races",
  "character-create": "/character-create",
  "story-create": "/stories",
  game: "/game",
  "model-config": "/models",
};

const ROUTE_VIEWS = Object.fromEntries(
  Object.entries(VIEW_ROUTES).map(([view, route]) => [route, view]),
);
ROUTE_VIEWS["/play"] = "game";
const ROUTE_BASE = "/dnd-agent/v1";

export function routeForView(view) {
  return VIEW_ROUTES[view] || VIEW_ROUTES.home;
}

export function viewFromPath(pathname = window.location.pathname) {
  let route = pathname || "/";
  if (route.startsWith(ROUTE_BASE)) {
    route = route.slice(ROUTE_BASE.length) || "/";
  }
  route = route.replace(/\/+$/, "") || "/";
  const gameRoomMatch = route.match(/^\/game\/(\d+)$/);
  if (gameRoomMatch) {
    state.routeAdventureId = Number(gameRoomMatch[1]);
    state.selectedAdventureId = state.routeAdventureId;
    state.gameMode = "room";
    return "game";
  }
  state.routeAdventureId = null;
  if (route === "/game" || route === "/play") {
    state.gameMode = "setup";
    state.selectedAdventureId = null;
    state.selectedAdventure = null;
  }
  return ROUTE_VIEWS[route] || "home";
}

export function showView(view, { updateUrl = true, replace = false } = {}) {
  state.view = view;
  document.querySelectorAll(".app-view").forEach((node) => {
    node.classList.toggle("hidden", node.id !== `${view}-view`);
  });
  document.querySelectorAll(".view-nav [data-view-target]").forEach((button) => {
    button.classList.toggle("active", button.dataset.viewTarget === view);
  });
  syncViewRoute(view, { updateUrl, replace });
}

function syncViewRoute(view, { updateUrl, replace }) {
  if (!updateUrl || !window.history) {
    return;
  }
  const dynamicRoute = view === "game" && state.gameMode === "room" && state.selectedAdventureId
    ? `/game/${state.selectedAdventureId}`
    : routeForView(view);
  const route = `${apiBase}${dynamicRoute}`;
  if (window.location.pathname === route) {
    return;
  }
  const method = replace ? "replaceState" : "pushState";
  window.history[method]({ view }, "", route);
}

export function renderCapabilities() {
  if (!els.capabilities) {
    return;
  }
  const features = state.capabilities?.features || [];
  els.capabilities.textContent = features.length
    ? features.map(localizeFeature).join(" | ")
    : t("capabilitiesUnavailable");
}

export function statNode(label, value) {
  const node = document.createElement("div");
  node.className = "stat";
  node.innerHTML = `<span></span><strong></strong>`;
  node.querySelector("span").textContent = label;
  node.querySelector("strong").textContent = value;
  return node;
}

export function pillNode(text) {
  const node = document.createElement("span");
  node.className = "pill";
  node.textContent = text;
  return node;
}

export function emptyNode(text) {
  const node = document.createElement("div");
  node.className = "detail-empty";
  node.textContent = text;
  return node;
}

export function typingIndicatorNode(label = t("dmThinking")) {
  const node = document.createElement("span");
  node.className = "typing-indicator";
  node.setAttribute("aria-label", label);
  node.innerHTML = "<span></span><span></span><span></span>";
  return node;
}

export function numberOrDefault(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function setStatus(message, kind = "") {
  els.status.textContent = message;
  els.status.className = `status ${kind}`.trim();
}

export function showError(error) {
  setStatus(readErrorMessage(error.payload) || error.message, "error");
}
