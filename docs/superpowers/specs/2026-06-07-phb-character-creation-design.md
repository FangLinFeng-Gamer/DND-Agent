# 2014 PHB Character Creation Design

## Goal

Build a complete level-one DND 5e character creation workflow based only on the
2014 Player's Handbook rules that are stored as bilingual structured data in the
application.

The workflow uses a deterministic rules wizard for all legal choices and derived
values. A Character Creation Agent explains rules and proposes changes, but no
Agent suggestion changes the draft until the player explicitly accepts it.

## Rules Scope

The first complete release includes the 2014 PHB:

- Base races and subraces.
- All 12 classes.
- Level-one class choices and subclasses selected at level one.
- Backgrounds.
- Custom backgrounds.
- Skills.
- Languages.
- Tool proficiencies.
- Equipment and class/background starting equipment choices.
- Feats and optional character creation rules.
- Variant human.
- Cantrips and level-one spells.
- Alignment, personality traits, ideals, bonds, and flaws.
- Level-one hit points, Armor Class, attacks, saving throws, skill modifiers,
  passive Perception, initiative, speed, proficiency bonus, languages, tools,
  inventory, spellcasting values, and other character sheet values derivable
  from the included rules.

Rules not present in the structured 2014 PHB dataset are unavailable. The model
must not invent or silently reconstruct missing rules from general knowledge.

Multiclassing is excluded from level-one creation and belongs to advancement.

## Data Model

Rules are stored as typed bilingual records rather than free-form text. Every
player-visible rule record provides:

- Stable canonical id.
- English name and description.
- Simplified Chinese name and description.
- Source reference.
- Rule type.
- Structured prerequisites.
- Structured choices.
- Structured grants and modifiers.

Primary rule types:

- `race`
- `subrace`
- `class`
- `class_option`
- `background`
- `skill`
- `language`
- `tool`
- `equipment`
- `equipment_option`
- `feat`
- `spell`

Rule records are immutable built-in data. Character drafts store canonical ids,
not localized display names.

## Wizard Architecture

The character creation workflow is a compiled LangGraph state machine with 12
player-visible steps:

1. Basic identity and appearance.
2. Race and subrace.
3. Class and level-one class branch.
4. Ability point buy.
5. Background and personality.
6. Skills, languages, and tool proficiencies.
7. Class features and level-one choices.
8. Optional PHB rules and feats.
9. Cantrips and level-one spells.
10. Starting equipment.
11. Adventure motivation and story/NPC connections.
12. Final character sheet review and confirmation.

The graph separates:

- Draft mutation.
- Rule option discovery.
- Validation.
- Dependency invalidation.
- Derived-stat calculation.
- Agent suggestions.
- Final persistence.

Only deterministic graph nodes can modify the draft. The Agent returns a
structured proposed patch that the player must accept before it is sent to the
draft mutation node.

## Draft State

The persisted draft contains:

- Current step.
- Completed steps.
- Locale.
- Identity and appearance.
- Selected canonical rule ids.
- Point-buy base ability values.
- Race ability bonuses.
- Final ability values.
- Background personality fields.
- Selected proficiencies.
- Selected class options.
- Selected optional rules and feats.
- Selected spells.
- Selected equipment option ids and resolved inventory.
- Adventure motivation and relationships.
- Derived character sheet.
- Validation errors and warnings by step.
- Pending Agent suggestion.
- Revision number.

Every successful draft mutation increments the revision and saves the complete
draft to SQLite.

## Ability Point Buy

The workflow uses the 27-point method.

Allowed base scores and costs:

| Score | Cost |
| --- | --- |
| 8 | 0 |
| 9 | 1 |
| 10 | 2 |
| 11 | 3 |
| 12 | 4 |
| 13 | 5 |
| 14 | 7 |
| 15 | 9 |

Each base score must be from 8 through 15 and total cost cannot exceed 27.

The interface displays separately:

- Point-buy base score.
- Fixed 2014 PHB race/subrace bonus.
- Final score.
- Ability modifier.

Race bonuses do not change point-buy cost.

## Race and Optional Rules

Normal races use their fixed 2014 PHB ability modifiers and features.

Variant human is available as an optional rule. It uses its PHB ability choices,
skill proficiency, and level-one feat. Its choices are validated as one
integrated dependency group.

Changing race or subrace invalidates:

- Race-granted choices.
- Race languages.
- Race tool or skill selections.
- Variant-human ability choices.
- Variant-human feat.
- Derived ability scores, speed, size, and features.
- Any feat or option whose prerequisite is no longer met.

## Class and Level-One Choices

All 12 PHB classes are available.

Level-one choices are made during creation where applicable, including:

- Cleric Divine Domain.
- Sorcerous Origin.
- Warlock Otherworldly Patron.
- Any other class-specific level-one choice represented in the PHB dataset.

The rules engine validates:

- Saving throw proficiencies.
- Skill choice counts and allowed pools.
- Armor, weapon, and tool proficiencies.
- Hit die and level-one hit points.
- Spellcasting availability and spell choice limits.
- Starting equipment groups.
- Feature prerequisites and mutually exclusive choices.

Changing class invalidates all class-dependent skills, options, spells,
equipment, proficiencies, attacks, and derived values.

## Background and Personality

Standard backgrounds provide:

- Background feature.
- Two skill proficiencies.
- Languages and/or tools.
- Starting equipment.
- Suggested personality traits, ideals, bonds, and flaws.

Custom background follows the PHB optional rule and allows the player to select
the legal combination of feature, skills, languages, and tools defined by the
structured rule.

Personality fields may use a listed suggestion or player-authored text.

## Proficiency Conflict Resolution

The rules engine tracks every proficiency source.

When race, class, and background grant the same proficiency, the player receives
the replacement choice allowed by the applicable PHB rule. The interface shows:

- Granted proficiency.
- Source.
- Conflict.
- Legal replacement pool.

The player must resolve every conflict before completing the step.

## Feats and Optional Rules

All PHB character creation optional rules are enabled.

Feats are available when a level-one rule grants one, such as variant human.
Prerequisites are evaluated against final ability scores and other canonical
draft selections.

The rules engine, not the model, calculates feat grants and derived effects.

## Spell Selection

Spellcasting classes complete level-one spell selection during creation.

The structured class rules define:

- Whether the class knows or prepares spells.
- Number of cantrips.
- Number of known level-one spells.
- Preparation formula where applicable.
- Class spell list.
- Ritual casting and spellbook behavior.
- Spellcasting ability.

The interface filters legal spells and provides bilingual searchable
descriptions. It prevents excessive selections and spells outside the class
list.

The final sheet calculates spell attack bonus and spell save DC where applicable.

## Starting Equipment

The first release uses class and background starting equipment choices only.
Starting-gold purchasing is excluded.

Equipment choice groups support:

- Choose one option.
- Choose several items from a pool.
- Fixed grants.
- Quantity.
- Nested alternatives.

The final inventory merges race, class, background, feature, and feat grants.
Armor Class and attacks are calculated from equipped items and proficiencies.

## Adventure Connection

Step 11 connects the character to the selected reusable story:

- Adventure motivation.
- Reason for joining the main quest.
- Relationship to relevant key NPCs.
- Prior knowledge of the location or conflict.

This data belongs to the character/adventure connection rather than immutable
PHB rules. It is stored in the draft and copied into the adventure context when
the player starts a game.

The system does not automatically create a full NPC party.

## Derived Character Sheet

Before confirmation, the deterministic calculator produces:

- Level and proficiency bonus.
- Final ability scores and modifiers.
- Maximum and current HP.
- Armor Class.
- Initiative.
- Speed and size.
- Saving throws.
- Skill modifiers.
- Passive Perception.
- Proficiencies and languages.
- Features and feat effects.
- Inventory.
- Attacks, attack bonuses, damage expressions, and properties.
- Spellcasting ability, spell save DC, spell attack bonus, slots, cantrips, and
  prepared/known spells.

Every value includes source metadata so the UI can explain how it was calculated.

## Agent Role

The Character Creation Agent can:

- Explain the current step and available options.
- Search structured PHB rule records.
- Compare legal choices.
- Explain consequences and derived values.
- Propose a structured patch.
- Suggest personality text and adventure motivation.

The Agent cannot:

- Create new rule records.
- Select unsupported content.
- Apply a patch without player confirmation.
- Bypass prerequisites or choice limits.
- Calculate authoritative derived stats.
- Persist the final character.

Agent proposals contain:

- Summary.
- Reasoning.
- Proposed canonical field changes.
- Consequences.
- Whether the proposal affects later steps.

The player can apply or reject the complete proposal. Applying it invokes normal
deterministic validation and dependency invalidation.

## Dependency Invalidation

Players can return to any earlier step.

After a change, the dependency engine:

1. Identifies affected selections.
2. Removes selections that are no longer legal.
3. Recalculates derived values.
4. Marks affected later steps incomplete.
5. Presents a localized change summary.

It does not silently replace invalidated selections with defaults.

Examples:

- Changing class clears class skills, class branch, spells, and class equipment.
- Changing race clears subrace choices, race languages, and a variant-human feat.
- Reducing an ability score can invalidate a feat prerequisite.
- Changing background clears background equipment and conflict replacements.

## Frontend Layout

The confirmed desktop layout contains:

- Left step navigation with completion and error status.
- Central workspace for the current deterministic rule step.
- Right character summary, Agent conversation, pending suggestion, and
  validation status.

On smaller screens, the steps become a compact top navigation and the Agent
panel moves below the current step.

The UI supports:

- Automatic save status.
- Previous and next navigation.
- Direct navigation to completed or invalid steps.
- Bilingual rule search.
- Rule detail panels.
- Point-buy steppers.
- Selection counts.
- Apply/reject Agent proposal controls.
- Source-aware calculation explanations.
- Final confirmation only when all required steps are valid.

## Internationalization

All rule names, descriptions, validation messages, source explanations, Agent
prompts, and interface labels support:

- `en`
- `zh-CN`

Canonical ids and stored selections do not change with locale.

Changing language re-renders the current wizard and causes the next Agent reply
to use the new language. It does not clear or translate player-authored text.

## Persistence and Concurrency

Drafts are stored in SQLite and can be resumed.

Mutation requests include the expected revision number. A stale request returns a
conflict response rather than overwriting a newer draft.

Final character persistence occurs only when:

- Every required step is complete.
- No validation error remains.
- Derived values were recalculated for the current revision.
- The player explicitly confirms the final character sheet.

## Migration

Existing simple character creation sessions are migrated to the new draft
schema with:

- Existing name, race, class, background, alignment, and notes preserved.
- Current step set to the first incomplete step.
- All newly required choices marked incomplete.

Existing completed characters remain readable. New character fields require
additive database columns or normalized related tables; destructive migration is
not allowed.

## Testing

Rules data tests:

- Every canonical rule id is unique.
- Every required English and Chinese field exists.
- Every reference resolves.
- Every choice pool and prerequisite is valid.
- All 12 classes and PHB races/subraces/backgrounds/feats/spells are covered.

Rules engine tests:

- Point-buy costs and limits.
- Fixed race bonuses.
- Variant human choices.
- Class and background choice counts.
- Proficiency conflict replacements.
- Feat prerequisites.
- Spell choice and preparation rules.
- Equipment alternatives.
- Derived HP, AC, saves, skills, attacks, and spellcasting.
- Dependency invalidation.
- Revision conflicts.

Agent tests:

- Only structured PHB search tools are available.
- Suggestions never directly mutate drafts.
- Unsupported choices are rejected.
- Prompt language follows locale.

API tests:

- Create, resume, mutate, navigate, request suggestion, apply/reject suggestion,
  validate, calculate, and confirm.
- Existing simple clients receive a compatibility response or a clear migration
  path.

Frontend tests:

- All 12 steps render.
- Automatic saving and revision conflicts.
- Back navigation and invalidation messages.
- Point-buy display separation.
- Agent suggestion confirmation.
- Complete English and Chinese interface.
- Responsive desktop and mobile layouts.

End-to-end verification:

1. Build a normal PHB character.
2. Build a variant human with a legal feat.
3. Build a level-one spellcaster with valid spells.
4. Change an early selection and verify dependent choices are invalidated.
5. Resume a saved draft.
6. Confirm and create the final character.
7. Start an adventure and verify the character sheet is used by DM rules.

## Acceptance Criteria

- The workflow covers the complete 2014 PHB level-one creation scope defined
  above.
- Every authoritative decision and calculation comes from structured rules.
- The Agent can advise but cannot silently change the draft.
- Point buy, race bonuses, and final abilities are separately visible.
- Drafts automatically save and can return to any step.
- Upstream changes correctly invalidate dependent choices.
- All options and explanations are available in English and Simplified Chinese.
- A final character cannot be created until the complete deterministic character
  sheet is valid and explicitly confirmed.
