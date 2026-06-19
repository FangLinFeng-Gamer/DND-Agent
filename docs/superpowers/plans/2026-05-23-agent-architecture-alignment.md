# Agent Architecture Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move DM Agent harness code under `backend/src/agent`, preserve the original Chinese design document, and update system capabilities without changing runtime behavior.

**Architecture:** `backend/src/agent` becomes the agent orchestration layer; `backend/src/services` remains the domain service layer. Compatibility shims keep old imports working while API routes switch to the new agent entrypoint.

**Tech Stack:** FastAPI, SQLite, pytest, static frontend JavaScript.

---

### Task 1: Design Document and Capability Alignment

**Files:**
- Create: `docs/设计文档.md`
- Modify: `backend/src/services/system.py`
- Test: `test/test_design_alignment.py`

- [ ] **Step 1: Write failing tests**

Create tests that assert:

- `docs/设计文档.md` exists and contains `一、引言`, `2.1 Agent服务`, and `四、代码要求`.
- `/api/system/capabilities` includes `llm_models`, `streaming_dm`, `context_summary`, and `world_events`.
- Limitations no longer say DM responses use only the offline template provider.

Run: `uv run pytest test/test_design_alignment.py -q`

Expected: FAIL because the design file is absent from the worktree and capabilities are stale.

- [ ] **Step 2: Add design document**

Create `docs/设计文档.md` as UTF-8 Markdown using the original design, plus clarified MVP architecture choices.

- [ ] **Step 3: Update system capabilities**

Update `SystemService` capability lists to match current implementation.

- [ ] **Step 4: Verify and commit**

Run:

```powershell
uv run pytest test/test_design_alignment.py -q
```

Expected: tests pass.

Commit:

```powershell
git add docs/设计文档.md backend/src/services/system.py test/test_design_alignment.py
git commit -m "docs: align design document with implementation"
```

### Task 2: Agent Package Structure Tests

**Files:**
- Create: `test/test_agent_architecture.py`

- [ ] **Step 1: Write failing tests**

Create tests that assert imports exist for:

- `backend.src.agent.dm.service.DMService`
- `backend.src.agent.dm.prompts.build_dm_messages`
- `backend.src.agent.dm.memory.AgentMemoryManager`
- `backend.src.agent.dm.tools.DMAgentTools`
- `backend.src.agent.dm.output.extract_narration_text`
- `backend.src.agent.dm.locks.AdventureLockService`
- `backend.src.agent.dm.subagents.SubAgentContext`
- `backend.src.agent.llm.client.OpenAICompatibleClient`

Also assert `backend/src/api/adventures.py` imports `DMService` from `backend.src.agent.dm.service`.

Run: `uv run pytest test/test_agent_architecture.py -q`

Expected: FAIL because the modules are not present yet.

- [ ] **Step 2: Commit failing architecture tests only if desired**

Do not commit failing tests. Continue to implementation after verifying red.

### Task 3: Move Agent Harness Code

**Files:**
- Create: `backend/src/agent/dm/__init__.py`
- Create: `backend/src/agent/dm/service.py`
- Create: `backend/src/agent/dm/conversation.py`
- Create: `backend/src/agent/dm/prompts.py`
- Create: `backend/src/agent/dm/memory.py`
- Create: `backend/src/agent/dm/tools.py`
- Create: `backend/src/agent/dm/output.py`
- Create: `backend/src/agent/dm/locks.py`
- Create: `backend/src/agent/dm/subagents.py`
- Create: `backend/src/agent/llm/__init__.py`
- Create: `backend/src/agent/llm/client.py`
- Modify: `backend/src/services/dm.py`
- Modify: `backend/src/services/llm_client.py`
- Modify: `backend/src/services/adventure_locks.py`
- Modify: `backend/src/api/adventures.py`
- Test: `test/test_agent_architecture.py`

- [ ] **Step 1: Move LLM client**

Move `OpenAICompatibleClient` implementation to `backend/src/agent/llm/client.py`; make `backend/src/services/llm_client.py` a re-export shim.

- [ ] **Step 2: Move locks**

Move `AdventureLockService` to `backend/src/agent/dm/locks.py`; make `backend/src/services/adventure_locks.py` a re-export shim.

- [ ] **Step 3: Extract prompts**

Move `_build_model_messages` behavior to `backend/src/agent/dm/prompts.py` as `build_dm_messages(...)`.

- [ ] **Step 4: Extract output parsing**

Move narration extraction/chunking helpers to `backend/src/agent/dm/output.py`.

- [ ] **Step 5: Add memory and tool scaffolding**

Create `AgentMemoryManager` wrapping `ContextService` and `WorldEventService`; create `DMAgentTools` wrapping character, adventure, world, combat, story, and event services.

- [ ] **Step 6: Add subagent context scaffolding**

Create `SubAgentContext` dataclass for future child-agent orchestration context.

- [ ] **Step 7: Move DMService**

Move `DMService`, `TemplateDMProvider`, and the `LLMProvider` protocol to `backend/src/agent/dm/service.py`, importing prompt/output/memory/tool modules.

- [ ] **Step 8: Update imports**

Update `backend/src/api/adventures.py` to import from `backend.src.agent.dm.service`. Make `backend/src/services/dm.py` a re-export shim.

- [ ] **Step 9: Verify and commit**

Run:

```powershell
uv run pytest test/test_agent_architecture.py test/test_dm_agent.py test/test_dm_streaming.py test/test_llm_client.py -q
```

Expected: tests pass.

Commit:

```powershell
git add backend/src/agent backend/src/services/dm.py backend/src/services/llm_client.py backend/src/services/adventure_locks.py backend/src/api/adventures.py test/test_agent_architecture.py
git commit -m "refactor: move dm agent harness into agent package"
```

### Task 4: Full Regression

**Files:**
- No planned source changes unless verification exposes defects.

- [ ] **Step 1: Run full verification**

Run:

```powershell
uv run pytest -q
node --check frontend/static/app.js
```

Expected: all tests pass and JavaScript syntax check exits 0.

- [ ] **Step 2: Commit any regression fixes**

If verification fails, write or update a focused failing test, fix the root cause, rerun verification, and commit.
