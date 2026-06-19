# Complete PHB Character Creation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this roadmap phase-by-phase. Each phase has its own detailed plan and must finish with a working, tested checkpoint.

**Goal:** Deliver the complete bilingual 2014 PHB level-one character creation workflow defined in `docs/superpowers/specs/2026-06-07-phb-character-creation-design.md`.

**Architecture:** Build a new authoritative structured-rules domain and deterministic character-building engine beside the existing display-oriented world search. Migrate the current character creation session into a revisioned 12-step wizard, then layer PHB option packs, Agent suggestions, final character persistence, and the confirmed responsive frontend on top.

**Tech Stack:** FastAPI, Pydantic, SQLite, LangGraph, LangChain, vanilla JavaScript ES modules, pytest.

---

## Phase 1: Rules and Draft Foundation

- Typed bilingual PHB rule records and repository.
- Built-in rule pack loader and integrity validation.
- Revisioned 12-step character creation draft.
- 27-point buy engine.
- Fixed racial ability bonus calculation.
- Basic derived ability modifiers and proficiency bonus.
- Compatibility mapping from current simple drafts.

Detailed plan:
`docs/superpowers/plans/2026-06-07-phb-character-creation-phase-1.md`

## Phase 2: Race, Class, Background, and Proficiencies

- Complete PHB races, subraces, variant human, and racial choices.
- All 12 class level-one rules and level-one branch choices.
- Standard and custom backgrounds.
- Skills, languages, tools, grants, conflicts, and replacement choices.
- Dependency invalidation for race, class, and background changes.

Exit criteria: a non-spellcasting character can complete steps 1-8 with all
choices validated.

## Phase 3: Feats, Spells, Equipment, and Derived Sheet

- Complete PHB feats and prerequisites.
- Cantrips and level-one spell lists and class selection rules.
- Class/background starting equipment option trees.
- Inventory, attacks, HP, AC, saves, skills, initiative, passive Perception,
  spell save DC, and spell attack bonus.
- Source metadata for every derived value.

Exit criteria: normal, variant-human, and spellcasting level-one characters
produce complete deterministic character sheets.

## Phase 4: Agent Suggestions and API

- Read-only structured PHB search tools.
- Step-aware Character Creation Agent prompts.
- Structured pending suggestions.
- Apply/reject flow with deterministic validation.
- Revision conflict responses.
- Resume, mutate, navigate, validate, calculate, and confirm APIs.
- Additive migration and full character persistence.

Exit criteria: Agent suggestions never directly mutate drafts, and confirmed
valid drafts create complete characters.

## Phase 5: Twelve-Step Frontend and End-to-End Verification

- Confirmed three-column desktop wizard and responsive mobile layout.
- Step navigation, save state, rule search/details, point-buy controls,
  selection counts, invalidation summaries, Agent proposal controls, and final
  review.
- Complete English and Simplified Chinese copy.
- Browser tests for normal, variant-human, spellcaster, invalidation, resume,
  and final adventure use.

Exit criteria: all acceptance criteria in the design specification pass.

