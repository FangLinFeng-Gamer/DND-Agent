# Multilingual Agent Interactions Implementation Plan

**Status:** Implemented and verified on 2026-06-07.

**Verification:** `131 passed`, plus a live bilingual
HTTP flow covering Chinese character creation, Chinese streaming DM narration,
and an English reply after switching locale.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the frontend character creation page to the Character Creation Agent and make the selected frontend locale control every new player-visible Agent response.

**Architecture:** Add one shared backend locale helper and pass normalized locale values through request schemas, DM graph planning, model prompts, narration, and template fallback. Move character creation frontend behavior into a focused module that owns the Agent session, conversation, draft rendering, confirmation, and busy state while preserving existing character CRUD for non-Agent clients.

**Tech Stack:** FastAPI, Pydantic, SQLite, LangChain, LangGraph, vanilla JavaScript ES modules, pytest, Node syntax checks, in-app browser verification.

---

### Task 1: Locale Contract and Prompt Helper

**Files:**
- Create: `backend/src/agent/locale.py`
- Modify: `backend/src/schemas/adventure.py`
- Modify: `backend/src/schemas/character_creation.py`
- Test: `test/test_agent_locale.py`

- [ ] **Step 1: Write failing locale contract tests**

Add tests proving:

```python
from backend.src.agent.locale import language_instruction, normalize_locale
from backend.src.schemas.adventure import MessageCreate
from backend.src.schemas.character_creation import CharacterCreationMessage


def test_normalize_locale_supports_english_and_simplified_chinese():
    assert normalize_locale("zh-CN") == "zh-CN"
    assert normalize_locale("en") == "en"
    assert normalize_locale("invalid") == "en"
    assert normalize_locale(None) == "en"


def test_language_instruction_is_explicit():
    assert "Simplified Chinese" in language_instruction("zh-CN")
    assert "English" in language_instruction("en")


def test_message_schemas_default_locale_to_english():
    assert MessageCreate(content="look").locale == "en"
    assert CharacterCreationMessage(content="help").locale == "en"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run pytest test/test_agent_locale.py -q
```

Expected: collection or assertion failure because the locale helper and schema fields do not exist.

- [ ] **Step 3: Implement normalized locale helpers and schema fields**

Implement:

```python
SUPPORTED_LOCALES = {"en", "zh-CN"}


def normalize_locale(locale: str | None) -> str:
    return locale if locale in SUPPORTED_LOCALES else "en"


def language_instruction(locale: str | None) -> str:
    if normalize_locale(locale) == "zh-CN":
        return (
            "All player-visible prose must be written in natural Simplified Chinese. "
            "Keep JSON field names, tool names, and internal identifiers in English."
        )
    return (
        "All player-visible prose must be written in natural English. "
        "Keep JSON field names, tool names, and internal identifiers in English."
    )
```

Add `locale: str = "en"` to `MessageCreate` and `CharacterCreationMessage`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
uv run pytest test/test_agent_locale.py -q
```

Expected: all locale contract tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/agent/locale.py backend/src/schemas/adventure.py backend/src/schemas/character_creation.py test/test_agent_locale.py
git commit -m "feat: add agent locale contract"
```

### Task 2: Character Creation Locale and Agent Responses

**Files:**
- Modify: `backend/src/api/character_creation.py`
- Modify: `backend/src/services/character_drafts.py`
- Modify: `backend/src/agent/character_creation/graph.py`
- Modify: `backend/src/agent/character_creation/state.py`
- Test: `test/test_character_creation_agent.py`

- [ ] **Step 1: Write failing character creation locale tests**

Add tests proving:

```python
def test_character_creation_returns_chinese_welcome(client):
    response = client.post(
        "/api/character-creation/sessions",
        json={"locale": "zh-CN"},
    )
    assert response.status_code == 200
    assert "角色" in response.json()["assistant_message"]


def test_character_creation_message_updates_session_locale(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()
    response = client.post(
        f"/api/character-creation/sessions/{session['id']}/messages",
        json={"content": "Help me", "locale": "zh-CN"},
    )
    assert response.json()["locale"] == "zh-CN"
    assert "角色" in response.json()["assistant_message"]


def test_character_creation_prompt_requires_selected_language(client, monkeypatch):
    # Capture the character creation ReAct system prompt and assert the
    # Simplified Chinese instruction is included for zh-CN.
    ...
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run pytest test/test_character_creation_agent.py -q
```

Expected: Chinese welcome contains mojibake, message locale is ignored, or prompt assertion fails.

- [ ] **Step 3: Pass locale through the character creation graph**

Add locale to `CharacterCreationState`. Change:

```python
CharacterCreationAgent.process(draft, content, locale)
```

and include `language_instruction(locale)` in the ReAct system prompt.

Change the API handler to call:

```python
service(request).handle_message(session_id, payload.content, payload.locale)
```

Normalize and persist the current locale before constructing the response.

- [ ] **Step 4: Replace corrupted Chinese strings**

Use valid Unicode text:

```python
"请告诉我角色名称、种族、职业和背景。完成后我会展示角色草稿并等待你确认。"
"角色已创建。"
f"角色草稿：{draft.name}，{draft.race} {draft.class_name}，背景 {draft.background}。请回复“确认创建”。"
```

Keep English equivalents for `en`.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```powershell
uv run pytest test/test_character_creation_agent.py -q
```

Expected: all character creation tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/api/character_creation.py backend/src/services/character_drafts.py backend/src/agent/character_creation test/test_character_creation_agent.py
git commit -m "feat: localize character creation agent"
```

### Task 3: Propagate Locale Through the DM Agent

**Files:**
- Modify: `backend/src/agent/dm/state.py`
- Modify: `backend/src/agent/dm/graph.py`
- Modify: `backend/src/agent/dm/prompts.py`
- Modify: `backend/src/agent/dm/supervisor.py`
- Modify: `backend/src/agent/dm/subagents.py`
- Modify: `backend/src/agent/dm/service.py`
- Test: `test/test_dm_agent_locale.py`
- Test: `test/test_dm_langgraph_supervisor.py`
- Test: `test/test_dm_langgraph_integration.py`

- [ ] **Step 1: Write failing prompt propagation tests**

Add tests that capture model messages and prove:

```python
assert "Simplified Chinese" in supervisor_system_prompt
assert "Simplified Chinese" in subagent_system_prompt
assert "Simplified Chinese" in narration_system_prompt
assert "Simplified Chinese" in legacy_dm_system_prompt
```

Add a graph test proving `locale == "zh-CN"` remains present from plan input to resolver input.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run pytest test/test_dm_agent_locale.py test/test_dm_langgraph_supervisor.py test/test_dm_langgraph_integration.py -q
```

Expected: locale is absent from graph state and prompts.

- [ ] **Step 3: Add locale to DM graph and planner APIs**

Change graph calls to accept locale:

```python
DMGraphRunner.plan(player_input, locale="en", model=None)
DMGraphRunner.run(player_input, resolver, locale="en", model=None)
DMSupervisor.plan(player_input, locale="en")
```

Store normalized locale in `DMGraphState` and include it when invoking the resolver.

- [ ] **Step 4: Add locale instructions to all model prompts**

Update prompt builders and Agent constructors to append:

```python
language_instruction(locale)
```

Apply this to:

- Supervisor.
- Exploration, social, story, NPC, and rules research agents.
- Narration Agent.
- Legacy combined DM messages.

Do not localize JSON keys or tool names.

- [ ] **Step 5: Pass request locale through DMService**

Use:

```python
locale = normalize_locale(message.locale)
```

and pass it into synchronous graph execution, streaming graph execution,
narration messages, and fallback provider calls.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
uv run pytest test/test_dm_agent_locale.py test/test_dm_langgraph_supervisor.py test/test_dm_langgraph_integration.py -q
```

Expected: all locale propagation tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/src/agent/dm test/test_dm_agent_locale.py test/test_dm_langgraph_supervisor.py test/test_dm_langgraph_integration.py
git commit -m "feat: propagate locale through dm agents"
```

### Task 4: Localize Offline DM Fallback

**Files:**
- Modify: `backend/src/agent/dm/service.py`
- Test: `test/test_dm_agent_locale.py`
- Test: `test/test_dm_streaming.py`

- [ ] **Step 1: Write failing fallback language tests**

Test both no-model and model-failure paths:

```python
def test_template_dm_uses_chinese_for_chinese_request(client):
    response = client.post(
        f"/api/adventures/{adventure_id}/messages",
        json={"content": "查看房间", "locale": "zh-CN"},
    )
    assert contains_chinese(response.json()["dm_message"]["content"])


def test_streaming_template_fallback_uses_chinese(client):
    # Configure a failing model client, send zh-CN, parse NDJSON, and assert
    # final narration contains Chinese.
    ...
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run pytest test/test_dm_agent_locale.py test/test_dm_streaming.py -q
```

Expected: template narration remains English.

- [ ] **Step 3: Make TemplateDMProvider locale-aware**

Change:

```python
opening_scene(character, world_entries, story=None, locale="en")
advance(scene, player_input, dice_result, combat_state, locale="en")
```

Return equivalent Simplified Chinese text when locale is `zh-CN`. Preserve scene
state semantics and English defaults.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
uv run pytest test/test_dm_agent_locale.py test/test_dm_streaming.py -q
```

Expected: synchronous and streaming fallback tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/agent/dm/service.py test/test_dm_agent_locale.py test/test_dm_streaming.py
git commit -m "feat: localize dm fallback narration"
```

### Task 5: Agent-Guided Character Creation Frontend

**Files:**
- Create: `frontend/static/js/character-creation.js`
- Modify: `frontend/static/index.html`
- Modify: `frontend/static/app.js`
- Modify: `frontend/static/js/state.js`
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/i18n.js`
- Modify: `frontend/static/styles.css`
- Test: `test/test_frontend_character_creation_agent.py`
- Test: `test/test_frontend_i18n.py`

- [ ] **Step 1: Write failing static frontend tests**

Assert:

```python
assert "/api/character-creation/sessions" in character_creation_js
assert 'locale: state.locale' in character_creation_js
assert 'api("/api/characters"' not in character_creation_js
assert "character-creation-messages" in index_html
assert "character-draft" in index_html
assert "character-confirm" in index_html
assert "./js/character-creation.js" in app_js
```

Also assert every new `data-i18n` key exists in English and Chinese.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run pytest test/test_frontend_character_creation_agent.py test/test_frontend_i18n.py -q
```

Expected: module and UI elements do not exist.

- [ ] **Step 3: Replace direct creation form with Agent workspace**

Add:

```html
<div id="character-creation-messages" class="agent-messages"></div>
<form id="character-agent-form">
  <textarea id="character-agent-input"></textarea>
  <button id="character-agent-send" type="submit"></button>
</form>
<div id="character-draft"></div>
<div id="character-validation"></div>
<button id="character-confirm" type="button" disabled></button>
```

Keep the character library and race browser navigation.

- [ ] **Step 4: Implement the character creation module**

The module owns:

```javascript
export async function ensureCharacterCreationSession()
export async function sendCharacterCreationMessage(content)
export async function confirmCharacterCreation()
export function renderCharacterCreation()
export function setCharacterCreationBusy(isBusy)
```

Session creation and messages send `state.locale`. Confirmation sends
`state.locale === "zh-CN" ? "确认创建" : "confirm"`.

On successful creation:

```javascript
state.selectedCharacterId = payload.created_character.id;
await loadCharacters();
showView("game");
```

- [ ] **Step 5: Integrate navigation and locale changes**

When a `data-view-target="character-create"` button is clicked, call
`ensureCharacterCreationSession()`. On locale change, re-render labels and draft
without clearing conversation or session state.

Remove the old character form submit binding and direct `createCharacter()`
frontend path.

- [ ] **Step 6: Add translations and focused styles**

Add English and Chinese strings for:

- Agent welcome area.
- Message placeholder.
- Send.
- Draft heading and empty state.
- Validation heading.
- Confirm creation.
- Agent busy and request failure.

Use an unframed two-column desktop layout and one-column mobile layout. Do not
nested-card the conversation and draft panels.

- [ ] **Step 7: Run static tests and syntax checks**

Run:

```powershell
uv run pytest test/test_frontend_character_creation_agent.py test/test_frontend_i18n.py -q
node --check frontend/static/app.js
node --check frontend/static/js/character-creation.js
node --check frontend/static/js/game.js
```

Expected: tests and syntax checks pass.

- [ ] **Step 8: Commit**

```powershell
git add frontend test/test_frontend_character_creation_agent.py test/test_frontend_i18n.py
git commit -m "feat: add guided character creation ui"
```

### Task 6: Send Locale With DM Requests

**Files:**
- Modify: `frontend/static/js/api.js`
- Modify: `frontend/static/js/game.js`
- Test: `test/test_frontend_dm_locale.py`

- [ ] **Step 1: Write failing frontend request tests**

Assert:

```python
assert 'JSON.stringify({ content, locale: state.locale })' in game_js_or_api_js
```

Cover both standard and streaming message paths.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run pytest test/test_frontend_dm_locale.py -q
```

Expected: locale is absent from the request body.

- [ ] **Step 3: Add locale to DM request bodies**

Update streaming helper:

```javascript
readStreamingResponse(adventureId, content, locale, onDelta)
```

and serialize:

```javascript
JSON.stringify({ content, locale })
```

Pass `state.locale` from `sendMessage()`. Apply the same shape to any
non-streaming DM request.

- [ ] **Step 4: Run tests and syntax checks**

Run:

```powershell
uv run pytest test/test_frontend_dm_locale.py -q
node --check frontend/static/js/api.js
node --check frontend/static/js/game.js
```

Expected: tests and syntax checks pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend/static/js/api.js frontend/static/js/game.js test/test_frontend_dm_locale.py
git commit -m "feat: send locale with dm messages"
```

### Task 7: Full Verification and Runtime Flow

**Files:**
- Modify: `docs/superpowers/progress/2026-05-22-dnd-agent-mvp-handoff.md`
- Modify: `docs/设计文档.md`
- Create: `scripts/verify_multilingual_agent_flow.py`

- [ ] **Step 1: Add an automated bilingual flow script**

The script must:

1. Create a `zh-CN` character creation session.
2. Submit character details.
3. Confirm creation in Chinese.
4. Create an adventure.
5. Send a Chinese DM action with `locale: "zh-CN"`.
6. Parse streaming events and assert the final narration contains Chinese.
7. Send a second action with `locale: "en"`.
8. Assert the next narration is English.

- [ ] **Step 2: Run focused and full automated verification**

Run:

```powershell
uv run pytest test/test_agent_locale.py test/test_character_creation_agent.py test/test_dm_agent_locale.py test/test_dm_langgraph_supervisor.py test/test_dm_langgraph_integration.py test/test_dm_streaming.py test/test_frontend_character_creation_agent.py test/test_frontend_dm_locale.py test/test_frontend_i18n.py -q
uv run pytest -q
uv run python -m compileall backend scripts
node --check frontend/static/app.js
node --check frontend/static/js/character-creation.js
node --check frontend/static/js/api.js
node --check frontend/static/js/game.js
uv run python -m scripts.verify_multilingual_agent_flow
git diff --check
```

Expected: zero failures and a successful bilingual end-to-end flow.

- [ ] **Step 3: Restart and verify the local service**

Restart the service from:

```text
F:\project\DND-Agent\.worktrees\dnd-agent-mvp
```

Verify:

- `GET http://127.0.0.1:5000/` returns `200`.
- Character creation session endpoint returns a Chinese welcome.
- Capabilities endpoint still advertises the Agent features.

- [ ] **Step 4: Browser verification**

Use the in-app browser to complete the acceptance flow from the design:

- Chinese character creation Agent conversation.
- Explicit confirmation.
- Adventure creation.
- Chinese streaming DM reply.
- Switch to English.
- English next DM reply.
- No overlapping controls or console errors.

- [ ] **Step 5: Update design and handoff documentation**

Document:

- Locale contract.
- Agent-guided character creation UI.
- Verification commands and results.
- Service URL and branch commit.

- [ ] **Step 6: Commit**

```powershell
git add docs scripts
git commit -m "docs: record multilingual agent verification"
```
