# Streaming DM Response Design

## Goal

Make DM responses feel responsive while a large model is thinking, and enforce one player action per DM response in each adventure.

## Requirements

- Add a streaming message endpoint for adventure chat.
- Show a visible waiting/typing state immediately after the player sends a message.
- Disable the message textarea and Send button as soon as the player sends a message, before any model output is received.
- Prevent Enter from sending another message while the DM response is pending.
- Enforce the same one-at-a-time rule on the backend for each adventure.
- Stream DM narration chunks to the browser when the active model supports streaming.
- Keep the existing non-streaming endpoint for compatibility and tests.
- Use localized English and Chinese strings for all new frontend text.

## API Design

Add:

`POST /api/adventures/{adventure_id}/messages/stream`

The response is `application/x-ndjson`, one JSON object per line:

```json
{"type":"status","message":"dm_thinking"}
{"type":"player_message","message":{"id":1,"role":"player","content":"..."}}
{"type":"delta","content":"The door creaks"}
{"type":"delta","content":" open."}
{"type":"final","adventure":{},"dm_message":{},"scene":{},"messages":[],"combat_state":null,"dice_result":null}
```

If another response is already running for the same adventure, return HTTP 409:

```json
{"detail":{"error":{"code":"dm_busy","message":"DM is still responding.","details":{}}}}
```

## Backend Design

- Add an in-process lock manager keyed by `adventure_id`.
- The stream endpoint acquires the adventure lock before appending the player message and releases it in a `finally` block.
- `DMService` gets a streaming path that yields structured events:
  - status
  - player message
  - delta chunks
  - final response
- For model-backed responses, call OpenAI-compatible chat completions with `stream: true`.
- The model prompt still requests JSON. The backend accumulates the full streamed content, extracts visible narration text as soon as possible, and parses final JSON at the end.
- If streaming fails, fallback to the offline template provider and emit the fallback narration in chunks.
- The old `advance()` method remains non-streaming and unchanged for compatibility.

## Frontend Design

- Add `state.dmBusy`.
- `sendMessage()` immediately:
  - validates selected adventure and non-empty text
  - sets `state.dmBusy = true`
  - disables textarea and Send button
  - appends player message locally
  - appends a DM placeholder with a typing indicator
  - starts reading `/messages/stream`
- While `state.dmBusy` is true:
  - clicking Send does nothing except show the localized busy status
  - pressing Enter does not submit
  - textarea is disabled
- As `delta` events arrive, update the placeholder DM message content.
- On `final`, replace local state with server state, rerender scene/combat/messages, clear the input, and restore controls.
- On error, restore controls and show a localized error.

## Testing

- Backend tests:
  - streaming endpoint emits `status`, `delta`, and `final`
  - second concurrent request for the same adventure returns `409 dm_busy`
  - OpenAI-compatible SSE chunks are parsed into text
- Frontend static tests:
  - `/messages/stream` is used
  - `dmBusy` state exists
  - message input and Send button are disabled while busy
  - typing indicator markup and localized strings exist
- Full verification:
  - `uv run pytest -q`
  - `node --check frontend/static/app.js`
