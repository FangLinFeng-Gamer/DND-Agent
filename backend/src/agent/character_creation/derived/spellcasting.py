from __future__ import annotations

from dataclasses import dataclass

from backend.src.agent.character_creation.rules.models import PHBRuleRecord
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft


@dataclass(frozen=True)
class SpellChoiceRequirement:
    id: str
    source_id: str
    source_name: str
    category: str
    level: int
    classes: tuple[str, ...]
    count: int
    ritual: bool = False
    attack: bool = False

    def matches(self, spell: PHBRuleRecord) -> bool:
        if spell.rule_type != "spell":
            return False
        if int(spell.metadata.get("level", -1)) != self.level:
            return False
        spell_classes = set(spell.metadata.get("classes", []))
        if self.classes and not spell_classes.intersection(self.classes):
            return False
        if self.ritual and not spell.metadata.get("ritual"):
            return False
        if self.attack and not spell.metadata.get("attack"):
            return False
        return True

    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "category": self.category,
            "level": self.level,
            "classes": list(self.classes),
            "count": self.count,
            "ritual": self.ritual,
            "attack": self.attack,
        }


def spell_selection_requirements(
    draft: CharacterDraft,
    repository: PHBRuleRepository,
) -> list[SpellChoiceRequirement]:
    requirements: list[SpellChoiceRequirement] = []
    class_rule = _selected_class_rule(draft, repository)
    if class_rule:
        profile = class_rule.metadata.get("spell_selection")
        class_name = class_rule.id.removeprefix("class.")
        if profile:
            cantrips = int(profile.get("cantrips", 0))
            if cantrips:
                requirements.append(
                    SpellChoiceRequirement(
                        id=f"{class_rule.id}.cantrips",
                        source_id=class_rule.id,
                        source_name=class_rule.name.en,
                        category="cantrip",
                        level=0,
                        classes=(class_name,),
                        count=cantrips,
                    )
                )
            mode = str(profile.get("mode") or "")
            if mode == "known":
                count = int(profile.get("level_one", 0))
                category = "known"
            elif mode == "spellbook":
                count = int(profile.get("spellbook_level_one", 0))
                category = "spellbook"
            elif mode == "prepared":
                count = _prepared_spell_limit(draft, class_rule)
                category = "prepared"
            else:
                count = 0
                category = "level_one"
            if count:
                requirements.append(
                    SpellChoiceRequirement(
                        id=f"{class_rule.id}.{category}.level-one",
                        source_id=class_rule.id,
                        source_name=class_rule.name.en,
                        category=category,
                        level=1,
                        classes=(class_name,),
                        count=count,
                    )
                )

    for rule in _selected_rules(draft, repository):
        for grant in rule.grants:
            if grant.kind != "cantrip_choice":
                continue
            parsed = _parse_spell_choice_target(grant.target)
            if parsed is None:
                continue
            classes, level = parsed
            requirements.append(
                SpellChoiceRequirement(
                    id=f"{grant.source or rule.id}.{grant.kind}.{grant.target}",
                    source_id=grant.source or rule.id,
                    source_name=rule.name.en,
                    category="cantrip",
                    level=level,
                    classes=classes,
                    count=int(grant.value or 1),
                )
            )
        requirements.extend(_feat_spell_requirements(rule, draft))

    return [requirement for requirement in requirements if requirement.count > 0]


def can_add_spell_selection(
    draft: CharacterDraft,
    spell_id: str,
    repository: PHBRuleRepository,
) -> bool:
    if spell_id in draft.selections.spell_ids:
        return True
    try:
        validate_spell_selection(
            draft,
            [*draft.selections.spell_ids, spell_id],
            repository,
            partial=True,
        )
    except (LookupError, ValueError):
        return False
    return True


def valid_partial_spell_ids(
    draft: CharacterDraft,
    repository: PHBRuleRepository,
) -> list[str]:
    kept: list[str] = []
    for spell_id in draft.selections.spell_ids:
        if spell_id in kept:
            continue
        try:
            validate_spell_selection(
                draft,
                [*kept, spell_id],
                repository,
                partial=True,
            )
        except (LookupError, ValueError):
            continue
        kept.append(spell_id)
    return kept


def validate_spell_selection(
    draft: CharacterDraft,
    spell_ids: list[str],
    repository: PHBRuleRepository,
    *,
    partial: bool = False,
) -> None:
    requirements = spell_selection_requirements(draft, repository)
    if not requirements:
        if spell_ids:
            raise ValueError(
                "This character does not currently have any spell-choice requirements."
            )
        return
    if len(spell_ids) != len(set(spell_ids)):
        raise ValueError("Spell selections cannot contain duplicates.")

    spells = [repository.get(spell_id) for spell_id in spell_ids]
    if not _can_assign_spells_to_requirements(spells, requirements):
        raise ValueError(
            "Spell selections do not satisfy current spell-choice requirements: "
            f"{_format_requirement_summary(requirements)}."
        )
    if partial:
        return
    required_count = sum(requirement.count for requirement in requirements)
    if len(spells) != required_count:
        raise ValueError(
            "Spell selections must satisfy current spell-choice requirements: "
            f"{_format_requirement_summary(requirements)}."
        )


def calculate_spellcasting(
    draft: CharacterDraft,
    spell_ids: list[str],
    repository: PHBRuleRepository,
) -> dict:
    if not spell_ids:
        return {}
    validate_spell_selection(draft, spell_ids, repository)

    spells = [repository.get(spell_id) for spell_id in spell_ids]
    class_rule = _selected_class_rule(draft, repository)
    profile = class_rule.metadata.get("spell_selection") if class_rule else None
    result = {
        "cantrips": [
            spell.id for spell in spells if spell.metadata["level"] == 0
        ],
    }
    if profile and class_rule:
        ability = class_rule.metadata["spellcasting_ability"]
        modifier = draft.abilities.modifiers[ability]
        result.update(
            {
                "ability": ability,
                "save_dc": 8 + draft.derived.proficiency_bonus + modifier,
                "attack_bonus": draft.derived.proficiency_bonus + modifier,
                "slots": {1: profile["slots"]},
            }
        )
    level_one = [spell.id for spell in spells if spell.metadata["level"] == 1]
    if profile:
        if profile["mode"] == "spellbook":
            result["spellbook"] = level_one
        elif profile["mode"] == "known":
            result["known"] = level_one
        else:
            result["prepared"] = level_one
        formula = profile.get("prepared_formula")
        if formula:
            result["prepared_limit"] = _prepared_spell_limit(draft, class_rule)
    elif level_one:
        result["known"] = level_one
    return result


def _prepared_spell_limit(
    draft: CharacterDraft,
    class_rule: PHBRuleRecord,
) -> int:
    ability = str(class_rule.metadata.get("spellcasting_ability") or "")
    return max(1, int(draft.abilities.modifiers.get(ability, -1)) + 1)


def _selected_rules(
    draft: CharacterDraft,
    repository: PHBRuleRepository,
) -> list[PHBRuleRecord]:
    rule_ids: list[str] = []
    race_id = draft.selections.race_id
    subrace_id = draft.selections.subrace_id
    if not race_id and draft.race:
        race = _find_rule_by_name(draft.race, {"race", "subrace"}, repository)
        if race:
            if race.rule_type == "subrace":
                race_id = race.parent_id
                subrace_id = race.id
            else:
                race_id = race.id
    for rule_id in (
        race_id,
        subrace_id,
        draft.selections.class_id,
        *draft.selections.class_option_ids,
        *draft.selections.feat_ids,
    ):
        if rule_id and rule_id not in rule_ids:
            rule_ids.append(rule_id)
    return [repository.get(rule_id) for rule_id in rule_ids]


def _selected_class_rule(
    draft: CharacterDraft,
    repository: PHBRuleRepository,
) -> PHBRuleRecord | None:
    if draft.selections.class_id:
        return repository.get(draft.selections.class_id)
    if not draft.class_name:
        return None
    return _find_rule_by_name(draft.class_name, {"class"}, repository)


def _find_rule_by_name(
    value: str,
    rule_types: set[str],
    repository: PHBRuleRepository,
) -> PHBRuleRecord | None:
    normalized = value.strip().casefold()
    for record in repository.list():
        if record.rule_type not in rule_types:
            continue
        if normalized in {
            record.id.casefold(),
            record.name.en.casefold(),
            record.name.zh_cn.casefold(),
        }:
            return record
    return None


def _parse_spell_choice_target(target: str) -> tuple[tuple[str, ...], int] | None:
    parts = target.split(".")
    if len(parts) < 3 or parts[0] != "spell":
        return None
    class_name = parts[1]
    selector = parts[2]
    if selector == "cantrip":
        return (class_name,), 0
    if selector in {"level-one", "level_one", "1"}:
        return (class_name,), 1
    if selector.startswith("level-"):
        try:
            return (class_name,), int(selector.removeprefix("level-"))
        except ValueError:
            return None
    return None


def _feat_spell_requirements(
    rule: PHBRuleRecord,
    draft: CharacterDraft,
) -> list[SpellChoiceRequirement]:
    if rule.rule_type != "feat":
        return []
    class_name = _selected_feat_spell_class(rule, draft)
    if not class_name:
        return []
    effects = set(rule.metadata.get("effects", []))
    requirements: list[SpellChoiceRequirement] = []
    if {"two-cantrips", "one-first-level-spell-per-long-rest"}.issubset(effects):
        requirements.append(
            SpellChoiceRequirement(
                id=f"{rule.id}.cantrips",
                source_id=rule.id,
                source_name=rule.name.en,
                category="cantrip",
                level=0,
                classes=(class_name,),
                count=2,
            )
        )
        requirements.append(
            SpellChoiceRequirement(
                id=f"{rule.id}.level-one",
                source_id=rule.id,
                source_name=rule.name.en,
                category="known",
                level=1,
                classes=(class_name,),
                count=1,
            )
        )
    if {"ritual-book", "two-first-level-rituals"}.issubset(effects):
        requirements.append(
            SpellChoiceRequirement(
                id=f"{rule.id}.rituals",
                source_id=rule.id,
                source_name=rule.name.en,
                category="ritual",
                level=1,
                classes=(class_name,),
                count=2,
                ritual=True,
            )
        )
    if "attack-cantrip" in effects:
        requirements.append(
            SpellChoiceRequirement(
                id=f"{rule.id}.attack-cantrip",
                source_id=rule.id,
                source_name=rule.name.en,
                category="attack_cantrip",
                level=0,
                classes=(class_name,),
                count=1,
                attack=True,
            )
        )
    return requirements


def _selected_feat_spell_class(
    rule: PHBRuleRecord,
    draft: CharacterDraft,
) -> str | None:
    for choice in rule.choices:
        for value in draft.selections.choice_values.get(choice.id, []):
            if value.startswith("feat_option.class."):
                return value.removeprefix("feat_option.class.")
    return None


def _can_assign_spells_to_requirements(
    spells: list[PHBRuleRecord],
    requirements: list[SpellChoiceRequirement],
) -> bool:
    slots = [
        requirement
        for requirement in requirements
        for _ in range(requirement.count)
    ]
    if len(spells) > len(slots):
        return False
    assigned_spell_by_slot = [-1 for _ in slots]
    adjacency = [
        [index for index, requirement in enumerate(slots) if requirement.matches(spell)]
        for spell in spells
    ]
    if any(not matches for matches in adjacency):
        return False

    def assign(spell_index: int, seen: set[int]) -> bool:
        for slot_index in adjacency[spell_index]:
            if slot_index in seen:
                continue
            seen.add(slot_index)
            previous_spell = assigned_spell_by_slot[slot_index]
            if previous_spell == -1 or assign(previous_spell, seen):
                assigned_spell_by_slot[slot_index] = spell_index
                return True
        return False

    matched = 0
    for spell_index in sorted(range(len(spells)), key=lambda index: len(adjacency[index])):
        if assign(spell_index, set()):
            matched += 1
    return matched == len(spells)


def _format_requirement_summary(
    requirements: list[SpellChoiceRequirement],
) -> str:
    parts = []
    for requirement in requirements:
        filters = ", ".join(requirement.classes)
        label = "cantrips" if requirement.level == 0 else "level-one spells"
        if requirement.ritual:
            label = "level-one ritual spells"
        if requirement.attack:
            label = "attack cantrips"
        parts.append(f"{requirement.source_name}: {requirement.count} {filters} {label}")
    return "; ".join(parts)
