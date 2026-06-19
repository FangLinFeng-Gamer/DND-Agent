# PHB Character Creation Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete PHB 2014 race, class, background, and proficiency choices so a non-spellcasting level-one character can validly finish wizard steps 1-8.

**Architecture:** Keep bilingual PHB facts in focused JSON rule packs and evaluate them through generic choice/grant resolvers. Draft mutations select canonical rule IDs, recompute granted proficiencies and level-one features, and invalidate only dependent later steps.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, SQLite, pytest, PHB 2014 bilingual local source.

---

## File Structure

- `backend/src/resources/phb2014/races.json`: all nine PHB races, PHB subraces, variant human, racial grants, and racial choices.
- `backend/src/resources/phb2014/classes.json`: all twelve classes and level-one class option records.
- `backend/src/resources/phb2014/backgrounds.json`: thirteen standard backgrounds plus custom-background rules.
- `backend/src/resources/phb2014/proficiencies.json`: canonical skills, languages, tools, armor groups, and weapon groups.
- `backend/src/agent/character_creation/rules/choices.py`: generic cardinality, option membership, and distinct-choice validation.
- `backend/src/agent/character_creation/rules/grants.py`: grant aggregation with source metadata and duplicate handling.
- `backend/src/agent/character_creation/rules/draft_service.py`: class, background, and proficiency draft mutations and dependency invalidation.
- `backend/src/schemas/character_creation.py`: typed mutation operations and canonical selected proficiency fields.
- `test/test_phb_races.py`: race-pack completeness and representative mechanics.
- `test/test_phb_classes.py`: class-pack completeness and first-level mechanics.
- `test/test_phb_backgrounds.py`: standard/custom background rules.
- `test/test_character_creation_choices.py`: generic choice validation and conflict replacement.
- `test/test_character_creation_phase2_api.py`: revisioned API flow through wizard step 8.

### Task 1: Complete PHB Race Rule Pack

**Files:**
- Modify: `backend/src/resources/phb2014/races.json`
- Modify: `backend/src/resources/phb2014/manifest.json`
- Create: `backend/src/agent/character_creation/rules/choices.py`
- Create: `test/test_phb_races.py`

- [ ] **Step 1: Write failing completeness tests**

```python
def test_builtin_pack_contains_all_phb_races_and_subraces():
    repository = PHBRuleRepository.load_builtin()
    assert {rule.id for rule in repository.list("race")} == {
        "race.dragonborn", "race.dwarf", "race.elf", "race.gnome",
        "race.half-elf", "race.half-orc", "race.halfling",
        "race.human", "race.tiefling",
    }
    assert {rule.id for rule in repository.list("subrace")} == {
        "race.drow", "race.forest-gnome", "race.high-elf",
        "race.hill-dwarf", "race.lightfoot-halfling",
        "race.mountain-dwarf", "race.rock-gnome",
        "race.stout-halfling", "race.variant-human", "race.wood-elf",
    }
```

- [ ] **Step 2: Run the tests and verify missing race IDs fail**

Run: `uv run pytest test/test_phb_races.py -q`

Expected: FAIL because the Phase 1 pack contains only five race records.

- [ ] **Step 3: Add concise bilingual records**

Encode fixed ability bonuses, size, speed, senses, languages, proficiencies,
resistances, innate spells, breath weapon ancestry, high-elf cantrip,
half-elf skills/language, dwarf tool, and variant-human skill/feat choices.
Descriptions must summarize mechanics and identity without copying long source
paragraphs.

- [ ] **Step 4: Add generic choice validation**

```python
def validate_rule_choices(rule, choice_values):
    for choice in rule.choices:
        selected = choice_values.get(choice.id, [])
        if not choice.minimum <= len(selected) <= choice.maximum:
            raise ValueError(f"{choice.id} requires {choice.minimum}-{choice.maximum} choices.")
        if len(selected) != len(set(selected)):
            raise ValueError(f"{choice.id} choices must be distinct.")
        if any(value not in choice.option_ids for value in selected):
            raise ValueError(f"{choice.id} contains an invalid choice.")
```

- [ ] **Step 5: Run race and Phase 1 tests**

Run: `uv run pytest test/test_phb_races.py test/test_phb_rule_repository.py test/test_character_creation_point_buy.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/resources/phb2014 backend/src/agent/character_creation/rules/choices.py test/test_phb_races.py
git commit -m "feat: complete phb race rule pack"
```

### Task 2: Canonical Proficiency Vocabulary and Grant Resolver

**Files:**
- Create: `backend/src/resources/phb2014/proficiencies.json`
- Create: `backend/src/agent/character_creation/rules/grants.py`
- Modify: `backend/src/resources/phb2014/manifest.json`
- Create: `test/test_character_creation_choices.py`

- [ ] **Step 1: Write failing vocabulary and aggregation tests**

Test all 18 skills, standard PHB languages, adventuring tools used by character
creation, source-preserving grants, and duplicate proficiency detection.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest test/test_character_creation_choices.py -q`

Expected: FAIL because the vocabulary and resolver do not exist.

- [ ] **Step 3: Implement focused JSON vocabulary and resolver**

The resolver returns `dict[str, list[str]]` plus source metadata. Exact
duplicates merge; a duplicate selected skill/tool/language creates a
replacement requirement rather than silently wasting the grant.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest test/test_character_creation_choices.py test/test_phb_rule_repository.py -q`

Expected: PASS.

Commit: `feat: add character proficiency resolver`

### Task 3: All Twelve Level-One Classes

**Files:**
- Create: `backend/src/resources/phb2014/classes.json`
- Modify: `backend/src/resources/phb2014/manifest.json`
- Create: `test/test_phb_classes.py`

- [ ] **Step 1: Write failing class completeness tests**

Assert the twelve canonical class IDs, hit dice, primary abilities, saving
throws, armor/weapons, skill choice counts, level-one feature IDs, and
level-one branch choices for cleric, sorcerer, and warlock.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest test/test_phb_classes.py -q`

Expected: FAIL because no class records are loaded.

- [ ] **Step 3: Add class records and first-level option records**

Store only level-one creation data in this phase. Higher-level subclass rules
remain out of scope unless a class requires the choice at level one.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest test/test_phb_classes.py test/test_phb_rule_repository.py -q`

Expected: PASS.

Commit: `feat: add phb level one class rules`

### Task 4: Standard and Custom Backgrounds

**Files:**
- Create: `backend/src/resources/phb2014/backgrounds.json`
- Modify: `backend/src/resources/phb2014/manifest.json`
- Create: `test/test_phb_backgrounds.py`

- [ ] **Step 1: Write failing background tests**

Assert thirteen standard backgrounds, fixed skill grants, language/tool
choices, background features, equipment option references, and a custom
background rule requiring any two skills plus two language/tool selections.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest test/test_phb_backgrounds.py -q`

Expected: FAIL because no background records exist.

- [ ] **Step 3: Add concise bilingual background records**

Include personality tables as optional metadata references; the deterministic
creation requirements are grants and choices.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest test/test_phb_backgrounds.py test/test_phb_rule_repository.py -q`

Expected: PASS.

Commit: `feat: add phb background rules`

### Task 5: Draft Mutations and Dependency Invalidation

**Files:**
- Modify: `backend/src/schemas/character_creation.py`
- Modify: `backend/src/agent/character_creation/rules/draft_service.py`
- Create: `test/test_character_creation_phase2_api.py`

- [ ] **Step 1: Write failing API flow tests**

Create a draft, choose mountain dwarf, fighter, point-buy scores, soldier
background, resolve skill/tool/language choices, and select fighting style.
Assert each revision increments and steps 1-8 become complete.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest test/test_character_creation_phase2_api.py -q`

Expected: FAIL because class/background/proficiency/class-feature operations
are rejected.

- [ ] **Step 3: Add typed operations and generic recomputation**

Add `class`, `background`, `proficiencies`, and `class_features` operations.
Every mutation validates canonical IDs, recomputes grants, and clears
dependent selections when an earlier choice changes.

- [ ] **Step 4: Add invalidation regression tests**

Changing race invalidates racial choices and steps 6-12; changing class
invalidates class skill choices and steps 6-12; changing background invalidates
replacement choices and steps 6, 10, and 12.

- [ ] **Step 5: Run Phase 2 and full tests**

Run: `uv run pytest test/test_phb_races.py test/test_phb_classes.py test/test_phb_backgrounds.py test/test_character_creation_choices.py test/test_character_creation_phase2_api.py -q`

Run: `uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/schemas/character_creation.py backend/src/agent/character_creation/rules/draft_service.py test/test_character_creation_phase2_api.py
git commit -m "feat: support phb character creation through step eight"
```

