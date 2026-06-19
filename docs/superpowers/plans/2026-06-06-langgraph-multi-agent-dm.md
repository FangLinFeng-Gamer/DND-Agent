# LangGraph Multi-Agent DM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-written DM orchestration with a LangChain/LangGraph hybrid multi-agent runtime while preserving API compatibility and offline fallback.

**Architecture:** A constrained ReAct supervisor plans and aggregates. Open-ended subagents use ReAct and return proposals; deterministic rule and persistence subagents use compiled StateGraph workflows. A narration agent is the only component that produces final prose, and a commit workflow is the only component allowed to persist game state.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, LangChain 1.3, LangGraph 1.1, pytest.

---

### Task 1: Graph Contracts and Architecture Tests

**Files:**
- Create: `backend/src/agent/dm/state.py`
- Create: `backend/src/agent/dm/schemas.py`
- Create: `test/test_dm_langgraph_architecture.py`

- [x] Add failing tests requiring `DMGraphState`, structured plans/results, compiled deterministic graphs, and a supervisor without direct persistence tools.
- [x] Run `uv run pytest test/test_dm_langgraph_architecture.py -q` and verify failure.
- [x] Implement minimal Pydantic and TypedDict contracts.

### Task 2: Deterministic StateGraph Subagents

**Files:**
- Create: `backend/src/agent/dm/workflows.py`
- Modify: `backend/src/agent/dm/tools.py`
- Test: `test/test_dm_langgraph_workflows.py`

- [x] Add failing tests for ability checks, scene patch validation, memory extraction, and commit behavior.
- [x] Implement compiled `StateGraph` workflows.
- [x] Verify dice results come from `CombatService` and state writes only occur in commit.

### Task 3: ReAct Supervisor and Open Subagents

**Files:**
- Create: `backend/src/agent/dm/react.py`
- Create: `backend/src/agent/dm/supervisor.py`
- Modify: `backend/src/agent/dm/prompts.py`
- Test: `test/test_dm_langgraph_supervisor.py`

- [x] Add failing tests for supervisor planning, tool restrictions, NPC/story/exploration/social delegation, and narration isolation.
- [x] Implement LangChain `create_agent` factories with injectable model adapters.
- [x] Implement deterministic fallback planners for offline tests.

### Task 4: DMService Integration

**Files:**
- Create: `backend/src/agent/dm/graph.py`
- Modify: `backend/src/agent/dm/service.py`
- Modify: `backend/src/agent/dm/output.py`
- Test: `test/test_dm_agent.py`
- Test: `test/test_dm_streaming.py`

- [x] Add failing integration tests proving DMService invokes the graph.
- [x] Route synchronous and streaming model paths through one graph runner.
- [x] Preserve `TemplateDMProvider` fallback and existing response structures.

### Task 5: Character Creation Agent

**Files:**
- Create: `backend/src/agent/character_creation/__init__.py`
- Create: `backend/src/agent/character_creation/state.py`
- Create: `backend/src/agent/character_creation/graph.py`
- Create: `backend/src/services/character_drafts.py`
- Create: `backend/src/schemas/character_creation.py`
- Create: `backend/src/api/character_creation.py`
- Modify: `backend/src/db/sqlite.py`
- Modify: `backend/src/main.py`
- Test: `test/test_character_creation_agent.py`

- [x] Add failing tests for resumable drafts, rule validation, explicit confirmation, and successful creation.
- [x] Implement ReAct guidance plus deterministic validation and commit workflows.
- [x] Add API endpoints without changing existing character CRUD.

### Task 6: Verification and Documentation

**Files:**
- Modify: `docs/设计文档.md`
- Modify: `docs/superpowers/progress/2026-05-22-dnd-agent-mvp-handoff.md`

- [x] Run focused graph, DM, streaming, and character creation tests.
- [x] Run `uv run pytest -q`.
- [x] Execute one complete character creation and adventure action flow.
- [x] Commit implementation with verification evidence.
