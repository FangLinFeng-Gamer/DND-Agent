import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_frontend_routes_map_core_views_to_real_paths(tmp_path):
    script_path = tmp_path / "frontend-routing-test.mjs"
    ui_url = json.dumps((PROJECT_ROOT / "frontend/static/js/ui.js").as_uri())
    state_url = json.dumps((PROJECT_ROOT / "frontend/static/js/state.js").as_uri() + "?v=20260619-world-state-progress")
    script_path.write_text(
        textwrap.dedent(
            """
            import assert from "node:assert/strict";

            const historyCalls = [];
            const appViews = [
              { id: "home-view", classList: { toggle: () => {} } },
              { id: "story-create-view", classList: { toggle: () => {} } },
              { id: "character-create-view", classList: { toggle: () => {} } },
              { id: "game-view", classList: { toggle: () => {} } },
              { id: "model-config-view", classList: { toggle: () => {} } },
            ];
            const navButtons = [
              { dataset: { viewTarget: "home" }, classList: { toggle: () => {} } },
              { dataset: { viewTarget: "story-create" }, classList: { toggle: () => {} } },
              { dataset: { viewTarget: "character-create" }, classList: { toggle: () => {} } },
              { dataset: { viewTarget: "game" }, classList: { toggle: () => {} } },
              { dataset: { viewTarget: "model-config" }, classList: { toggle: () => {} } },
            ];

            globalThis.window = {
              location: { pathname: "/" },
              localStorage: { getItem() { return "en"; } },
              history: {
                pushState: (_state, _title, url) => historyCalls.push(["push", url]),
                replaceState: (_state, _title, url) => historyCalls.push(["replace", url]),
              },
            };
            globalThis.document = {
              querySelectorAll(selector) {
                if (selector === ".app-view") return appViews;
                if (selector === ".view-nav [data-view-target]") return navButtons;
                return [];
              },
            };

            const ui = await import(UI_URL);
            const stateModule = await import(STATE_URL);

            assert.equal(ui.routeForView("home"), "/home");
            assert.equal(ui.routeForView("character-create"), "/character-create");
            assert.equal(ui.routeForView("story-create"), "/stories");
            assert.equal(ui.routeForView("game"), "/game");
            assert.equal(ui.routeForView("model-config"), "/models");
            assert.equal(ui.viewFromPath("/"), "home");
            assert.equal(ui.viewFromPath("/home"), "home");
            assert.equal(ui.viewFromPath("/character-create"), "character-create");
            assert.equal(ui.viewFromPath("/stories"), "story-create");
            assert.equal(ui.viewFromPath("/game"), "game");
            assert.equal(ui.viewFromPath("/game/42"), "game");
            assert.equal(stateModule.state.selectedAdventureId, 42);
            assert.equal(stateModule.state.routeAdventureId, 42);
            assert.equal(stateModule.state.gameMode, "room");
            assert.equal(ui.viewFromPath("/game"), "game");
            assert.equal(stateModule.state.selectedAdventureId, null);
            assert.equal(stateModule.state.routeAdventureId, null);
            assert.equal(stateModule.state.gameMode, "setup");
            assert.equal(ui.viewFromPath("/play"), "game");
            assert.equal(ui.viewFromPath("/dnd-agent/v1/game"), "game");
            assert.equal(ui.viewFromPath("/models"), "model-config");

            ui.showView("home", { replace: true });
            assert.deepEqual(historyCalls, [["replace", "/home"]]);

            historyCalls.length = 0;
            globalThis.window.location.pathname = "/home";
            ui.showView("character-create");
            assert.deepEqual(historyCalls, [["push", "/character-create"]]);

            historyCalls.length = 0;
            globalThis.window.location.pathname = "/game";
            stateModule.state.selectedAdventureId = 42;
            stateModule.state.gameMode = "room";
            ui.showView("game");
            assert.deepEqual(historyCalls, [["push", "/game/42"]]);
            """
        ).replace("UI_URL", ui_url),
        encoding="utf-8",
    )
    script = script_path.read_text(encoding="utf-8").replace("STATE_URL", state_url)
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        ["node", str(script_path)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
