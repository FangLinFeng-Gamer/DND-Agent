# Story Template UI Design

## Goal

Add a guided home page, reusable story templates, a custom story creation page, and a clearer game-start flow for DND-Agent.

## Definitions

- Story template: reusable plot and world setup. A template can start many game sessions.
- Adventure session: one playable run created from a character and a story template. Player actions mutate only the session scene, messages, combat state, and world changes.
- Default story: built-in offline DND-style story generated for the MVP.

## User Experience

The first screen becomes a home view. It explains how to play in short operational steps:

1. Create or select a character.
2. Choose the default story or create a custom story.
3. Start a new game session from that story.
4. Type character actions in the chat.
5. Watch the DM update the current scene and world changes.

The home page exposes actions for:

- Start the default story.
- Open story creation.
- Open the existing game page.

The story creation view lets users create their own reusable story template with:

- Title.
- World background.
- Main quest.
- Opening location.
- Opening environment.
- Opening objective.

The game page keeps the existing three-column layout, but adventure creation uses a selected story template. Starting a session posts `story_id` to the adventure API. Existing sessions remain selectable from the adventure list.

## Backend Design

Add a `stories` table:

- `id`: text primary key.
- `title`: text.
- `description`: text.
- `world_background`: text.
- `main_quest`: text.
- `opening_location`: text.
- `opening_environment`: text.
- `opening_objective`: text.
- `important_objects_json`: JSON list.
- `npcs_json`: JSON list.
- timestamps.

Seed one default story with id `mistbell_tower`.

Extend adventure creation:

- `AdventureCreate.story_id` defaults to `mistbell_tower`.
- `adventures.story_id` stores the template id.
- `adventures.story_snapshot_json` stores a snapshot of the story used at session creation.

The snapshot makes existing sessions stable even if a template changes later.

Add API routes:

- `GET /api/stories`.
- `GET /api/stories/{story_id}`.
- `POST /api/stories`.

## Default Story

Title: Mistbell Tower.

The default story is an original low-level DND-style adventure. The world is a rain-soaked border region where the town of Ravenford depends on a trade road and an old signal tower. Recently the tower bell rings by itself at midnight, caravans vanish in the fog, and villagers report pale lights beneath the hill.

The main quest asks the party to investigate the tower, find the missing caravan, and decide what to do with a buried shrine whose old ward is failing.

Opening scene:

- Location: Ravenford Wayhouse.
- Environment: Rain taps on the shutters, worried townsfolk crowd the common room, and the old tower bell sounds once from the fog.
- Objective: Speak with Mayor Elira Voss, inspect the tower road, and find the first trace of the missing caravan.

## DM Behavior

When a game session starts, the first DM message must introduce:

- World background.
- Main quest.
- Current environment.
- Immediate objective.

Subsequent player actions keep using the current offline template DM behavior, but scene data comes from the selected story.

## Frontend Design

Use the existing static app without a build step.

Views:

- `home`: tutorial and primary actions.
- `story-create`: custom story form and story list.
- `game`: existing game surface, with story selection added to adventure creation.

Routing can be client-side state only. No URL routing is required for the MVP.

Internationalization:

- Keep the existing language selector.
- Add English and Chinese copy for new views.
- Keep API keys and JSON fields English.

## Error Handling

- Creating an adventure with a missing story returns a structured 404 `story_not_found`.
- Creating a story with an existing id is not exposed in the UI; backend generated ids avoid collisions.
- Frontend status area shows API error messages.

## Testing

Backend tests:

- Default story is seeded.
- Custom story can be created and retrieved.
- Same story can create multiple adventure sessions.
- Opening DM message includes world background, main quest, environment, and objective.

Frontend static tests:

- Home view and tutorial copy are present.
- Story creation view and form fields are present.
- Game view still contains the chat/game controls.

Full verification:

- `uv run pytest -q`.
- `node --check frontend/static/app.js`.
- Local HTTP flow: create character, create story, start adventure from story, send action.
