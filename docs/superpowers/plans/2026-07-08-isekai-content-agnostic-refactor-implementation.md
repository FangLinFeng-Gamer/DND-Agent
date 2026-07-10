# Isekai Content-Agnostic Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move isekai mode from concrete keyword branches toward content packs and validated runtime content for objects, locations, discoveries, and offers.

**Architecture:** Add content-pack primitives that hold concrete locations, scene objects, discovery tables, and merchant offers. Keep rule services responsible for validation, target binding, preconditions, time/survival, economy, rewards, and narration; concrete content should live in content-pack data or LLM proposals.

**Tech Stack:** Python 3.12, FastAPI service layer, Pydantic schemas, pytest service tests, existing SQLite-backed store.

## Global Constraints

- Do not add new action types beyond the current stable action set.
- Do not allow LLM proposals to directly mutate final money, items, entitlements, quest stages, or NPC relationships.
- Keep old furnace inn and night wolf as P1 content, but migrate concrete text/data out of generic services where feasible.
- Preserve legacy fallback for existing saves, but mark new code paths as content-pack or LLM-proposal sourced.
- Every behavior change must start with a failing test.

---

### Task 1: Content Pack Core

**Files:**
- Create: `backend/src/services/isekai_content.py`
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Produces: `IsekaiContentService.builtin_pack(pack_id: str) -> dict`
- Produces: `IsekaiContentService.ensure_world_state(world_state: dict | None) -> dict`
- Produces: `IsekaiContentService.location_nodes(world_state: dict | None) -> dict[str, dict]`
- Produces: `IsekaiContentService.discovery_tables(world_state: dict | None) -> dict[str, list[dict]]`
- Produces: `IsekaiContentService.merchant_offers(world_state: dict | None) -> dict[str, list[dict]]`

- [ ] **Step 1: Write failing tests**

```python
def test_old_furnace_pack_exposes_locations_offers_and_discoveries():
    service = IsekaiContentService()
    state = service.ensure_world_state({})
    nodes = service.location_nodes(state)
    offers = service.merchant_offers(state)
    discoveries = service.discovery_tables(state)

    assert "inn_front_hall" in nodes
    assert "inn_bed" in {offer["offer_id"] for offer in offers["innkeeper_01"]}
    assert "broken_pot_handle" in discoveries
```

- [ ] **Step 2: Run test to verify RED**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_old_furnace_pack_exposes_locations_offers_and_discoveries -q`

Expected: fails because `backend.src.services.isekai_content` does not exist.

- [ ] **Step 3: Implement minimal content service**

Create `IsekaiContentService` with a built-in `old_furnace_inn_p1` pack containing location nodes, merchant offers, and discovery entries now scattered in generic services.

- [ ] **Step 4: Run test to verify GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_old_furnace_pack_exposes_locations_offers_and_discoveries -q`

Expected: passes.

### Task 2: Location Service Reads Content Pack

**Files:**
- Modify: `backend/src/services/isekai_locations.py`
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Consumes: `IsekaiContentService.location_nodes(world_state)`
- Produces: `IsekaiLocationService(content_service: IsekaiContentService | None = None)`

- [ ] **Step 1: Write failing test**

```python
def test_location_service_loads_nodes_from_content_pack():
    locations = IsekaiLocationService()
    scene = locations.scene_for("inn_front_hall")

    assert scene.location_path["node_id"] == "inn_front_hall"
    assert {entry["id"] for entry in scene.interactables} >= {"innkeeper_01", "kitchen_door"}
```

- [ ] **Step 2: Run RED**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_location_service_loads_nodes_from_content_pack -q`

Expected: fails until `IsekaiLocationService` uses content-pack nodes.

- [ ] **Step 3: Implement minimal migration**

Refactor `IsekaiLocationService._nodes()` to hydrate `IsekaiLocationNode` objects from `IsekaiContentService.location_nodes({})`.

- [ ] **Step 4: Run GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_location_service_loads_nodes_from_content_pack -q`

Expected: passes.

### Task 3: Scene Object Proposal Materialization

**Files:**
- Modify: `backend/src/services/isekai_content.py`
- Modify: `backend/src/services/isekai.py`
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Produces: `IsekaiContentService.materialize_scene_objects(scene: SceneState, proposals: Any) -> tuple[list[dict], dict]`
- Consumes: model payload key `scene_objects`

- [ ] **Step 1: Write failing test**

```python
def test_model_scene_objects_materialize_without_keyword_projector(store):
    payload = {
        "narration": "你看见蓝盐水洼旁有一只虫蚀皮袋。",
        "scene_objects": {
            "add": [
                {"type": "resource", "name": "蓝盐水洼", "aliases": ["水洼"], "suggested_affordances": ["observe", "search"]},
                {"type": "container", "name": "虫蚀皮袋", "aliases": ["皮袋"], "suggested_affordances": ["observe", "search", "open"]},
            ]
        },
        "suggested_actions": ["搜索虫蚀皮袋"],
    }
    # Advance with a fake model payload and assert both objects enter current_scene.interactables.
```

- [ ] **Step 2: Run RED**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_model_scene_objects_materialize_without_keyword_projector -q`

Expected: fails because `scene_objects` is ignored.

- [ ] **Step 3: Implement materialization**

Parse `scene_objects` in `parse_model_payload`, validate object type and affordances, and merge current-scene objects after `apply_scene_progression`.

- [ ] **Step 4: Run GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_model_scene_objects_materialize_without_keyword_projector -q`

Expected: passes.

### Task 4: Alias-Based Target Grounding

**Files:**
- Modify: `backend/src/services/isekai_action_parser.py`
- Modify: `backend/src/services/isekai_action_grounder.py`
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Consumes: `SceneObject.aliases`
- Produces: exact and alias target binding without adding concrete tokens to parser.

- [ ] **Step 1: Write failing test**

```python
def test_grounder_matches_random_object_alias_without_parser_token():
    scene = SceneState(... interactables=[{"id": "random_bag_01", "type": "container", "name": "虫蚀皮袋", "aliases": ["皮袋"], "affordances": ["观察", "搜索"]}])
    plan = schema.validate({... "steps": [{"action_type": "search", "target_text": "皮袋"}]}, raw_text="搜索皮袋")
    grounded = IsekaiActionGrounder(IsekaiTimeService()).ground(plan, scene)
    assert grounded.steps[0].action.target_id == "random_bag_01"
```

- [ ] **Step 2: Run RED**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_grounder_matches_random_object_alias_without_parser_token -q`

Expected: fails because aliases are not part of candidates.

- [ ] **Step 3: Implement alias matching**

Include `aliases` in candidate payloads and target matching. Do not add the random object name to `_loose_target_match`.

- [ ] **Step 4: Run GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_grounder_matches_random_object_alias_without_parser_token -q`

Expected: passes.

### Task 5: Discovery Table Resolution

**Files:**
- Modify: `backend/src/services/isekai_action_resolution.py`
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Consumes: `world_state["isekai_content"]["discovery_tables"]`
- Produces: search/observe result text and reveal objects from discovery table.

- [ ] **Step 1: Write failing test**

```python
def test_discovery_table_reveals_random_object_without_resolution_branch(store):
    # Inject discovery for target "虫蚀皮袋" revealing "骨笛".
    # Search should mention "骨笛" and current_scene should include the revealed object.
```

- [ ] **Step 2: Run RED**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_discovery_table_reveals_random_object_without_resolution_branch -q`

Expected: fails because resolution does not consult discovery tables.

- [ ] **Step 3: Implement discovery lookup**

Pass world state into scene/action result helpers and apply matching discovery entries by target id.

- [ ] **Step 4: Run GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_discovery_table_reveals_random_object_without_resolution_branch -q`

Expected: passes.

### Task 6: Offer-Based Economy Purchase

**Files:**
- Modify: `backend/src/services/isekai_economy.py`
- Modify: `backend/src/services/isekai_action_resolution.py`
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Consumes: `merchant_offers` from content pack/world state.
- Produces: purchase by `offer_id`, with existing `inn_bed` and `stew_meal` preserved.

- [ ] **Step 1: Write failing test**

```python
def test_purchase_random_offer_without_price_config_constant(store):
    # Add offer_id "dry_wax_rope" with price 4.
    # Player buys "干蜡绳"; copper decreases and inventory gains item.
```

- [ ] **Step 2: Run RED**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_purchase_random_offer_without_price_config_constant -q`

Expected: fails because only hardcoded price configs are supported.

- [ ] **Step 3: Implement offer purchase**

Add `IsekaiEconomyService.purchase_offer(state, offer, valid_until)` and let resolution use bound `offer_id` or name matching against current offers.

- [ ] **Step 4: Run GREEN**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_purchase_random_offer_without_price_config_constant -q`

Expected: passes.

### Task 7: Boundary Regression Scan

**Files:**
- Test: `test/backend/src/services/test_isekai_content_agnostic.py`

**Interfaces:**
- Produces: guard tests preventing new hardcoded random content names in generic services.

- [ ] **Step 1: Write scan test**

```python
def test_random_fixture_names_are_not_hardcoded_in_generic_services():
    forbidden = ["蓝盐水洼", "虫蚀皮袋", "骨笛", "干蜡绳"]
    paths = [...]
    for path in paths:
        text = Path(path).read_text()
        assert not any(term in text for term in forbidden)
```

- [ ] **Step 2: Run RED/GREEN as appropriate**

Run: `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py::test_random_fixture_names_are_not_hardcoded_in_generic_services -q`

Expected: passes once tests keep fixtures out of generic services.

### Final Verification

- [ ] Run `uv run pytest test/backend/src/services/test_isekai_content_agnostic.py -q`.
- [ ] Run `uv run pytest test/backend/src/services -q`.
- [ ] Run `git diff --check`.
- [ ] Restart the local service on port 5001 if it is running.
