# Step-Driven Character Creation Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert character creation chat from basic field extraction into a stateful step guide that tracks missing slots, supports user edits, and asks the next required question.

**Architecture:** Keep `CharacterDraft` as the single source of truth inside `CharacterCreationState`. Add a slot requirement module that derives missing single, multi, structured, and conditional slots from the draft, then have the graph update changed fields, choose the next step, compose the assistant response, and return metadata to the API.

**Tech Stack:** Python, LangGraph, Pydantic schemas, pytest, existing SQLite-backed session service.

---

### Task 1: Slot Requirements And Next-Step Metadata

**Files:**
- Create: `backend/src/agent/character_creation/slots.py`
- Modify: `backend/src/agent/character_creation/state.py`
- Modify: `backend/src/agent/character_creation/graph.py`
- Modify: `backend/src/services/character_drafts.py`
- Test: `test/test_character_creation_agent.py`

- [ ] Write failing tests for:
  - after name/race/class/background are supplied, `metadata.next_step == "abilities"`;
  - metadata contains `missing_slots` with `abilities.base`;
  - assistant message asks for ability assignment instead of asking to confirm;
  - confirming before review does not create a character.
- [ ] Run `uv run pytest test/test_character_creation_agent.py -q` and verify RED.
- [ ] Implement `SlotRequirement` and `missing_required_slots(draft)`.
- [ ] Extend `CharacterCreationState` with `changed_fields`, `next_step`, `missing_slots`, `assistant_message`, and `metadata`.
- [ ] Update graph validation to select the earliest missing slot and compose the next question.
- [ ] Update `CharacterDraftService.handle_message()` to use `result["assistant_message"]` and `result["metadata"]`.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 2: User Edits And Dependency Invalidation

**Files:**
- Modify: `backend/src/agent/character_creation/graph.py`
- Modify: `backend/src/agent/character_creation/slots.py`
- Test: `test/test_character_creation_agent.py`

- [ ] Write failing tests for:
  - "Change my name to Mira" updates only `draft.name`;
  - race, class, background, and completed steps are preserved on name update;
  - changing race invalidates later dependent steps and keeps identity complete.
- [ ] Run focused tests and verify RED.
- [ ] Add changed-field detection by comparing draft before and after extraction.
- [ ] Add English and Chinese name-change fallback parsing.
- [ ] Add dependency invalidation for race, class, abilities, and background.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 3: Conditional Class Questions

**Files:**
- Modify: `backend/src/agent/character_creation/slots.py`
- Modify: `backend/src/agent/character_creation/graph.py`
- Test: `test/test_character_creation_agent.py`

- [ ] Write failing tests for:
  - Fighter does not get asked for spells at level one;
  - Wizard gets a spell slot requirement after abilities/background basics are complete.
- [ ] Run focused tests and verify RED.
- [ ] Add initial class spellcasting conditional slots for PHB level-one classes.
- [ ] Compose class-specific next questions.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 4: Verification

**Files:**
- No production file changes expected.

- [ ] Run `uv run pytest -q`.
- [ ] Run `git diff --check`.
- [ ] Restart the local service.
- [ ] Exercise a Chinese role creation flow through HTTP:
  - provide name/race/class/background;
  - confirm it asks for abilities;
  - rename the character;
  - confirm only the name changes.
- [ ] Report remaining gaps for later phases.
