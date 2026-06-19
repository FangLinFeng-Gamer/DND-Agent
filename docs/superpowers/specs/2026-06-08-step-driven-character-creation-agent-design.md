# Step-Driven Character Creation Agent Design

## Goal

Upgrade character creation from a loose field extractor into a stateful DND 5e
character creation guide. The agent must track the current step, preserve and
update user-provided state, ask for missing information, and invalidate later
choices when an upstream decision changes.

## Current Problem

The existing `CharacterCreationAgent` stores a `CharacterDraft`, but the graph
only extracts a small set of fields from free text:

- `name`
- `race`
- `class_name`
- `background`
- `alignment`
- `notes`

The draft schema already contains many more fields: ability scores, selected
rules, proficiencies, class options, spells, equipment, personality details,
adventure connection, derived sheet values, validation maps, and invalidated
steps. Those fields are not consistently surfaced through the conversational
agent. As a result, the agent can appear to accept a character concept while
leaving most of the actual sheet unresolved.

The current implementation also treats user messages as replacement field
extraction rather than explicit intent. A message such as "change the name to
Arwen" should update only the name and keep other valid choices. A message such
as "change my race to elf" should update race and invalidate dependent later
steps.

## Scope

This design covers the backend character creation agent and API responses. The
existing frontend character creation chat can continue to render
`assistant_message`, `draft`, and validation errors. A later UI pass may add
structured controls for each step, but this phase must work through natural
language messages.

In scope:

- Step-aware state transitions using `CHARACTER_CREATION_STEPS`.
- Intent extraction for create, update, confirm, skip, ask-rules, and help.
- Natural-language updates in English and Chinese.
- User edits to previously supplied fields.
- Dependency invalidation after upstream changes.
- Missing-information prompts for every creation step.
- Explicit response metadata showing whether LLM extraction or fallback parsing
  was used.

Out of scope for this phase:

- Replacing the existing draft mutation API.
- Adding new frontend widgets for every step.
- Generating final character art.
- Full rules explanation chat; the agent may summarize options and direct users
  to choose, but it should not become a general rules encyclopedia.

## Agent State

Extend `CharacterCreationState` to carry execution details instead of only the
draft and validation result:

- `draft`: the current `CharacterDraft`.
- `content`: current user message.
- `locale`: normalized response language.
- `intent`: one of `provide_info`, `update_field`, `confirm`, `skip`,
  `ask_rules`, or `help`.
- `extracted_changes`: normalized draft changes proposed by the LLM or fallback.
- `changed_fields`: draft fields actually changed.
- `invalidated_steps`: steps invalidated by upstream changes.
- `next_step`: the step the user should address next.
- `missing_fields`: human-readable items still needed for `next_step`.
- `assistant_message`: final response text for the user.
- `validation_errors`: blocking validation messages.
- `created_character`: created character record, only set after review
  confirmation succeeds.
- `metadata`: source and diagnostic data such as `extractor=llm|fallback`,
  `model_name`, `intent`, and `next_step`.

`CharacterCreationSessionOut.metadata` should expose the metadata so the
frontend and tests can tell whether an LLM was used or fallback handled the
message.

`CharacterDraft` must remain inside `CharacterCreationState`. It is the single
source of truth for the character being built. The graph state should not copy
draft fields such as `name`, `race`, `class_name`, `spell_ids`, or inventory to
top-level state fields. Top-level state exists only for one-turn processing:
intent, extracted changes, changed fields, invalidation, missing slots,
assistant text, and metadata.

This separation prevents two-state drift:

- `CharacterDraft`: "What is the character right now?"
- `CharacterCreationState`: "What did this user message do, and what should the
  agent ask next?"

## Slot And Requirement Model

Add a slot requirement layer that is derived from the current draft, selected
rules, and current creation step. Slots describe what the agent needs, not where
the final value is stored.

Each slot requirement should include:

- `id`: stable slot id, such as `identity.name`, `race.base`,
  `abilities.base`, or `spells.known`.
- `step`: owning step from `CHARACTER_CREATION_STEPS`.
- `kind`: `single`, `multi`, or `structured`.
- `required`: whether the slot blocks step completion.
- `condition`: why the slot is active, for example `class.is_spellcaster`.
- `options`: available canonical option ids or labels when applicable.
- `min_count` and `max_count`: for multi-value choices.
- `current_value`: current draft value or selected values.
- `question_key`: response template key for asking the user.

### Single-Value Slots

Single-value slots accept one current value and replace that value when updated:

- `identity.name`
- `identity.alignment`
- `identity.appearance`
- `race.base`
- `race.subrace`
- `class.base`
- `background.base`
- `background.ideal`
- `background.bond`
- `background.flaw`
- `adventure_connection.motivation`

Name updates are ordinary single-slot replacement. If the user says "change my
name to Mira" or "把名字改成阿尔文", only `draft.name` changes. Race, class,
background, ability scores, and later selections are preserved.

### Multi-Value Slots

Multi-value slots accept a list and may have count constraints:

- `background.personality_traits`
- `proficiencies.skills`
- `proficiencies.tools`
- `proficiencies.languages`
- `class_features.options`
- `optional_rules.feats`
- `spells.cantrips`
- `spells.known`
- `spells.prepared`
- `equipment.options`
- `inventory.items`

Multi-value updates should support add, remove, and replace intents. The first
implementation may treat natural-language choices as replacement when the user
provides a complete list, but it must not erase unrelated slots.

### Structured Slots

Structured slots hold nested data and need specialized validation:

- `abilities.base`: six ability scores or a selected generation method.
- `selections.choice_values`: rule-specific choices such as bonus language,
  skill selection, equipment branch, or ability increase choice.
- `derived`: calculated sheet data, never directly edited by the user.
- `proficiencies`: calculated and chosen proficiencies.
- `adventure_connection`: motivation, hook, and story relationship.

Structured slots should be updated through helper services rather than direct
ad hoc dictionary mutation where rules already exist.

### Conditional Slots

Some slots exist only after earlier choices are known:

- `spells.*` is active only if race, class, subclass, feat, or other selected
  rules grant level-one spellcasting choices.
- `class_features.options` is active only when the selected class has level-one
  choices.
- `optional_rules.feats` is active only when a selected race or optional rule
  grants feat choices.
- `race.subrace` is active only when the selected race has selectable subraces.
- `equipment.options` is active only after class and background are known.

The agent must not ask about inactive slots. For example, a level-one Fighter
should not be asked to choose spells, while a Wizard must be asked for cantrips
and spellbook spells.

## First Information To Ask

The agent should not ask every possible field at once. It should derive the next
question from the earliest incomplete active slot.

Initial order:

1. Ask for `identity.name` if missing.
2. Ask for `race.base` if missing.
3. Ask for `class.base` if missing.
4. Ask for `abilities.base` after race and class are known.
5. Ask for `background.base`.
6. Ask conditional rule slots generated by race, class, background, abilities,
   and selected optional rules.
7. Ask for `adventure_connection.motivation`.
8. Ask for review confirmation.

Earlier choices decide later questions. The selected class is especially
important because it controls whether spell slots, class options, and some
equipment choices are active.

## Graph

The graph should become a fixed workflow:

1. `extract_intent_and_changes`
   - Use the active LLM in JSON mode when available.
   - Normalize Chinese and English synonyms to canonical internal values.
   - Parse markdown-wrapped JSON if a provider ignores the strict prompt.
   - Fall back to deterministic parsers for common Chinese and English updates.

2. `apply_changes`
   - Update only fields the user explicitly supplied.
   - Preserve previously valid state unless a changed upstream field requires
     invalidation.
   - Support editing fields already completed, including name changes.

3. `invalidate_dependents`
   - If `identity` fields change, preserve later choices.
   - If `race` changes, invalidate race-dependent choices, abilities, feats,
     proficiencies, derived sheet values, spells where applicable, equipment,
     adventure connection, and review.
   - If `class` changes, invalidate abilities-dependent derived values, class
     features, spell choices, equipment, adventure connection, and review.
   - If `abilities` change, recalculate derived sheet values and invalidate
     feats whose prerequisites are no longer met.
   - If `background` changes, invalidate background choices, proficiencies,
     equipment, adventure connection, and review.

4. `validate_current_step`
   - Validate only the current and invalidated steps needed to continue.
   - Store errors in `validation_errors_by_step`.

5. `choose_next_step`
   - Pick the earliest incomplete or invalid step from
     `CHARACTER_CREATION_STEPS`.
   - Mark completed steps when their required fields are valid.

6. `compose_response`
   - Summarize what changed.
   - Show the current draft summary.
   - Ask the next concrete question.
   - For option-heavy steps, present a small numbered option list.

7. `commit`
   - Only runs when the user confirms at `review` and there are no blocking
     validation errors.

## Step Requirements

### `identity`

Required:

- name
- alignment, if the user wants to specify it; otherwise default `Neutral`
- optional appearance and notes

The agent must ask for name if missing. If the user changes the name later, only
`name` changes and the step remains completed.

### `race`

Required:

- supported base race
- subrace or required race choices when applicable
- race choice values, such as bonus language or ability choices

Changing race must clear or invalidate dependent race choices and derived
values.

### `class`

Required:

- supported class

Changing class must clear incompatible class features, spell choices, equipment
choices, and derived class data.

### `abilities`

Required:

- six manually entered base ability scores

The agent should not offer standard array or point buy in this version. When no
ability information is provided, it must ask the user to manually input all six
scores and briefly explain what each ability affects:

- Strength: melee attacks, carrying, athletics.
- Dexterity: armor class, initiative, ranged attacks, stealth.
- Constitution: hit points and endurance.
- Intelligence: knowledge and wizard spellcasting.
- Wisdom: perception, insight, survival, many divine/nature checks.
- Charisma: social influence and several spellcasting classes.

### `background`

Required:

- supported background
- optional personality traits, ideal, bond, flaw

If optional personality fields are missing, ask whether the user wants to fill
them now or continue with defaults.

### `proficiencies`

Required:

- all rule-required skill/tool/language choices not automatically granted

The response should list available choices in the selected language and ask for
the exact number required.

### `class_features`

Required:

- fighting style, favored enemy, domain, school, or other class-specific level
  one choices as applicable

If the class has no level-one choices, mark the step complete.

### `optional_rules`

Required:

- feat choices only when granted by race or optional rule selection

If no feat is available or required, mark complete and explain that no optional
choice is needed.

### `spells`

Required:

- cantrips, prepared spells, or known spells for spellcasting classes

If the class does not cast spells at level one, mark complete.

### `equipment`

Required:

- all starting equipment choices, including nested item choices

The agent should ask for unresolved options and then calculate inventory,
attacks, armor class, and other derived sheet data.

### `adventure_connection`

Required:

- short motivation, connection to selected story, or acceptance of a default
  hook

This produces notes used by the DM opening scene.

### `review`

Required:

- no blocking validation errors
- user explicit confirmation

The agent must present a concise sheet summary and ask the user to confirm.

## Natural Language Updates

The agent must support additive and corrective messages:

- "My name is Aria."
- "Change my name to Mira."
- "把名字改成阿尔文。"
- "我是人类战士。"
- "种族换成精灵。"
- "职业改成法师。"
- "用标准数组。"
- "背景选士兵。"
- "确认创建。"

Update messages should modify only the mentioned field or choice. The response
must explicitly say what changed and what still needs input.

## LLM And Fallback Policy

The active LLM should be used for intent and extraction when configured. The
request must use JSON mode where the provider supports it, and the prompt must
include the word JSON and a schema-like example. If the model returns markdown
or prose around JSON, parse the embedded JSON. If the model request or parse
fails, deterministic fallback parsers should handle common English and Chinese
phrases.

The agent must not silently hide which path was used. Response metadata should
include:

- `extractor`: `llm` or `fallback`
- `model_name`: active model name when applicable
- `intent`
- `changed_fields`
- `next_step`

## Response Shape

Every assistant message should follow this structure:

1. Acknowledge applied changes.
2. Show a short draft summary.
3. Ask exactly one next-step question, unless the user asked for help.

For Chinese locale, the visible draft summary must localize known canonical
values such as `Human`, `Fighter`, and `Soldier`. The API may keep canonical
English values in `draft` and `metadata`, but `assistant_message` must not show
mixed-language fragments such as `Human Fighter, background Adventurer`.
`Adventurer` in `CharacterDraft.background` is a legacy placeholder and should
be treated as unset by the character creation agent until the user explicitly
chooses a supported background.

Example Chinese response:

```text
已更新：名字改为阿尔文。

当前草稿：阿尔文，Human Fighter，背景 Soldier。

下一步需要分配属性值。你想使用标准数组、购点，还是手动输入六项属性？
```

## Testing

Add focused backend tests for:

- Chinese name/race/class/background extraction.
- LLM markdown JSON extraction.
- Name update preserves race, class, background, and completed steps.
- Race update invalidates dependent later steps.
- Missing ability scores prompts for ability assignment after identity, race,
  and class are present.
- Background personality fields are asked or explicitly skipped.
- Confirmation before review does not create a character.
- Confirmation at review creates a character.
- Response metadata exposes extractor, changed fields, and next step.

Run the full pytest suite after each implementation task.
