from pathlib import Path

from backend.src.agent.character_creation.messages import (
    CharacterCreationMessageRepository,
)
from backend.src.agent.character_creation.models import StateGraphResult
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.character_creation.supervisor import CharacterCreationReActAgent
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character_creation import CharacterDraft
from backend.src.schemas.character_creation import CharacterCreationSessionOut
from backend.src.schemas.character_creation import CharacterDraftMutation
from backend.src.services.character_creation_guide import CharacterCreationGuideService
from backend.src.services.character_drafts import CharacterDraftService


def test_character_creation_guide_exposes_current_step_options(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")
    session = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="identity",
            payload={"name": "米拉"},
            locale="zh-CN",
        ),
    )

    guide = service.guide(session.id, "zh-CN")

    assert guide.active_step == "class"
    assert any(option.id == "class.wizard" for option in guide.options)
    wizard = next(option for option in guide.options if option.id == "class.wizard")
    assert wizard.title == "法师"
    assert "d6" in wizard.badges
    assert any(step.id == "spells" for step in guide.steps)


def test_spellcasting_class_reaches_spells_after_abilities(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")
    for operation, payload in [
        ("identity", {"name": "米拉"}),
        ("class", {"class_id": "class.wizard"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.sage"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 8,
                    "dexterity": 14,
                    "constitution": 14,
                    "intelligence": 15,
                    "wisdom": 10,
                    "charisma": 10,
                }
            },
        ),
        (
            "proficiencies",
            {
                "choice_values": {
                    "human-language": ["language.dwarvish"],
                    "wizard-skills": ["skill.investigation", "skill.medicine"],
                    "sage-languages": ["language.draconic", "language.elvish"],
                }
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="zh-CN",
            ),
        )

    guide = service.guide(session.id, "zh-CN")

    assert guide.active_step == "spells"
    assert "spells" not in session.draft.completed_steps
    assert guide.requirements["cantrips"] == 3
    assert guide.requirements["level_one"] == 6
    assert any(option.id.startswith("spell.") for option in guide.options)


def test_level_one_paladin_can_confirm_without_stale_spell_step(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("en")
    for operation, payload in [
        ("identity", {"name": "Dale"}),
        ("class", {"class_id": "class.paladin"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.noble"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 8,
                    "dexterity": 8,
                    "constitution": 8,
                    "intelligence": 8,
                    "wisdom": 8,
                    "charisma": 8,
                }
            },
        ),
        (
            "proficiencies",
            {
                "choice_values": {
                    "human-language": ["language.celestial"],
                    "paladin-skills": ["skill.insight", "skill.athletics"],
                    "noble-gaming-set": ["tool.gaming.dice"],
                    "noble-language": ["language.dwarvish"],
                }
            },
        ),
        (
            "equipment",
            {
                "option_ids": [
                    "paladin-weapons-shield",
                    "paladin-secondary-javelins",
                    "paladin-pack-priest",
                ],
                "item_choices": {
                    "paladin-primary-martial-weapon": ["equipment.longsword"],
                },
            },
        ),
        (
            "adventure_connection",
            {
                "motivation": "Protect the innocent.",
                "quest_hook": "Called to the opening adventure.",
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="en",
            ),
        )

    guide = service.guide(session.id, "en")
    confirmed = service.handle_message(session.id, "confirm", "en")

    assert guide.active_step == "review"
    assert "spells" not in session.draft.invalid_steps
    assert confirmed.validation_errors == []
    assert confirmed.created_character is not None


def test_character_creation_guide_can_display_completed_step_for_editing(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")
    for operation, payload in [
        ("identity", {"name": "米拉"}),
        ("class", {"class_id": "class.wizard"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.sage"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 8,
                    "dexterity": 14,
                    "constitution": 14,
                    "intelligence": 15,
                    "wisdom": 10,
                    "charisma": 10,
                }
            },
        ),
        (
            "proficiencies",
            {
                "choice_values": {
                    "human-language": ["language.dwarvish"],
                    "wizard-skills": ["skill.investigation", "skill.medicine"],
                    "sage-languages": ["language.draconic", "language.elvish"],
                }
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="zh-CN",
            ),
        )

    guide = service.guide(session.id, "zh-CN", step="class")

    assert guide.actual_step == "spells"
    assert guide.active_step == "class"
    assert "class" in guide.editable_steps
    assert "identity" in guide.editable_steps
    assert "abilities" in guide.editable_steps
    assert any(option.id == "class.fighter" for option in guide.options)


def test_character_creation_review_summary_uses_requested_locale_names():
    repository = PHBRuleRepository.load_builtin()
    draft = CharacterDraft(
        name="Dale",
        race="Human",
        class_name="Fighter",
        background="Noble",
        completed_steps=[
            "identity",
            "class",
            "race",
            "background",
            "abilities",
            "proficiencies",
            "class_features",
            "optional_rules",
            "spells",
            "equipment",
            "adventure_connection",
        ],
        inventory=[
            {"item_id": "equipment.longsword", "quantity": 1},
            {"item_id": "equipment.dagger", "quantity": 2},
        ],
        adventure_connection={"motivation": "Protect the innocent."},
    )
    draft.selections.race_id = "race.human"
    draft.selections.class_id = "class.fighter"
    draft.selections.background_id = "background.noble"
    draft.selections.class_option_ids = ["class_option.fighter.defense"]
    draft.selections.choice_values = {
        "fighter-style": ["class_option.fighter.defense"],
    }
    session = CharacterCreationSessionOut(
        id=99,
        locale="zh-CN",
        status="draft",
        revision=0,
        draft=draft,
        assistant_message="",
    )

    guide = CharacterCreationGuideService(repository).build(session, "zh-CN")
    summary = guide.requirements["summary"]

    assert guide.active_step == "review"
    assert summary["race"] == repository.get("race.human").name.for_locale("zh-CN")
    assert summary["class_name"] == repository.get("class.fighter").name.for_locale("zh-CN")
    assert summary["background"] == repository.get("background.noble").name.for_locale("zh-CN")
    assert summary["inventory"][0]["item_id"] == "equipment.longsword"
    assert summary["inventory"][0]["title"] == repository.get("equipment.longsword").name.for_locale("zh-CN")
    assert summary["inventory"][1]["quantity"] == 2
    assert summary["inventory"][1]["title"] == repository.get("equipment.dagger").name.for_locale("zh-CN")


def test_language_choices_disable_languages_already_granted_by_race():
    repository = PHBRuleRepository.load_builtin()
    draft = CharacterDraft(
        name="Lethariel",
        race="Elf",
        class_name="Fighter",
        background="Acolyte",
        current_step="proficiencies",
        completed_steps=[
            "identity",
            "class",
            "race",
            "background",
            "abilities",
        ],
    )
    draft.selections.race_id = "race.elf"
    draft.selections.class_id = "class.fighter"
    draft.selections.background_id = "background.acolyte"
    session = CharacterCreationSessionOut(
        id=77,
        locale="en",
        status="draft",
        revision=0,
        draft=draft,
        assistant_message="",
    )

    guide = CharacterCreationGuideService(repository).build(session, "en")
    acolyte_languages = next(
        group
        for group in guide.requirements["choice_groups"]
        if group["id"] == "acolyte-languages"
    )
    disabled = {
        option["id"]
        for option in acolyte_languages["options"]
        if option.get("disabled")
    }

    assert "language.elvish" in disabled


def test_attribute_point_buy_failure_is_synced_to_chat_history(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")
    for operation, payload in [
        ("identity", {"name": "米拉"}),
        ("class", {"class_id": "class.wizard"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.sage"}),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="zh-CN",
            ),
        )

    failed = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="abilities",
            payload={
                "base": {
                    "strength": 15,
                    "dexterity": 15,
                    "constitution": 15,
                    "intelligence": 15,
                    "wisdom": 15,
                    "charisma": 15,
                }
            },
            locale="zh-CN",
        ),
    )
    messages = CharacterCreationMessageRepository(service.store).list_recent(
        session.id,
        limit=10,
    )

    assert failed.validation_errors
    assert "超过可用的 27 点" in failed.assistant_message
    assert any(
        message.role == "assistant" and "超过可用的 27 点" in message.content
        for message in messages
    )


def test_switching_from_spellcaster_to_barbarian_does_not_loop_on_abilities(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")
    for operation, payload in [
        ("identity", {"name": "米拉"}),
        ("class", {"class_id": "class.wizard"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.sage"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 14,
                    "dexterity": 11,
                    "constitution": 11,
                    "intelligence": 14,
                    "wisdom": 12,
                    "charisma": 11,
                }
            },
        ),
        ("spells", {"spell_ids": ["spell.fire-bolt"]}),
        ("class", {"class_id": "class.barbarian"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 14,
                    "dexterity": 11,
                    "constitution": 11,
                    "intelligence": 14,
                    "wisdom": 12,
                    "charisma": 11,
                }
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="zh-CN",
            ),
        )

    guide = service.guide(session.id, "zh-CN")

    assert session.draft.class_name == "Barbarian"
    assert session.draft.selections.spell_ids == []
    assert "abilities" in session.draft.completed_steps
    assert "abilities" not in session.draft.invalid_steps
    assert guide.active_step == "proficiencies"
    assert "下一步：属性" not in session.assistant_message


def test_committed_character_response_uses_authoritative_template(tmp_path: Path):
    agent = CharacterCreationReActAgent(_store(tmp_path))
    draft = CharacterDraft(
        revision=1,
        current_step="completed",
        name="米拉",
        race="Human",
        class_name="Barbarian",
        background="Sage",
    )
    result = StateGraphResult(
        success=True,
        draft_revision=1,
        current_step="completed",
        next_step="completed",
        committed=True,
        created_character_id=1,
        draft=draft,
    )
    fallback = agent._template_response(result, "zh-CN")

    text, guard = agent._guard_response(
        "角色创建成功！法术：火焰箭",
        fallback,
        result,
        "zh-CN",
    )

    assert guard == "committed_template"
    assert text == "角色已创建：米拉, 人类 野蛮人, 背景 智者。"
    assert "火焰箭" not in text


def test_explicit_confirmation_bypasses_model(tmp_path: Path):
    class ModelThatShouldNotBeUsed:
        name = "should-not-be-called"

    agent = CharacterCreationReActAgent(
        _store(tmp_path),
        model=ModelThatShouldNotBeUsed(),
    )
    draft = CharacterDraft(
        current_step="review",
        name="米拉",
        race="Human",
        class_name="Barbarian",
        background="Sage",
        completed_steps=[
            "identity",
            "class",
            "race",
            "background",
            "abilities",
            "proficiencies",
            "class_features",
            "optional_rules",
            "spells",
            "equipment",
            "adventure_connection",
        ],
    )
    draft.selections.class_id = "class.barbarian"
    draft.selections.race_id = "race.human"
    draft.selections.background_id = "background.sage"
    draft.inventory = [{"item_id": "equipment.greataxe", "quantity": 1}]
    draft.adventure_connection = {"motivation": "Seek glory."}

    result = agent.process(
        session_id=1,
        draft=draft,
        content="确认创建",
        locale="zh-CN",
    )

    assert result.created_character is not None
    assert result.validation_errors == []
    assert result.diagnostics["agent_kind"] == "deterministic_confirmation"
    assert result.diagnostics["model_name"] == "should-not-be-called"


def test_structured_mutation_records_success_in_chat_history(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")
    session = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="identity",
            payload={"name": "米拉"},
            locale="zh-CN",
        ),
    )

    updated = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="class",
            payload={"class_id": "class.wizard"},
            locale="zh-CN",
        ),
    )
    messages = CharacterCreationMessageRepository(service.store).list_recent(
        session.id,
        limit=10,
    )

    assert updated.draft.class_name == "Wizard"
    assert "已记录" in updated.assistant_message
    assert any(message.role == "user" and "界面选择" in message.content for message in messages)
    assert any(message.role == "assistant" and "已记录" in message.content for message in messages)


def test_structured_mutation_records_validation_failure_in_chat_history(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")
    for operation, payload in [
        ("identity", {"name": "米拉"}),
        ("race", {"race_id": "race.human"}),
        ("class", {"class_id": "class.wizard"}),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="zh-CN",
            ),
        )
    before_revision = session.revision

    failed = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="abilities",
            payload={
                "base": {
                    "strength": 20,
                    "dexterity": 8,
                    "constitution": 8,
                    "intelligence": 8,
                    "wisdom": 8,
                    "charisma": 8,
                }
            },
            locale="zh-CN",
        ),
    )
    messages = CharacterCreationMessageRepository(service.store).list_recent(
        session.id,
        limit=10,
    )

    assert failed.revision == before_revision
    assert failed.validation_errors
    assert "未通过规则校验" in failed.assistant_message
    assert failed.draft.abilities.base["strength"] == 8
    assert any(message.role == "user" and "界面尝试" in message.content for message in messages)
    assert any(message.role == "assistant" and "未通过规则校验" in message.content for message in messages)


def _service(tmp_path: Path) -> CharacterDraftService:
    return CharacterDraftService(_store(tmp_path))


def _store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "test.sqlite")
    store.init_schema()
    return store
