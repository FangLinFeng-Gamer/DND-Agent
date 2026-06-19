# PHB Character Creation Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add complete level-one PHB feats, spells, starting equipment, and deterministic derived character sheets.

**Architecture:** Store feats, spells, equipment, and starting option trees as immutable bilingual rule packs. Split deterministic calculations into focused derived modules, then expose `optional_rules`, `spells`, and `equipment` draft mutations that validate canonical IDs before recalculating the sheet.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, SQLite, pytest, PHB 2014 bilingual local source.

---

## File Structure

- `backend/src/resources/phb2014/feats.json`: all 42 PHB feats, prerequisites, choices, and structured grants.
- `backend/src/resources/phb2014/spells.json`: PHB cantrips and level-one spells with bilingual summaries, classes, ritual flag, attack/save data, and damage/healing metadata.
- `backend/src/resources/phb2014/equipment.json`: armor, weapons, ammunition, packs, focuses, tools, and background items used by starting equipment.
- `backend/src/resources/phb2014/starting_equipment.json`: class and background fixed grants and nested alternatives.
- `backend/src/agent/character_creation/rules/prerequisites.py`: generic ability, spellcasting, armor, and selection prerequisite validation.
- `backend/src/agent/character_creation/rules/equipment.py`: resolve nested equipment choices into inventory entries.
- `backend/src/agent/character_creation/derived/abilities.py`: saves, skills, initiative, and passive Perception.
- `backend/src/agent/character_creation/derived/combat.py`: HP, speed, AC, weapon attacks, and source metadata.
- `backend/src/agent/character_creation/derived/spellcasting.py`: level-one spell limits, slots, save DC, and attack bonus.
- `backend/src/agent/character_creation/derived/sheet.py`: aggregate focused calculators into `CharacterDerivedSheet`.
- `backend/src/agent/character_creation/rules/draft_service.py`: delegate recalculation and implement steps 8-10.

### Task 1: Derived Ability and Skill Sheet

**Files:**
- Create: `backend/src/agent/character_creation/derived/__init__.py`
- Create: `backend/src/agent/character_creation/derived/abilities.py`
- Create: `backend/src/agent/character_creation/derived/sheet.py`
- Modify: `backend/src/agent/character_creation/rules/draft_service.py`
- Create: `test/test_character_creation_derived_sheet.py`

- [ ] Write failing tests for initiative, two class saving throws, proficient and non-proficient skill modifiers, passive Perception, and source metadata.
- [ ] Run `uv run pytest test/test_character_creation_derived_sheet.py -q` and verify failures are caused by missing calculators.
- [ ] Implement canonical skill-to-ability mapping and source-preserving calculations.
- [ ] Delegate draft recalculation to `calculate_derived_sheet`.
- [ ] Run focused and full tests.
- [ ] Commit as `feat: calculate character ability derived values`.

### Task 2: Complete PHB Feats and Optional Rules

**Files:**
- Create: `backend/src/resources/phb2014/feats.json`
- Create: `backend/src/agent/character_creation/rules/prerequisites.py`
- Modify: `backend/src/resources/phb2014/manifest.json`
- Modify: `backend/src/agent/character_creation/rules/draft_service.py`
- Create: `test/test_phb_feats.py`
- Create: `test/test_character_creation_feats.py`

- [ ] Write failing tests asserting exactly 42 feat records and representative ability, proficiency, spellcasting, and armor prerequisites.
- [ ] Verify RED.
- [ ] Add concise bilingual feat records with structured grants and choices.
- [ ] Implement prerequisite validation against final abilities, proficiencies, and spellcasting.
- [ ] Replace the placeholder `optional_rules` mutation with variant-human feat selection and derived effects.
- [ ] Verify changing race/abilities removes or invalidates an illegal feat.
- [ ] Run focused and full tests.
- [ ] Commit as `feat: add phb character creation feats`.

### Task 3: Cantrips and Level-One Spells

**Files:**
- Create: `backend/src/resources/phb2014/spells.json`
- Create: `backend/src/agent/character_creation/derived/spellcasting.py`
- Modify: `backend/src/resources/phb2014/classes.json`
- Modify: `backend/src/resources/phb2014/manifest.json`
- Modify: `backend/src/agent/character_creation/rules/draft_service.py`
- Create: `test/test_phb_level_one_spells.py`
- Create: `test/test_character_creation_spellcasting.py`

- [ ] Write failing tests for complete PHB cantrip/level-one class lists and bilingual spell metadata.
- [ ] Verify RED.
- [ ] Add canonical spell records and level-one class selection profiles.
- [ ] Implement known/prepared/spellbook validation for Bard, Cleric, Druid, Sorcerer, Warlock, and Wizard.
- [ ] Calculate slots, spell save DC, and spell attack bonus.
- [ ] Verify non-spellcasters complete the spell step with an empty selection.
- [ ] Run focused and full tests.
- [ ] Commit as `feat: add level one phb spell selection`.

### Task 4: Starting Equipment Trees

**Files:**
- Create: `backend/src/resources/phb2014/equipment.json`
- Create: `backend/src/resources/phb2014/starting_equipment.json`
- Create: `backend/src/agent/character_creation/rules/equipment.py`
- Modify: `backend/src/resources/phb2014/manifest.json`
- Modify: `backend/src/agent/character_creation/rules/draft_service.py`
- Create: `test/test_phb_equipment.py`
- Create: `test/test_character_creation_equipment.py`

- [ ] Write failing tests for armor/weapon mechanics and all twelve class/background starting packages.
- [ ] Verify RED.
- [ ] Add focused bilingual equipment records and nested option records.
- [ ] Implement deterministic nested choice resolution and quantity merging.
- [ ] Add the `equipment` mutation and class/background invalidation.
- [ ] Run focused and full tests.
- [ ] Commit as `feat: resolve phb starting equipment`.

### Task 5: Combat Sheet and Phase 3 End-to-End

**Files:**
- Create: `backend/src/agent/character_creation/derived/combat.py`
- Modify: `backend/src/agent/character_creation/derived/sheet.py`
- Modify: `backend/src/schemas/character_creation.py`
- Create: `test/test_character_creation_combat_sheet.py`
- Create: `test/test_character_creation_phase3_api.py`

- [ ] Write failing tests for HP, armor AC, shield bonus, unarmored formulas, weapon attack bonus, damage expression, spellcasting values, inventory, and source metadata.
- [ ] Verify RED.
- [ ] Implement combat calculations from equipped canonical items and grants.
- [ ] Verify a normal fighter, variant-human fighter with a feat, cleric, sorcerer, warlock, and wizard produce deterministic level-one sheets.
- [ ] Run `uv run pytest -q` and compile checks.
- [ ] Commit as `feat: complete phb level one derived sheets`.

