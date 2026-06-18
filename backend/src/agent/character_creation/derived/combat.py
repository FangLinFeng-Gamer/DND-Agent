from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft, CharacterDerivedSheet


def apply_combat_derived_values(
    draft: CharacterDraft,
    sheet: CharacterDerivedSheet,
    repository: PHBRuleRepository,
) -> CharacterDerivedSheet:
    if not draft.selections.class_id:
        return sheet

    class_rule = repository.get(draft.selections.class_id)
    selected_rules = [
        repository.get(rule_id)
        for rule_id in (
            draft.selections.race_id,
            draft.selections.subrace_id,
            *draft.selections.class_option_ids,
            *draft.selections.feat_ids,
        )
        if rule_id
    ]
    constitution = draft.abilities.modifiers["constitution"]
    hp_bonus = sum(
        int(grant.value)
        for rule in selected_rules
        for grant in rule.grants
        if grant.kind == "hp_per_level"
    )
    sheet.hp_max = int(class_rule.metadata["hit_die"]) + constitution + hp_bonus
    sheet.sources["hp_max"] = [
        {"source": class_rule.id, "value": int(class_rule.metadata["hit_die"])},
        {"source": "ability.constitution", "value": constitution},
    ]
    sheet.sources["hp_max"].extend(
        {"source": rule.id, "value": int(grant.value)}
        for rule in selected_rules
        for grant in rule.grants
        if grant.kind == "hp_per_level"
    )

    inventory_rules = [
        repository.get(entry["item_id"])
        for entry in draft.inventory
        if int(entry.get("quantity", 0)) > 0
    ]
    _apply_armor_class(draft, sheet, class_rule, selected_rules, inventory_rules)
    _apply_weapon_attacks(draft, sheet, inventory_rules)
    return sheet


def _apply_armor_class(
    draft: CharacterDraft,
    sheet: CharacterDerivedSheet,
    class_rule,
    selected_rules: list,
    inventory_rules: list,
) -> None:
    dexterity = draft.abilities.modifiers["dexterity"]
    armor_candidates = []
    for item in inventory_rules:
        if item.metadata.get("category") != "armor":
            continue
        dexterity_rule = item.metadata["dexterity"]
        dexterity_bonus = (
            dexterity
            if dexterity_rule == "full"
            else min(2, dexterity)
            if dexterity_rule == "max_2"
            else 0
        )
        armor_candidates.append(
            (int(item.metadata["base_ac"]) + dexterity_bonus, item.id)
        )

    formula_candidates = [(10 + dexterity, "unarmored")]
    if class_rule.id == "class.barbarian":
        formula_candidates.append(
            (
                10
                + dexterity
                + draft.abilities.modifiers["constitution"],
                class_rule.id,
            )
        )
    if class_rule.id == "class.monk":
        formula_candidates.append(
            (
                10 + dexterity + draft.abilities.modifiers["wisdom"],
                class_rule.id,
            )
        )
    for rule in selected_rules:
        for grant in rule.grants:
            if grant.kind == "armor_formula" and grant.value == "13+dexterity":
                formula_candidates.append((13 + dexterity, rule.id))

    if armor_candidates:
        base_ac, source = max(armor_candidates)
    else:
        base_ac, source = max(formula_candidates)
    sources = [{"source": source, "value": base_ac}]

    shield_bonus = sum(
        int(item.metadata.get("ac_bonus", 0))
        for item in inventory_rules
        if item.metadata.get("category") == "shield"
    )
    if shield_bonus:
        base_ac += shield_bonus
        sources.append({"source": "equipment.shield", "value": shield_bonus})

    defense = "class_option.fighter.defense" in draft.selections.class_option_ids
    if defense and armor_candidates:
        base_ac += 1
        sources.append(
            {"source": "class_option.fighter.defense", "value": 1}
        )
    sheet.armor_class = base_ac
    sheet.sources["armor_class"] = sources


def _apply_weapon_attacks(
    draft: CharacterDraft,
    sheet: CharacterDerivedSheet,
    inventory_rules: list,
) -> None:
    attacks = []
    for item in inventory_rules:
        if item.metadata.get("category") != "weapon":
            continue
        tags = set(item.tags)
        properties = set(item.metadata.get("properties", []))
        if "ranged" in tags:
            ability = "dexterity"
        elif "finesse" in properties:
            ability = max(
                ("strength", "dexterity"),
                key=lambda value: draft.abilities.modifiers[value],
            )
        else:
            ability = "strength"
        modifier = draft.abilities.modifiers[ability]
        proficient = any(
            proficiency in draft.proficiencies.get("weapons", [])
            for proficiency in (
                f"weapon.{item.id.removeprefix('equipment.')}",
                *(f"weapon.{tag}" for tag in tags),
            )
        )
        attack_bonus = modifier + (
            sheet.proficiency_bonus if proficient else 0
        )
        damage = str(item.metadata["damage"])
        if modifier:
            damage = f"{damage}{modifier:+d}"
        attack = {
            "item_id": item.id,
            "ability": ability,
            "attack_bonus": attack_bonus,
            "damage": damage,
            "damage_type": item.metadata["damage_type"],
        }
        if "ranged" in tags and item.metadata.get("range"):
            weapon_range = list(item.metadata["range"])
            attack["attack_kind"] = "ranged"
            attack["normal_range_ft"] = int(weapon_range[0])
            attack["long_range_ft"] = int(weapon_range[1] if len(weapon_range) > 1 else weapon_range[0])
        attacks.append(attack)
    sheet.attacks = attacks
