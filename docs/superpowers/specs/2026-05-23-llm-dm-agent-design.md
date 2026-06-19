# LLM DM Agent Design

## Goal

Add configurable large-model support and a DM Agent that can use an OpenAI-compatible model to judge player actions, update the world, drive NPC behavior, and manage long adventure context while preserving the offline template fallback.

## Requirements

- Add a frontend model configuration page where users can add, edit, delete, and activate model configs.
- Store model configs locally in SQLite. API keys are stored for local use, but list/detail responses return masked keys.
- Support an OpenAI-compatible chat completions endpoint first: `base_url`, `model_name`, `api_key`, `temperature`, `max_context_tokens`.
- Add a DM Agent path that uses the active model when available and falls back to the offline template provider when no model is active or the model call fails.
- DM Agent must consider DND-like action rules:
  - Ask for ability checks when actions are uncertain.
  - Server rolls the check result so the game state is deterministic and auditable.
  - Record check metadata in the DM message.
  - Update current scene fields and world changes.
  - Generate NPC actions from scene NPC data and model response.
- Add important world-event persistence for changes such as NPC death, sacrifice, alliances, discovered secrets, and irreversible world changes.
- Add context management:
  - Build model context from adventure summary, recent messages, scene, character, story snapshot, and important world events.
  - Estimate token size locally.
  - When context exceeds the configured model limit, update `adventures.summary` with a compact running summary and keep only recent messages in prompts.
- All frontend text added in this feature must support English and Chinese via the existing language selector.

## Non-Goals

- No provider-specific SDK dependency in v1. Use standard-library HTTP for OpenAI-compatible calls.
- No streaming response UI in this iteration.
- No real image generation changes in this iteration.
- No full 5e rules engine. The agent returns structured check requests and the server resolves simple d20 ability checks.

## Architecture

Backend adds three focused services:

- `LLMModelService`: CRUD, activation, masked output for local model configs.
- `LLMClient` and `LLMDMProvider`: OpenAI-compatible chat call and structured JSON response parsing.
- `ContextService` and `WorldEventService`: context packing, summary updates, and important event persistence.

`DMService.advance()` remains the orchestration point. It appends the player message, builds context, asks the configured provider for a structured decision, rolls requested checks server-side, updates the scene and summary, persists world events, and appends the DM response.

Frontend adds a `Models` view using existing static HTML/CSS/JS patterns. The page has model list, edit form, activate/delete actions, and status messages localized through `translations`.

## Data Model

### `llm_models`

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `name TEXT NOT NULL`
- `provider TEXT NOT NULL`
- `base_url TEXT NOT NULL`
- `api_key TEXT NOT NULL`
- `model_name TEXT NOT NULL`
- `temperature REAL NOT NULL`
- `max_context_tokens INTEGER NOT NULL`
- `is_active INTEGER NOT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

### `world_events`

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `adventure_id INTEGER NOT NULL`
- `event_type TEXT NOT NULL`
- `title TEXT NOT NULL`
- `description TEXT NOT NULL`
- `importance INTEGER NOT NULL`
- `metadata_json TEXT NOT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

## DM Agent Structured Output

The model is instructed to return JSON:

```json
{
  "narration": "What the DM says to the player.",
  "scene": {
    "location": "Current location",
    "environment": "Current environment",
    "important_objects": ["object"],
    "npcs": ["NPC name and short behavior"],
    "current_objective": "Immediate objective",
    "world_changes": ["change"]
  },
  "requires_check": true,
  "check": {
    "ability": "wisdom",
    "dc": 12,
    "reason": "Searching a hidden mechanism"
  },
  "npc_actions": [
    "The wounded scout retreats toward the bell rope."
  ],
  "world_events": [
    {
      "event_type": "npc",
      "title": "Scout flees",
      "description": "The wounded scout retreated and warned the tower.",
      "importance": 3
    }
  ]
}
```

If the model returns invalid JSON or the HTTP call fails, the system uses `TemplateDMProvider` so the game remains playable.

## Frontend UX

The top navigation becomes:

- Home
- Stories
- Play
- Models

The Models page contains:

- Model list with active marker.
- Create/edit form:
  - Display name
  - Provider
  - Base URL
  - API key
  - Model name
  - Temperature
  - Max context tokens
- Actions:
  - Save
  - Reset
  - Activate
  - Delete

All labels, buttons, placeholders, empty states, and status messages use i18n keys in both English and Chinese.
