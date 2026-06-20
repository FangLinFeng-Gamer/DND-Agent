import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_character_detail_renders_inventory_object_labels(tmp_path):
    script_path = tmp_path / "character-detail-inventory-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    game_url = json.dumps((PROJECT_ROOT / "frontend/static/js/game.js").as_uri())
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
                this._query = {};
                this.classList = {
                  add: () => {},
                  remove: () => {},
                  toggle: () => {},
                };
              }

              set innerHTML(value) {
                this.children = [];
                this._query = {};
                if (value.includes("<span></span>")) {
                  const span = new FakeElement("span");
                  const strong = new FakeElement("strong");
                  this.children.push(span, strong);
                  this._query.span = span;
                  this._query.strong = strong;
                }
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

              querySelector(selector) {
                return this._query[selector] || new FakeElement();
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
            const { renderCharacter } = await import(__GAME_URL__);

            state.locale = "zh-CN";
            state.characterDetailTab = "inventory";
            els.characterDetail = new FakeElement();

            renderCharacter({
              name: "阿林",
              level: 1,
              race: "人类",
              class_name: "战士",
              hp_current: 12,
              hp_max: 12,
              armor_class: 16,
              strength: 16,
              dexterity: 12,
              constitution: 14,
              charisma: 10,
              inventory: [
                { item_id: "equipment.quarterstaff", title: "长棍", quantity: 1 },
                { item_id: "equipment.dagger", title: "匕首", quantity: 2 },
              ],
            });

            const text = collectText(els.characterDetail);
            assert.match(text, /长棍/);
            assert.match(text, /匕首 x2/);
            assert.doesNotMatch(text, /\\[object Object\\]/);
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


def test_character_detail_localizes_inventory_item_ids(tmp_path):
    script_path = tmp_path / "character-detail-inventory-id-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    game_url = json.dumps((PROJECT_ROOT / "frontend/static/js/game.js").as_uri())
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "en"; } },
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
                this._query = {};
                this.classList = {
                  add: () => {},
                  remove: () => {},
                  toggle: () => {},
                };
              }

              set innerHTML(value) {
                this.children = [];
                this._query = {};
                if (value.includes("<span></span>")) {
                  const span = new FakeElement("span");
                  const strong = new FakeElement("strong");
                  this.children.push(span, strong);
                  this._query.span = span;
                  this._query.strong = strong;
                }
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

              querySelector(selector) {
                return this._query[selector] || new FakeElement();
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
            const { renderCharacter } = await import(__GAME_URL__);

            state.locale = "en";
            state.characterDetailTab = "inventory";
            els.characterDetail = new FakeElement();

            renderCharacter({
              name: "Dale",
              level: 1,
              race: "Human",
              class_name: "Ranger",
              hp_current: 12,
              hp_max: 12,
              armor_class: 14,
              strength: 12,
              dexterity: 16,
              constitution: 14,
              charisma: 10,
              inventory: [
                { item_id: "equipment.arrow", quantity: 20 },
                { item_id: "equipment.con-tools", quantity: 1 },
                { item_id: "equipment.dungeoneers-pack", quantity: 1 },
                { item_id: "equipment.longbow", quantity: 1 },
                { item_id: "equipment.shortsword", quantity: 2 },
              ],
            });

            const text = collectText(els.characterDetail);
            assert.match(text, /Arrow x20/);
            assert.match(text, /Con tools/);
            assert.match(text, /Dungeoneer's pack/);
            assert.match(text, /Longbow/);
            assert.match(text, /Shortsword x2/);
            assert.doesNotMatch(text, /equipment\\./);
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


def test_character_detail_localizes_custom_story_inventory_item_ids(tmp_path):
    script_path = tmp_path / "character-detail-custom-inventory-id-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    game_url = json.dumps((PROJECT_ROOT / "frontend/static/js/game.js").as_uri())
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
                this._query = {};
                this.classList = {
                  add: () => {},
                  remove: () => {},
                  toggle: () => {},
                };
              }

              set innerHTML(value) {
                this.children = [];
                this._query = {};
                if (value.includes("<span></span>")) {
                  const span = new FakeElement("span");
                  const strong = new FakeElement("strong");
                  this.children.push(span, strong);
                  this._query.span = span;
                  this._query.strong = strong;
                }
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

              querySelector(selector) {
                return this._query[selector] || new FakeElement();
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
            const { renderCharacter } = await import(__GAME_URL__);

            state.locale = "zh-CN";
            state.characterDetailTab = "inventory";
            els.characterDetail = new FakeElement();

            renderCharacter({
              name: "阿瑟",
              level: 1,
              race: "Human",
              class_name: "Fighter",
              hp_current: 12,
              hp_max: 12,
              armor_class: 14,
              strength: 16,
              dexterity: 12,
              constitution: 14,
              charisma: 10,
              inventory: [
                { item_id: "equipment.steel-longsword", quantity: 1 },
                { item_id: "equipment.small-shield", quantity: 1 },
                { item_id: "equipment.rusty-iron-key", quantity: 1 },
              ],
            });

            const text = collectText(els.characterDetail);
            assert.match(text, /钢制长剑/);
            assert.match(text, /小圆盾/);
            assert.match(text, /生锈铁制钥匙/);
            assert.doesNotMatch(text, /equipment\\./);
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


def test_room_actor_and_party_render_static_room_cards(tmp_path):
    script_path = tmp_path / "room-actor-party-static-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    game_url = json.dumps((PROJECT_ROOT / "frontend/static/js/game.js").as_uri())
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "en"; } },
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
                this._query = {};
                this.classList = {
                  add: () => {},
                  remove: () => {},
                  toggle: () => {},
                };
              }

              set innerHTML(value) {
                this.children = [];
                this._query = {};
                if (value.includes("<span></span>")) {
                  const span = new FakeElement("span");
                  const strong = new FakeElement("strong");
                  this.children.push(span, strong);
                  this._query.span = span;
                  this._query.strong = strong;
                }
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

              querySelector(selector) {
                return this._query[selector] || new FakeElement();
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

            function hasClass(node, className) {
              if (!node) return false;
              const classes = String(node.className || "").split(/\\s+/);
              return classes.includes(className) || (node.children || []).some((child) => hasClass(child, className));
            }

            function collectText(node) {
              if (!node) return "";
              const own = node.textContent || "";
              const childText = (node.children || []).map(collectText).join(" ");
              return `${own} ${childText}`;
            }

            const { els, state } = await import(__STATE_URL__);
            const { renderCharacter, renderRoomParty } = await import(__GAME_URL__);

            state.locale = "en";
            state.characterDetailTab = "attributes";
            els.characterDetail = new FakeElement();
            els.roomPartyList = new FakeElement();

            const party = [
              {
                id: 1,
                name: "Tav",
                level: 1,
                race: "Human",
                class_name: "Druid",
                hp_current: 8,
                hp_max: 11,
                armor_class: 14,
                strength: 12,
                dexterity: 14,
                constitution: 12,
                intelligence: 8,
                wisdom: 15,
                charisma: 11,
              },
              {
                id: 2,
                name: "Dale",
                race: "Human",
                class_name: "Paladin",
                hp_current: 10,
                hp_max: 12,
                armor_class: 16,
              },
            ];

            state.selectedCharacterId = 1;
            state.selectedAdventure = { party_characters: party };
            state.gameMode = "room";

            renderCharacter(party[0]);
            renderRoomParty();

            assert.equal(els.characterDetail.className, "character-card");
            assert.ok(hasClass(els.characterDetail, "bars"));
            assert.ok(hasClass(els.characterDetail, "bar-row"));
            assert.ok(hasClass(els.characterDetail, "bar-track"));
            assert.ok(hasClass(els.characterDetail, "bar-fill"));
            assert.ok(hasClass(els.characterDetail, "stat-grid"));
            assert.match(collectText(els.characterDetail), /Tav/);
            assert.match(collectText(els.characterDetail), /Dale/);
            assert.match(collectText(els.characterDetail), /Attributes/);
            assert.match(collectText(els.characterDetail), /Equipment/);
            assert.match(collectText(els.characterDetail), /Backpack/);
            assert.match(collectText(els.characterDetail), /WIS/);
            assert.match(collectText(els.characterDetail), /15/);

            assert.equal(els.roomPartyList.className, "party-list");
            assert.equal(els.roomPartyList.children.length, 2);
            assert.match(els.roomPartyList.children[0].className, /party-member/);
            assert.match(els.roomPartyList.children[0].className, /current/);
            assert.doesNotMatch(els.roomPartyList.children[0].className, /combatant/);
            assert.match(collectText(els.roomPartyList), /Current turn/);
            assert.match(collectText(els.roomPartyList), /Waiting/);

            els.roomPartyList.children[1].listeners.click();
            assert.equal(state.selectedCharacterId, 2);
            assert.match(collectText(els.characterDetail), /Dale/);
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
