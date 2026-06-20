import { t } from "./i18n.js?v=20260619-world-state-progress";

const MAX_HISTORY = 10;
const ROLL_DURATION_MS = 700;
const ROLL_TICK_MS = 75;

const D20_OUTLINE = `<svg viewBox="0 0 100 100" aria-hidden="true" fill="none" stroke="currentColor"><polygon points="50,4 90,27 90,73 50,96 10,73 10,27" stroke-width="3"/><polygon points="50,24 74,66 26,66" stroke-width="2"/><path d="M50 4 L50 24 M90 27 L74 66 M10 27 L26 66 M50 96 L74 66 M50 96 L26 66 M90 73 L74 66 M10 73 L26 66 M50 24 L10 27 M50 24 L90 27" stroke-width="1.4" opacity=".8"/></svg>`;

const history = [];
let rolling = false;

export function initDiceTray() {
  document.querySelectorAll("#dice-buttons .die-btn").forEach((button) => {
    button.addEventListener("click", () => rollDie(Number(button.dataset.die)));
  });
  renderDiceTray();
}

export function renderDiceTray() {
  if (rolling) {
    return;
  }
  const result = document.getElementById("dice-result");
  if (!result) {
    return;
  }
  const latest = history[0];
  if (!latest) {
    result.className = "dice-result is-empty";
    result.textContent = t("diceEmpty");
  } else {
    result.className = `dice-result settled${latest.crit ? " crit" : ""}${latest.fumble ? " fumble" : ""}`;
    result.innerHTML = faceMarkup(latest.value, captionFor(latest));
  }
  renderHistory();
}

function rollDie(sides) {
  const result = document.getElementById("dice-result");
  if (rolling || !result) {
    return;
  }
  rolling = true;
  result.className = "dice-result rolling";
  const started = Date.now();
  const timer = setInterval(() => {
    result.innerHTML = faceMarkup(rollValue(sides), `d${sides}`);
    if (Date.now() - started >= ROLL_DURATION_MS) {
      clearInterval(timer);
      const value = rollValue(sides);
      history.unshift({
        sides,
        value,
        crit: sides === 20 && value === 20,
        fumble: sides === 20 && value === 1,
      });
      if (history.length > MAX_HISTORY) {
        history.pop();
      }
      rolling = false;
      renderDiceTray();
    }
  }, ROLL_TICK_MS);
}

function rollValue(sides) {
  return 1 + Math.floor(Math.random() * sides);
}

function faceMarkup(value, caption) {
  return `<div><div class="die-shape">${D20_OUTLINE}<span class="die-value">${value}</span></div><span class="die-caption">${caption}</span></div>`;
}

function captionFor(entry) {
  if (entry.crit) {
    return `d${entry.sides} · ${t("diceCrit")}`;
  }
  if (entry.fumble) {
    return `d${entry.sides} · ${t("diceFumble")}`;
  }
  return `d${entry.sides}`;
}

function renderHistory() {
  const list = document.getElementById("dice-history");
  if (!list) {
    return;
  }
  list.replaceChildren();
  history.forEach((entry) => {
    const item = document.createElement("li");
    if (entry.crit) {
      item.className = "crit";
    } else if (entry.fumble) {
      item.className = "fumble";
    }
    item.textContent = `d${entry.sides} · ${entry.value}`;
    list.append(item);
  });
}
