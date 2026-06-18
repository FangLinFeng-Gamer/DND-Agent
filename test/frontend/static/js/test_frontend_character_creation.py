import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_character_creation_layout_keeps_wizard_separate_from_character_cards():
    html = (PROJECT_ROOT / "frontend/static/index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend/static/styles.css").read_text(encoding="utf-8")

    assert 'class="character-create-main"' in html
    assert 'grid-template-areas: "main draft";' in css
    assert 'grid-template-areas: "agent draft" "library draft";' not in css
    assert 'grid-template-areas: "agent" "draft" "library";' in css
    assert ".character-create-main {\n  grid-area: main;" in css
    assert ".character-agent-panel {\n  grid-area: agent;" in css
    assert ".character-draft-panel {\n  grid-area: draft;" in css
    assert ".character-library {\n  grid-area: library;" in css


def test_character_creation_form_omits_duplicate_race_class_and_summary():
    html = (PROJECT_ROOT / "frontend/static/index.html").read_text(encoding="utf-8")

    assert 'id="character-name"' in html
    assert 'id="character-race"' not in html
    assert 'id="character-class"' not in html
    assert 'id="character-draft"' not in html


def test_character_creation_prevents_duplicate_language_choices():
    module = (PROJECT_ROOT / "frontend/static/js/character-creation.js").read_text(encoding="utf-8")

    assert 'option?.rule_type === "language"' in module


def test_character_creation_new_session_after_completed_draft_resets_conversation(tmp_path):
    script_path = tmp_path / "character-new-session-reset-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    character_url = json.dumps(
        (PROJECT_ROOT / "frontend/static/js/character-creation.js").as_uri()
    )
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "en"; } },
            };

            class FakeElement {
              constructor() {
                this.value = "";
                this.children = [];
                this.className = "";
                this.textContent = "";
                this.disabled = false;
                this.scrollTop = 0;
                this.scrollHeight = 0;
                this.listeners = {};
                this.classList = {
                  add: () => {},
                  remove: () => {},
                  toggle: () => {},
                };
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
              createElement() {
                return new FakeElement();
              },
              getElementById() {
                return new FakeElement();
              },
            };

            function collectText(node) {
              if (!node) return "";
              const own = node.textContent || "";
              const childText = (node.children || []).map(collectText).join(" ");
              return `${own} ${childText}`;
            }

            function jsonResponse(payload) {
              return {
                ok: true,
                status: 200,
                headers: {
                  get(name) {
                    return name.toLowerCase() === "content-type" ? "application/json" : "";
                  },
                },
                async json() {
                  return payload;
                },
                async text() {
                  return JSON.stringify(payload);
                },
              };
            }

            const freshSession = {
              id: 22,
              locale: "en",
              status: "draft",
              revision: 0,
              draft: {
                name: "",
                race: "",
                class_name: "",
                background: "Adventurer",
                selections: { spell_ids: [] },
                abilities: { base: {}, final: {}, point_buy_remaining: 27 },
              },
              assistant_message: "Fresh character creation welcome.",
              validation_errors: [],
              metadata: {},
            };

            const freshGuide = {
              session_id: 22,
              locale: "en",
              active_step: "identity",
              actual_step: "identity",
              editable_steps: [],
              steps: [
                { id: "identity", label: "Name", status: "active" },
                { id: "class", label: "Class", status: "pending" },
              ],
              options: [],
              current_value: { name: "" },
              requirements: { prompt: "Enter a character name." },
              validation_errors: [],
            };

            const requests = [];
            globalThis.fetch = async (url, options = {}) => {
              requests.push({ url, options });
              if (url === "/api/character-creation/sessions" && options.method === "POST") {
                return jsonResponse(freshSession);
              }
              if (url === "/api/character-creation/sessions/22/guide?locale=en") {
                return jsonResponse(freshGuide);
              }
              throw new Error(`Unexpected request: ${options.method || "GET"} ${url}`);
            };

            const { els, state } = await import(__STATE_URL__);
            const {
              ensureCharacterCreationSession,
            } = await import(__CHARACTER_URL__);

            Object.assign(els, {
              status: new FakeElement(),
              characterWizard: new FakeElement(),
              characterCreationMessages: new FakeElement(),
              characterName: new FakeElement(),
              characterValidation: new FakeElement(),
              characterConfirm: new FakeElement(),
              characterAgentInput: new FakeElement(),
              characterAgentSend: new FakeElement(),
            });

            state.locale = "en";
            state.characterCreationSession = {
              ...freshSession,
              id: 9,
              status: "completed",
              assistant_message: "Old completed session.",
            };
            state.characterCreationGuide = null;
            state.characterCreationMessages = [
              { role: "assistant", content: "Old character draft transcript." },
              { role: "user", content: "confirm" },
            ];

            await ensureCharacterCreationSession();

            assert.equal(state.characterCreationSession.id, 22);
            assert.deepEqual(state.characterCreationMessages, [
              { role: "assistant", content: "Fresh character creation welcome." },
            ]);
            assert.doesNotMatch(collectText(els.characterCreationMessages), /Old character draft transcript/);
            assert.deepEqual(
              requests.map((request) => `${request.options.method || "GET"} ${request.url}`),
              [
                "POST /api/character-creation/sessions",
                "GET /api/character-creation/sessions/22/guide?locale=en",
              ],
            );
          """
        )
        .replace("__STATE_URL__", state_url)
        .replace("__CHARACTER_URL__", character_url),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["node", str(script_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_character_creation_review_panel_localizes_chinese_summary(tmp_path):
    script_path = tmp_path / "character-review-locale-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    character_url = json.dumps(
        (PROJECT_ROOT / "frontend/static/js/character-creation.js").as_uri()
    )
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "zh-CN"; } },
            };

            class FakeElement {
              constructor(value = "") {
                this.value = value;
                this.children = [];
                this.className = "";
                this.textContent = "";
                this.disabled = false;
                this.dataset = {};
                this.listeners = {};
                this.classList = {
                  add: (...names) => {
                    this.className = [this.className, ...names].filter(Boolean).join(" ");
                  },
                  remove: () => {},
                  toggle: () => {},
                };
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
              createElement() {
                return new FakeElement();
              },
              getElementById() {
                return new FakeElement();
              },
            };

            function collectText(node) {
              if (!node) return "";
              const own = node.textContent || "";
              const childText = (node.children || []).map(collectText).join(" ");
              return `${own} ${childText}`;
            }

            const session = {
              id: 7,
              locale: "zh-CN",
              status: "draft",
              revision: 3,
              draft: {
                name: "戴尔",
                race: "Human",
                class_name: "Fighter",
                background: "Noble",
                selections: { spell_ids: [] },
                abilities: { base: {}, final: {}, point_buy_remaining: 0 },
              },
              assistant_message: "",
              validation_errors: [],
              metadata: {},
            };

            const reviewGuide = {
              session_id: 7,
              locale: "zh-CN",
              active_step: "review",
              actual_step: "review",
              editable_steps: ["identity", "class", "race", "background", "abilities"],
              steps: [
                { id: "identity", label: "名称", status: "completed" },
                { id: "class", label: "职业", status: "completed" },
                { id: "race", label: "种族", status: "completed" },
                { id: "background", label: "背景", status: "completed" },
                { id: "review", label: "确认", status: "active" },
              ],
              options: [],
              current_value: null,
              requirements: {
                mode: "review",
                can_confirm: true,
                summary: {
                  name: "戴尔",
                  race: "Human",
                  class_name: "Fighter",
                  background: "Noble",
                  derived: {
                    hp_max: 12,
                    armor_class: 16,
                    speed: 30,
                    initiative: 1,
                  },
                  inventory: [
                    { item_id: "equipment.quarterstaff", title: "长棍", quantity: 1 },
                    { item_id: "equipment.dagger", title: "匕首", quantity: 2 },
                  ],
                },
              },
              validation_errors: [],
            };

            const { els, state } = await import(__STATE_URL__);
            const {
              renderCharacterCreation,
            } = await import(__CHARACTER_URL__);

            Object.assign(els, {
              status: new FakeElement(),
              characterWizard: new FakeElement(),
              characterCreationMessages: new FakeElement(),
              characterName: new FakeElement(),
              characterValidation: new FakeElement(),
              characterConfirm: new FakeElement(),
              characterAgentInput: new FakeElement(),
              characterAgentSend: new FakeElement(),
            });

            state.locale = "zh-CN";
            state.characterCreationSession = session;
            state.characterCreationGuide = reviewGuide;
            state.characterCreationMessages = [];

            renderCharacterCreation();
            const reviewText = collectText(els.characterWizard);

            assert.match(reviewText, /名称/);
            assert.match(reviewText, /种族/);
            assert.match(reviewText, /职业/);
            assert.match(reviewText, /背景/);
            assert.match(reviewText, /生命/);
            assert.match(reviewText, /护甲/);
            assert.match(reviewText, /速度/);
            assert.match(reviewText, /先攻/);
            assert.match(reviewText, /装备/);
            assert.match(reviewText, /人类/);
            assert.match(reviewText, /战士/);
            assert.match(reviewText, /贵族/);
            assert.match(reviewText, /长棍/);
            assert.match(reviewText, /匕首 x2/);
            assert.doesNotMatch(reviewText, /\\bName\\b|\\bRace\\b|\\bClass\\b|\\bBackground\\b|\\bSpeed\\b|\\bInitiative\\b/);
            assert.doesNotMatch(reviewText, /\\bHuman\\b|\\bFighter\\b|\\bNoble\\b|equipment\\./);
          """
        )
        .replace("__STATE_URL__", state_url)
        .replace("__CHARACTER_URL__", character_url),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["node", str(script_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_character_creation_wizard_renders_options_and_syncs_choice(tmp_path):
    script_path = tmp_path / "character-wizard-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    character_url = json.dumps(
        (PROJECT_ROOT / "frontend/static/js/character-creation.js").as_uri()
    )
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "zh-CN"; } },
            };

            const createdElements = [];

            class FakeElement {
              constructor(value = "") {
                this.value = value;
                this.children = [];
                this.className = "";
                this.textContent = "";
                this.disabled = false;
                this.dataset = {};
                this.listeners = {};
                this.classList = {
                  add: (...names) => {
                    this.className = [this.className, ...names].filter(Boolean).join(" ");
                  },
                  remove: () => {},
                  toggle: () => {},
                };
                createdElements.push(this);
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

              reset() {
                this.resetCalled = true;
              }
            }

            globalThis.document = {
              createElement() {
                return new FakeElement();
              },
              getElementById() {
                return new FakeElement();
              },
            };

            function collectText(node) {
              if (!node) return "";
              const own = node.textContent || "";
              const childText = (node.children || []).map(collectText).join(" ");
              return `${own} ${childText}`;
            }

            function jsonResponse(payload) {
              return {
                ok: true,
                status: 200,
                headers: {
                  get(name) {
                    return name.toLowerCase() === "content-type" ? "application/json" : "";
                  },
                },
                async json() {
                  return payload;
                },
                async text() {
                  return JSON.stringify(payload);
                },
              };
            }

            const initialSession = {
              id: 1,
              locale: "zh-CN",
              status: "draft",
              revision: 1,
              draft: {
                name: "米拉",
                race: "",
                class_name: "",
                background: "Adventurer",
                selections: { spell_ids: [] },
                abilities: { base: {}, final: {}, point_buy_remaining: 27 },
              },
              assistant_message: "",
              validation_errors: [],
              metadata: {},
            };

            const classGuide = {
              session_id: 1,
              locale: "zh-CN",
              active_step: "class",
              actual_step: "class",
              editable_steps: ["identity", "class"],
              steps: [
                { id: "identity", label: "名称", status: "completed" },
                { id: "class", label: "职业", status: "active" },
                { id: "race", label: "种族", status: "pending" },
              ],
              options: [
                {
                  id: "class.wizard",
                  title: "法师",
                  subtitle: "以法术书记录魔法的学术型奥术施法者。",
                  badges: ["d6", "智力", "施法者"],
                  selected: false,
                  metadata: {
                    operation: "class",
                    payload: { class_id: "class.wizard" },
                  },
                },
              ],
              current_value: null,
              requirements: {},
              validation_errors: [],
            };

            const identityGuide = {
              ...classGuide,
              active_step: "identity",
              actual_step: "class",
              options: [],
              current_value: { name: "米拉" },
              requirements: { prompt: "请输入角色名称。" },
            };

            const abilityGuide = {
              ...classGuide,
              active_step: "abilities",
              actual_step: "abilities",
              editable_steps: ["identity", "class", "race", "background", "abilities"],
              steps: [
                { id: "identity", label: "名称", status: "completed" },
                { id: "class", label: "职业", status: "completed" },
                { id: "race", label: "种族", status: "completed" },
                { id: "background", label: "背景", status: "completed" },
                { id: "abilities", label: "属性", status: "active" },
              ],
              options: [],
              current_value: {
                strength: 8,
                dexterity: 14,
                constitution: 13,
                intelligence: 15,
                wisdom: 10,
                charisma: 8,
              },
              requirements: {
                mode: "point_buy",
                budget: 27,
                spent: 23,
                remaining: 4,
                prompt: "使用27点购点分配六项属性。",
              },
            };

            const updatedSession = {
              ...initialSession,
              revision: 2,
              draft: {
                ...initialSession.draft,
                class_name: "Wizard",
                selections: { class_id: "class.wizard", spell_ids: [] },
              },
              assistant_message: "已记录：职业 = 法师。下一步：种族。",
            };

            const requests = [];
            globalThis.fetch = async (url, options = {}) => {
              requests.push({ url, options });
              if (url === "/api/character-creation/sessions/1/draft" && options.method === "PATCH") {
                return jsonResponse(updatedSession);
              }
              if (url === "/api/character-creation/sessions/1/guide?locale=zh-CN&step=identity") {
                return jsonResponse(identityGuide);
              }
              if (url === "/api/character-creation/sessions/1/guide?locale=zh-CN") {
                return jsonResponse({ ...classGuide, active_step: "race", options: [] });
              }
              throw new Error(`Unexpected request: ${options.method || "GET"} ${url}`);
            };

            const { els, state } = await import(__STATE_URL__);
            const {
              applyCharacterWizardChoice,
              renderCharacterCreation,
            } = await import(__CHARACTER_URL__);

            Object.assign(els, {
              status: new FakeElement(),
              characterWizard: new FakeElement(),
              characterCreationMessages: new FakeElement(),
              characterName: new FakeElement(),
              characterClass: new FakeElement(),
              characterRace: new FakeElement(),
              characterDraft: new FakeElement(),
              characterValidation: new FakeElement(),
              characterConfirm: new FakeElement(),
              characterAgentInput: new FakeElement(),
              characterAgentSend: new FakeElement(),
            });

            state.locale = "zh-CN";
            state.characterCreationSession = initialSession;
            state.characterCreationGuide = classGuide;
            state.characterCreationMessages = [
              { role: "assistant", content: "请选择职业。" },
            ];

            renderCharacterCreation();
            assert.match(collectText(els.characterWizard), /法师/);
            assert.match(collectText(els.characterWizard), /施法者/);
            assert.doesNotMatch(collectText(els.characterDraft), /未设置|not set|Adventurer|背景/);

            const nameStep = createdElements.find((element) => (
              element.textContent === "名称"
              && String(element.className).includes("wizard-step-action")
            ));
            assert.ok(nameStep, "completed step should render as a clickable control");
            await nameStep.listeners.click();
            assert.equal(state.characterCreationGuide.active_step, "identity");

            await applyCharacterWizardChoice(classGuide.options[0]);

            assert.equal(state.characterCreationSession.revision, 2);
            assert.equal(state.characterCreationMessages.at(-1).content, updatedSession.assistant_message);
            assert.deepEqual(
              requests.map((request) => `${request.options.method || "GET"} ${request.url}`),
              [
                "GET /api/character-creation/sessions/1/guide?locale=zh-CN&step=identity",
                "PATCH /api/character-creation/sessions/1/draft",
                "GET /api/character-creation/sessions/1/guide?locale=zh-CN",
              ],
            );

            state.characterCreationGuide = abilityGuide;
            state.characterCreationSession = {
              ...initialSession,
              draft: {
                ...initialSession.draft,
                abilities: {
                  base: abilityGuide.current_value,
                  final: abilityGuide.current_value,
                  point_buy_spent: 22,
                  point_buy_remaining: 5,
                },
              },
            };
            renderCharacterCreation();
            const abilityText = collectText(els.characterWizard);
            assert.match(abilityText, /可用点数\\s+27/);
            assert.match(abilityText, /已用\\s+23/);
            assert.match(abilityText, /剩余\\s+4/);

            const strengthInput = createdElements.find((element) => element.name === "strength");
            assert.ok(strengthInput, "strength input should exist");
            strengthInput.value = "15";
            strengthInput.listeners.input();
            assert.equal(strengthInput.value, "8");
            const updatedAbilityText = collectText(els.characterWizard);
            assert.match(updatedAbilityText, /已用\\s+23/);
            assert.match(updatedAbilityText, /剩余\\s+4/);

            const cappedAbilityGuide = {
              ...abilityGuide,
              current_value: {
                strength: 15,
                dexterity: 14,
                constitution: 13,
                intelligence: 12,
                wisdom: 10,
                charisma: 8,
              },
              requirements: {
                ...abilityGuide.requirements,
                spent: 27,
                remaining: 0,
              },
            };
            state.characterCreationGuide = cappedAbilityGuide;
            state.characterCreationSession = {
              ...initialSession,
              draft: {
                ...initialSession.draft,
                abilities: {
                  base: cappedAbilityGuide.current_value,
                  final: cappedAbilityGuide.current_value,
                  point_buy_spent: 27,
                  point_buy_remaining: 0,
                },
              },
            };
            renderCharacterCreation();
            const latestInput = (name) => [...createdElements].reverse().find((element) => element.name === name);
            const charismaInput = latestInput("charisma");
            charismaInput.value = "9";
            charismaInput.listeners.input();
            assert.equal(charismaInput.value, "8");
            assert.match(collectText(els.characterWizard), /已用\\s+27/);
            assert.match(collectText(els.characterWizard), /剩余\\s+0/);

            const wisdomInput = latestInput("wisdom");
            wisdomInput.value = "8";
            wisdomInput.listeners.input();
            assert.match(collectText(els.characterWizard), /已用\\s+25/);
            assert.match(collectText(els.characterWizard), /剩余\\s+2/);

            charismaInput.value = "9";
            charismaInput.listeners.input();
            assert.equal(charismaInput.value, "9");
            assert.match(collectText(els.characterWizard), /已用\\s+26/);
            assert.match(collectText(els.characterWizard), /剩余\\s+1/);
          """
        )
        .replace("__STATE_URL__", state_url)
        .replace("__CHARACTER_URL__", character_url),
        encoding="utf-8",
    )

    result = subprocess.run(["node", str(script_path)], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr


def test_character_creation_wizard_renders_choice_groups_and_submits_selection(tmp_path):
    script_path = tmp_path / "character-choice-groups-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    character_url = json.dumps(
        (PROJECT_ROOT / "frontend/static/js/character-creation.js").as_uri()
    )
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "en"; } },
            };

            const createdElements = [];

            class FakeElement {
              constructor() {
                this.value = "";
                this.children = [];
                this.className = "";
                this.textContent = "";
                this.disabled = false;
                this.dataset = {};
                this.listeners = {};
                this.classList = {
                  add: (...names) => {
                    this.className = [this.className, ...names].filter(Boolean).join(" ");
                  },
                  remove: (...names) => {
                    const remove = new Set(names);
                    this.className = String(this.className)
                      .split(" ")
                      .filter((name) => name && !remove.has(name))
                      .join(" ");
                  },
                  toggle: (name, force) => {
                    const names = new Set(String(this.className).split(" ").filter(Boolean));
                    const shouldAdd = force ?? !names.has(name);
                    if (shouldAdd) {
                      names.add(name);
                    } else {
                      names.delete(name);
                    }
                    this.className = [...names].join(" ");
                  },
                };
                createdElements.push(this);
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
              createElement() {
                return new FakeElement();
              },
              getElementById() {
                return new FakeElement();
              },
            };

            function collectText(node) {
              if (!node) return "";
              const own = node.textContent || "";
              const childText = (node.children || []).map(collectText).join(" ");
              return `${own} ${childText}`;
            }

            function jsonResponse(payload) {
              return {
                ok: true,
                status: 200,
                headers: {
                  get(name) {
                    return name.toLowerCase() === "content-type" ? "application/json" : "";
                  },
                },
                async json() {
                  return payload;
                },
                async text() {
                  return JSON.stringify(payload);
                },
              };
            }

            const session = {
              id: 7,
              locale: "en",
              status: "draft",
              revision: 3,
              draft: {
                name: "Mira",
                race: "Human",
                class_name: "Wizard",
                background: "Sage",
                selections: {
                  choice_values: { "wizard-skills": ["skill.arcana"] },
                  spell_ids: [],
                },
                abilities: { base: {}, final: {}, point_buy_remaining: 0 },
              },
              assistant_message: "",
              validation_errors: [],
              metadata: {},
            };

            const proficiencyGuide = {
              session_id: 7,
              locale: "en",
              active_step: "proficiencies",
              actual_step: "proficiencies",
              editable_steps: ["identity", "class", "race", "background", "abilities"],
              steps: [
                { id: "identity", label: "Name", status: "completed" },
                { id: "class", label: "Class", status: "completed" },
                { id: "race", label: "Race", status: "completed" },
                { id: "background", label: "Background", status: "completed" },
                { id: "abilities", label: "Abilities", status: "completed" },
                { id: "proficiencies", label: "Proficiencies", status: "active" },
              ],
              options: [],
              current_value: null,
              requirements: {
                mode: "choice_groups",
                prompt: "Choose the required skill, tool, or language proficiencies.",
                choice_groups: [
                  {
                    id: "wizard-skills",
                    title: "Wizard Skills",
                    minimum: 2,
                    maximum: 2,
                    selected: ["skill.arcana"],
                    options: [
                      { id: "skill.arcana", title: "Arcana", description: "Lore and magic." },
                      { id: "skill.history", title: "History", description: "Past events." },
                      { id: "skill.investigation", title: "Investigation", description: "Find clues." },
                    ],
                  },
                ],
              },
              validation_errors: [],
            };

            const updatedSession = {
              ...session,
              revision: 4,
              assistant_message: "Recorded: Proficiencies = wizard-skills: Arcana, Investigation. Next: Class Features.",
            };

            const requests = [];
            globalThis.fetch = async (url, options = {}) => {
              requests.push({ url, options });
              if (url === "/api/character-creation/sessions/7/draft" && options.method === "PATCH") {
                return jsonResponse(updatedSession);
              }
              if (url === "/api/character-creation/sessions/7/guide?locale=en") {
                return jsonResponse({
                  ...proficiencyGuide,
                  active_step: "class_features",
                  actual_step: "class_features",
                  requirements: { mode: "choice_groups", choice_groups: [] },
                });
              }
              throw new Error(`Unexpected request: ${options.method || "GET"} ${url}`);
            };

            const { els, state } = await import(__STATE_URL__);
            const {
              renderCharacterCreation,
            } = await import(__CHARACTER_URL__);

            Object.assign(els, {
              status: new FakeElement(),
              characterWizard: new FakeElement(),
              characterCreationMessages: new FakeElement(),
              characterName: new FakeElement(),
              characterValidation: new FakeElement(),
              characterConfirm: new FakeElement(),
              characterAgentInput: new FakeElement(),
              characterAgentSend: new FakeElement(),
            });

            state.locale = "en";
            state.characterCreationSession = session;
            state.characterCreationGuide = proficiencyGuide;
            state.characterCreationMessages = [];

            renderCharacterCreation();
            const wizardText = collectText(els.characterWizard);
            assert.match(wizardText, /Wizard Skills/);
            assert.match(wizardText, /Arcana/);
            assert.match(wizardText, /Investigation/);
            assert.doesNotMatch(wizardText, /No options are available/);

            const investigationButton = createdElements.find((element) => (
              element.listeners.click
              && collectText(element).includes("Investigation")
            ));
            assert.ok(investigationButton, "choice option should be clickable");
            investigationButton.listeners.click();

            const saveButton = createdElements.find((element) => (
              element.listeners.click
              && collectText(element).includes("Save Selections")
            ));
            assert.ok(saveButton, "choice groups should expose a save control");
            await saveButton.listeners.click();

            assert.deepEqual(
              requests.map((request) => `${request.options.method || "GET"} ${request.url}`),
              [
                "PATCH /api/character-creation/sessions/7/draft",
                "GET /api/character-creation/sessions/7/guide?locale=en",
              ],
            );
            assert.deepEqual(
              JSON.parse(requests[0].options.body),
              {
                expected_revision: 3,
                operation: "proficiencies",
                payload: {
                  choice_values: {
                    "wizard-skills": ["skill.arcana", "skill.investigation"],
                  },
                },
                locale: "en",
              },
            );
          """
        )
        .replace("__STATE_URL__", state_url)
        .replace("__CHARACTER_URL__", character_url),
        encoding="utf-8",
    )

    result = subprocess.run(["node", str(script_path)], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr


def test_character_creation_choice_groups_disable_duplicate_tool_selections(tmp_path):
    script_path = tmp_path / "character-choice-duplicate-tools-test.mjs"
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri())
    character_url = json.dumps(
        (PROJECT_ROOT / "frontend/static/js/character-creation.js").as_uri()
    )
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "en"; } },
            };

            const createdElements = [];

            class FakeElement {
              constructor() {
                this.value = "";
                this.children = [];
                this.className = "";
                this.textContent = "";
                this.disabled = false;
                this.dataset = {};
                this.listeners = {};
                this.classList = {
                  add: (...names) => {
                    this.className = [this.className, ...names].filter(Boolean).join(" ");
                  },
                  remove: (...names) => {
                    const remove = new Set(names);
                    this.className = String(this.className)
                      .split(" ")
                      .filter((name) => name && !remove.has(name))
                      .join(" ");
                  },
                  toggle: (name, force) => {
                    const names = new Set(String(this.className).split(" ").filter(Boolean));
                    const shouldAdd = force ?? !names.has(name);
                    if (shouldAdd) {
                      names.add(name);
                    } else {
                      names.delete(name);
                    }
                    this.className = [...names].join(" ");
                  },
                };
                createdElements.push(this);
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
              createElement() {
                return new FakeElement();
              },
              getElementById() {
                return new FakeElement();
              },
            };

            function collectText(node) {
              if (!node) return "";
              const own = node.textContent || "";
              const childText = (node.children || []).map(collectText).join(" ");
              return `${own} ${childText}`;
            }

            const session = {
              id: 9,
              locale: "en",
              status: "draft",
              revision: 5,
              draft: {
                name: "Mira",
                race: "Human",
                class_name: "Bard",
                background: "Entertainer",
                selections: {
                  choice_values: {
                    "bard-instruments": ["tool.instrument.lute"],
                  },
                  spell_ids: [],
                },
                abilities: { base: {}, final: {}, point_buy_remaining: 0 },
              },
              assistant_message: "",
              validation_errors: [],
              metadata: {},
            };

            const proficiencyGuide = {
              session_id: 9,
              locale: "en",
              active_step: "proficiencies",
              actual_step: "proficiencies",
              editable_steps: ["identity", "class", "race", "background", "abilities"],
              steps: [
                { id: "proficiencies", label: "Proficiencies", status: "active" },
              ],
              options: [],
              current_value: null,
              requirements: {
                mode: "choice_groups",
                prompt: "Choose proficiencies.",
                choice_groups: [
                  {
                    id: "bard-instruments",
                    title: "Bard Instruments",
                    minimum: 3,
                    maximum: 3,
                    selected: ["tool.instrument.lute"],
                    options: [
                      { id: "tool.instrument.lute", title: "Lute", rule_type: "tool" },
                      { id: "tool.instrument.flute", title: "Flute", rule_type: "tool" },
                      { id: "tool.instrument.drum", title: "Drum", rule_type: "tool" },
                    ],
                  },
                  {
                    id: "entertainer-instrument",
                    title: "Entertainer Instrument",
                    minimum: 1,
                    maximum: 1,
                    selected: [],
                    options: [
                      { id: "tool.instrument.lute", title: "Lute", rule_type: "tool" },
                      { id: "tool.instrument.viol", title: "Viol", rule_type: "tool" },
                    ],
                  },
                ],
              },
              validation_errors: [],
            };

            const { els, state } = await import(__STATE_URL__);
            const {
              renderCharacterCreation,
            } = await import(__CHARACTER_URL__);

            Object.assign(els, {
              status: new FakeElement(),
              characterWizard: new FakeElement(),
              characterCreationMessages: new FakeElement(),
              characterName: new FakeElement(),
              characterValidation: new FakeElement(),
              characterConfirm: new FakeElement(),
              characterAgentInput: new FakeElement(),
              characterAgentSend: new FakeElement(),
            });

            state.locale = "en";
            state.characterCreationSession = session;
            state.characterCreationGuide = proficiencyGuide;
            state.characterCreationMessages = [];

            renderCharacterCreation();
            const luteButtons = createdElements.filter((element) => (
              element.listeners.click
              && collectText(element).includes("Lute")
            ));

            assert.equal(luteButtons.length, 2);
            assert.equal(luteButtons[0].disabled, false);
            assert.equal(luteButtons[1].disabled, true);
          """
        )
        .replace("__STATE_URL__", state_url)
        .replace("__CHARACTER_URL__", character_url),
        encoding="utf-8",
    )

    result = subprocess.run(["node", str(script_path)], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
