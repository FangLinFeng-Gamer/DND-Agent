# Character Creation Wizard Design

## Goal

Optimize DND-Agent character creation using the approved "A" approach: a structured step-by-step wizard inspired by the TRPGCard DND flow, while keeping the chat agent synchronized with every structured choice and every validation failure.

## Scope

The first implementation covers the reliable rules already supported by this codebase:

- Identity: character name.
- Class: PHB 2014 class options with summary facts.
- Race: PHB 2014 race and subrace options with summary facts.
- Background: PHB 2014 background options with granted skills, tools, languages, and choices summarized.
- Abilities: point-buy input with live cost feedback.
- Spells: required level-one spell selections for spellcasting classes, including cantrip and first-level counts.
- Review: structured confirmation only when the draft is review-ready.

The first implementation does not add full custom backgrounds, FVTT export, all expansion books, or complete equipment selection. Those remain later enhancements.

## User Experience

The character creation screen becomes a wizard-led interface with chat as a companion. A step rail shows progress. The active step displays option cards, counts, current values, validation hints, and an enabled/disabled next action. The chat panel remains visible and records what happened.

Each step must answer four questions without requiring the user to ask the agent:

- What choices are available?
- How many choices are required?
- What has already been selected?
- Why can I not continue yet?

For example, the spell step shows the selected class requirements such as "法师：选择 3 个戏法和 6 个 1 环法术", filters the spell catalog to the class spell list, and displays selected counts.

## Chat Synchronization

Structured wizard actions must write into the same character creation session history that the chat agent reads.

On successful structured selection:

- Append a user-visible synthetic user message such as "界面选择：职业 = 法师".
- Append an assistant message summarizing the accepted choice and next step.
- Return the updated session with this assistant message.
- Keep draft state authoritative so the agent can answer follow-up chat questions using the latest selections.

On validation failure:

- Do not mutate the draft.
- Append a synthetic user message describing the attempted structured choice.
- Append an assistant message explaining why validation failed.
- Return the session with validation errors and the assistant message instead of leaving the user with only a toast.

This makes later chat turns aware of both successful choices and failed rule checks.

## Backend Design

Add a guide/options service for the frontend wizard. It reads `PHBRuleRepository` and the current `CharacterDraft`, then returns:

- Ordered step metadata.
- The active step.
- Localized option cards for classes, races, backgrounds, and spells.
- Ability point-buy metadata.
- Current selections and counts.
- Whether the draft can be confirmed.

Reuse existing deterministic rules:

- `CharacterCreationStateGraph.apply_changes` for core chat-compatible updates.
- Existing spell validation and derived spellcasting logic.
- Existing draft/session persistence.

Structured mutations use the existing character creation session and append sync messages before returning.

## Frontend Design

Replace the minimal draft panel with a structured wizard panel:

- Step rail with active/completed/error states.
- Option cards for class, race, background, and spells.
- Point-buy ability controls.
- Review summary with confirm button.
- Chat panel remains on the page as a companion and receives sync messages after structured actions.

The UI should reuse the existing dark fantasy style without making the page a marketing landing page.

## Testing

Backend tests cover:

- Guide data exposes options for the active step.
- Successful structured mutation appends chat-visible sync messages.
- Failed structured mutation appends validation explanation and does not change the draft.

Frontend tests cover:

- The wizard renders available options for the current step.
- Selecting an option calls the mutation API, updates the session, and appends the assistant sync message.
- Validation failures from structured mutation appear in chat and validation areas.

## Acceptance Criteria

- A user can see concrete choices before making each supported creation decision.
- A successful UI selection is visible in chat history and future chat turns have the updated draft.
- A failed UI selection explains the rule failure in chat.
- The existing chat input still works.
- The full test suite passes.
