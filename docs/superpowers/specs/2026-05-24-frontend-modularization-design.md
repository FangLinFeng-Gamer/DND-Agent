# Frontend Modularization Design

## Problem

`frontend/static/app.js` has grown past 1,700 lines because it contains state, API access, i18n strings, routing, rendering, event binding, streaming chat, story management, model management, character management, race browsing, combat, and rule search. This makes future UI changes risky because unrelated features share one large file.

## Design

Keep the existing no-build static frontend, but convert the entry script to a native browser ES module. `app.js` becomes the startup and event-wiring entrypoint. Shared infrastructure moves into `frontend/static/js/state.js`, `api.js`, `i18n.js`, and `ui.js`. Feature logic moves into focused modules: `stories.js`, `models.js`, `races.js`, and `game.js`.

The split is intentionally conservative. It does not introduce React, Vue, bundlers, npm dependencies, or new runtime behavior. Existing DOM ids, API endpoints, translations, streaming behavior, and test-visible strings stay intact, but tests read across all static JS modules instead of assuming all code lives in `app.js`.

## Testing

Add a structure test requiring `app.js` to stay below 350 lines, require the new module files, and require `index.html` to load the entrypoint with `type="module"`. Existing frontend tests are adjusted to search all static JS files for feature-specific strings.
