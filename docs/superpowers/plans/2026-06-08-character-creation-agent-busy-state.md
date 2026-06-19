# Character Creation Agent Busy State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show an in-conversation character guide typing animation and prevent duplicate character creation requests while the agent is processing.

**Architecture:** Keep request serialization in `character-creation.js`, using the existing `state.characterCreationBusy` as a synchronous frontend lock acquired before any awaited work. Represent the waiting guide as a pending assistant message and reuse the shared typing indicator with a character-specific accessible label.

**Tech Stack:** Vanilla JavaScript ES modules, HTML/CSS, Python pytest contract tests, Playwright-based in-app browser verification.

---

### Task 1: Define the busy-state frontend contract

**Files:**
- Modify: `test/test_frontend_character_creation_agent.py`

- [ ] **Step 1: Write failing contract tests**

Add assertions that require:

```python
assert "characterAgentStillResponding" in module
assert "pending: true" in module
assert "typingIndicatorNode(t(\"characterAgentThinking\"))" in module
assert "els.characterConfirm.disabled = isBusy" in module
assert '"characterAgentStillResponding": "Character guide is still responding."' in i18n
assert '"characterAgentStillResponding": "角色创建向导仍在回复。"' in i18n
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
uv run pytest test/test_frontend_character_creation_agent.py -q
```

Expected: FAIL because the pending assistant rendering and localized duplicate-submit status are not implemented.

- [ ] **Step 3: Commit the failing test**

```powershell
git add test/test_frontend_character_creation_agent.py
git commit -m "test: define character guide busy state"
```

### Task 2: Implement serialized character guide requests

**Files:**
- Modify: `frontend/static/js/character-creation.js`
- Modify: `frontend/static/js/ui.js`
- Modify: `frontend/static/js/i18n.js`

- [ ] **Step 1: Acquire the request lock synchronously**

At the start of `sendCharacterCreationMessage`, reject a busy request with
`characterAgentStillResponding`, validate content, and call
`setCharacterCreationBusy(true)` before awaiting session creation.

- [ ] **Step 2: Add and remove the pending assistant message**

Append:

```javascript
const pendingAssistant = {
  role: "assistant",
  content: "",
  pending: true,
};
```

Render it immediately after the player message. Remove it before appending the
real response and in the error path.

- [ ] **Step 3: Render the shared typing animation**

Import `typingIndicatorNode`, and when an assistant message is pending with no
content, append:

```javascript
typingIndicatorNode(t("characterAgentThinking"))
```

instead of plain text.

- [ ] **Step 4: Keep every creation control locked**

Update `setCharacterCreationBusy` so the textarea, send button, and confirm
button are disabled while busy. On release, call `renderCharacterCreation()` to
restore confirm-button validity.

- [ ] **Step 5: Add localized duplicate-submit feedback**

Add:

```javascript
"characterAgentStillResponding": "Character guide is still responding."
```

and:

```javascript
"characterAgentStillResponding": "角色创建向导仍在回复。"
```

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
uv run pytest test/test_frontend_character_creation_agent.py test/test_frontend_streaming_ui.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit the implementation**

```powershell
git add frontend/static/js/character-creation.js frontend/static/js/ui.js frontend/static/js/i18n.js
git commit -m "feat: show character guide busy state"
```

### Task 3: Verify behavior end to end

**Files:**
- No production file changes expected.

- [ ] **Step 1: Run frontend and full regression tests**

Run:

```powershell
uv run pytest test/test_frontend_character_creation_agent.py test/test_frontend_streaming_ui.py -q
uv run pytest -q
node --check frontend/static/js/character-creation.js
node --check frontend/static/js/ui.js
```

Expected: all pytest tests pass and both Node syntax checks exit successfully.

- [ ] **Step 2: Restart the local service**

Start the application on `http://127.0.0.1:5000/` with the recovered runtime
database if the existing process is not serving the updated static files.

- [ ] **Step 3: Verify in the browser**

Open the character creation page, submit a message, and confirm:

- The player message appears once.
- The character guide displays the animated three-dot indicator.
- Textarea, send button, and confirm button are disabled while waiting.
- Repeated Enter/click attempts do not append or send another message.
- The animation is replaced by the returned guide response.
- Controls recover after completion.

- [ ] **Step 4: Check the final diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors and only intentional changes, if any remain.
