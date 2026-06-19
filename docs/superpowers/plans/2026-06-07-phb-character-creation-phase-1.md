# PHB Character Creation Phase 1 Implementation Plan

**Status:** Complete and verified on 2026-06-07.

**Verification:** `150 passed`, backend compilation passed, and
`scripts.verify_character_creation_phase1` verified revisioned race and point-buy
mutations against the running service.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the authoritative structured PHB rules boundary, revisioned 12-step draft, and deterministic point-buy/ability calculation foundation.

**Architecture:** Introduce a focused `agent/character_creation/rules` package with typed immutable records loaded from bundled JSON. Replace the six-field draft with a backward-compatible versioned wizard state. Put point-buy and ability calculations in pure deterministic functions so later race/class/background workflows can reuse them without model involvement.

**Tech Stack:** Pydantic, SQLite JSON persistence, pytest, existing FastAPI character creation session API.

---

### Task 1: Structured Rule Contracts

**Files:**
- Create: `backend/src/agent/character_creation/rules/__init__.py`
- Create: `backend/src/agent/character_creation/rules/models.py`
- Create: `backend/src/agent/character_creation/rules/repository.py`
- Create: `backend/src/resources/phb2014/manifest.json`
- Test: `test/test_phb_rule_repository.py`

- [x] Write failing tests requiring bilingual text, canonical ids, typed grants,
  unique ids, supported rule types, and manifest loading.
- [x] Run `uv run pytest test/test_phb_rule_repository.py -q` and verify RED.
- [x] Implement `LocalizedText`, `RuleGrant`, `RuleChoice`, `RulePrerequisite`,
  `PHBRuleRecord`, and `PHBRuleManifest`.
- [x] Implement an immutable repository that loads JSON resources, rejects
  duplicate ids and unresolved references, and supports `get`, `list`, and
  localized search.
- [x] Add a minimal phase-one manifest containing ability definitions and the
  race records needed for point-buy bonus tests: human, elf, dwarf, mountain
  dwarf, half-elf, and variant human.
- [x] Run the focused test and commit.

### Task 2: Versioned Twelve-Step Draft

**Files:**
- Modify: `backend/src/schemas/character_creation.py`
- Modify: `backend/src/services/character_drafts.py`
- Modify: `backend/src/db/sqlite.py`
- Test: `test/test_character_creation_draft_v2.py`

- [x] Write failing tests for schema version, 12 step ids, current step,
  completed/invalid steps, canonical selections, base/racial/final abilities,
  derived sheet, pending suggestion, revision, and legacy draft migration.
- [x] Run the focused test and verify RED.
- [x] Add small nested Pydantic models rather than one large untyped dictionary.
- [x] Preserve current `name`, `race`, `class_name`, `background`, `alignment`,
  and `notes` compatibility properties.
- [x] Add `revision INTEGER NOT NULL DEFAULT 0` to creation sessions through
  additive migration.
- [x] Migrate loaded legacy JSON in memory and persist v2 on the next mutation.
- [x] Run existing and new character creation tests and commit.

### Task 3: Deterministic Point-Buy Engine

**Files:**
- Create: `backend/src/agent/character_creation/rules/abilities.py`
- Test: `test/test_character_creation_point_buy.py`

- [x] Write failing tests for the PHB cost table, 8-15 bounds, 27-point limit,
  ability modifiers, fixed race bonuses, final scores, half-elf choices, and
  variant-human choices.
- [x] Run the focused test and verify RED.
- [x] Implement pure functions `point_buy_cost`, `validate_point_buy`,
  `ability_modifier`, `resolve_racial_bonuses`, and `calculate_abilities`.
- [x] Return structured calculation sources for base score, racial bonus, final
  score, and modifier.
- [x] Run the focused test and commit.

### Task 4: Draft Mutation and Revision Safety

**Files:**
- Create: `backend/src/agent/character_creation/rules/draft_service.py`
- Modify: `backend/src/schemas/character_creation.py`
- Modify: `backend/src/api/character_creation.py`
- Modify: `backend/src/services/character_drafts.py`
- Test: `test/test_character_creation_draft_api.py`

- [x] Write failing API tests for reading a v2 draft, updating identity,
  updating point-buy scores, revision increments, stale revision `409`, and
  localized validation errors.
- [x] Run focused tests and verify RED.
- [x] Add `PATCH /api/character-creation/sessions/{id}/draft` with
  `expected_revision`, typed operation, and payload.
- [x] Route mutations through deterministic draft service and recalculate
  abilities after point-buy or race changes.
- [x] Keep the existing message endpoint working during migration.
- [x] Run focused tests and commit.

### Task 5: Phase Verification

**Files:**
- Modify: `docs/superpowers/progress/2026-05-22-dnd-agent-mvp-handoff.md`
- Modify: `docs/设计文档.md`

- [x] Run all new phase tests.
- [x] Run `uv run pytest -q`.
- [x] Run `uv run python -m compileall backend`.
- [x] Run `git diff --check`.
- [x] Exercise create/read/mutate/resume against the local API.
- [x] Update documentation with phase-one status and commit.
