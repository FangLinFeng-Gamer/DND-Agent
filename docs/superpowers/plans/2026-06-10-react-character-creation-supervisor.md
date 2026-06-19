# ReAct Character Creation Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the character creation agent's misleading fixed-flow outer shell with a real ReAct supervisor that selects controlled tools, observes deterministic StateGraph results, and can only claim a character was created after a verified commit.

**Architecture:** Keep `CharacterDraft` and the deterministic character-creation rules as the source of truth. Move draft mutation, validation, and commit behavior behind six controlled tools. Each stateful tool invokes an inner StateGraph workflow and returns a serialized `StateGraphResult` as a `ToolMessage`; the outer ReAct agent uses those observations to decide its next action and compose the player-facing response. A final response guard reconciles model text with authoritative tool results.

**Tech Stack:** Python 3.12, FastAPI, SQLite, Pydantic, LangChain `create_agent`, LangGraph `StateGraph`, pytest.

---

## File Structure

- Modify `backend/src/agent/character_creation/models.py`: add the authoritative tool result contract and ReAct turn result models.
- Create `backend/src/agent/character_creation/workflow.py`: deterministic inner StateGraph for read, apply, validate, and confirm operations.
- Create `backend/src/agent/character_creation/tools.py`: controlled LangChain tools and per-turn execution context.
- Create `backend/src/agent/character_creation/supervisor.py`: outer ReAct agent, prompts, bounded loop, ToolMessage observation, and final response guard.
- Modify `backend/src/agent/character_creation/graph.py`: retain parsing and deterministic helpers while delegating orchestration to the new workflow/supervisor boundary.
- Modify `backend/src/services/character_drafts.py`: invoke the supervisor and persist only authoritative draft/session results.
- Modify `backend/src/agent/character_creation/__init__.py`: export the new public agent entry point.
- Create `test/test_character_creation_react.py`: focused ReAct/tool-observation tests.
- Modify `test/test_character_creation_agent.py`: regression tests for confirmation, help, language, and response truthfulness.
- Modify `test/test_character_creation_draft_api.py`: service/API persistence and revision tests.

### Task 1: Define the StateGraph Result Contract

**Files:**
- Modify: `backend/src/agent/character_creation/models.py`
- Create: `test/test_character_creation_react.py`

- [ ] **Step 1: Write failing contract tests**

Add tests for the exact result shape:

```python
def test_state_graph_result_serializes_for_tool_message():
    result = StateGraphResult(
        success=True,
        draft_revision=8,
        changed_fields=["background"],
        current_step="background",
        next_step="review",
        facts=["Background changed to Noble."],
        allowed_actions=["confirm", "update", "ask_rules"],
        draft=CharacterDraft(revision=8),
    )

    payload = json.loads(result.to_tool_content())
    assert payload["draft_revision"] == 8
    assert payload["committed"] is False
    assert payload["next_step"] == "review"
```

Also assert invalid combinations are rejected:

```python
with pytest.raises(ValidationError):
    StateGraphResult(
        success=True,
        draft_revision=8,
        current_step="review",
        next_step="review",
        committed=True,
        created_character_id=None,
        draft=CharacterDraft(revision=8),
    )
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
uv run pytest test/test_character_creation_react.py -q
```

Expected: import failure because `StateGraphResult` does not exist.

- [ ] **Step 3: Implement the Pydantic contracts**

Add:

```python
class StateGraphResult(BaseModel):
    success: bool
    draft_revision: int
    changed_fields: list[str] = Field(default_factory=list)
    current_step: str
    next_step: str
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    created_character_id: int | None = None
    committed: bool = False
    facts: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    draft: CharacterDraft

    @model_validator(mode="after")
    def validate_commit_state(self):
        if self.committed and self.created_character_id is None:
            raise ValueError("A committed result requires created_character_id.")
        return self

    def to_tool_content(self) -> str:
        return self.model_dump_json(exclude={"draft"})
```

Add a turn-level result model carrying the final assistant text, authoritative draft, created character, validation errors, and diagnostics metadata.

- [ ] **Step 4: Run the contract tests**

Run:

```powershell
uv run pytest test/test_character_creation_react.py -q
```

Expected: contract tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/agent/character_creation/models.py test/test_character_creation_react.py
git commit -m "feat: define character state graph result"
```

### Task 2: Extract the Deterministic Inner StateGraph

**Files:**
- Create: `backend/src/agent/character_creation/workflow.py`
- Modify: `backend/src/agent/character_creation/graph.py`
- Modify: `test/test_character_creation_react.py`

- [ ] **Step 1: Write failing workflow tests**

Cover four operations without using an LLM:

```python
result = workflow.apply_changes(
    draft=draft,
    expected_revision=3,
    changes={"name": "戴尔", "race": "Human", "class_name": "Fighter"},
    locale="zh-CN",
)
assert result.success is True
assert result.changed_fields == ["name", "race", "class_name"]
assert result.draft_revision == 4
assert result.next_step == "abilities"
assert result.committed is False
```

Add tests proving:

- invalid 27-point-buy input returns validation errors and preserves the previous valid draft;
- changing race/class invalidates dependent steps;
- `validate` never commits;
- `confirm` commits only at `next_step == "review"` with no blocking errors;
- revision mismatch returns `success=False`, `allowed_actions=["get_draft"]`, and does not mutate.

- [ ] **Step 2: Verify workflow tests fail**

Run:

```powershell
uv run pytest test/test_character_creation_react.py -k "workflow or revision" -q
```

Expected: failures because the workflow module is absent.

- [ ] **Step 3: Implement `CharacterCreationStateGraph`**

Build an inner graph with deterministic nodes:

```text
START
  -> load_and_check_revision
  -> apply_operation
  -> validate_draft
  -> route
       -> commit_character
       -> build_result
  -> END
```

The operation enum is limited to:

```python
Literal["read", "apply", "validate", "confirm"]
```

Reuse existing helpers and services:

- `CharacterStructuredExtractor` only when converting natural text to proposed changes;
- `CharacterDraftRulesService` for structured mutations;
- `calculate_abilities` for point-buy validation;
- `first_missing_step` and `mark_completed_steps`;
- `CharacterService.create` only in the confirm branch.

Do not generate player-facing prose in this workflow. Return only `StateGraphResult`.

- [ ] **Step 4: Reduce `graph.py` to reusable deterministic behavior**

Move graph orchestration into `workflow.py`. Keep canonicalization, fallback extraction, confirmation detection, localized rule facts, and draft-summary helpers in focused functions/classes. Remove the current fixed outer graph after its tests are migrated.

- [ ] **Step 5: Run workflow and existing rule tests**

Run:

```powershell
uv run pytest test/test_character_creation_react.py test/test_character_creation_agent.py test/test_character_creation_point_buy.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/agent/character_creation/workflow.py backend/src/agent/character_creation/graph.py test/test_character_creation_react.py test/test_character_creation_agent.py
git commit -m "refactor: extract character creation state graph"
```

### Task 3: Implement Controlled Character Creation Tools

**Files:**
- Create: `backend/src/agent/character_creation/tools.py`
- Modify: `test/test_character_creation_react.py`

- [ ] **Step 1: Write failing tool-boundary tests**

Assert the registry exposes exactly:

```python
assert {tool.name for tool in tools} == {
    "get_character_draft",
    "search_character_rules",
    "explain_character_option",
    "apply_character_changes",
    "validate_character_draft",
    "confirm_character_creation",
}
```

Assert state-changing tools require `expected_revision`, return JSON matching `StateGraphResult`, and never expose a raw store/connection argument in their public schema.

- [ ] **Step 2: Verify tool tests fail**

Run:

```powershell
uv run pytest test/test_character_creation_react.py -k "tool" -q
```

Expected: import or assertion failures because the tools do not exist.

- [ ] **Step 3: Add a scoped tool execution context**

Implement a context owned by one supervisor turn:

```python
@dataclass
class CharacterToolContext:
    session_id: int
    locale: str
    workflow: CharacterCreationStateGraph
    latest_result: StateGraphResult | None = None
    tool_call_count: int = 0
    tool_results: list[StateGraphResult] = field(default_factory=list)
```

The context, not model-supplied arguments, owns `session_id`, locale, store access, and workflow references.

- [ ] **Step 4: Implement the six tools**

Use `@tool` functions or `StructuredTool` schemas. Every invocation increments `tool_call_count`; reject calls above six with a safe result.

Rules tools are read-only and return source, applicability, and facts. Stateful tools delegate to `CharacterCreationStateGraph` and set `latest_result`.

`confirm_character_creation` must require:

- explicit confirmation already detected from the current user message;
- current expected revision;
- a review-ready draft;
- no validation errors.

- [ ] **Step 5: Run tool tests**

Run:

```powershell
uv run pytest test/test_character_creation_react.py -k "tool" -q
```

Expected: all tool-boundary tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/agent/character_creation/tools.py test/test_character_creation_react.py
git commit -m "feat: add controlled character creation tools"
```

### Task 4: Build the Outer ReAct Supervisor

**Files:**
- Create: `backend/src/agent/character_creation/supervisor.py`
- Modify: `backend/src/agent/character_creation/__init__.py`
- Modify: `test/test_character_creation_react.py`

- [ ] **Step 1: Write a scripted fake-model ReAct test**

Use a fake chat model that:

1. requests `get_character_draft`;
2. receives its `ToolMessage`;
3. requests `apply_character_changes`;
4. receives the second `ToolMessage`;
5. answers using `next_step`.

Record every model invocation and assert:

```python
tool_messages = [
    message for message in model.calls[-1]
    if isinstance(message, ToolMessage)
]
assert json.loads(tool_messages[-1].content)["next_step"] == "abilities"
```

This is the primary proof that the ReAct model perceives the StateGraph result.

- [ ] **Step 2: Add failing safety tests**

Cover:

- the model says “角色已创建” while `committed=false`;
- the model calls a seventh tool;
- the model attempts confirm without explicit user confirmation;
- a revision conflict occurs and the next tool call re-reads the draft;
- no model is configured.

Expected behavior is truthful localized fallback text with no unauthorized commit.

- [ ] **Step 3: Implement `CharacterCreationReActAgent`**

Build it with the shared helper:

```python
self.react_agent = build_react_agent(
    model,
    tools,
    system_prompt=self._system_prompt(locale),
    name="character_creation_supervisor",
)
```

The system prompt must state:

- plan and aggregate through tools only;
- never invent draft changes;
- use the selected frontend language;
- preserve numeric rules and validation facts;
- after each stateful call, inspect the returned `ToolMessage`;
- ask only one next-step question;
- never claim creation unless `committed=true` and an ID exists;
- help questions explain rules and then resume the unchanged step.

Invoke with bounded recursion/tool calls. Include recent persisted messages, the current user message, and a compact authoritative session header.

- [ ] **Step 4: Add the final response guard**

After ReAct returns:

1. choose the latest authoritative `StateGraphResult`;
2. compare commit claims against `committed`;
3. preserve validation errors and facts;
4. enforce the requested locale;
5. replace unsafe/empty output with the deterministic template composer.

Do not trust final model prose to determine status, revision, draft contents, or created character.

- [ ] **Step 5: Add no-model fallback**

When no active model is configured, run deterministic intent/extraction and workflow operations, then use `CharacterResponseComposer`'s template path. The public response shape must match the ReAct path.

- [ ] **Step 6: Run supervisor tests**

Run:

```powershell
uv run pytest test/test_character_creation_react.py -q
```

Expected: ReAct observation, tool-limit, commit-guard, revision, locale, and fallback tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/src/agent/character_creation/supervisor.py backend/src/agent/character_creation/__init__.py test/test_character_creation_react.py
git commit -m "feat: add react character creation supervisor"
```

### Task 5: Wire the Supervisor into Session Persistence

**Files:**
- Modify: `backend/src/services/character_drafts.py`
- Modify: `test/test_character_creation_draft_api.py`
- Modify: `test/test_character_creation_messages.py`

- [ ] **Step 1: Write failing service tests**

Assert `handle_message()`:

- appends the user message before execution;
- loads the latest 12 prior messages;
- invokes the ReAct supervisor with `session_id`, locale, revision, draft, and history;
- persists the authoritative returned draft and revision;
- marks the session completed only when `committed=true`;
- appends the final assistant response and diagnostic metadata.

Add a test where the model falsely claims creation and verify:

```python
assert response.status == "draft"
assert response.created_character is None
assert character_count == 0
```

- [ ] **Step 2: Verify service tests fail**

Run:

```powershell
uv run pytest test/test_character_creation_draft_api.py test/test_character_creation_messages.py -q
```

Expected: assertions fail because the current service invokes the fixed-flow agent.

- [ ] **Step 3: Replace the service entry point**

Construct `CharacterCreationReActAgent` with the active LangChain model. Pass the current session rather than allowing tools to select arbitrary sessions.

Persist with optimistic concurrency:

```sql
UPDATE character_creation_sessions
SET locale = ?, status = ?, draft_json = ?, revision = ?,
    updated_at = CURRENT_TIMESTAMP
WHERE id = ? AND revision = ?
```

Raise `DraftRevisionConflict` when `rowcount != 1`. Do not increment revision for read-only help/rule queries unless the authoritative draft actually changed.

- [ ] **Step 4: Persist richer diagnostics**

Store metadata including:

```python
{
    "agent_kind": "react",
    "tool_names": [...],
    "tool_call_count": 3,
    "state_graph_results": [...],
    "responder": "llm" | "template",
    "model_name": "...",
    "next_step": "abilities",
    "committed": False,
}
```

Do not persist secrets, full provider errors, chain-of-thought, or hidden model reasoning.

- [ ] **Step 5: Run service/API tests**

Run:

```powershell
uv run pytest test/test_character_creation_draft_api.py test/test_character_creation_messages.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/services/character_drafts.py test/test_character_creation_draft_api.py test/test_character_creation_messages.py
git commit -m "feat: route character sessions through react agent"
```

### Task 6: Fix Confirmation and Help Regressions

**Files:**
- Modify: `backend/src/agent/character_creation/graph.py`
- Modify: `backend/src/agent/character_creation/supervisor.py`
- Modify: `test/test_character_creation_agent.py`
- Modify: `test/test_character_creation_react.py`

- [ ] **Step 1: Add the reproduced failing cases**

Create tests from `test/角色创建测试`:

```python
def test_chinese_complete_commits_once_when_review_ready(...):
    response = service.handle_message(session_id, "完成", "zh-CN")
    assert response.status == "completed"


def test_fighter_spell_question_does_not_end_creation(...):
    response = service.handle_message(session_id, "我不能学法术吗", "zh-CN")
    assert response.status == "draft"
    assert response.metadata["next_step"] == previous_next_step
    assert "战士" in response.assistant_message
```

Also cover English `complete`, `done`, and `confirm`.

- [ ] **Step 2: Verify the regression tests fail before fixes**

Run:

```powershell
uv run pytest test/test_character_creation_agent.py test/test_character_creation_react.py -k "complete or spell_question or help" -q
```

- [ ] **Step 3: Make confirmation detection deterministic**

Recognize explicit localized confirmation phrases before model planning. Pass an immutable `explicit_confirmation` flag into tool context. The model cannot create this permission through tool arguments.

- [ ] **Step 4: Keep help intent non-mutating**

For a help question:

- read the current draft;
- query/explain relevant rules;
- do not call confirm;
- preserve current/next step;
- end with the same next-step question.

For a level-1 Fighter spell question, include the verified alternatives: racial spellcasting, eligible feat, or later multiclassing.

- [ ] **Step 5: Run regression tests**

Run:

```powershell
uv run pytest test/test_character_creation_agent.py test/test_character_creation_react.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/src/agent/character_creation/graph.py backend/src/agent/character_creation/supervisor.py test/test_character_creation_agent.py test/test_character_creation_react.py
git commit -m "fix: guard character confirmation and help flow"
```

### Task 7: Verify Bilingual API and Frontend Compatibility

**Files:**
- Modify only if failures require it:
  - `backend/src/api/character_creation.py`
  - `frontend/static/character-create.js`
  - `test/test_frontend_character_creation_agent.py`
  - `test/test_character_creation_draft_api.py`

- [ ] **Step 1: Run compatibility tests**

Run:

```powershell
uv run pytest test/test_frontend_character_creation_agent.py test/test_character_creation_draft_api.py -q
```

Verify the existing API contract still provides:

- `assistant_message`;
- `validation_errors`;
- `created_character`;
- draft/session revision;
- busy-state behavior that blocks a second request.

- [ ] **Step 2: Add bilingual end-to-end assertions**

Test the same draft flow with `zh-CN` and `en`. Assert the selected locale controls the final answer even when the user's short input is ambiguous.

- [ ] **Step 3: Make only compatibility fixes proven necessary by tests**

Do not redesign the UI in this task. Preserve streaming/loading and request-lock behavior.

- [ ] **Step 4: Run compatibility tests again**

Run:

```powershell
uv run pytest test/test_frontend_character_creation_agent.py test/test_character_creation_draft_api.py -q
```

- [ ] **Step 5: Commit if files changed**

```powershell
git add backend/src/api/character_creation.py frontend/static/character-create.js test/test_frontend_character_creation_agent.py test/test_character_creation_draft_api.py
git commit -m "fix: preserve character agent client contract"
```

### Task 8: Full Verification and Live Character Creation

**Files:**
- Modify only for defects found during verification.

- [ ] **Step 1: Run formatting/static sanity checks**

Run:

```powershell
git diff --check
uv run python -m compileall backend/src
```

Expected: no whitespace errors or syntax failures.

- [ ] **Step 2: Run the focused character creation suite**

Run:

```powershell
uv run pytest test/test_character_creation_react.py test/test_character_creation_agent.py test/test_character_creation_draft_api.py test/test_character_creation_messages.py test/test_frontend_character_creation_agent.py -q
```

Expected: all focused tests pass.

- [ ] **Step 3: Run the full backend suite**

Run:

```powershell
uv run pytest -q
```

Expected: all tests pass; compare the count with the current 234-test baseline and explain any intentional count change.

- [ ] **Step 4: Start the service and run a live flow**

Exercise:

1. create a Chinese character-creation session;
2. provide name/race/class;
3. provide legal six-ability point-buy values;
4. answer all required slots;
5. ask “我不能学法术吗” and verify the session stays active;
6. enter “完成” once;
7. verify one character row is created and the session becomes completed.

Inspect persisted assistant metadata to confirm:

- `agent_kind == "react"`;
- one or more controlled tools were used;
- StateGraph result content is recorded;
- `committed=true` only on the final turn.

- [ ] **Step 5: Verify in the browser**

Open `http://127.0.0.1:5000`, run one Chinese and one English creation turn, and verify:

- loading indicator appears;
- input/send are disabled while waiting;
- no duplicate request is accepted;
- answer language follows the frontend selector;
- the UI displays the created character only after authoritative commit.

- [ ] **Step 6: Review final diff and commit verification fixes**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Commit only files changed to fix verified defects:

```powershell
git add <changed-files>
git commit -m "test: verify react character creation flow"
```
