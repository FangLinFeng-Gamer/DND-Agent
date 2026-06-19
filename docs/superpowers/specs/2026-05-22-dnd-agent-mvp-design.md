# DND-Agent MVP Design

## Goal

Build the first playable offline MVP of DND-Agent: a local FastAPI application with a static web UI, SQLite persistence, character management, adventure sessions, a DM-agent, world/rule lookup, and a basic DND combat loop.

## Scope

The MVP focuses on a single-player playable loop:

1. The user opens the web UI.
2. The user creates or selects a character.
3. The user creates or selects an adventure session.
4. The DM-agent creates the opening scene and objective.
5. The user sends actions through the chat UI.
6. The backend saves messages, updates scene state, performs checks or combat when needed, and returns the next DM response.

The first version must run offline by default. It may expose provider interfaces for local or online models, but the default behavior must not require network access.

## Key Decisions

- Use a lightweight monolithic FastAPI app for the first version.
- Use a static HTML/CSS/JavaScript frontend served by FastAPI.
- Use SQLite directly for persistence; do not introduce an ORM or migration tool in the MVP.
- Implement MCP-compatible internal tools first, not a real MCP protocol server.
- Implement an `LLMProvider` abstraction with an offline template provider as the default.
- Implement built-in structured world/rule data for MVP queries and reserve a PDF retrieval interface for later.
- Implement a basic combat prototype with initiative, turn order, HP, AC, attacks, damage, d20 checks, advantage, and disadvantage.

## Architecture

The app uses a simple layered structure:

- API layer: FastAPI routes and request/response schemas.
- Service/tool layer: business operations for characters, world data, adventures, DM narration, combat, agent routing, and image requests.
- Repository layer: SQLite table creation and CRUD helpers.
- Static UI layer: a single-page browser interface under the FastAPI static mount.

The backend should keep API handlers thin. API handlers validate request input, call services, and return structured outputs. Services own business rules. Repositories own SQL and serialization.

## Agent Design

### Main Agent

The main agent introduces system capabilities and routes user intent to the correct service/tool. In the MVP it does not need complex LLM planning. It can use explicit API operations and lightweight keyword or command routing for capability descriptions and simple dispatch.

### DM-Agent

The DM-agent owns the game loop:

- Guide the user to choose a world and character.
- Generate an opening scene from the world and character.
- Maintain the current scene state.
- Describe environment, important objects, NPCs, current objective, and consequences.
- Apply player actions to the scene.
- Trigger checks or combat when the action requires rules resolution.
- Generate subsequent story beats based on the current scene and history.

Narration is generated through an `LLMProvider` interface. The default `TemplateDMProvider` must be deterministic enough for tests and playable without external services. Later providers can call Ollama, LM Studio, DeepSeek, OpenAI, or LangGraph-based workflows.

The DM text must not directly mutate combat HP, turn order, or dice results. Rule outcomes come from combat and dice services, then DM narration explains them.

## MCP-Compatible Tools

The MVP implements internal Python tools with stable inputs and outputs. These are not exposed as a real MCP server yet, but the boundaries should make migration straightforward.

Initial tool groups:

- Character tools: create, list, get, update, delete.
- World tools: search built-in race, class, background, equipment, spell, condition, combat, adventure, and setting entries.
- Adventure tools: create, list, get, delete, append message, summarize current state.
- DM tools: create opening scene, advance scene, answer state questions.
- Combat tools: start combat, roll initiative, resolve checks, resolve attacks, advance turn, end combat.
- Image tools: accept image generation requests and return a not-connected response with a generated prompt.

Each tool should return structured data and avoid returning only free text.

## Data Model

SQLite stores the MVP state. JSON fields are stored as text and serialized by services.

### `characters`

Stores player characters.

Fields:

- `id`
- `name`
- `race`
- `class_name`
- `level`
- `background`
- `alignment`
- `hp_current`
- `hp_max`
- `armor_class`
- `strength`
- `dexterity`
- `constitution`
- `intelligence`
- `wisdom`
- `charisma`
- `skills_json`
- `inventory_json`
- `spells_json`
- `notes`
- `created_at`
- `updated_at`

Natural-language character creation may be accepted by the API, but the MVP can fill missing values with safe defaults. It does not need advanced free-text extraction.

### `adventures`

Stores adventure sessions.

Fields:

- `id`
- `title`
- `world_id`
- `character_id`
- `status`
- `summary`
- `current_scene_json`
- `created_at`
- `updated_at`

`current_scene_json` includes location, environment description, important objects, NPCs, current objective, known world changes, and local consequences.

### `messages`

Stores chat history.

Fields:

- `id`
- `adventure_id`
- `role`
- `content`
- `metadata_json`
- `created_at`

Roles include `player`, `dm`, and `system`.

### `combat_states`

Stores combat state for an adventure.

Fields:

- `id`
- `adventure_id`
- `is_active`
- `round_number`
- `turn_index`
- `participants_json`
- `created_at`
- `updated_at`

`participants_json` includes name, kind, side, HP, AC, initiative, status, available attacks, and whether the participant is defeated.

### `world_entries`

Stores built-in world and rule entries.

Fields:

- `id`
- `category`
- `name`
- `content`
- `tags_json`
- `source`
- `page`
- `metadata_json`

The MVP seeds structured entries for common races, classes, backgrounds, equipment, basic spells, conditions, combat rules, adventure rules, and a default fantasy setting. The PDF retrieval interface is reserved but not implemented in the MVP.

### `generated_assets`

Stores future image generation requests.

Fields:

- `id`
- `kind`
- `subject_id`
- `prompt`
- `status`
- `result_uri`
- `metadata_json`
- `created_at`
- `updated_at`

The MVP returns `status = "not_connected"` for real generation.

## API Design

All API endpoints are under `/api`.

### System

- `GET /api/system/capabilities`

Returns system capabilities, current limitations, and available operations.

### Characters

- `POST /api/characters`
- `GET /api/characters`
- `GET /api/characters/{id}`
- `PATCH /api/characters/{id}`
- `DELETE /api/characters/{id}`

### World and Rules

- `GET /api/world/search?query=&category=`

Returns matching built-in world/rule entries. It should also return an empty result with a clear message when no entries match.

### Adventures

- `POST /api/adventures`
- `GET /api/adventures`
- `GET /api/adventures/{id}`
- `DELETE /api/adventures/{id}`
- `POST /api/adventures/{id}/messages`

Posting a player message advances the DM loop and returns the DM reply, updated scene state, combat state, and dice results when applicable.

### Combat

- `POST /api/adventures/{id}/combat/start`
- `POST /api/adventures/{id}/combat/action`
- `POST /api/adventures/{id}/combat/end`

### Images

- `POST /api/assets/images`

Returns a generated prompt and a not-connected status.

## Service Design

### `CharacterService`

Responsibilities:

- Create characters.
- Fill safe default attributes.
- Validate HP, AC, level, and ability scores.
- Update character fields.
- Delete and retrieve characters.

### `WorldService`

Responsibilities:

- Seed MVP world/rule entries.
- Search by query, category, and tags.
- Reserve a retrieval method for future PDF indexing.

### `AdventureService`

Responsibilities:

- Create and list sessions.
- Attach an adventure to a character.
- Store and retrieve messages.
- Store and update scene state.
- Return recent history for UI display.

### `DMService`

Responsibilities:

- Generate opening scenes.
- Advance scenes from player actions.
- Ask combat and dice services to resolve rule-dependent actions.
- Update scene state through `AdventureService`.
- Return structured DM responses.

### `CombatService`

Responsibilities:

- Roll d20 checks with normal, advantage, and disadvantage modes.
- Roll initiative and sort turn order.
- Start combat with player and NPC participants.
- Resolve attacks against AC.
- Roll damage and update HP.
- Advance turn and round counters.
- End combat and return consequences.

### `AgentRouterService`

Responsibilities:

- Return capability descriptions.
- Route simple user intents to service methods where API-level routing is not enough.
- Keep routing deterministic in the MVP.

### `ImageService`

Responsibilities:

- Build image prompts from character or scene state.
- Save request records.
- Return a clear not-connected response.

## UI Design

The MVP UI is a single static page served by FastAPI.

Layout:

- Left panel: adventure session list, create/delete adventure controls, character selector.
- Center panel: chat history, DM responses, player input box.
- Right panel: current character card, current scene, combat panel, rule search.
- Top bar: system capability entry and create-character control.

Core interactions:

1. Load capabilities, characters, and adventures on page load.
2. Let the user create a character with a compact form.
3. Let the user create an adventure for a selected character.
4. Show recent messages when an adventure is selected.
5. Send player input to `/api/adventures/{id}/messages`.
6. Refresh messages, scene, combat, and character state after each DM response.
7. Let the user search world/rule entries from the right panel.

The first UI should be usable, dense, and direct. It should avoid a marketing landing page.

## Error Handling

Errors use a consistent structure:

```json
{
  "error": {
    "code": "adventure_not_found",
    "message": "Adventure not found.",
    "details": {}
  }
}
```

Common error codes:

- `character_not_found`
- `adventure_not_found`
- `adventure_requires_character`
- `combat_not_active`
- `combat_already_active`
- `invalid_turn`
- `world_entry_not_found`
- `image_generation_not_connected`
- `validation_error`

The UI should display the message clearly and keep the previous state visible.

## Testing Strategy

Backend tests are required for the MVP.

Test coverage:

- `CharacterService`: defaults, validation, create, update, delete, get, list.
- `WorldService`: seed data and search.
- `AdventureService`: create adventure, append messages, retrieve current state.
- `CombatService`: d20 checks, advantage, disadvantage, initiative sorting, attack hit/miss, damage, defeated participants, turn advancement.
- API flow: create character, create adventure, send player message, receive DM reply and state.

The UI is manually verified in the MVP. Browser automation is not required for the first version.

## Out of Scope

The MVP does not implement:

- A real MCP protocol server.
- PDF parsing or vector retrieval for the PHB.
- Full LangGraph or deepagents orchestration.
- Voice input or voice output.
- Real image generation.
- Complete DND 5e spell, class feature, feat, monster, and condition automation.
- Multiplayer sessions.
- Authentication or account management.

## Acceptance Criteria

- The app starts locally with FastAPI.
- Opening the root page shows the static web UI.
- The user can create, list, edit, and delete characters.
- The user can create, list, select, and delete adventures.
- The user can send a player message and receive a DM response.
- The app persists characters, adventures, messages, scene state, and combat state in SQLite.
- World/rule search returns useful built-in DND MVP entries.
- Combat can be started, ordered by initiative, advanced by turns, and resolved with attack and damage rolls.
- The default DM provider works offline without external model services.
- Image generation requests return a clear not-connected response rather than failing.
