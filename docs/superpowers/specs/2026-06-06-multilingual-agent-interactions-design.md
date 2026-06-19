# Multilingual Agent Interactions Design

## Goal

Complete the missing user-facing integration between the frontend and the existing
agent architecture:

- Replace direct frontend character creation with a guided Character Creation
  Agent conversation.
- Propagate the frontend language selection through every model-backed workflow.
- Require all player-visible model and fallback output to use the selected
  language.
- Preserve existing API clients, offline fallback behavior, streaming behavior,
  persisted drafts, and explicit confirmation before character creation.

This change supports `en` and `zh-CN`. Invalid or missing locale values fall back
to `en`.

## Scope

Included:

- Guided character creation UI and API integration.
- Character draft display, validation display, and explicit confirmation.
- Locale propagation for character creation and DM requests.
- Locale-aware prompts for the supervisor, open-ended subagents, character
  creation agent, and narration agent.
- Locale-aware template fallback responses.
- Repair of corrupted Chinese character creation messages.
- Automated backend, static frontend, and browser workflow coverage.

Excluded:

- A public MCP protocol server.
- PHB PDF retrieval or RAG.
- A real image-generation provider.
- Voice input or output.
- Additional locales.

## Locale Contract

The canonical locale values are:

- `en`
- `zh-CN`

The frontend owns the current selection in `state.locale`. Every request that may
produce player-visible text sends the current locale. The backend normalizes the
value and does not infer language from the player's message.

Requests use the following shapes:

```json
POST /api/character-creation/sessions
{"locale": "zh-CN"}
```

```json
POST /api/character-creation/sessions/{id}/messages
{"content": "...", "locale": "zh-CN"}
```

```json
POST /api/adventures/{id}/messages
{"content": "...", "locale": "zh-CN"}
```

```json
POST /api/adventures/{id}/messages/stream
{"content": "...", "locale": "zh-CN"}
```

The locale fields on message payloads are optional for backward compatibility.
When omitted, the backend uses `en`. Character creation sessions store their
most recent locale, but the locale supplied with the current request takes
precedence and updates the session.

## Prompt Language Policy

A shared prompt helper converts a normalized locale into an explicit instruction:

- `zh-CN`: all player-visible prose must be written in Simplified Chinese.
- `en`: all player-visible prose must be written in English.

Internal identifiers remain English:

- JSON field names.
- Tool and agent names.
- Schema enum values.
- Database values that already use canonical English identifiers.

The language instruction is included in:

- DM supervisor prompts.
- Exploration, social, story, NPC, and rules-research agent prompts.
- Character Creation Agent prompts.
- Narration Agent prompts.
- Combined legacy DM prompts used by clients without tool-call support.

The Narration Agent applies the final language constraint again. This prevents
English planning or tool output from leaking into the final player-visible reply.

## Character Creation UI

The character creation page becomes an agent-guided workspace rather than a
direct CRUD form.

The page contains:

- A conversation history panel.
- A text input and send button.
- A busy indicator while the Agent is responding.
- A structured draft summary showing name, race, class, background, alignment,
  and notes.
- Validation errors.
- A confirmation button enabled only when the required draft fields are valid.
- The existing character library.
- A link to the race browser.

Opening the page creates a character creation session if there is no active,
incomplete session. The initial assistant message explains which information is
needed in the selected language.

Sending a message:

1. Disables the input and send controls.
2. Posts the message and current locale to the session endpoint.
3. Appends the user and assistant messages to the visible conversation.
4. Updates the structured draft and validation display.
5. Re-enables input after success or failure.

Confirming:

1. Sends the localized explicit confirmation phrase through the Agent session.
2. Runs deterministic validation.
3. Creates the character only when validation succeeds.
4. Refreshes the character library.
5. Selects the new character and opens the game page.

The frontend no longer directly posts the character creation form to
`POST /api/characters`. Existing character CRUD endpoints remain available for
other clients and editing flows.

The character creation frontend logic lives in a dedicated
`frontend/static/js/character-creation.js` module.

## Character Creation Backend

`CharacterCreationMessage` gains an optional locale. `CharacterDraftService`
normalizes it, updates the stored session locale, and constructs the Agent with
that locale for the current turn.

The welcome, draft summary, validation, confirmation, and success messages are
properly encoded Unicode strings for both supported locales.

Character creation remains split by responsibility:

- ReAct agent: guidance and extraction of explicitly supplied values.
- Deterministic validation graph: supported options and required fields.
- Character service: persistence after explicit confirmation.

The model may not invent unsupported races, classes, backgrounds, equipment, or
rules. Unsupported values remain validation errors.

## DM Locale Flow

`MessageCreate` gains an optional locale with an `en` default. Both synchronous
and streaming adventure routes pass the normalized locale into `DMService`.

Locale travels through:

1. Context loading.
2. Supervisor planning.
3. Open-ended subagent calls.
4. Deterministic resolution.
5. Narration.
6. Template fallback.

Locale does not change dice, combat, validation, scene patch, memory, or commit
semantics.

The streaming protocol remains:

- `status`
- `player_message`
- `delta`
- `final`

Only player-visible narration produces `delta` events. The frontend keeps the
message controls disabled until a `final` event or an error.

## Fallback Behavior

Model, tool-call, structured-output, or narration failure must:

- Avoid committing unresolved world events or scene changes.
- Use the existing offline provider.
- Produce fallback narration in the requested locale.
- Preserve the existing HTTP and NDJSON response shapes.

Changing the frontend locale does not clear character drafts, adventure history,
context summaries, or world events. The next request uses the new language.

## Frontend Localization

All new visible labels, empty states, validation headings, busy states,
confirmation controls, and error messages have English and Simplified Chinese
translations in `i18n.js`.

Changing language while the character creation page is open:

- Re-renders static labels immediately.
- Preserves the current draft and conversation.
- Sends the new locale with the next message.
- Causes the next Agent response to use the newly selected language.

Historical messages are not translated retroactively.

## Testing

Backend tests verify:

- Locale normalization and backward-compatible defaults.
- Character creation welcome and response text in both languages.
- Chinese and English confirmation.
- Session locale updates when the frontend language changes.
- Every model-facing prompt includes the required language instruction.
- Synchronous DM replies follow locale.
- Streaming DM replies follow locale.
- Template fallback follows locale.
- Narration failure does not partially commit world events.

Static frontend tests verify:

- Character creation uses `/api/character-creation/sessions`.
- Character creation no longer directly posts to `/api/characters`.
- DM synchronous and streaming messages include `state.locale`.
- New interface elements and translations exist.
- JavaScript modules pass syntax checks.

Browser verification covers:

1. Select Simplified Chinese.
2. Open character creation.
3. Receive a Chinese Agent welcome.
4. Describe a character.
5. See the draft and validation state update.
6. Confirm and create the character.
7. Start an adventure.
8. Send an action.
9. Receive Chinese streaming DM narration.
10. Switch to English and verify the next DM reply is English.

## Acceptance Criteria

- Clicking Create Character opens a working Agent-guided flow.
- A character cannot be persisted without deterministic validation and explicit
  confirmation.
- The selected frontend locale controls every new player-visible Agent response.
- Chinese output is valid Simplified Chinese without mojibake.
- Existing API clients that omit locale continue to work in English.
- Existing character CRUD, adventure, streaming, and offline fallback behavior
  remains compatible.
- The full automated test suite and one complete bilingual browser flow pass.
