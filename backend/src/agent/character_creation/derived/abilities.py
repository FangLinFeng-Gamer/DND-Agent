from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft, CharacterDerivedSheet


SKILL_ABILITIES = {
    "skill.acrobatics": "dexterity",
    "skill.animal-handling": "wisdom",
    "skill.arcana": "intelligence",
    "skill.athletics": "strength",
    "skill.deception": "charisma",
    "skill.history": "intelligence",
    "skill.insight": "wisdom",
    "skill.intimidation": "charisma",
    "skill.investigation": "intelligence",
    "skill.medicine": "wisdom",
    "skill.nature": "intelligence",
    "skill.perception": "wisdom",
    "skill.performance": "charisma",
    "skill.persuasion": "charisma",
    "skill.religion": "intelligence",
    "skill.sleight-of-hand": "dexterity",
    "skill.stealth": "dexterity",
    "skill.survival": "wisdom",
}


def apply_ability_derived_values(
    draft: CharacterDraft,
    sheet: CharacterDerivedSheet,
    repository: PHBRuleRepository,
) -> CharacterDerivedSheet:
    sheet.initiative = draft.abilities.modifiers["dexterity"]
    feat_rules = [
        repository.get(feat_id)
        for feat_id in draft.selections.feat_ids
    ]
    initiative_bonus = sum(
        int(grant.value)
        for rule in feat_rules
        for grant in rule.grants
        if grant.kind == "initiative_bonus"
    )
    sheet.initiative += initiative_bonus
    sheet.sources["initiative"] = [
        {
            "source": "ability.dexterity",
            "value": draft.abilities.modifiers["dexterity"],
        }
    ]
    if initiative_bonus:
        sheet.sources["initiative"].append(
            {"source": "feat.alert", "value": initiative_bonus}
        )

    class_rule = (
        repository.get(draft.selections.class_id)
        if draft.selections.class_id
        else None
    )
    save_sources = {
        ability: class_rule.id
        for ability in (
            class_rule.metadata.get("saving_throws", []) if class_rule else []
        )
    }
    for feat_rule in feat_rules:
        for grant in feat_rule.grants:
            if grant.kind != "saving_throw_proficiency_choice":
                continue
            for ability_id in draft.selections.choice_values.get(
                grant.target,
                [],
            ):
                save_sources[ability_id.removeprefix("ability.")] = feat_rule.id
    proficient_saves = set(save_sources)
    sheet.saving_throws = {}
    for ability, modifier in draft.abilities.modifiers.items():
        proficiency = sheet.proficiency_bonus if ability in proficient_saves else 0
        sheet.saving_throws[ability] = modifier + proficiency
        sources = [{"source": f"ability.{ability}", "value": modifier}]
        if proficiency:
            sources.append(
                {"source": save_sources[ability], "value": proficiency}
            )
        sheet.sources[f"saving_throw.{ability}"] = sources

    proficient_skills = set(draft.proficiencies.get("skills", []))
    sheet.skills = {}
    for skill_id, ability in SKILL_ABILITIES.items():
        modifier = draft.abilities.modifiers[ability]
        proficiency = sheet.proficiency_bonus if skill_id in proficient_skills else 0
        sheet.skills[skill_id] = modifier + proficiency
        sources = [{"source": f"ability.{ability}", "value": modifier}]
        if proficiency:
            sources.append(
                {"source": f"proficiency.{skill_id}", "value": proficiency}
            )
        sheet.sources[f"skill.{skill_id}"] = sources

    perception = sheet.skills["skill.perception"]
    passive_bonus = sum(
        int(grant.value)
        for rule in feat_rules
        for grant in rule.grants
        if grant.kind == "passive_bonus"
        and grant.target == "skill.perception"
    )
    sheet.passive_perception = 10 + perception + passive_bonus
    sheet.sources["passive_perception"] = [
        {"source": "base", "value": 10},
        {"source": "skill.perception", "value": perception},
    ]
    if passive_bonus:
        sheet.sources["passive_perception"].append(
            {"source": "feat.observant", "value": passive_bonus}
        )
    return sheet
