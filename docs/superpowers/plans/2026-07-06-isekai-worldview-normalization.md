# Isekai Worldview Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep isekai generated narration, scene updates, events, and inventory-like text aligned with a DND-style fantasy world instead of modern or overly local everyday wording.

**Architecture:** Add a focused normalization service for isekai text. Isekai gameplay services keep their existing responsibilities and call the normalizer at boundaries where model/template text enters persistent state or player-visible output. The LLM prompt also receives compact style guidance so the model avoids these terms before post-processing is needed.

**Tech Stack:** FastAPI backend services, Pydantic scene models, pytest.

---

## File Structure

- Create `backend/src/services/isekai_worldview.py`
  - Own phrase-level fantasy wording guidance and deterministic normalization.
- Modify `backend/src/services/isekai.py`
  - Add prompt guidance.
  - Normalize model narration, fallback narration, scene updates, opening text, generated character inventory, and location history summaries.
- Modify `backend/src/services/isekai_events.py`
  - Normalize generated world event titles/descriptions/affected areas.
- Modify `test/backend/src/services/test_isekai_survival.py`
  - Add tests for prompt guidance and model output normalization.
- Modify `test/backend/src/services/test_isekai_events.py`
  - Add test for event text normalization.
- Add `test/backend/src/services/test_isekai_worldview.py`
  - Unit-test the deterministic normalizer.

## Task 1: Normalizer Unit

- [ ] **Step 1: Write failing tests**

Add `test/backend/src/services/test_isekai_worldview.py`:

```python
from backend.src.services.isekai_worldview import IsekaiWorldviewNormalizer


def test_normalizes_out_of_setting_food_shop_terms():
    normalizer = IsekaiWorldviewNormalizer()

    text = normalizer.normalize_text("镇上新开了一家烤饼铺子，老板还卖早餐套餐。")

    assert "烤饼铺子" not in text
    assert "早餐套餐" not in text
    assert "炉饼摊" in text
    assert "晨食" in text


def test_normalizes_nested_scene_payload():
    normalizer = IsekaiWorldviewNormalizer()
    payload = {
        "location": "商业街",
        "environment": "街边有烤饼铺子和便利店。",
        "important_objects": ["广告牌", "热销菜单"],
    }

    result = normalizer.normalize_scene_update(payload)

    assert result["location"] == "集市街"
    assert result["environment"] == "街边有炉饼摊和杂货铺。"
    assert result["important_objects"] == ["告示牌", "招牌菜单"]
```

- [ ] **Step 2: Run the unit test and verify it fails**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_worldview.py -q
```

Expected: FAIL because `backend.src.services.isekai_worldview` does not exist.

- [ ] **Step 3: Implement the normalizer**

Create `backend/src/services/isekai_worldview.py` with:

```python
from __future__ import annotations

from typing import Any


class IsekaiWorldviewNormalizer:
    STYLE_GUIDANCE = (
        "世界观风格：故事发生在 DND 风格奇幻世界。避免现代商业、现代科技、中文街边店铺感过强的表达；"
        "需要食物或店铺时，优先使用面包房、炉饼摊、馅饼铺、旅店厨房、集市摊贩、杂货铺、铁匠铺、药草铺等奇幻城镇表达。"
    )

    REPLACEMENTS = (
        ("烤饼铺子", "炉饼摊"),
        ("烧饼铺", "炉饼摊"),
        ("早餐套餐", "晨食"),
        ("便利店", "杂货铺"),
        ("商业街", "集市街"),
        ("广告牌", "告示牌"),
        ("热销菜单", "招牌菜单"),
    )

    def normalize_text(self, value: Any) -> str:
        text = str(value or "")
        for source, target in self.REPLACEMENTS:
            text = text.replace(source, target)
        return text

    def normalize_list(self, values: Any, limit: int | None = None) -> list[str]:
        if not isinstance(values, list):
            return []
        result = [self.normalize_text(item).strip() for item in values if self.normalize_text(item).strip()]
        return result[:limit] if limit else result

    def normalize_scene_update(self, scene_update: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(scene_update, dict):
            return {}
        result: dict[str, Any] = {}
        for key in ("location", "environment", "current_objective"):
            if key in scene_update:
                value = self.normalize_text(scene_update.get(key)).strip()
                if value:
                    result[key] = value
        objects = self.normalize_list(scene_update.get("important_objects"), limit=8)
        if objects:
            result["important_objects"] = objects
        return result
```

- [ ] **Step 4: Run the unit test and verify it passes**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_worldview.py -q
```

Expected: PASS.

## Task 2: Isekai Narration And Scene Boundary

- [ ] **Step 1: Write failing service tests**

Add to `test/backend/src/services/test_isekai_survival.py`:

```python
class OutOfSettingIsekaiLLMClient:
    def chat(self, model, messages):
        return json.dumps(
            {
                "narration": "你来到商业街，看见一家烤饼铺子正在卖早餐套餐。",
                "scene_update": {
                    "location": "商业街",
                    "environment": "烤饼铺子旁边有便利店。",
                    "important_objects": ["广告牌", "热销菜单"],
                    "current_objective": "询问烤饼铺子老板。",
                },
            },
            ensure_ascii=False,
        )
```

Then add:

```python
def test_isekai_model_output_is_normalized_to_fantasy_world_terms(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(store, llm_client=OutOfSettingIsekaiLLMClient())
    adventure = service.create_adventure(AdventureCreate(title="Worldview Road", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我去镇上找食物。", locale="zh-CN"))

    assert "烤饼铺子" not in response.dm_message.content
    assert "早餐套餐" not in response.dm_message.content
    assert "炉饼摊" in response.dm_message.content
    assert response.adventure.current_scene.location == "集市街"
    assert response.adventure.current_scene.environment == "炉饼摊旁边有杂货铺。"
    assert response.adventure.current_scene.important_objects == ["告示牌", "招牌菜单"]
```

And:

```python
def test_isekai_prompt_includes_worldview_style_guidance(store):
    activate_test_model(store)
    llm_client = FakeIsekaiLLMClient()
    service = IsekaiSurvivalService(store, llm_client=llm_client)
    adventure = service.create_adventure(AdventureCreate(title="Prompt Road", mode="isekai_survival"))

    service.advance(adventure.id, MessageCreate(content="我寻找食物。", locale="zh-CN"))

    system_prompt = llm_client.chat_calls[-1]["messages"][0]["content"]
    assert "DND 风格奇幻世界" in system_prompt
    assert "烤饼铺子" not in system_prompt
    assert "炉饼摊" in system_prompt
```

- [ ] **Step 2: Run the new service tests and verify they fail**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_model_output_is_normalized_to_fantasy_world_terms test/backend/src/services/test_isekai_survival.py::test_isekai_prompt_includes_worldview_style_guidance -q
```

Expected: FAIL because `IsekaiSurvivalService` does not use the normalizer yet.

- [ ] **Step 3: Wire the normalizer into `IsekaiSurvivalService`**

In `backend/src/services/isekai.py`:

- Import `IsekaiWorldviewNormalizer`.
- Add `self.worldview = IsekaiWorldviewNormalizer()` in `__init__`.
- Normalize generated character inventory.
- Normalize opening text and fallback narration before returning.
- Include `self.worldview.STYLE_GUIDANCE` in the system prompt.
- Normalize `parse_model_payload()` narration and `scene_update`.
- Normalize `clean_scene_update()` values after trimming.
- Normalize location history summaries.

- [ ] **Step 4: Run the service tests and verify they pass**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_model_output_is_normalized_to_fantasy_world_terms test/backend/src/services/test_isekai_survival.py::test_isekai_prompt_includes_worldview_style_guidance -q
```

Expected: PASS.

## Task 3: World Event Boundary

- [ ] **Step 1: Write failing event test**

Add to `test/backend/src/services/test_isekai_events.py`:

```python
def test_world_event_text_is_normalized_to_fantasy_world_terms(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    scene = adventure.current_scene.model_copy(update={"location": "商业街", "environment": "镇上的商业街挤满商人。"})
    turn = {
        "player_input": "我在烤饼铺子做早餐套餐。",
        "action_type": "talk",
        "time": {"advances_time": True, "time_cost_minutes": 30},
        "scene": scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(adventure.id, turn, {"turn_count": 1, "player_preferences": {}})

    assert events
    event = events[0]
    assert event.metadata["affected_area"] == "集市街"
    assert "烤饼铺子" not in event.metadata["triggering_action"]
    assert "早餐套餐" not in event.metadata["triggering_action"]
    assert "炉饼摊" in event.metadata["triggering_action"]
```

- [ ] **Step 2: Run the event test and verify it fails**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_events.py::test_world_event_text_is_normalized_to_fantasy_world_terms -q
```

Expected: FAIL because event metadata is not normalized.

- [ ] **Step 3: Wire the normalizer into `IsekaiWorldEventDirector`**

In `backend/src/services/isekai_events.py`:

- Import `IsekaiWorldviewNormalizer`.
- Add `self.worldview = IsekaiWorldviewNormalizer()` in `__init__`.
- Normalize candidate title, description, affected area, preference tags, and triggering action in `_to_create()`.
- Normalize `_location()` result.

- [ ] **Step 4: Run the event test and verify it passes**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_events.py::test_world_event_text_is_normalized_to_fantasy_world_terms -q
```

Expected: PASS.

## Task 4: Verification

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_worldview.py test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_events.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

- [ ] **Step 3: Commit**

Run:

```bash
git add backend/src/services/isekai_worldview.py backend/src/services/isekai.py backend/src/services/isekai_events.py test/backend/src/services/test_isekai_worldview.py test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_events.py docs/superpowers/plans/2026-07-06-isekai-worldview-normalization.md
git commit -m "Normalize isekai fantasy world terminology"
```
