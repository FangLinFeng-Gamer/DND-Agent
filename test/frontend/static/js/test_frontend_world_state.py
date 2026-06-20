import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "static"


def test_game_room_exposes_world_state_panel_and_i18n():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    i18n = (FRONTEND_DIR / "js/locales/en.js").read_text(encoding="utf-8") + (
        FRONTEND_DIR / "js/locales/zh-CN.js"
    ).read_text(encoding="utf-8")

    for element_id in [
        "world-state-phase",
        "world-state-clocks",
        "world-state-events",
    ]:
        assert f'id="{element_id}"' in html

    for key in [
        "worldSituation",
        "worldSituationEmpty",
        "worldRecentChanges",
    ]:
        assert f'"{key}"' in i18n


def test_render_world_state_hides_hidden_events(tmp_path):
    script_path = tmp_path / "world-state-render-test.mjs"
    state_url = json.dumps((FRONTEND_DIR / "js/state.js").as_uri())
    game_url = json.dumps((FRONTEND_DIR / "js/game.js").as_uri())
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "zh-CN"; } },
              history: { pushState() {}, replaceState() {} },
            };

            class FakeElement {
              constructor(tag = "div") {
                this.tag = tag;
                this.children = [];
                this.className = "";
                this.textContent = "";
                this.style = {};
                this.disabled = false;
                this.listeners = {};
                this.classList = { add() {}, remove() {}, toggle() {} };
              }

              replaceChildren(...children) {
                this.children = children;
              }

              append(...children) {
                this.children.push(...children);
              }

              appendChild(child) {
                this.children.push(child);
                return child;
              }

              addEventListener(name, handler) {
                this.listeners[name] = handler;
              }

              querySelector() {
                return new FakeElement();
              }

              setAttribute(name, value) {
                this[name] = value;
              }
            }

            globalThis.document = {
              createElement(tag) {
                return new FakeElement(tag);
              },
              getElementById() {
                return new FakeElement();
              },
              querySelectorAll() {
                return [];
              },
            };

            function collectText(node) {
              if (!node) return "";
              const own = node.textContent || "";
              const childText = (node.children || []).map(collectText).join(" ");
              return `${own} ${childText}`;
            }

            const { els, state } = await import(__STATE_URL__);
            const { renderWorldState } = await import(__GAME_URL__);

            state.locale = "zh-CN";
            els.worldStatePhase = new FakeElement();
            els.worldStateClocks = new FakeElement();
            els.worldStateEvents = new FakeElement();

            renderWorldState({
              phase_label: "节庆混乱",
              threat_clocks: [
                { label: "月井危机", value: 3, max: 6, visible: true },
              ],
              pressure_clocks: [],
              visible_events: ["广场音乐停了，村民围在月井旁争吵。"],
              hidden_events: ["井下怪物正在突破封印"],
            });

            const text = [
              collectText(els.worldStatePhase),
              collectText(els.worldStateClocks),
              collectText(els.worldStateEvents),
            ].join(" ");
            assert.match(text, /节庆混乱/);
            assert.match(text, /月井危机 3\\/6/);
            assert.match(text, /广场音乐停了/);
            assert.doesNotMatch(text, /井下怪物/);
            """
        )
        .replace("__STATE_URL__", state_url)
        .replace("__GAME_URL__", game_url),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["node", str(script_path)],
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
