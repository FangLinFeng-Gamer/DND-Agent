# Character Creation Agent Busy State Design

## Goal

Make character creation agent requests visibly pending and strictly one-at-a-time.
While the agent is processing, the conversation shows the same animated typing
indicator used by the DM, and the player cannot submit another message.

## Scope

- Update only the character creation frontend interaction.
- Reuse the existing typing indicator component and CSS.
- Keep the existing character creation HTTP API unchanged.
- Support both English and Chinese through the existing i18n system.

## Interaction

1. When the player submits a non-empty message, acquire the frontend busy state
   before any asynchronous session lookup or request begins.
2. Immediately append the player message and a pending assistant message.
3. Render the pending assistant message as the existing three-dot typing
   indicator with a character-guide-specific accessible label.
4. Disable the character creation textarea, send button, and confirm button for
   the entire request.
5. Ignore any submit, click, or Enter action received while busy and show the
   localized "still responding" status.
6. On success, remove the pending message and append the returned assistant
   message.
7. On failure, remove the pending message, display the existing error status,
   and preserve the submitted player message in the conversation.
8. Release the busy state in `finally`, restoring the controls according to
   draft validity.

## Component Changes

### Character Creation Module

`frontend/static/js/character-creation.js` will own the request lock and pending
message lifecycle. Session creation will accept an already-held busy state so
the send path does not briefly unlock while creating its first session.

### Shared UI

`typingIndicatorNode` will accept an optional accessible-label translation key
or text. DM behavior remains unchanged; character creation passes its own
localized thinking text.

### Localization

Add English and Chinese strings for a character guide that is still responding.
The existing character guide thinking strings remain the visible/accessibility
label for the animated pending message.

## Error Handling

- Empty messages continue to show the existing validation status.
- Repeated submissions while busy do not call the API.
- Failed requests always clear the pending animation and release controls.
- Session initialization failures do not leave the page locked.

## Testing

Automated frontend contract tests will verify:

- A pending assistant message is created before the request.
- The typing indicator is rendered for that pending message.
- Busy state is acquired before awaiting session creation.
- Textarea, send button, and confirm button are disabled while busy.
- Repeated submissions return before issuing an API request.
- Busy state and pending state are cleared on success or failure.
- English and Chinese busy strings exist.

Browser verification will cover:

- The typing animation appears after sending.
- Input, send, and confirm controls remain disabled during processing.
- Repeated click and Enter attempts do not create duplicate player messages.
- Controls recover after the agent response.
