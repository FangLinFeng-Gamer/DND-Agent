# Map Combat Phase 2 Design

## Goal

Phase 2 turns stored maps into combat-aware tactical scenes. A running adventure can activate one map scene, sync combat participants into map tokens, move those tokens on a grid, expose distance/context to the DM agent, and provide a basic frontend board for manual verification.

## Scope

This phase implements:

- Combat token storage separate from uploaded map assets and reusable scene items.
- Automatic token sync when combat starts on an adventure with an active scene.
- Token listing and coordinate updates through backend APIs.
- Distance and tactical context APIs based on the active scene grid.
- DM/NPC context enrichment so the model sees scene, token positions, nearby enemies, and distances.
- Fallback NPC movement behavior when no model is configured.
- Frontend map board with background, grid overlay, token layer, token selection, and click-to-move.

This phase does not implement WebSocket collaboration, dynamic lighting, wall collision, complex fog of war, image token editing, or rule-complete player movement enforcement. Those belong to Phase 3.

## Data Model

`map_scene_items` remains the reusable canvas asset layer: background maps, props, uploaded token images, and other placed assets.

`map_combat_tokens` is added as the transient tactical layer for combat participants. It stores one row per participant per scene and does not require an uploaded image asset. Fields include scene/adventure identity, participant name, side, kind, x/y coordinates, token size, speed, reach, visibility, and metadata. The separation avoids forcing every goblin, bandit, or player character to upload an image before combat can work.

## Backend Flow

When `/api/adventures/{id}/combat/start` succeeds, `MapService.ensure_combat_tokens` checks whether the adventure has an active scene. If it does, each combat participant gets a token if one does not already exist. Existing token positions are preserved; participant stats such as side, speed, and reach are refreshed.

The map API exposes:

- `GET /api/map-scenes/{scene_id}/combat-tokens`
- `POST /api/map-scenes/{scene_id}/combat-tokens/sync`
- `PATCH /api/map-scenes/{scene_id}/combat-tokens/{token_id}`
- `GET /api/adventures/{adventure_id}/map-context`

Distance is computed from pixel coordinates using scene `grid_size` and `scale`. The initial implementation uses Euclidean distance because it is stable for both free placement and square-grid previews. It returns feet and leaves alternate 5e grid counting for a later rules refinement.

## DM/NPC Behavior

The DM agent receives map context in NPC combat decisions:

- Active map scene name, grid type, grid size, and scale.
- Current NPC token.
- Visible combat tokens.
- Nearby hostile targets with `distance_ft`.

When no model is active, fallback NPC logic uses the same context. If the nearest hostile is outside reach, the NPC moves its token toward that target and resolves `dash`. If the target is within reach, it uses the existing attack fallback. This keeps NPC behavior deterministic and testable while still using the map.

## Frontend Flow

The game page map panel becomes a lightweight tactical board:

- Background item renders as the board image when present.
- Grid overlay uses the active scene grid size.
- Combat tokens render above the map.
- Token list allows selecting a participant.
- Clicking the board moves the selected token through the token update API.
- Starting combat or resolving an NPC turn refreshes map tokens.

The frontend remains bilingual through the existing i18n dictionary.

## Testing

Backend tests cover:

- Starting combat creates tokens for the active scene.
- Token coordinates can be patched and reflected in map context.
- Model NPC payload includes map context and distances.
- Fallback NPC dashes and moves toward a distant target.

Frontend static tests cover:

- Required map token DOM controls exist.
- Game JS calls combat token APIs.
- Token rendering and click-to-move wiring exists.

Full verification uses all Python tests, JS syntax checks, and an in-browser smoke check of the map panel.
