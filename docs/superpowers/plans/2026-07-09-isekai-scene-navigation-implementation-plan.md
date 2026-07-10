# Isekai Scene Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved scene-generation/navigation P0 so isekai play resolves movement through per-adventure scene state instead of keyword jumps or generic fallback objects.

**Architecture:** Add a narrow scene graph/navigation layer that reads `world_state` and current scene, resolves leave/return/travel intentions into route plans, and blocks impossible movement before action resolution changes location. Keep DM narration downstream of deterministic state. Remove normal use of `周围环境` as the projector fallback.

**Tech Stack:** Python 3, Pydantic schemas, existing SQLite adventure `current_scene_json` and `world_state_json`, pytest via `uv run pytest`.

## Global Constraints

- Runtime scene state must be adventure-bound; no cross-save global scene state.
- DM agent cannot directly create final node/edge/object facts.
- Movement can only switch node by legal edge or legal route plan.
- `observe/search/status_check` must not change location.
- `hidden_edges` cannot be visible suggestions until discovery reveals them.
- Empty/generic scenes must be repaired or blocked, not silently treated as valid play state.

---

### Task 1: Scene Graph and Navigation Service

**Files:**
- Create: `backend/src/services/isekai_scene_navigation.py`
- Test: `test/backend/src/services/test_isekai_scene_navigation.py`

**Interfaces:**
- Consumes: `SceneState`
- Produces:
  - `NavigationResult`
  - `IsekaiSceneNavigationService.resolve(action, scene, world_state) -> NavigationResult`

- [ ] **Step 1: Write failing tests**

```python
from dataclasses import asdict

from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import ParsedIsekaiAction
from backend.src.services.isekai_scene_navigation import IsekaiSceneNavigationService


def action(action_type: str, text: str = "", **arguments):
    return ParsedIsekaiAction(
        action_type=action_type,
        time_cost_minutes=10,
        advances_time=True,
        survival_intent="move",
        reason="move",
        arguments={"raw_text": text, **arguments},
    )


def scene(node_id: str = "mine_entrance"):
    return SceneState(
        location="铁炉镇外 / 旧矿道入口",
        location_path={"node_id": node_id, "display_name": "铁炉镇外 / 旧矿道入口"},
        environment="旧矿道入口有一条回到林间小路的旧路。",
        current_objective="确认路线。",
        interactables=[],
    )


def test_leave_current_scene_uses_back_edge():
    world = {
        "scene_graph": {
            "edges": [
                {"id": "edge_mine_to_path", "from_node_id": "mine_entrance", "to_node_id": "forest_path", "kind": "back", "access": "open"}
            ]
        }
    }
    result = IsekaiSceneNavigationService().resolve(action("leave_location", "离开这里"), scene(), world)
    assert result.status == "resolved"
    assert result.target_node_id == "forest_path"
    assert result.edge_ids == ["edge_mine_to_path"]


def test_return_to_known_settlement_uses_location_history():
    world = {
        "known_locations": [{"node_id": "grey_oak_gate", "name": "灰橡镇", "type": "settlement"}],
        "location_history": [
            {"from_node_id": "grey_oak_gate", "to_node_id": "forest_path", "edge_id": "edge_town_to_path"},
            {"from_node_id": "forest_path", "to_node_id": "mine_entrance", "edge_id": "edge_path_to_mine"},
        ],
    }
    result = IsekaiSceneNavigationService().resolve(action("travel", "回到城镇"), scene(), world)
    assert result.status == "resolved"
    assert result.target_node_id == "grey_oak_gate"
    assert result.edge_ids == ["edge_path_to_mine", "edge_town_to_path"]


def test_unknown_settlement_becomes_seek_destination():
    result = IsekaiSceneNavigationService().resolve(action("travel", "回到城镇"), scene(), {})
    assert result.status == "unknown_target"
    assert result.navigation_intent == "seek_destination"
    assert "寻找道路" in result.alternatives


def test_blocked_edge_returns_blocked_route():
    world = {
        "scene_graph": {
            "edges": [
                {
                    "id": "edge_mine_to_path",
                    "from_node_id": "mine_entrance",
                    "to_node_id": "forest_path",
                    "kind": "back",
                    "access": "blocked",
                    "blocked_by": ["塌方"],
                }
            ]
        }
    }
    result = IsekaiSceneNavigationService().resolve(action("leave_location", "离开这里"), scene(), world)
    assert result.status == "blocked_route"
    assert "清理阻碍" in result.alternatives
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest -q test/backend/src/services/test_isekai_scene_navigation.py`

Expected: fail because `backend.src.services.isekai_scene_navigation` does not exist.

- [ ] **Step 3: Implement service**

Create `IsekaiSceneNavigationService` with:

```python
@dataclass(frozen=True)
class NavigationResult:
    status: str
    navigation_intent: str
    target_node_id: str = ""
    target_name: str = ""
    edge_ids: list[str] = field(default_factory=list)
    reason: str = ""
    alternatives: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

Implement deterministic checks:

- `leave_location` uses open `parent/exit/back/leave` edge from current node.
- `travel` text containing return markers binds settlement from `known_locations` or `location_history`.
- Known route comes from direct `scene_graph.edges` or reversed `location_history`.
- Blocked edges return `blocked_route`.
- Unknown settlement returns `seek_destination`.

- [ ] **Step 4: Verify tests pass**

Run: `uv run pytest -q test/backend/src/services/test_isekai_scene_navigation.py`

Expected: all tests pass.

---

### Task 2: Gate Movement Through Navigation

**Files:**
- Modify: `backend/src/services/isekai_action_resolution.py`
- Modify: `backend/src/services/isekai.py`
- Test: `test/backend/src/services/test_isekai_survival.py`

**Interfaces:**
- Consumes: `IsekaiSceneNavigationService.resolve(...)`
- Produces: movement metadata in `dm_message.metadata["navigation"]`

- [ ] **Step 1: Write failing integration tests**

Add tests that:

- current node is `mine_entrance`
- world state has no edge to `street_inn`
- user submits `进入街边旅店`
- response stays at `mine_entrance`
- metadata contains `navigation.status == "unknown_target"` or `blocked_route`
- response text gives alternatives

Add tests that:

- current node is `mine_entrance`
- world state has `location_history` back to `grey_oak_gate`
- user submits `回到城镇`
- response moves to `grey_oak_gate`

- [ ] **Step 2: Run failing integration tests**

Run: `uv run pytest -q test/backend/src/services/test_isekai_survival.py -k "navigation or edge"`

Expected: fail because action resolution still uses text-to-node fallback.

- [ ] **Step 3: Wire navigation into action resolution**

In `IsekaiActionResolutionEngine.resolve`, before preconditions for movement actions:

```python
if action.action_type in {"enter_location", "travel", "leave_location"} and self.navigation:
    navigation = self.navigation.resolve(action, current_scene, current_world_state)
    if navigation.status in {"unknown_target", "ambiguous_target", "known_target_unknown_route", "blocked_route"}:
        action = self._navigation_failure(action, navigation)
    else:
        action = self._action_with_route_plan(action, navigation)
```

Use `condition_failed` for failures. Store `navigation` in step delta for metadata.

- [ ] **Step 4: Switch scene only by route plan**

Update `_scene_after_action` so `enter_location/travel/leave_location` first checks `action.arguments["route_plan"]["target_node_id"]`. Do not call `locations.node_id_for_text(text, "")` for arbitrary text.

- [ ] **Step 5: Verify integration tests pass**

Run: `uv run pytest -q test/backend/src/services/test_isekai_survival.py -k "navigation or edge"`

Expected: new tests pass.

---

### Task 3: Remove Generic Projector Fallback and Add Scene Structure Guard

**Files:**
- Modify: `backend/src/services/isekai_interactables.py`
- Modify: `backend/src/services/isekai.py`
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Produces: no normal `surroundings_01` fallback
- Produces: metadata flag for scene repair/block

- [ ] **Step 1: Write failing tests**

Add tests asserting:

- `IsekaiInteractableProjector().project(empty_scene, "search")` does not return `周围环境`.
- An adventure with only `周围环境` is marked invalid before action resolution and repaired by model-proposed scene objects, or returns a non-advancing failure if no structure can be produced.

- [ ] **Step 2: Run failing tests**

Run: `uv run pytest -q test/backend/src/services/test_isekai_content_agnostic.py -k "surroundings or scene_structure"`

Expected: fail because projector currently creates `surroundings_01`.

- [ ] **Step 3: Remove fallback**

Update `IsekaiInteractableProjector.project` to only return current visible interactables and suggestions from those interactables.

- [ ] **Step 4: Add scene validity helper**

Add a small helper in `IsekaiSurvivalService`:

```python
def _scene_is_structured(self, scene: SceneState) -> bool:
    if not scene.interactables:
        return False
    return any(entry.get("name") not in {"", "周围环境", "门口"} for entry in scene.interactables if isinstance(entry, dict))
```

Before resolving non-status actions, if invalid and model cannot materialize objects, return a blocked response without advancing time.

- [ ] **Step 5: Verify tests pass**

Run: `uv run pytest -q test/backend/src/services/test_isekai_content_agnostic.py -k "surroundings or scene_structure"`

Expected: pass.

---

### Task 4: Full Regression and Metadata

**Files:**
- Modify: `backend/src/services/isekai_narration_composer.py` if navigation text needs a clearer fallback
- Test: `test/backend/src/services/test_isekai_survival.py`
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Produces: `metadata["navigation"]`
- Produces: readable failure/seek-destination narration

- [ ] **Step 1: Add regression tests**

Cover:

- `观察/搜索` does not move.
- hidden object remains hidden until discovery.
- `进入街边旅店` from unrelated mine scene does not switch location.
- `离开这里` uses back edge.
- `回到城镇` uses history.
- `回到城镇` with no known settlement becomes seek-destination.

- [ ] **Step 2: Run targeted regression**

Run: `uv run pytest -q test/backend/src/services/test_isekai_scene_navigation.py test/backend/src/services/test_isekai_content_agnostic.py test/backend/src/services/test_isekai_survival.py -k "navigation or edge or surroundings or scene_structure"`

Expected: all targeted tests pass.

- [ ] **Step 3: Run full backend tests**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 4: Run diff check**

Run: `git diff --check`

Expected: no output and exit code 0.
