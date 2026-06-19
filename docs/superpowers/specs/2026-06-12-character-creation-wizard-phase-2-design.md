# Character Creation Wizard Phase 2 Design

## Goal

Complete the required Phase 2 character creation rules workflow so a level-one
2014 PHB character can be built through the structured wizard without relying on
the chat agent to invent or skip unresolved rules.

Phase 1 made the wizard usable for identity, class, race, background, point-buy
abilities, spell selection, and final confirmation. Phase 2 fills the remaining
creation steps that are already present in the draft model:

1. Proficiencies.
2. Class features and level-one choices.
3. Optional rules and feats.
4. Starting equipment.
5. Adventure connection.
6. Final derived sheet review.

## Source Policy

Runtime rules continue to come from structured files under
`backend/src/resources/phb2014`. The PDF at
`docs/5eDnD_玩家手册PHB_中译v1.72版.pdf` is a local reference for manual
cross-checking and data completion only.

This phase does not add PDF/RAG retrieval, does not store extracted long-form
PDF text in the database, and does not expose PHB text passages through the API.
Any missing rule must be added as compact structured data: canonical ids,
localized names, choice constraints, grants, prerequisites, and source
references.

## Scope

Included:

- Show all twelve character creation steps in the wizard rail.
- Drive every Phase 2 step through the existing character creation session,
  revision, validation, and chat-sync flow.
- Expose localized guide data for proficiency choices, class choices, feat
  choices, equipment options, and adventure connection prompts.
- Support deterministic validation for required choice counts, allowed option
  pools, duplicate proficiency replacement, feat prerequisites, and equipment
  groups.
- Calculate final character sheet values before confirmation: HP, AC, speed,
  initiative, saving throws, skill modifiers, passive Perception, proficiencies,
  inventory, attacks, and spellcasting values.
- Preserve the existing chat companion and ensure structured successes and
  failures are recorded in `character_creation_messages`.
- Keep English and Simplified Chinese UI text for all new visible labels and
  validation messages.

Excluded:

- Character advancement after level one.
- Multiclassing.
- Character import/export.
- FVTT export.
- Additional source books beyond the structured 2014 PHB data.
- Real PDF/RAG retrieval.
- Custom background free-form rule creation, except for preserving the data
  model path for a separate post-Phase-2 design.

## Architecture

Phase 2 keeps the current separation of authority:

- `CharacterDraft` remains the only authoritative character state.
- `PHBRuleRepository` remains the immutable built-in rule source.
- `CharacterCreationStateGraph` remains the only state-changing path used by
  chat and structured wizard mutations.
- `CharacterCreationGuideService` builds player-facing wizard data from the
  current draft and repository.
- The frontend renders controls from guide metadata and sends structured
  mutations back to the existing draft endpoint.

The main implementation change is to stop treating the wizard as a seven-step
surface. The visible wizard should use `CHARACTER_CREATION_STEPS` and skip or
complete inactive steps deterministically when no rule choice is required.

## Backend Design

### Step Detection

`first_missing_step` and `CharacterCreationGuideService.active_step` must
evaluate all twelve steps:

1. `identity`
2. `class`
3. `race`
4. `background`
5. `abilities`
6. `proficiencies`
7. `class_features`
8. `optional_rules`
9. `spells`
10. `equipment`
11. `adventure_connection`
12. `review`

Inactive steps are marked complete when their requirements are empty. Examples:

- A Fighter with no level-one class option skips `class_features`.
- A non-spellcasting character with no race or feat spell grants skips
  `spells`.
- A character with no feat capacity skips `optional_rules`.

### Guide Data

The guide service returns a common shape for Phase 2 steps:

- `options`: localized option cards.
- `requirements`: counts, choice ids, step prompt, and validation context.
- `current_value`: current selected ids or text fields.
- `validation_errors`: blocking messages for the active step.

New guide step behavior:

- `proficiencies`: lists unresolved skill, tool, and language choice groups,
  including selected count, required count, allowed options, granted
  proficiencies, and duplicate replacement prompts.
- `class_features`: lists class rule choices and selected class options.
- `optional_rules`: lists available feat slots, legal feats, prerequisites, and
  required feat choice groups such as variant human and Magic Initiate choices.
- `equipment`: lists fixed grants, required starting equipment choice groups,
  nested item choices, selected groups, and resolved inventory preview.
- `adventure_connection`: prompts for motivation, quest hook, NPC relation, and
  prior knowledge. These fields are stored on `draft.adventure_connection`.
- `review`: shows a final derived sheet summary and blocks confirmation when
  any required step is incomplete or invalid.

### Mutation

Structured mutation extends `CharacterDraftMutation` so it accepts every wizard
operation required by Phase 2:

- `identity`
- `race`
- `class`
- `abilities`
- `background`
- `proficiencies`
- `class_features`
- `optional_rules`
- `spells`
- `equipment`
- `adventure_connection`

All mutations go through `CharacterCreationStateGraph.apply_changes`. The graph
delegates detailed rule mutation to deterministic helpers instead of duplicating
rules in the API service. A failed mutation returns the unchanged session and
records the failed attempt in chat, matching Phase 1 behavior.

### Derived Sheet

Every successful Phase 2 mutation recalculates derived values. The review step
must present values from `draft.derived`, `draft.proficiencies`,
`draft.inventory`, and `draft.selections`, not recalculated ad hoc in the
frontend.

Before confirmation:

- `draft.current_step` must be `review`.
- No actionable step may be in `invalid_steps`.
- Required choice groups must be satisfied.
- Derived values must reflect the latest revision.
- Explicit confirmation must still be required.

## Frontend Design

The existing character creation layout remains:

- Wizard panel for structured choices.
- Chat panel as companion history.
- Draft summary and validation display.
- Character library.

Phase 2 adds generic renderers rather than one bespoke component per rule:

- `choiceGroupRenderer` for proficiencies, class choices, feat choices, and
  equipment alternatives.
- `optionCardGrid` for single-select and multi-select cards.
- `selectionCounter` for "selected N of M".
- `textFieldsRenderer` for adventure connection.
- `reviewSheetRenderer` for final derived values.

The frontend sends structured mutations using the same session revision. On
success, it replaces the current session, reloads guide data, and renders the
assistant sync message. On validation failure, it leaves the draft unchanged and
shows the assistant failure message in chat and validation areas.

## Error Handling

- Stale revisions return conflict errors and do not mutate the draft.
- Missing required choices produce localized validation errors.
- Invalid option ids are rejected by the backend even if a stale frontend sends
  them.
- Duplicate proficiency conflicts produce a replacement prompt rather than
  silently choosing a replacement.
- Feats with unmet prerequisites are disabled in guide data and rejected in
  mutation.
- Equipment choice groups must satisfy exactly their required counts.
- Unsupported PDF-only rules are reported as unavailable until represented in
  structured data.

## Testing

Backend tests:

- Guide uses all twelve steps and marks inactive steps complete.
- Proficiency guide exposes class/background/race choice groups and duplicate
  replacement requirements.
- Structured proficiency mutation persists valid choices and rejects invalid
  counts.
- Class feature guide and mutation support a class with a level-one choice.
- Optional rule guide supports variant human feat selection and feat
  prerequisites.
- Magic Initiate feat choices affect spell requirements.
- Equipment guide exposes fixed grants and choice groups.
- Equipment mutation resolves inventory and derived attacks/AC.
- Adventure connection mutation stores motivation and hook fields.
- Review blocks confirmation until Phase 2 required steps are complete.
- Final confirmation creates a character with derived proficiencies, inventory,
  attacks, and spellcasting values.

Frontend tests:

- All twelve step labels render in the wizard.
- Choice groups show selected counts and disabled states.
- Proficiency, feat, equipment, and adventure connection actions call the draft
  mutation endpoint with expected payloads.
- Validation failures are displayed in chat and validation areas.
- Review renders derived sheet fields and keeps confirm disabled until ready.

Full verification:

- Run `.\.venv\Scripts\python.exe -m pytest backend\test -q`.
- Run `node --check frontend/static/app.js`.
- Run `node --check frontend/static/js/character-creation.js`.
- Manually create at least one Fighter, one Wizard, and one variant Human with a
  feat through the local UI.

## Acceptance Criteria

- The wizard exposes and can complete all twelve character creation steps.
- A legal PHB level-one non-spellcaster can be created without chat-only
  workaround steps.
- A legal PHB level-one spellcaster can be created with valid spell choices.
- A variant human can select a legal feat and complete any feat-required
  choices.
- Starting equipment produces resolved inventory and derived combat values.
- The final character record includes derived proficiencies, inventory, attacks,
  spellcasting, HP, AC, initiative, saves, skills, and passive Perception.
- All new player-visible labels and validation messages support English and
  Simplified Chinese.
- The full automated test suite passes.
