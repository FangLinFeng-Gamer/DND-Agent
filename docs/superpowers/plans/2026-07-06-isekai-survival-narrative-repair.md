# Isekai Survival Narrative Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair isekai survival narration so the active model receives player-visible survival state, treats NPC dialogue as in-world action, and stays in an otherworldly survival frame.

**Architecture:** Keep deterministic survival/resource rules in backend services and strengthen the model-facing payload, prompt, event catalog, and post-generation guard. Do not change DND mode. P2 frontend debug panel is deliberately out of scope for this plan.

**Tech Stack:** Python services, SQLite-backed adventure state, pytest service tests.

---

### Task 1: Context-Aware Action Classification

**Files:**
- Modify: `backend/src/services/isekai_time.py`
- Modify: `backend/src/services/isekai.py`
- Test: `test/backend/src/services/test_isekai_time.py`

- [ ] **Step 1: Write failing tests**

Add tests that pass a scene/NPC context to `IsekaiTimeService.classify_action()`:

```python
def test_npc_identity_question_is_short_dialogue_when_scene_has_npcs():
    service = IsekaiTimeService()

    action = service.classify_action("你是什么种族的？", scene_context={"has_npcs": True})

    assert action.action_type == "short_dialogue"
    assert action.advances_time is True
    assert action.time_cost_minutes == 10
```

Also keep clear UI/system questions as `table_talk`.

- [ ] **Step 2: Run red test**

Run: `uv run pytest test/backend/src/services/test_isekai_time.py::test_npc_identity_question_is_short_dialogue_when_scene_has_npcs -q`

Expected: FAIL because `classify_action()` does not accept scene context and currently treats the input as table/system talk.

- [ ] **Step 3: Implement minimal classifier change**

Change `classify_action(content, scene_context=None)` to inspect `has_npcs`. If NPCs are present and input contains in-world address patterns such as `你是什么`, `你是谁`, `你这里`, `你们`, classify as `short_dialogue`. Keep explicit system/UI/rule questions as `table_talk`.

- [ ] **Step 4: Wire scene context**

In `IsekaiSurvivalService.prepare_turn()`, load the current scene before classification and pass whether the scene has NPCs or obvious NPC/object context into the classifier.

- [ ] **Step 5: Verify**

Run: `uv run pytest test/backend/src/services/test_isekai_time.py -q`

### Task 2: Player-Visible Survival State for LLM

**Files:**
- Modify: `backend/src/services/isekai.py`
- Test: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing tests**

Add a service test that sets raw `hunger=26`, `thirst=53`, `fatigue=21`, `sleep_need=4`, advances once with an active model, then asserts model payload contains:

```python
visible = payload["system_state"]["visible_survival"]
assert visible["satiety"] == 74
assert visible["hydration"] == 47
assert visible["energy"] == 79
assert visible["sleep_sufficiency"] == 96
assert "饱腹度较高" in visible["status_summary"]
```

- [ ] **Step 2: Run red test**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_model_payload_uses_player_visible_survival_terms -q`

Expected: FAIL because visible survival fields are not in the payload.

- [ ] **Step 3: Implement helper**

Add `visible_survival_state(survival)` on `IsekaiSurvivalService`. It translates raw pressure values into positive player-facing values and a threshold-based Chinese summary:

```python
satiety = 100 - hunger
hydration = 100 - thirst
energy = 100 - fatigue
sleep_sufficiency = 100 - sleep_need
```

- [ ] **Step 4: Add prompt rule**

Update the isekai system prompt so DM narrates using player-visible values, especially: satiety 70+ must not describe obvious hunger.

- [ ] **Step 5: Verify**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_model_payload_uses_player_visible_survival_terms -q`

### Task 3: Worldview Guard and Legacy Scene Repair

**Files:**
- Modify: `backend/src/services/isekai_worldview.py`
- Modify: `backend/src/services/isekai.py`
- Test: `test/backend/src/services/test_isekai_worldview.py`
- Test: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing tests**

Add tests for:
- legacy terms like `烤饼铺子/胖女人/小本生意` being rewritten into isekai conflict language.
- high satiety narration not keeping `肚子饿` or `明显饥饿`.
- low-signal ordinary trade narration receiving an appended isekai pressure signal.

- [ ] **Step 2: Run red tests**

Run: `uv run pytest test/backend/src/services/test_isekai_worldview.py test/backend/src/services/test_isekai_survival.py::test_isekai_narration_guard_adds_otherworld_signal -q`

Expected: FAIL because no guard/legacy repair exists yet.

- [ ] **Step 3: Implement deterministic guard**

Add worldview methods to normalize stronger legacy terms and repair narration using current scene, character, visible survival, and world event impacts. Prefer deterministic fixes over another LLM call.

- [ ] **Step 4: Apply guard**

Run guard after model/fallback narration and before message persistence, in both normal and streaming paths. Store useful guard result in metadata only if already available through turn data.

- [ ] **Step 5: Verify**

Run: `uv run pytest test/backend/src/services/test_isekai_worldview.py test/backend/src/services/test_isekai_survival.py -q`

### Task 4: Stronger Prompt and Event Pool

**Files:**
- Modify: `backend/src/services/isekai.py`
- Modify: `backend/src/services/isekai_event_catalog.py`
- Test: `test/backend/src/services/test_isekai_survival.py`
- Test: `test/backend/src/services/test_isekai_events.py`

- [ ] **Step 1: Write failing tests**

Add prompt assertions for `异界来客`, `文化隔阂`, `资源稀缺`, `每轮至少体现一个异世界信号`, and output hooks. Add event catalog test that available random settlement/regional events include alien tax, taboo, temple/lord/patrol/price/reputation pressure.

- [ ] **Step 2: Run red tests**

Run: `uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_prompt_requires_otherworld_survival_signals test/backend/src/services/test_isekai_events.py::test_event_catalog_contains_isekai_social_pressure_events -q`

Expected: FAIL because prompt and event pool are too thin.

- [ ] **Step 3: Implement prompt and catalog changes**

Extend the system prompt and `IsekaiEventCatalog.SEEDS` with concrete otherworld survival/social pressure events.

- [ ] **Step 4: Verify focused tests**

Run: `uv run pytest test/backend/src/services/test_isekai_time.py test/backend/src/services/test_isekai_worldview.py test/backend/src/services/test_isekai_events.py test/backend/src/services/test_isekai_survival.py -q`

### Task 5: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run full backend/frontend test suite**

Run: `uv run pytest -q`

- [ ] **Step 2: Optional local game/32 smoke test**

If service is running, inspect `/api/adventures/32` and send one NPC identity question to confirm latest metadata remains `mode: isekai_survival`, `source: active_model` when model is available, and action type is `short_dialogue`.
