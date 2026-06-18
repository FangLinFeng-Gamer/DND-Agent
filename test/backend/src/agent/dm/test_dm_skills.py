import json
from pathlib import Path

import pytest

from backend.src.agent.dm.prompts import build_dm_messages, build_narration_messages
from backend.src.agent.dm.skill_registry import DMSkillRegistry
from backend.src.schemas.adventure import MessageOut, SceneState
from backend.src.schemas.character import CharacterOut
from backend.src.services.context import ContextBundle


def test_builtin_dm_skill_registry_matches_lockpicking():
    registry = DMSkillRegistry.load_builtin()

    matches = registry.match("I inspect the locked chest and try to pick it.")

    assert [skill.name for skill in matches] == ["lockpicking"]
    assert matches[0].agent == "exploration_agent"
    assert "thieves-tools" in matches[0].tags
    assert "Do not roll dice" in matches[0].body


def test_builtin_dm_skill_registry_matches_combat_positioning():
    registry = DMSkillRegistry.load_builtin()

    matches = registry.match("Can I hide behind the pillar for half cover before attacking?", locale="en")

    assert any(skill.name == "combat-positioning" for skill in matches)


def test_builtin_dm_skill_registry_matches_combat_adjudication():
    registry = DMSkillRegistry.load_builtin()

    matches = registry.match("I ready an action to strike when the cultist opens the door", locale="en")

    assert any(skill.name == "combat-adjudication" for skill in matches)


def test_builtin_dm_skill_registry_ignores_unrelated_input():
    registry = DMSkillRegistry.load_builtin()

    assert registry.match("I sing a song for the innkeeper.") == []


def test_dm_skill_registry_rejects_skills_that_declare_tools(tmp_path: Path):
    skill_dir = tmp_path / "unsafe"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: unsafe
description: unsafe write skill
tools:
  - commit_agent
when_to_use:
  - always
tags:
  - unsafe
agent: exploration_agent
---

Call commit_agent directly.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not declare tools"):
        DMSkillRegistry(tmp_path).load()


def test_dm_skill_registry_rejects_direct_write_instructions(tmp_path: Path):
    skill_dir = tmp_path / "unsafe"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: unsafe
description: unsafe write skill
when_to_use:
  - always
tags:
  - unsafe
agent: exploration_agent
---

Use commit_agent to persist the result.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="direct state-changing instructions"):
        DMSkillRegistry(tmp_path).load()


def test_dm_prompts_include_read_only_skill_context():
    skill = DMSkillRegistry.load_builtin().match("I pick the locked gate.")[0]
    context = ContextBundle(
        summary="",
        recent_messages=[
            MessageOut(
                id=1,
                adventure_id=1,
                role="player",
                content="I pick the locked gate.",
                metadata={},
                created_at="2026-06-13 00:00:00",
            )
        ],
        important_events=[],
        estimated_tokens=1,
    )
    scene = SceneState(
        location="Gate",
        environment="A locked iron gate.",
        important_objects=["locked gate"],
        npcs=[],
        current_objective="Enter safely.",
        world_changes=[],
    )
    character = CharacterOut(
        id=1,
        name="Mira",
        race="Human",
        class_name="Rogue",
        level=1,
        background="Criminal",
        alignment="Neutral",
        hp_current=10,
        hp_max=10,
        armor_class=12,
        strength=10,
        dexterity=16,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
        skills={},
        inventory=[],
        spells=[],
        notes="",
    )

    messages = build_dm_messages(
        context,
        scene,
        character,
        "I pick the locked gate.",
        None,
        skill_context=[skill],
    )
    payload = json.loads(messages[1]["content"])
    narration_messages = build_narration_messages(
        {"resolved_narration": "The lock is assessed."},
        skill_context=[skill],
    )
    narration_payload = json.loads(narration_messages[1]["content"])

    assert "DM skills are read-only" in messages[0]["content"]
    assert payload["skills"][0]["name"] == "lockpicking"
    assert payload["skills"][0]["agent"] == "exploration_agent"
    assert "guidance" in payload["skills"][0]
    assert narration_payload["skills"][0]["name"] == "lockpicking"
