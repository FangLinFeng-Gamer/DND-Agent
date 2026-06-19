# Character Creation Wizard Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 2 of the structured character creation wizard so all twelve PHB level-one creation steps are visible, deterministic, and synchronized with chat.

**Architecture:** Keep `CharacterDraft` as the authoritative state and route every structured change through `CharacterCreationStateGraph`. Expand `CharacterCreationGuideService` to expose all Phase 2 step options from `PHBRuleRepository`, then render those generic choice groups in the existing static frontend.

**Tech Stack:** FastAPI, Pydantic, SQLite, LangGraph StateGraph, existing PHB JSON resources, vanilla ES modules, pytest, Node syntax checks.

---

## File Structure

- Modify: `backend/src/schemas/character_creation.py`
  - Extend `CharacterDraftMutation.operation` with `adventure_connection`.
  - Reuse existing `CharacterDraft.adventure_connection`.
- Modify: `backend/src/agent/character_creation/slots.py`
  - Make missing-step detection evaluate all twelve steps.
- Modify: `backend/src/agent/character_creation/workflow.py`
  - Delegate Phase 2 structured changes to deterministic rule helpers and include new actionable steps.
- Modify: `backend/src/agent/character_creation/rules/draft_service.py`
  - Add `adventure_connection` mutation and ensure derived recalculation after every Phase 2 operation.
- Modify: `backend/src/services/character_creation_guide.py`
  - Replace the seven-step `WIZARD_STEPS` surface with `CHARACTER_CREATION_STEPS`.
  - Add guide data for `proficiencies`, `class_features`, `optional_rules`, `equipment`, and `adventure_connection`.
- Modify: `backend/src/services/character_drafts.py`
  - Map Phase 2 structured payloads into the StateGraph mutation path.
  - Localize sync messages for new operations.
- Modify: `frontend/static/js/character-creation.js`
  - Render generic choice groups, equipment groups, adventure connection fields, and review sheet.
- Modify: `frontend/static/js/i18n.js`
  - Add English and Simplified Chinese labels for Phase 2 controls.
- Modify: `frontend/static/styles.css`
  - Add compact styles for choice groups, counters, and final sheet review.
- Test: `backend/test/test_character_creation_phase2.py`
  - New backend tests for Phase 2 guide and mutation behavior.
- Test: `backend/test/test_frontend_character_creation.py`
  - Extend static frontend coverage for the twelve-step wizard and Phase 2 actions.

## Tasks

### Task 1: Twelve-Step Guide Surface

**Files:**
- Modify: `backend/src/services/character_creation_guide.py`
- Modify: `backend/src/agent/character_creation/slots.py`
- Test: `backend/test/test_character_creation_phase2.py`

- [ ] **Step 1: Write the failing guide step test**

Add a test named `test_phase2_guide_exposes_all_twelve_steps`:

```python
def test_phase2_guide_exposes_all_twelve_steps(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")

    guide = service.guide(session.id, "zh-CN")

    assert [step.id for step in guide.steps] == list(CHARACTER_CREATION_STEPS)
    assert guide.active_step == "identity"
    assert any(step.id == "proficiencies" for step in guide.steps)
    assert any(step.id == "equipment" for step in guide.steps)
    assert any(step.id == "adventure_connection" for step in guide.steps)
```

- [ ] **Step 2: Run the red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test\test_character_creation_phase2.py::test_phase2_guide_exposes_all_twelve_steps -q
```

Expected: fail because the current guide surface only includes seven steps.

- [ ] **Step 3: Use `CHARACTER_CREATION_STEPS` in guide output**

Change `CharacterCreationGuideService` so its step rail is built from
`CHARACTER_CREATION_STEPS` instead of the local seven-step tuple. Keep active
step logic conservative: unsupported Phase 2 steps can be visible before they
are made actionable in later tasks.

- [ ] **Step 4: Run the green test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test\test_character_creation_phase2.py::test_phase2_guide_exposes_all_twelve_steps -q
```

Expected: pass.

### Task 2: Proficiency Guide and Mutation

**Files:**
- Modify: `backend/src/services/character_creation_guide.py`
- Modify: `backend/src/services/character_drafts.py`
- Modify: `backend/src/agent/character_creation/workflow.py`
- Test: `backend/test/test_character_creation_phase2.py`

- [ ] **Step 1: Write failing guide and mutation tests**

Add tests proving a Wizard reaches `proficiencies` after background and
abilities, the guide exposes the `wizard-skills` choice group, and a valid
choice persists selected skill proficiencies.

- [ ] **Step 2: Run the red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test\test_character_creation_phase2.py -q
```

Expected: fail because `proficiencies` has no guide options and structured
mutation currently rejects the operation.

- [ ] **Step 3: Implement proficiency guide data**

Expose choice groups from selected race, class, background, and feat rules.
Each group includes `choice_id`, `minimum`, `maximum`, localized option cards,
current selected ids, and granted proficiencies.

- [ ] **Step 4: Route proficiency mutation**

Map structured payload `{"choice_values": {"wizard-skills": [...]}}` into the
StateGraph, then into `CharacterDraftRulesService._update_proficiencies`.

- [ ] **Step 5: Run green tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test\test_character_creation_phase2.py -q
```

Expected: pass for Task 1 and Task 2 tests.

### Task 3: Class Features and Optional Rules

**Files:**
- Modify: `backend/src/services/character_creation_guide.py`
- Modify: `backend/src/services/character_drafts.py`
- Modify: `backend/src/agent/character_creation/workflow.py`
- Test: `backend/test/test_character_creation_phase2.py`

- [ ] **Step 1: Write failing tests**

Add tests for a class with a level-one choice and for variant human feat
capacity. The tests assert guide requirements, disabled feat prerequisites, and
successful mutation into `draft.selections.class_option_ids` and
`draft.selections.feat_ids`.

- [ ] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test\test_character_creation_phase2.py -q
```

Expected: fail because guide data and structured mutation are not wired for
`class_features` or `optional_rules`.

- [ ] **Step 3: Implement guide and mutation support**

Use existing rule choices, prerequisites, and grants. Mark inactive steps
complete when there is no required class option or feat capacity.

- [ ] **Step 4: Run green tests**

Run the same pytest command and expect all Phase 2 backend tests so far to pass.

### Task 4: Equipment and Derived Sheet Review

**Files:**
- Modify: `backend/src/services/character_creation_guide.py`
- Modify: `backend/src/services/character_drafts.py`
- Modify: `backend/src/agent/character_creation/workflow.py`
- Modify: `backend/src/agent/character_creation/rules/draft_service.py`
- Test: `backend/test/test_character_creation_phase2.py`

- [ ] **Step 1: Write failing tests**

Add tests asserting Fighter equipment guide exposes class equipment groups,
equipment mutation resolves `draft.inventory`, and review exposes derived AC,
attacks, HP, saves, skills, and passive Perception.

- [ ] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test\test_character_creation_phase2.py -q
```

Expected: fail because equipment guide and review sheet metadata are missing.

- [ ] **Step 3: Implement equipment guide and mutation**

Read `starting_equipment.json` through existing equipment helpers, expose fixed
items and choice groups, then persist valid selections through the StateGraph.

- [ ] **Step 4: Implement review requirements**

Return final sheet data in guide requirements for `review`, sourced from
`draft.derived`, `draft.proficiencies`, `draft.inventory`, and
`draft.selections`.

- [ ] **Step 5: Run green tests**

Run the same pytest command and expect all Phase 2 backend tests so far to pass.

### Task 5: Adventure Connection

**Files:**
- Modify: `backend/src/schemas/character_creation.py`
- Modify: `backend/src/agent/character_creation/rules/draft_service.py`
- Modify: `backend/src/agent/character_creation/workflow.py`
- Modify: `backend/src/services/character_creation_guide.py`
- Modify: `backend/src/services/character_drafts.py`
- Test: `backend/test/test_character_creation_phase2.py`

- [ ] **Step 1: Write failing mutation test**

Add a test asserting `operation="adventure_connection"` stores fields such as
`motivation`, `quest_hook`, `npc_relation`, and `prior_knowledge`, advances the
draft to `review`, and records chat sync messages.

- [ ] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test\test_character_creation_phase2.py::test_adventure_connection_mutation_advances_to_review -q
```

Expected: fail because the schema and mutation path do not accept
`adventure_connection`.

- [ ] **Step 3: Implement schema and mutation support**

Add `adventure_connection` to `CharacterDraftMutation.operation`, update the
rules service to store trimmed text fields, and update guide active-step logic.

- [ ] **Step 4: Run green test**

Run the same test and expect pass.

### Task 6: Frontend Phase 2 Controls

**Files:**
- Modify: `frontend/static/js/character-creation.js`
- Modify: `frontend/static/js/i18n.js`
- Modify: `frontend/static/styles.css`
- Test: `backend/test/test_frontend_character_creation.py`

- [ ] **Step 1: Write failing frontend tests**

Extend the static frontend test so a guide payload containing twelve steps,
choice groups, equipment options, adventure connection fields, and review sheet
data renders the expected controls.

- [ ] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test\test_frontend_character_creation.py -q
```

Expected: fail because Phase 2 controls do not render yet.

- [ ] **Step 3: Implement generic renderers**

Add reusable renderers for choice groups, counters, multi-select option cards,
equipment groups, adventure text fields, and review sheet data.

- [ ] **Step 4: Run green frontend tests**

Run the same frontend test file and expect pass.

### Task 7: Full Verification

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run backend tests**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend syntax checks**

```powershell
node --check frontend/static/app.js
node --check frontend/static/js/character-creation.js
node --check frontend/static/js/i18n.js
```

Expected: all commands exit 0.

- [ ] **Step 3: Manual browser smoke test**

Start the local app, create a Fighter, Wizard, and variant Human with a feat,
and confirm each reaches final character creation without chat-only workaround.

## Self-Review

- Spec coverage: every Phase 2 requirement in the design has a task.
- Placeholder scan: no placeholder tasks are intentionally left open.
- Type consistency: operation names match `CHARACTER_CREATION_STEPS` and the
  planned `CharacterDraftMutation.operation` values.
