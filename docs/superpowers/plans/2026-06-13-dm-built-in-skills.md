# DM Built-In Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend-only, read-only DM skills that are matched from player input and injected into the DM agent context without granting any direct state-changing tools.

**Architecture:** Create a focused `DMSkillRegistry` that loads built-in `SKILL.md` files, validates that they do not declare write tools, and returns deterministic keyword matches. Pass matched skills through `DMService`, `DMGraphRunner`, `DMSupervisor`, open subagent prompts, resolver prompts, and narration facts while keeping deterministic StateGraph workflows as the only state-changing path.

**Tech Stack:** Python 3.12, Pydantic-style schemas where existing code expects them, LangGraph, LangChain fake chat models in tests, pytest.

---

## File Structure

- Create `backend/src/agent/dm/skill_registry.py`: parse built-in `SKILL.md`, validate safety constraints, match skills, format prompt payloads.
- Create `backend/src/agent/dm/skills/lockpicking/SKILL.md`: initial read-only built-in skill.
- Modify `backend/src/agent/dm/prompts.py`: accept `skill_context` and include it in system/user/narration payloads.
- Modify `backend/src/agent/dm/supervisor.py`: accept matched skills and inject read-only context into supervisor prompt.
- Modify `backend/src/agent/dm/subagents.py`: accept matched skills and inject read-only context into open subagent prompts.
- Modify `backend/src/agent/dm/graph.py`: carry skill context through the plan node.
- Modify `backend/src/agent/dm/service.py`: match skills once per player action and pass them through sync and streaming paths.
- Create `test/backend/src/agent/dm/test_dm_skills.py`: registry and prompt tests.
- Modify `test/backend/src/agent/dm/test_dm_langgraph_supervisor.py`: supervisor prompt tests.
- Modify `test/backend/src/agent/dm/test_dm_langgraph_integration.py`: sync and streaming integration tests.

## Task 1: Registry and Built-In Skill

**Files:**
- Create: `backend/src/agent/dm/skill_registry.py`
- Create: `backend/src/agent/dm/skills/lockpicking/SKILL.md`
- Test: `test/backend/src/agent/dm/test_dm_skills.py`

- [ ] **Step 1: Write failing tests for loading, matching, and safety rejection**

```python
from pathlib import Path

import pytest

from backend.src.agent.dm.skill_registry import DMSkillRegistry


def test_builtin_dm_skill_registry_matches_lockpicking():
    registry = DMSkillRegistry.load_builtin()

    matches = registry.match("I inspect the locked chest and try to pick it.")

    assert [skill.name for skill in matches] == ["lockpicking"]
    assert matches[0].agent == "exploration_agent"
    assert "thieves-tools" in matches[0].tags
    assert "Do not roll dice" in matches[0].body


def test_builtin_dm_skill_registry_ignores_unrelated_input():
    registry = DMSkillRegistry.load_builtin()

    assert registry.match("I sing a song for the innkeeper.") == []


def test_dm_skill_registry_rejects_skills_that_declare_tools(tmp_path: Path):
    skill_dir = tmp_path / "unsafe"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: unsafe
description: unsafe write skill
tools:
  - commit_agent
when_to_use:
  - always
tags:
  - unsafe
agent: exploration_agent
---

Call commit_agent directly.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not declare tools"):
        DMSkillRegistry(tmp_path).load()
```

- [ ] **Step 2: Run registry tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest test\backend\src\agent\dm\test_dm_skills.py -q`

Expected: FAIL because `backend.src.agent.dm.skill_registry` does not exist.

- [ ] **Step 3: Implement minimal registry and lockpicking skill**

Create `backend/src/agent/dm/skill_registry.py` with a `DMSkill` dataclass, `DMSkillRegistry.load_builtin`, `load`, `match`, and safety validation.

Create `backend/src/agent/dm/skills/lockpicking/SKILL.md` with frontmatter and read-only guidance.

- [ ] **Step 4: Run registry tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest test\backend\src\agent\dm\test_dm_skills.py -q`

Expected: PASS.

## Task 2: Prompt and Supervisor Integration

**Files:**
- Modify: `backend/src/agent/dm/prompts.py`
- Modify: `backend/src/agent/dm/supervisor.py`
- Modify: `backend/src/agent/dm/subagents.py`
- Test: `test/backend/src/agent/dm/test_dm_skills.py`
- Test: `test/backend/src/agent/dm/test_dm_langgraph_supervisor.py`

- [ ] **Step 1: Write failing prompt payload test**

Add to `test/backend/src/agent/dm/test_dm_skills.py`:

```python
import json

from backend.src.agent.dm.prompts import build_dm_messages, build_narration_messages
from backend.src.schemas.adventure import MessageOut, SceneState
from backend.src.schemas.character import CharacterOut
from backend.src.services.context import ContextBundle


def test_dm_prompts_include_read_only_skill_context():
    skill = DMSkillRegistry.load_builtin().match("I pick the locked gate.")[0]
    context = ContextBundle(
        summary="",
        recent_messages=[
            MessageOut(
                id=1,
                adventure_id=1,
                role="player",
                content="I pick the locked gate.",
                metadata={},
                created_at="2026-06-13 00:00:00",
            )
        ],
        important_events=[],
        estimated_tokens=1,
    )
    scene = SceneState(
        location="Gate",
        environment="A locked iron gate.",
        important_objects=["locked gate"],
        npcs=[],
        current_objective="Enter safely.",
        world_changes=[],
    )
    character = CharacterOut(
        id=1,
        name="Mira",
        race="Human",
        class_name="Rogue",
        level=1,
        background="Criminal",
        alignment="Neutral",
        hp_current=10,
        hp_max=10,
        armor_class=12,
        strength=10,
        dexterity=16,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
        skills={},
        inventory=[],
        spells=[],
        notes="",
    )

    messages = build_dm_messages(
        context,
        scene,
        character,
        "I pick the locked gate.",
        None,
        skill_context=[skill],
    )
    payload = json.loads(messages[1]["content"])
    narration_messages = build_narration_messages(
        {"resolved_narration": "The lock is assessed."},
        skill_context=[skill],
    )
    narration_payload = json.loads(narration_messages[1]["content"])

    assert "DM skills are read-only" in messages[0]["content"]
    assert payload["skills"][0]["name"] == "lockpicking"
    assert payload["skills"][0]["agent"] == "exploration_agent"
    assert "guidance" in payload["skills"][0]
    assert narration_payload["skills"][0]["name"] == "lockpicking"
```

- [ ] **Step 2: Write failing supervisor/subagent prompt test**

Add to `test/backend/src/agent/dm/test_dm_langgraph_supervisor.py`:

```python
def test_supervisor_and_open_subagents_receive_read_only_skills(client, monkeypatch):
    prompts = []

    class FakeAgent:
        def invoke(self, _payload):
            return {"messages": [AIMessage(content='{"intent":"exploration","steps":[]}')]}

    def fake_build(_model, _tools, system_prompt, name):
        prompts.append((name, system_prompt))
        return FakeAgent()

    monkeypatch.setattr(supervisor_module, "build_react_agent", fake_build)
    monkeypatch.setattr(subagents_module, "build_react_agent", fake_build)
    skill = DMSkillRegistry.load_builtin().match("I pick the lock.")[0]
    model = FakeMessagesListChatModel(responses=[])
    supervisor = DMSupervisor(client.app.state.store, model=model)

    supervisor.plan("I pick the lock.", skills=[skill])
    ReactSubAgentRegistry(
        model,
        client.app.state.store,
        skill_context=[skill],
    ).tools()[0].invoke({"instruction": "I pick the lock."})

    assert any(name == "dm_supervisor" and "lockpicking" in prompt for name, prompt in prompts)
    assert any(name == "exploration_agent" and "lockpicking" in prompt for name, prompt in prompts)
    assert all("DM skills are read-only" in prompt for _, prompt in prompts)
    assert all("commit_agent" not in prompt for _, prompt in prompts)
```

- [ ] **Step 3: Run prompt and supervisor tests to verify they fail**

Run:

`.\.venv\Scripts\python.exe -m pytest test\backend\src\agent\dm\test_dm_skills.py test\backend\src\agent\dm\test_dm_langgraph_supervisor.py -q`

Expected: FAIL because prompt and supervisor functions do not yet accept `skill_context` or `skills`.

- [ ] **Step 4: Implement prompt, supervisor, and subagent skill context injection**

Update prompt builders to accept `skill_context=None`. Add a helper that renders a concise read-only skill section and serializes skills into JSON payloads.

Update `DMSupervisor.plan(..., skills=None)` and `ReactSubAgentRegistry(..., skill_context=None)` to include read-only skill context in system prompts.

- [ ] **Step 5: Run tests to verify they pass**

Run:

`.\.venv\Scripts\python.exe -m pytest test\backend\src\agent\dm\test_dm_skills.py test\backend\src\agent\dm\test_dm_langgraph_supervisor.py -q`

Expected: PASS.

## Task 3: DMService Sync and Streaming Integration

**Files:**
- Modify: `backend/src/agent/dm/graph.py`
- Modify: `backend/src/agent/dm/service.py`
- Test: `test/backend/src/agent/dm/test_dm_langgraph_integration.py`

- [ ] **Step 1: Write failing sync integration assertion**

Modify `test_active_model_uses_supervisor_plan_and_separate_narration_agent` to send `MessageCreate(content="I pick the locked gate.")` and assert:

```python
resolution_payload = json.loads(scripted.resolution_messages[-1]["content"])

assert resolution_payload["supervisor_plan"]["intent"] == "exploration"
assert resolution_payload["skills"][0]["name"] == "lockpicking"
```

- [ ] **Step 2: Write failing streaming integration assertion**

Modify `test_active_model_streams_from_separate_narration_agent` to send `MessageCreate(content="I pick the locked gate.")`, keep a reference to the scripted client, and assert:

```python
resolution_payload = json.loads(scripted.resolution_messages[-1]["content"])

assert resolution_payload["skills"][0]["name"] == "lockpicking"
```

- [ ] **Step 3: Run integration tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest test\backend\src\agent\dm\test_dm_langgraph_integration.py -q`

Expected: FAIL because `DMService` has not matched or passed skills through.

- [ ] **Step 4: Implement service and graph propagation**

Add `self.skill_registry = DMSkillRegistry.load_builtin()` in `DMService.__init__`.

In `advance` and `advance_stream`, call `skill_context = self.skill_registry.match(message.content, locale=locale)` once per player message.

Pass `skill_context` into `_advance_with_model`, `_stream_with_model`, `_resolve_with_model`, `DMGraphRunner.run`, `DMGraphRunner.plan`, `build_dm_messages`, `build_narration_messages`, and `NarrationAgent.narrate` facts.

- [ ] **Step 5: Run integration tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest test\backend\src\agent\dm\test_dm_langgraph_integration.py -q`

Expected: PASS.

## Task 4: Regression Verification

**Files:**
- Existing DM tests under `test/backend/src/agent/dm`
- Existing service tests impacted by DM prompts

- [ ] **Step 1: Run DM agent tests**

Run: `.\.venv\Scripts\python.exe -m pytest test\backend\src\agent\dm -q`

Expected: PASS.

- [ ] **Step 2: Run combat service tests**

Run: `.\.venv\Scripts\python.exe -m pytest test\backend\src\services\test_combat.py -q`

Expected: PASS.

- [ ] **Step 3: Run Python syntax/import sanity for modified modules**

Run: `.\.venv\Scripts\python.exe -m py_compile backend\src\agent\dm\skill_registry.py backend\src\agent\dm\prompts.py backend\src\agent\dm\supervisor.py backend\src\agent\dm\subagents.py backend\src\agent\dm\graph.py backend\src\agent\dm\service.py`

Expected: exit code 0.

## Self-Review

Spec coverage:

- Backend-only built-in skills: Task 1.
- Read-only safety model and forbidden tool declarations: Task 1.
- Prompt/supervisor/subagent context injection: Task 2.
- Sync and streaming DM paths: Task 3.
- Existing StateGraph safety boundaries: Task 4 regression tests plus no new write tools.

Placeholder scan: no TBD/TODO placeholders remain.

Type consistency: the plan uses `DMSkillRegistry`, `DMSkill`, and `skill_context` consistently across tasks.
