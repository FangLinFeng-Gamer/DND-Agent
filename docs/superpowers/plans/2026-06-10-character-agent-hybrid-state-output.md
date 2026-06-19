# Character Agent Hybrid State And Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the character creation agent persistent conversational context, schema-validated extraction, deterministic DND state updates, and natural player-facing model responses.

**Architecture:** Add a focused character-creation message repository beside the existing draft service. Pass bounded history and the current structured draft into a dedicated extractor, apply changes through deterministic rules, then give validated facts to a separate response composer with a template fallback.

**Tech Stack:** FastAPI, SQLite, Pydantic, LangChain chat models, LangGraph, pytest.

---

## File Structure

- Create `backend/src/agent/character_creation/models.py`: extraction and persisted-message models.
- Create `backend/src/agent/character_creation/messages.py`: SQLite message repository.
- Create `backend/src/agent/character_creation/extractor.py`: structured model extraction and deterministic parsing boundary.
- Create `backend/src/agent/character_creation/responder.py`: ordinary language model response and template fallback.
- Modify `backend/src/db/sqlite.py`: add the character creation message table.
- Modify `backend/src/agent/character_creation/state.py`: carry recent messages and responder metadata.
- Modify `backend/src/agent/character_creation/graph.py`: orchestrate extractor, rules, validation, and responder.
- Modify `backend/src/services/character_drafts.py`: persist user/assistant turns and load bounded history.
- Test in `test/test_character_creation_messages.py` and `test/test_character_creation_agent.py`.

### Task 1: Persist Character Creation Messages

**Files:**
- Modify: `backend/src/db/sqlite.py`
- Create: `backend/src/agent/character_creation/models.py`
- Create: `backend/src/agent/character_creation/messages.py`
- Create: `test/test_character_creation_messages.py`

- [ ] **Step 1: Write failing repository tests**

Add tests that create a session, append user and assistant messages, and assert:

```python
messages = repository.list_recent(session_id, limit=12)
assert [(item.role, item.content) for item in messages] == [
    ("user", "戴尔 人类战士"),
    ("assistant", "请分配属性值"),
]
```

Also insert 15 messages and assert only the latest 12 are returned in chronological order.

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
uv run pytest test/test_character_creation_messages.py -q
```

Expected: collection or import failure because the message repository does not exist.

- [ ] **Step 3: Add schema and repository**

Add this SQLite table:

```sql
CREATE TABLE IF NOT EXISTS character_creation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

Define:

```python
class CharacterCreationHistoryMessage(BaseModel):
    id: int | None = None
    role: Literal["user", "assistant"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
```

Implement `append()` and `list_recent()` with parameterized SQL. Fetch descending with a limit, then reverse to chronological order.

- [ ] **Step 4: Run repository tests**

Run:

```powershell
uv run pytest test/test_character_creation_messages.py -q
```

Expected: all message repository tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/db/sqlite.py backend/src/agent/character_creation/models.py backend/src/agent/character_creation/messages.py test/test_character_creation_messages.py
git commit -m "feat: persist character creation messages"
```

### Task 2: Isolate Structured Extraction

**Files:**
- Create: `backend/src/agent/character_creation/extractor.py`
- Modify: `backend/src/agent/character_creation/models.py`
- Modify: `backend/src/agent/character_creation/graph.py`
- Modify: `test/test_character_creation_agent.py`

- [ ] **Step 1: Write failing structured extraction tests**

Use a recording fake model and assert the request contains:

```python
{
    "current_draft": {...},
    "recent_messages": [
        {"role": "user", "content": "戴尔 人类战士"},
        {"role": "assistant", "content": "请分配属性值"},
    ],
    "message": "改成精灵",
}
```

Assert the extraction result is validated through:

```python
class CharacterExtraction(BaseModel):
    intent: Literal["provide_info", "update", "confirm", "help"] = "provide_info"
    name: str | None = None
    race: str | None = None
    class_name: str | None = None
    background: str | None = None
    alignment: str | None = None
    notes: str | None = None
    ability_scores: dict[str, int] | None = None
```

Add a test proving unknown keys are rejected or ignored before they reach `CharacterDraft`.

- [ ] **Step 2: Verify extraction tests fail**

Run:

```powershell
uv run pytest test/test_character_creation_agent.py -k "structured_extraction or receives_recent_history" -q
```

Expected: failure because history is not passed and no extraction model exists.

- [ ] **Step 3: Implement the extractor**

Move model prompt construction and JSON parsing out of `graph.py`. Require JSON-only output with the exact allowed schema. Include locale instructions, current draft, latest 12 messages, and current input.

Keep ordered six-number parsing deterministic:

```python
def extract_ordered_abilities(content: str) -> dict[str, int] | None:
    ...
```

Return extractor metadata containing `extractor` and model name. Fall back to existing Chinese and English parsing if model invocation or validation fails.

- [ ] **Step 4: Integrate extraction into graph state**

Extend `CharacterCreationState` with:

```python
recent_messages: list[dict[str, Any]]
extracted_changes: dict[str, Any]
```

Change `CharacterCreationAgent.process()` to accept `recent_messages`. Apply only non-null extraction fields. Continue using `calculate_abilities()` for ability validation.

- [ ] **Step 5: Run extraction and existing agent tests**

Run:

```powershell
uv run pytest test/test_character_creation_agent.py -q
```

Expected: all character creation agent tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/agent/character_creation/models.py backend/src/agent/character_creation/extractor.py backend/src/agent/character_creation/state.py backend/src/agent/character_creation/graph.py test/test_character_creation_agent.py
git commit -m "refactor: isolate character structured extraction"
```

### Task 3: Add Ordinary Conversation Response Generation

**Files:**
- Create: `backend/src/agent/character_creation/responder.py`
- Modify: `backend/src/agent/character_creation/graph.py`
- Modify: `test/test_character_creation_agent.py`

- [ ] **Step 1: Write failing responder tests**

Use a fake model that returns natural text and assert:

```python
assert result["assistant_message"] == "属性还没有完成，请重新分配。"
assert result["metadata"]["responder"] == "llm"
```

Inspect the fake model input and assert it contains validated facts:

```python
assert payload["next_step"] == "abilities"
assert payload["validation_errors"] == ["六项属性共花费 54 点，超过可用的 27 点。"]
assert payload["locale"] == "zh-CN"
```

Add a failure fake and assert the existing deterministic template is returned with `responder=template`.

- [ ] **Step 2: Verify responder tests fail**

Run:

```powershell
uv run pytest test/test_character_creation_agent.py -k "responder" -q
```

Expected: failure because all responses currently come from `_compose_response`.

- [ ] **Step 3: Implement the response composer**

Create `CharacterResponseComposer.compose()` that receives validated state and recent messages. The system prompt must require:

```text
Respond in the requested locale.
Preserve every supplied numeric rule and validation fact.
Ask exactly one next question.
Do not output JSON.
Do not claim a state change absent from changed_fields.
```

Call the model normally without `response_format`. Return empty/failed calls to the template fallback.

- [ ] **Step 4: Integrate responder metadata**

Replace direct model-independent composition with:

```python
message, responder = self.responder.compose(...)
metadata["responder"] = responder
metadata["model_name"] = configured model name
```

Do not call the response model when there is no active model.

- [ ] **Step 5: Run responder and agent tests**

Run:

```powershell
uv run pytest test/test_character_creation_agent.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/agent/character_creation/responder.py backend/src/agent/character_creation/graph.py test/test_character_creation_agent.py
git commit -m "feat: generate natural character agent replies"
```

### Task 4: Wire Message History Through The Service

**Files:**
- Modify: `backend/src/services/character_drafts.py`
- Modify: `test/test_character_creation_messages.py`
- Modify: `test/test_character_creation_agent.py`

- [ ] **Step 1: Write failing service integration tests**

Create a character session and send two messages. Assert the repository contains:

```python
["user", "assistant", "user", "assistant"]
```

Use a recording fake agent or model to prove the second request receives the first user and assistant turn.

- [ ] **Step 2: Verify integration tests fail**

Run:

```powershell
uv run pytest test/test_character_creation_messages.py test/test_character_creation_agent.py -k "history" -q
```

Expected: failure because `CharacterDraftService.handle_message()` does not persist or load messages.

- [ ] **Step 3: Persist turns transactionally**

In `handle_message()`:

1. Load the latest 12 saved messages.
2. Save the current user message.
3. Call `agent.process(draft, content, locale, recent_messages)`.
4. Save the final assistant message with extractor/responder metadata.
5. Update the draft revision.

If agent processing raises, preserve the user message for diagnostics but do not save a fabricated assistant message.

- [ ] **Step 4: Run integration tests**

Run:

```powershell
uv run pytest test/test_character_creation_messages.py test/test_character_creation_agent.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/services/character_drafts.py test/test_character_creation_messages.py test/test_character_creation_agent.py
git commit -m "feat: add context to character creation sessions"
```

### Task 5: Verification And Live Smoke Test

**Files:**
- Modify only if verification finds a defect.

- [ ] **Step 1: Run the full backend suite**

```powershell
uv run pytest -q
```

Expected: zero failures.

- [ ] **Step 2: Check repository state**

```powershell
git diff --check
git status --short --branch
```

Expected: no whitespace errors and no uncommitted implementation files.

- [ ] **Step 3: Restart the service**

Stop the current port-5000 service and run `.tmp/start-server-5000.cmd` outside the sandbox so SQLite can acquire file locks.

- [ ] **Step 4: Execute a real Chinese flow**

Send:

```text
戴尔 人类战士
15、15、15、15、15、15
```

Assert:

- first response metadata identifies extraction and response paths
- second response states 54 points exceeds 27
- message history contains both user and assistant turns
- `GET /` returns HTTP 200

- [ ] **Step 5: Report evidence**

Report the test count, active model name, extractor/responder metadata from the smoke test, and the local URL.
